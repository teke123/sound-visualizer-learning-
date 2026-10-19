"""scoring 用例：个人音域（标定写入/滚动更新/删除重算）、评分结论缓存。"""
from __future__ import annotations

import logging

import numpy as np
from sqlalchemy.orm import Session

from app import config
from app.acoustics import analysis
from app.acoustics.models import AudioRow
from app.acoustics.usecases import audio_path, mark_deleted as mark_audio_deleted
from app.db import JSONText, get_session, now
from app.ids import new_id
from app.pinyin_utils import expected_syllables, main_vowel
from app.scoring.models import PitchRangeRow, PitchRangeSnapshotRow, ScoreCacheRow
from app.scoring.provider import ProviderError
from app.scoring.provider_mock import MockProvider

logger = logging.getLogger("svs.scoring")

ROLLING_WINDOW_N = 20   # 最近 N 条存档合格录音


def get_provider():
    """评分 Provider 工厂：默认讯飞，仅 SVS_PROVIDER=mock 时用本地替身。"""
    if config.PROVIDER_NAME == "mock":
        return MockProvider()
    from app.scoring.provider_xfyun import XfyunProvider

    return XfyunProvider()


# ---------------- 音域 ----------------

def _range_row_dict(row: PitchRangeRow) -> dict:
    return {
        "fLo": round(row.f_lo, 1),
        "fHi": round(row.f_hi, 1),
        "vowelSpace": JSONText.load(row.vowel_space),
        "algorithmVersion": row.algorithm_version,
        "basisCalibrationId": row.basis_calibration_id,
        "sourceRecordingIds": JSONText.load(row.source_recording_ids, []),
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def get_personal_range(db: Session, *, user_id: str) -> dict | None:
    """个人音域（FR-1006）。未标定返回 None，由调用方回落默认成人参考范围。"""
    row = (
        db.query(PitchRangeRow)
        .filter(PitchRangeRow.user_id == user_id,
                PitchRangeRow.deleted_at.is_(None))
        .one_or_none()
    )
    return {"status": "personal", **_range_row_dict(row)} if row else None


def create_snapshot(db: Session, *, user_id: str, f_lo: float,
                    f_hi: float, vowel_space: dict | None, created_from: dict) -> PitchRangeSnapshotRow:
    row = PitchRangeSnapshotRow(
        id=new_id("prs_"),
        user_id=user_id,
        f_lo=f_lo, f_hi=f_hi,
        vowel_space=JSONText.dump(vowel_space) if vowel_space else None,
        algorithm_version=analysis.ALGORITHM_VERSION,
        created_from=JSONText.dump(created_from),
        created_at=now(),
    )
    db.add(row)
    db.flush()
    return row


def snapshot_dict(row: PitchRangeSnapshotRow) -> dict:
    return {
        "id": row.id,
        "fLo": round(row.f_lo, 1),
        "fHi": round(row.f_hi, 1),
        "vowelSpace": JSONText.load(row.vowel_space),
        "algorithmVersion": row.algorithm_version,
    }


def calibrate_path(path, syllables: list[str]) -> dict:
    """纯计算：WAV + 标定文本 → 音高音域 + 元音空间（不写库）。
    供用户标定与参考发音人登记共用。"""
    signal = analysis.check_signal(path, purpose="calibration")
    if signal.verdict != "pass":
        return {"ok": False, "reason": _signal_advice(signal), "signal": signal.to_dict()}

    f0res = analysis.extract_f0(path)
    rng = analysis.robust_pitch_range(
        np.array([fr.get("hz", np.nan) for fr in f0res.frames], dtype=float))
    if rng is None:
        return {"ok": False,
                "reason": "这段标定录音没有足够的稳定嗓音，请用正常说话的音量再读一遍",
                "signal": signal.to_dict()}
    f_lo, f_hi = rng

    text = "".join(syllables)
    try:
        prov = get_provider().evaluate(str(path), text)
        segments = [(s.t0, s.t1) for s in prov.syllables]
    except ProviderError:
        # Provider 拿不到音节时间戳（不可达/返回异常）：退回有声段等分切分
        segments = []
    if not segments:
        voiced = f0res.voiced_ranges
        total = sum(b - a for a, b in voiced)
        if total <= 0:
            return {"ok": False, "reason": "录音里没有检测到声音，请重录",
                    "signal": signal.to_dict()}
        per = total / max(1, len(syllables))
        segments = []
        for a, b in voiced:
            s, r = a, b - a
            while r > 1e-3 and len(segments) < len(syllables):
                take = min(r, per)
                segments.append((s, s + take))
                s += take
                r -= take

    formants = analysis.extract_formants(path)
    vowel_space: dict = {}
    f1_all, f2_all = [], []
    expected = expected_syllables(text)
    for i, seg in enumerate(segments):
        stats = analysis.formant_stats_in_segments(formants, [seg])
        if not stats:
            continue
        exp = expected[i] if i < len(expected) else None
        vowel = main_vowel(exp.get("plain", "")) if exp else None
        if vowel:
            vowel_space[vowel] = {"f1Mean": stats["f1Mean"], "f2Mean": stats["f2Mean"]}
        f1_all.append(stats["f1Mean"])
        f2_all.append(stats["f2Mean"])
    missing = [v for v in ("a", "o", "e", "i", "u", "ü") if v not in vowel_space]
    if missing:
        return {"ok": False,
                "reason": "没有听全六个单韵母（缺 " + "、".join(missing) + "），请按标定文本逐字朗读",
                "signal": signal.to_dict()}
    vowel_space["overall"] = {
        "f1Mean": round(float(np.mean(f1_all)), 1), "f2Mean": round(float(np.mean(f2_all)), 1),
        "f1Std": round(float(np.std(f1_all)), 1) or 1.0, "f2Std": round(float(np.std(f2_all)), 1) or 1.0,
    }
    return {"ok": True, "fLo": round(f_lo, 1), "fHi": round(f_hi, 1),
            "vowelSpace": vowel_space, "signal": signal.to_dict()}


def compute_calibration(*, audio_id: str, syllables: list[str], user_id: str) -> dict:
    """同步处理标定（占用执行器与 45 秒上限由调用方保证）。

    在执行器线程内自建数据库会话：请求作用域会话会随 504/断连先行关闭，
    线程不能依赖它的生命周期（与 run_pipeline 同款约束）。
    成功：写个人音域 + 快照，标定音频即删；
    失败：200 CALIBRATION_FAIL + 重录指引，不写音域。
    """
    db = get_session()
    try:
        audio = db.get(AudioRow, audio_id)
        if audio is None or audio.deleted_at is not None:
            return {"ok": False, "reason": "标定音频已失效，请重新上传后再试",
                    "signal": None}
        result = calibrate_path(audio_path(audio), syllables)
        if not result.get("ok"):
            return {"ok": False, "reason": result["reason"], "signal": result.get("signal")}
        f_lo, f_hi, vowel_space = result["fLo"], result["fHi"], result["vowelSpace"]

        row = (
            db.query(PitchRangeRow)
            .filter(PitchRangeRow.user_id == user_id)
            .one_or_none()
        )
        if row is None:
            row = PitchRangeRow(user_id=user_id)
            db.add(row)
        row.f_lo, row.f_hi = f_lo, f_hi
        row.vowel_space = JSONText.dump(vowel_space)
        row.algorithm_version = analysis.ALGORITHM_VERSION
        row.deleted_at = None
        row.updated_at = now()
        snap = create_snapshot(db, user_id=user_id, f_lo=f_lo, f_hi=f_hi,
                               vowel_space=vowel_space,
                               created_from={"kind": "calibration", "audioId": audio.id})
        row.basis_calibration_id = snap.id
        row.source_recording_ids = JSONText.dump([])
        # 标定音频算完即删（FR-1006）
        mark_audio_deleted(db, audio)
        db.commit()
        return {
            "ok": True,
            "status": "personal",
            "pitchRange": {"fLo": round(f_lo, 1), "fHi": round(f_hi, 1)},
            "vowelSpaceReady": True,
            "rangeSnapshotId": snap.id,
            "updatedAt": row.updated_at.isoformat(),
        }
    finally:
        db.close()


def _signal_advice(signal) -> str:  # noqa: ANN001
    for dim in (signal.volume, signal.noise, signal.clipping, signal.duration, signal.silence):
        if dim and dim.get("advice"):
            return dim["advice"]
    return "录音质量不达标，请换个安静环境重录"


def recompute_personal_range(db: Session, *, user_id: str) -> None:
    """滚动更新/删除重算：标定基线 + 最近 N 条存档合格录音的 F0 统计；
    无剩余录音时回到标定基线。元音空间只随重新标定更新。"""
    from app.detection.models import RecordingRow

    personal = (
        db.query(PitchRangeRow)
        .filter(PitchRangeRow.user_id == user_id)
        .one_or_none()
    )
    if personal is None or personal.deleted_at is not None:
        return
    recs = (
        db.query(RecordingRow)
        .filter(RecordingRow.user_id == user_id,
                RecordingRow.outcome == "scored",
                RecordingRow.deleted_at.is_(None))
        .order_by(RecordingRow.created_at.desc())
        .limit(ROLLING_WINDOW_N)
        .all()
    )
    f_lo, f_hi = personal.f_lo, personal.f_hi
    src_ids: list[str] = []
    hzs = []
    from app.acoustics.models import AudioRow

    for rec in recs:
        audio = db.get(AudioRow, rec.audio_id)
        if audio is None or audio.deleted_at is not None:
            continue
        try:
            f0res = analysis.extract_f0(audio_path(audio))
        except Exception:
            # 跳过是对的（单条坏音频不阻断重算），但必须可观测，否则音域
            # 来源会无痕缩水
            logger.warning("音域滚动重算：录音 %s 的音频 %s 提取 F0 失败，已跳过",
                           rec.id, rec.audio_id, exc_info=True)
            continue
        arr = np.array([fr.get("hz", np.nan) for fr in f0res.frames], dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size >= 10:
            hzs.append(arr)
        src_ids.append(rec.id)
    if hzs:
        all_f = np.concatenate(hzs)
        rng = analysis.robust_pitch_range(all_f)
        if rng:
            f_lo, f_hi = rng
    personal.f_lo, personal.f_hi = f_lo, f_hi
    personal.source_recording_ids = JSONText.dump(src_ids)
    personal.updated_at = now()
    db.flush()


def delete_owner_ranges(db: Session, *, user_id: str) -> None:
    for row in db.query(PitchRangeRow).filter(PitchRangeRow.user_id == user_id).all():
        row.deleted_at = now()


# ---------------- 评分缓存 ----------------

def read_score_cache(db: Session, *, user_id: str, audio: AudioRow,
                     level_id: str) -> dict | None:
    row = (
        db.query(ScoreCacheRow)
        .filter(
            ScoreCacheRow.user_id == user_id,
            ScoreCacheRow.pcm_sha256 == audio.pcm_sha256, ScoreCacheRow.level_id == level_id,
            ScoreCacheRow.provider_version == config.PROVIDER_VERSION,
        )
        .one_or_none()
    )
    if row is None:
        return None
    return JSONText.load(row.payload)


def write_score_cache(db: Session, *, user_id: str, audio_id: str,
                      pcm_sha256: str, level_id: str, payload: dict) -> None:
    row = (
        db.query(ScoreCacheRow)
        .filter(
            ScoreCacheRow.user_id == user_id,
            ScoreCacheRow.pcm_sha256 == pcm_sha256, ScoreCacheRow.level_id == level_id,
            ScoreCacheRow.provider_version == config.PROVIDER_VERSION,
        )
        .one_or_none()
    )
    if row is not None:
        row.audio_id = audio_id
        row.payload = JSONText.dump(payload)
        row.created_at = now()
    else:
        db.add(ScoreCacheRow(
            user_id=user_id, audio_id=audio_id,
            pcm_sha256=pcm_sha256, level_id=level_id,
            provider_version=config.PROVIDER_VERSION,
            payload=JSONText.dump(payload), created_at=now(),
        ))
    db.flush()
