"""种子脚本：30 关内容 + 文章 + 标定文本 + 合成示范媒体 + 参考发音人 + 发布。

用法（backend/ 目录下）：
    python seed.py            # 幂等补种（已存在的不重做）
    python seed.py --reset    # 清库重建（删除 data/app.db 与媒体目录）
    python seed.py --publish N  # 只发布前 N 关（默认全部 30 关）

合成音频说明见 app/seed_support.py 模块注释。
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

from app import config
from app.content.models import (
    ArticleDraftRow, ArticleRow, ArticleVersionRow, CalibrationTextRow, CategoryRow,
    LevelDraftRow, LevelRow, MediaAssetRow, ReferenceSpeakerRow, SagittalPresetRow,
)
from app.content import usecases as content_uc
from app.db import JSONText, create_all, get_session, now
from app.ids import new_id
from app.seed_support import synthesize_text, write_wav

SEED_ACTOR = "seed"


def _reset() -> None:
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    for suffix in ("-wal", "-shm"):
        p = Path(str(config.DB_PATH) + suffix)
        if p.exists():
            p.unlink()
    for d in (config.PUBLIC_DIR, config.DRAFT_DIR, config.PRIVATE_DIR):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    if config.DELETION_LOG_PATH.exists():
        config.DELETION_LOG_PATH.unlink()
    print("[seed] 已重置数据库与文件存储")


def _register_media(db, *, kind: str, purpose: str, path: Path, filename: str,
                    text: str | None, license_note: str, duration: float | None) -> str:
    media_id = new_id("md_")
    db.add(MediaAssetRow(
        id=media_id, kind=kind, storage="draft", filename=filename,
        storage_path=str(path.relative_to(config.DATA_DIR)),
        mime="audio/wav", size_bytes=path.stat().st_size, purpose=purpose,
        license_note=license_note, author=SEED_ACTOR,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        duration_sec=duration, text=text, uploaded_by=SEED_ACTOR, created_at=now(),
    ))
    return media_id


def _synthesize_media(db, *, text: str, voice: str, purpose: str, ref_name: str,
                      license_note: str) -> tuple[str, Path]:
    wav = config.DATA_DIR / "media" / f"seed_{ref_name}_{voice}.wav"
    write_wav(wav, synthesize_text(text, voice))
    from app.acoustics.transcode import probe_duration

    media_id = _register_media(
        db, kind="audio", purpose=purpose, path=wav, filename=f"{ref_name}_{voice}.wav",
        text=text, license_note=license_note, duration=probe_duration(wav))
    return media_id, wav


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


def seed_reference_speakers(db) -> dict[str, str]:
    """合成男女声朗读标定文本 → 同一标定计算 → 登记参考发音人。"""
    from app.content_seed_data import CALIBRATION_TEXT
    from app.scoring.usecases import calibrate_path

    speakers: dict[str, str] = {}
    existing = {r.gender: r.id for r in db.query(ReferenceSpeakerRow).all()}
    if existing:
        print(f"[seed] 参考发音人已存在：{existing}")
        return existing
    text_row = content_uc.get_active_calibration_text(db)
    syllables = JSONText.load(text_row.syllables)
    for gender, name in (("male", "标准男声（合成）"), ("female", "标准女声（合成）")):
        wav = config.DATA_DIR / "media" / f"seed_calibration_{gender}.wav"
        write_wav(wav, synthesize_text("".join(syllables), gender, syllable_dur=0.36))
        result = calibrate_path(wav, syllables)
        if not result.get("ok"):
            print(f"[seed][WARN] {gender} 参考发音人标定失败：{result['reason']}")
            continue
        row = ReferenceSpeakerRow(
            id=new_id("spk_"), name=name, gender=gender,
            f_lo=result["fLo"], f_hi=result["fHi"],
            vowel_space=JSONText.dump(result["vowelSpace"]),
            algorithm_version=config.ALGORITHM_VERSION,
            registered_at=now(), note="种子合成音频登记",
        )
        db.add(row)
        speakers[gender] = row.id
        print(f"[seed] 参考发音人 {gender}: {result['fLo']}–{result['fHi']} Hz")
    db.commit()
    return speakers


def seed_levels(db, speakers: dict[str, str], publish_count: int) -> None:
    from app.content_seed_data import LEVELS

    male_speaker = speakers.get("male")
    for item in LEVELS[:publish_count]:
        level_id = item["id"]
        if db.get(LevelRow, level_id) is not None:
            print(f"[seed] {level_id} 已存在，跳过")
            continue
        content = dict(item)
        # 剖面关键帧归一到契约结构 articulation.sagittal.keyframes
        art = dict(content.get("articulation", {}))
        if "sagittalKeyframes" in art and "sagittal" not in art:
            art["sagittal"] = {"keyframes": art.pop("sagittalKeyframes")}
        # lips.contact 为接触方式枚举（none/bilabial/labiodental），
        # 种子数据早期把双唇闭合写成 closed，归一为 bilabial
        for kf in art["sagittal"]["keyframes"]:
            lips = kf.get("lips")
            if isinstance(lips, dict) and lips.get("contact") == "closed":
                lips["contact"] = "bilabial"
        content["articulation"] = art
        license_note = item.get("license", "内部演示授权（合成音频）")

        # 示范音频（男/女正常语速）
        demo_text = item.get("detection", {}).get("evaluationText") or \
            item.get("representativeChar", item["targetSound"])
        demos = []
        for d in content.get("demos", []):
            voice = d.get("voice", "male")
            media_id, _ = _synthesize_media(
                db, text=d.get("text", demo_text), voice=voice,
                purpose="demo", ref_name=f"{level_id}_{d.get('speed', 'normal')}",
                license_note=license_note)
            demos.append({**d, "mediaId": media_id})
        content["demos"] = demos

        # 听辨题刺激音频
        quizzes = []
        for q in content.get("quizzes", []):
            media_id, _ = _synthesize_media(
                db, text=q.get("stimulusText", demo_text), voice="female",
                purpose="quiz", ref_name=f"{level_id}_{q['id']}",
                license_note=license_note)
            quizzes.append({**q, "stimulusMediaId": media_id})
        content["quizzes"] = quizzes

        # 检测任务：参考示范 + 参考发音人
        det = dict(content.get("detection", {}))
        sample_voice = det.get("sampleVoice", "male")
        sample_media, sample_wav = _synthesize_media(
            db, text=det.get("evaluationText", demo_text), voice=sample_voice,
            purpose="demo", ref_name=f"{level_id}_sample",
            license_note=license_note)
        det["sampleMediaId"] = sample_media
        det["referenceSpeakerId"] = male_speaker if sample_voice == "male" \
            else speakers.get("female")
        content["detection"] = det

        db.add(LevelRow(id=level_id, order=item["order"], layer=item["layer"],
                        status="draft", skeleton_public=bool(item.get("skeletonPublic", True)),
                        created_at=now(), updated_at=now()))
        db.add(LevelDraftRow(level_id=level_id, revision=1,
                             content=JSONText.dump(content),
                             updated_at=now(), updated_by=SEED_ACTOR))
        # 声道剖面预设（后台起步微调用）
        db.add(SagittalPresetRow(
            key=level_id, layer=item["layer"], target_sound=item["targetSound"],
            keyframes=JSONText.dump(content["articulation"]["sagittal"]["keyframes"])))
        db.commit()
        print(f"[seed] {level_id} 草稿就绪（{item['targetSound']}）")


def publish_levels(db, publish_count: int) -> None:
    from app.content_seed_data import LEVELS

    published = 0
    for item in LEVELS[:publish_count]:
        level_id = item["id"]
        lv = db.get(LevelRow, level_id)
        if lv is None:
            continue
        if lv.status == "published":
            published += 1
            continue
        try:
            result = content_uc.publish_level(db, level_id, admin_actor=SEED_ACTOR,
                                              request_id="seed",
                                              change_note="种子初版")
            published += 1
            print(f"[seed] {level_id} 发布（v{result['contentVersion']}，"
                  f"标准曲线 {result['standardCurveSegments']} 段）")
        except Exception as e:
            print(f"[seed] {level_id} 发布失败：{e}")
    print(f"[seed] 已发布关卡：{published}")


def seed_articles(db) -> None:
    from app.content_seed_data import ARTICLES, ARTICLE_CATEGORIES

    for i, name in enumerate(ARTICLE_CATEGORIES):
        if db.query(CategoryRow).filter(CategoryRow.name == name).count() == 0:
            db.add(CategoryRow(name=name, sort=i, created_at=now()))
    db.commit()

    for a in ARTICLES:
        slug = a["slug"]
        if db.get(ArticleRow, slug) is not None:
            continue
        content = dict(a)
        demo_text = a.get("demoText") or a["title"]
        media_id, _ = _synthesize_media(
            db, text=demo_text, voice="male", purpose="article",
            ref_name=f"article_{slug}", license_note=a.get("license", "内部演示授权"))
        content["demoMediaId"] = media_id
        db.add(ArticleRow(slug=slug, status="draft", created_at=now(), updated_at=now()))
        db.add(ArticleDraftRow(article_slug=slug, revision=1,
                               content=JSONText.dump(content),
                               updated_at=now(), updated_by=SEED_ACTOR))
        db.commit()
        try:
            content_uc.publish_article(db, slug, admin_actor=SEED_ACTOR,
                                       request_id="seed", change_note="种子初版")
            print(f"[seed] 文章发布：{slug}")
        except Exception as e:
            print(f"[seed] 文章 {slug} 发布失败：{e}")


def main() -> None:
    args = sys.argv[1:]
    if "--reset" in args:
        _reset()
    publish_count = 30
    if "--publish" in args:
        publish_count = int(args[args.index("--publish") + 1])

    config.ensure_dirs()
    create_all()
    db = get_session()
    try:
        seed_calibration_text(db)
        speakers = seed_reference_speakers(db)
        if not speakers:
            print("[seed][ERROR] 参考发音人登记失败，标准曲线无法生成，终止")
            return
        seed_levels(db, speakers, publish_count)
        publish_levels(db, publish_count)
        seed_articles(db)
        print("[seed] 完成。默认管理员：admin / admin12345（可用环境变量覆盖）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
