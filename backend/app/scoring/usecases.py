"""scoring 用例：固定个人音域的标定与快照、评分结论缓存。"""
from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from app import config
from app.acoustics import analysis, f0_pipeline
from app.acoustics.models import AudioRow
from app.acoustics.usecases import audio_path, mark_deleted as mark_audio_deleted
from app.db import JSONText, get_session, now
from app.ids import new_id
from app.pinyin_utils import annotated_syllables, main_vowel
from app.scoring.models import PitchRangeRow, ScoreCacheRow
from app.scoring.provider import ProviderError
from app.scoring.provider_mock import MockProvider


def get_provider():
    """评分 Provider 工厂：默认讯飞，仅 SVS_PROVIDER=mock 时用本地替身。"""
    if config.PROVIDER_NAME == "mock":
        return MockProvider()
    from app.scoring.provider_xfyun import XfyunProvider

    return XfyunProvider()


# ---------------- 音域 ----------------

def get_personal_range(db: Session, *, user_id: str) -> dict | None:
    """个人音域（FR-1006）= 该用户最新一行标定值。未标定返回 None，
    由调用方回落默认成人参考范围。"""
    row = (
        db.query(PitchRangeRow)
        .filter(PitchRangeRow.user_id == user_id,
                PitchRangeRow.kind == "calibration",
                PitchRangeRow.deleted_at.is_(None))
        .order_by(PitchRangeRow.created_at.desc(), PitchRangeRow.id.desc())
        .first()
    )
    if row is None:
        return None
    return {
        "status": "personal",
        "fLo": round(row.f_lo, 1),
        "fHi": round(row.f_hi, 1),
        "vowelSpace": JSONText.load(row.vowel_space),
        "algorithmVersion": row.algorithm_version,
        "updatedAt": row.created_at.isoformat() if row.created_at else None,
    }


def create_range_row(db: Session, *, user_id: str, kind: str, f_lo: float,
                     f_hi: float, vowel_space: dict | None,
                     created_from: dict) -> PitchRangeRow:
    """插入一条音域行（标定值或受理快照），插入即冻结、原地不更新。"""
    row = PitchRangeRow(
        id=new_id("prs_"),
        user_id=user_id, kind=kind,
        f_lo=f_lo, f_hi=f_hi,
        vowel_space=JSONText.dump(vowel_space) if vowel_space else None,
        algorithm_version=analysis.ALGORITHM_VERSION,
        created_from=JSONText.dump(created_from),
        created_at=now(),
    )
    db.add(row)
    db.flush()
    return row


def snapshot_dict(row: PitchRangeRow) -> dict:
    return {
        "id": row.id,
        "fLo": round(row.f_lo, 1),
        "fHi": round(row.f_hi, 1),
        "vowelSpace": JSONText.load(row.vowel_space),
        "algorithmVersion": row.algorithm_version,
    }


def calibrate_path(path, syllables: list[dict]) -> dict:
    """纯计算：WAV + 标定文本（[{text, pinyin}]，读音以标注为准）→ 音高音域
    + 元音空间（不写库）。供用户标定与参考发音人登记共用。"""
    signal = analysis.check_signal(path, purpose="calibration")
    if signal.verdict != "pass":
        return {"ok": False, "reason": _signal_advice(signal), "signal": signal.to_dict()}

    try:
        track = f0_pipeline.extract_track(path)
    except f0_pipeline.F0PipelineError:
        return {"ok": False,
                "reason": "这段标定录音没有足够的稳定嗓音，请用正常说话的音量再读一遍",
                "signal": signal.to_dict()}

    text = "".join(s["text"] for s in syllables)
    pinyin = "|".join(s["pinyin"] for s in syllables)
    try:
        expected = annotated_syllables(text, pinyin)
    except ValueError as e:
        return {"ok": False, "reason": f"标定文本配置无效：{e}", "signal": None}
    try:
        prov = get_provider().evaluate(str(path), text, pinyin=pinyin)
        segments = [(s.t0, s.t1) for s in prov.syllables]
    except ProviderError:
        # Provider 拿不到音节时间戳（不可达/返回异常）：退回有声段等分切分
        segments = []
    if not segments:
        from app.content.usecases import _split_voiced_equal

        voiced = [[float(track.times[a]), float(track.times[b])]
                  for a, b in f0_pipeline._runs(np.isfinite(track.f0)) if b > a]
        segments = _split_voiced_equal(voiced, max(1, len(syllables)))
        if not segments:
            return {"ok": False, "reason": "录音里没有检测到声音，请重录",
                    "signal": signal.to_dict()}

    rng = analysis.robust_pitch_range(f0_pipeline.calibration_frequencies(track, segments))
    if rng is None:
        return {"ok": False,
                "reason": "这段标定录音没有足够的稳定嗓音，请用正常说话的音量再读一遍",
                "signal": signal.to_dict()}
    f_lo, f_hi = rng

    formants = analysis.extract_formants(path)
    vowel_space: dict = {}
    f1_all, f2_all = [], []
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


def _signal_advice(signal) -> str:  # noqa: ANN001
    for dim in (signal.volume, signal.noise, signal.clipping, signal.duration, signal.silence):
        if dim and dim.get("advice"):
            return dim["advice"]
    return "录音质量不达标，请换个安静环境重录"


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
