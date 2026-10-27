"""种子脚本：全部关卡内容 + 标定文本 + 真人语料库示范媒体（FV1~3、MV1~3）+ 参考发音人。

用法（backend/ 目录下，须先在 .env 或环境变量配置 CORPUS_DIR）：
    python seed.py            # 幂等补种（已存在的不重做；默认开放 LEVELS 全部关卡）
    python seed.py --reset    # 清库重建（删除 data/app.db 与媒体目录）
    python seed.py --open N   # 只开放前 N 关（用于分批放关；N 不设上限）
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

import numpy as np

from app import config
from app.acoustics import analysis, f0_pipeline, transcode
from app.content import usecases as content_uc
from app.content.models import (
    CalibrationTextRow, LevelRow, MediaAssetRow,
    ReferenceSpeakerRow,
)
from app.db import JSONText, create_all, get_session, now
from app.ids import new_id

SEED_ACTOR = "seed"

# 六位真人发音人：(语料库子目录/编号, 展示名称, 性别, 示范 voice 标签)
CORPUS_SPEAKERS: list[tuple[str, str, str, str]] = [
    ("FV1", "女声 1（FV1）", "female", "FV1"),
    ("FV2", "女声 2（FV2）", "female", "FV2"),
    ("FV3", "女声 3（FV3）", "female", "FV3"),
    ("MV1", "男声 1（MV1）", "male", "MV1"),
    ("MV2", "男声 2（MV2）", "male", "MV2"),
    ("MV3", "男声 3（MV3）", "male", "MV3"),
]

# 每位发音人用于计算真实五度音域 [f_lo, f_hi] 的代表音节池（覆盖四声与主要元音）
_PITCH_POOL_STEMS = (
    "a1", "a2", "a3", "a4",
    "yi1", "yi2", "yi3", "yi4",
    "wu1", "wu2", "wu3", "wu4",
    "ma1", "ma2", "ma3", "ma4",
    "po1", "che1", "mi3", "bu4", "nv3",
)

# 六个单韵母 → 语料库纯单韵母词干（用于提取不受声母干扰的标准元音空间靶区）
_VOWEL_ANCHOR_STEMS: dict[str, tuple[str, ...]] = {
    "a": ("a1", "a2", "a4"),
    "o": ("o1", "o2", "o4"),
    "e": ("e1", "e2", "e4"),
    "i": ("yi1", "yi2", "yi4"),
    "u": ("wu1", "wu2", "wu4"),
    "ü": ("yu1", "yu2", "yu4"),
}


def _require_corpus_dir() -> Path:
    corpus = config.CORPUS_DIR
    if corpus is None or not corpus.is_dir():
        raise SystemExit(
            "[seed][ERROR] 未找到真人语音语料库目录。\n"
            "请在仓库根目录 `.env` 或环境变量中设置 CORPUS_DIR（指向包含 FV1~3、MV1~3 的目录），\n"
            "参见 README.md 与 `.env.example`。"
        )
    missing = [code for code, *_ in CORPUS_SPEAKERS if not (corpus / code).is_dir()]
    if missing:
        raise SystemExit(
            f"[seed][ERROR] 语料库目录 {corpus} 下缺少发音人子目录：{', '.join(missing)}"
        )
    return corpus


def _reset() -> None:
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    for suffix in ("-wal", "-shm"):
        p = Path(str(config.DB_PATH) + suffix)
        if p.exists():
            p.unlink()
    for d in (config.PRIVATE_DIR, config.MEDIA_DIR):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    if config.DELETION_LOG_PATH.exists():
        config.DELETION_LOG_PATH.unlink()
    print("[seed] 已重置数据库与文件存储")


def _corpus_wav(corpus: Path, speaker_code: str, stem: str) -> Path:
    path = corpus / speaker_code / f"{stem}_{speaker_code}.wav"
    if not path.is_file():
        raise FileNotFoundError(f"语料库文件不存在：{path}")
    return path


# 规范化缓存：(speaker_code, stem) → (dest_wav_path, duration_sec, sha256)
_norm_cache: dict[tuple[str, str], tuple[Path, float, str]] = {}


def _ensure_normalized_media_file(corpus: Path, speaker_code: str, stem: str) -> tuple[Path, float, str]:
    key = (speaker_code, stem)
    cached = _norm_cache.get(key)
    if cached is not None and cached[0].exists():
        return cached
    src = _corpus_wav(corpus, speaker_code, stem)
    dest = config.MEDIA_DIR / f"corpus_{speaker_code}_{stem}.wav"
    norm = transcode.normalize_to_wav(src, dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    res = (dest, norm.duration_sec, digest)
    _norm_cache[key] = res
    return res


def _import_corpus_media(db, corpus: Path, *, stem: str, text: str, speaker_code: str,
                         purpose: str, license_note: str) -> str:
    """按词干直接导入真人语料库录音（词干由种子数据显式携带，不从文本推断）。"""
    wav_path, duration, digest = _ensure_normalized_media_file(corpus, speaker_code, stem)
    media_id = new_id("md_")
    db.add(MediaAssetRow(
        id=media_id, kind="audio", filename=f"{stem}_{speaker_code}.wav",
        storage_path=str(wav_path.relative_to(config.DATA_DIR)),
        mime="audio/wav", size_bytes=wav_path.stat().st_size, purpose=purpose,
        license_note=license_note, author=speaker_code,
        sha256=digest, duration_sec=duration, text=text,
        uploaded_by=SEED_ACTOR, created_at=now(),
    ))
    return media_id


def seed_calibration_text(db) -> None:
    from app.content_seed_data import CALIBRATION_TEXT

    row = content_uc.get_active_calibration_text(db)
    if row is not None:
        print(f"[seed] 标定文本已存在（{row.text_version}），跳过")
        return
    for r in db.query(CalibrationTextRow).all():
        r.active = False
    db.add(CalibrationTextRow(
        text_version=CALIBRATION_TEXT["textVersion"], text=CALIBRATION_TEXT["text"],
        syllables=JSONText.dump(CALIBRATION_TEXT["syllables"]), active=True,
        note="覆盖六个单韵母并含四声起伏", updated_at=now(),
    ))
    db.commit()
    print(f"[seed] 标定文本：{CALIBRATION_TEXT['text']}")


# ---------------- ma 构形媒体（2D 正中矢状动画 / 三维模型） ----------------

# (引用键, backend/assets/ma 下文件名, 资产 kind, mime)
MA_ARTICULATION_ASSETS: list[tuple[str, str, str, str]] = [
    ("ma_sagittal_2d", "ma-sagittal.html", "animation", "text/html"),
    ("ma_articulation_model", "ma-articulation.glb", "model", "model/gltf-binary"),
]

MA_LEVEL_IDS = ("L30", "L31", "L32", "L33")


def seed_ma_articulation_media(db) -> dict[str, str]:
    """导入 backend/assets/ma 的 ma 发音动作媒体并登记资产（按文件名幂等），
    返回引用键 → mediaId。随后把解析结果写进 L30–L33 的 articulation 段，
    已存在的关卡也覆盖（新建与老库同一条路径）。"""
    from app.content_seed_data import LEVELS

    assets_dir = Path(__file__).parent / "assets" / "ma"
    refs: dict[str, str] = {}
    for ref, filename, kind, mime in MA_ARTICULATION_ASSETS:
        src = assets_dir / filename
        if not src.is_file():
            raise SystemExit(f"[seed][ERROR] ma 构形媒体缺失：{src}")
        dest = config.MEDIA_DIR / f"ma_{filename}"
        if not dest.exists() or dest.read_bytes() != src.read_bytes():
            shutil.copyfile(src, dest)
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        row = (db.query(MediaAssetRow)
               .filter(MediaAssetRow.filename == f"ma_{filename}",
                       MediaAssetRow.purpose == "articulation",
                       MediaAssetRow.deleted_at.is_(None))
               .first())
        if row is None:
            row = MediaAssetRow(
                id=new_id("md_"), kind=kind, filename=f"ma_{filename}",
                storage_path=str(dest.relative_to(config.DATA_DIR)), mime=mime,
                size_bytes=dest.stat().st_size, purpose="articulation",
                license_note="内部教学示意授权（脚本建模，参考轮廓教学模型，非实测数据）",
                author="内容组（发音动作示意）", sha256=digest,
                uploaded_by=SEED_ACTOR, created_at=now(),
            )
            db.add(row)
            db.commit()
            print(f"[seed] ma 构形媒体登记：ma_{filename} → {row.id}")
        refs[ref] = row.id

    for item in LEVELS:
        level_id = item["id"]
        if level_id not in MA_LEVEL_IDS:
            continue
        level = db.get(LevelRow, level_id)
        if level is None:
            continue
        template = item.get("articulation") or {}
        art = {
            "media": [{k: v for k, v in m.items() if k != "ref"}
                      | {"mediaId": refs[m["ref"]]}
                      for m in template.get("media", [])]
        }
        model_ref = template.get("model3dRef")
        if model_ref:
            art["model3dMediaId"] = refs[model_ref]
        content = JSONText.load(level.content, {})
        content["articulation"] = art
        level.content = JSONText.dump(content)
        level.updated_at = now()
        db.commit()
        print(f"[seed] {level_id} 构形接入 ma 发音动作（2D 动画 / 三维模型）")
    return refs


def _compute_speaker_baseline(corpus: Path, speaker_code: str) -> tuple[float, float, dict]:
    """用发音人真实语料计算稳健五度音域 (f_lo, f_hi) 与六单韵母元音空间 vowel_space。"""
    hz_all: list[float] = []
    for stem in _PITCH_POOL_STEMS:
        wav_path, _, _ = _ensure_normalized_media_file(corpus, speaker_code, stem)
        track = f0_pipeline.extract_track(wav_path)
        hz_all.extend(f0_pipeline.calibration_frequencies(track, [(0.0, track.duration)]))
    rng = analysis.robust_pitch_range(np.array(hz_all, dtype=float))
    if rng is None:
        raise RuntimeError(f"发音人 {speaker_code} 音域统计失败")
    f_lo, f_hi = rng

    vowel_space: dict = {}
    f1_all: list[float] = []
    f2_all: list[float] = []
    for vowel, stems in _VOWEL_ANCHOR_STEMS.items():
        v_f1s: list[float] = []
        v_f2s: list[float] = []
        for stem in stems:
            wav_path, _, _ = _ensure_normalized_media_file(corpus, speaker_code, stem)
            fm = analysis.extract_formants(wav_path)
            stats = analysis.formant_stats_in_segments(fm, fm.vowel_segments)
            if stats:
                v_f1s.append(stats["f1Mean"])
                v_f2s.append(stats["f2Mean"])
        if v_f1s:
            f1_m = round(float(np.mean(v_f1s)), 1)
            f2_m = round(float(np.mean(v_f2s)), 1)
            vowel_space[vowel] = {"f1Mean": f1_m, "f2Mean": f2_m}
            f1_all.append(f1_m)
            f2_all.append(f2_m)

    vowel_space["overall"] = {
        "f1Mean": round(float(np.mean(f1_all)), 1),
        "f2Mean": round(float(np.mean(f2_all)), 1),
        "f1Std": round(float(np.std(f1_all)), 1) or 1.0,
        "f2Std": round(float(np.std(f2_all)), 1) or 1.0,
    }
    return f_lo, f_hi, vowel_space


def seed_reference_speakers(db, corpus: Path) -> dict[str, str]:
    """登记 FV1~3、MV1~3 六位真实参考发音人，返回 speaker_code/gender → id 映射。"""
    existing_rows = db.query(ReferenceSpeakerRow).all()
    if len(existing_rows) >= len(CORPUS_SPEAKERS):
        mapping: dict[str, str] = {}
        for r in existing_rows:
            for code, *_ in CORPUS_SPEAKERS:
                if code in r.name:
                    mapping[code] = r.id
            mapping.setdefault(r.gender, r.id)
        print(f"[seed] 参考发音人已存在：{list(mapping.keys())}")
        return mapping

    # 清理残缺旧行重建
    for r in existing_rows:
        db.delete(r)
    db.flush()

    speakers: dict[str, str] = {}
    for code, display_name, gender, _ in CORPUS_SPEAKERS:
        f_lo, f_hi, vowel_space = _compute_speaker_baseline(corpus, code)
        row = ReferenceSpeakerRow(
            id=new_id("spk_"), name=display_name, gender=gender,
            f_lo=f_lo, f_hi=f_hi,
            vowel_space=JSONText.dump(vowel_space),
            algorithm_version=config.ALGORITHM_VERSION,
            registered_at=now(), note=f"真人标准音节语料库（{code}）标定登记",
        )
        db.add(row)
        speakers[code] = row.id
        # male 默认指向 MV1，female 默认指向 FV1
        speakers.setdefault(gender, row.id)
        print(f"[seed] 参考发音人 {code} ({gender}): {f_lo}–{f_hi} Hz")
    db.commit()
    return speakers


def seed_levels(db, corpus: Path, speakers: dict[str, str], open_count: int | None) -> None:
    from app.content_seed_data import LEVELS

    items = LEVELS if open_count is None else LEVELS[:open_count]
    for item in items:
        level_id = item["id"]
        if db.get(LevelRow, level_id) is not None:
            print(f"[seed] {level_id} 已存在，跳过")
            continue
        content = dict(item)
        license_note = item.get("license", "真人标准音节语料库授权")

        demo_text = item.get("detection", {}).get("evaluationText") or \
            item.get("representativeChar", item["targetSound"])
        demo_stem = item.get("detection", {}).get("evaluationStem") or ""

        # 示范音频：将 FV1~3、MV1~3 全部放入关卡 demos 供学习者切换试听
        demos = []
        for code, _, _, voice_tag in CORPUS_SPEAKERS:
            media_id = _import_corpus_media(
                db, corpus, stem=demo_stem, text=demo_text, speaker_code=code,
                purpose="demo", license_note=license_note,
            )
            demos.append({
                "ref": f"{level_id}_demo_normal_{code}",
                "speed": "normal",
                "voice": voice_tag,
                "mediaId": media_id,
            })
        content["demos"] = demos

        # 听辨题刺激音频（交替使用 FV2 / MV2 真人发音，避免与默认参考音完全重合同一个文件）
        quizzes = []
        for idx, q in enumerate(content.get("quizzes", [])):
            q_spk = "FV2" if idx % 2 == 0 else "MV2"
            stim_text = q.get("stimulusText", demo_text)
            media_id = _import_corpus_media(
                db, corpus, stem=q["stimulusStem"], text=stim_text, speaker_code=q_spk,
                purpose="quiz", license_note=license_note,
            )
            quizzes.append({**q, "stimulusMediaId": media_id})
        content["quizzes"] = quizzes

        # 检测任务：参考示范 + 对应真实参考发音人（male → MV1，female → FV1）
        det = dict(content.get("detection", {}))
        sample_voice = det.get("sampleVoice", "male")
        sample_spk = sample_voice if sample_voice in speakers and sample_voice not in ("male", "female") \
            else ("MV1" if sample_voice == "male" else "FV1")
        eval_text = det.get("evaluationText", demo_text)
        det["sampleMediaId"] = _import_corpus_media(
            db, corpus, stem=demo_stem, text=eval_text, speaker_code=sample_spk,
            purpose="demo", license_note=license_note,
        )
        det["referenceSpeakerId"] = speakers[sample_spk]
        content["detection"] = det

        # 标准曲线（基于真实参考示范与真实发音人基线计算）
        content = content_uc.prepare_level_content(db, content)
        curve_segments = len((content.get("standardCurve") or {}).get("segments") or [])

        db.add(LevelRow(id=level_id, order=item["order"], layer=item["layer"],
                        published=True,
                        skeleton_public=bool(item.get("skeletonPublic", True)),
                        content=JSONText.dump(content),
                        created_at=now(), updated_at=now()))
        db.commit()
        print(f"[seed] {level_id} 已开放（{item['targetSound']}，6 发音人示范，标准曲线 {curve_segments} 段）")


def main() -> None:
    args = sys.argv[1:]
    if "--reset" in args:
        _reset()
    # 默认开放全部关卡（关卡随内容制作追加，数量不封顶）
    open_count = None
    if "--open" in args:
        open_count = int(args[args.index("--open") + 1])

    corpus = _require_corpus_dir()
    config.ensure_dirs()
    create_all()
    db = get_session()
    try:
        seed_calibration_text(db)
        speakers = seed_reference_speakers(db, corpus)
        if not speakers:
            print("[seed][ERROR] 参考发音人登记失败，标准曲线无法生成，终止")
            return
        seed_levels(db, corpus, speakers, open_count)
        seed_ma_articulation_media(db)
        print("[seed] 完成。默认管理员：admin / admin12345（可用环境变量覆盖）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
