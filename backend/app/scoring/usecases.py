"""scoring 用例：音域（有效判定/标定写入/滚动更新/删除重算）、评分结论缓存。"""
from __future__ import annotations

import datetime

import numpy as np
from sqlalchemy.orm import Session

from app import config
from app.acoustics import analysis
from app.acoustics.models import AudioRow
from app.acoustics.usecases import audio_path, mark_deleted as mark_audio_deleted
from app.db import JSONText, now
from app.ids import new_id
from app.platform.envelope import ApiError
from app.pinyin_utils import expected_syllables, main_vowel
from app.scoring.models import PitchRangeRow, PitchRangeSnapshotRow, ScoreCacheRow
from app.scoring.provider import ProviderError
from app.scoring.provider_mock import MockProvider

ROLLING_WINDOW_N = 20   # 最近 N 条存档合格录音

SIX_VOWELS = {"a": "a", "o": "o", "e": "e", "i": "i", "u": "u", "ü": "v"}


def get_provider():
    if config.PROVIDER_NAME == "xfyun":
        from app.scoring.provider_xfyun import XfyunProvider

        return XfyunProvider()
    return MockProvider()


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
        "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
    }


def get_effective_range(db: Session, *, owner_type: str, owner_id: str) -> dict | None:
    """有效音域判定（决策图 #7）：个人音域存在，或当前会话临时音域未过期。"""
    personal = (
        db.query(PitchRangeRow)
        .filter(PitchRangeRow.owner_type == "user", PitchRangeRow.owner_id == owner_id,
                PitchRangeRow.deleted_at.is_(None))
        .one_or_none()
    ) if owner_type == "user" else None
    if personal is not None:
        return {"status": "personal", **_range_row_dict(personal)}
    if owner_type == "sid":
        session_row = (
            db.query(PitchRangeRow)
            .filter(PitchRangeRow.owner_type == "sid", PitchRangeRow.owner_id == owner_id,
                    PitchRangeRow.deleted_at.is_(None))
            .one_or_none()
        )
        if session_row is not None and (session_row.expires_at is None or session_row.expires_at > now()):
            return {"status": "session", **_range_row_dict(session_row)}
    return None


def create_snapshot(db: Session, *, owner_type: str, owner_id: str, f_lo: float,
                    f_hi: float, vowel_space: dict | None, created_from: dict) -> PitchRangeSnapshotRow:
    row = PitchRangeSnapshotRow(
        id=new_id("prs_"),
        owner_type=owner_type, owner_id=owner_id,
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
    供用户标定与参考发音人登记共用（docs/architecture/03 第 5.2 节）。"""
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


def compute_calibration(db: Session, *, audio: AudioRow, syllables: list[str],
                        owner_type: str, owner_id: str, consent_valid: bool) -> dict:
    """同步处理标定（占用执行器与 30 秒上限由调用方保证）。

    成功：按同意状态写个人/会话音域 + 快照，标定音频即删；
    失败：200 CALIBRATION_FAIL + 重录指引，不写音域。
    """
    result = calibrate_path(audio_path(audio), syllables)
    if not result.get("ok"):
        return {"ok": False, "reason": result["reason"], "signal": result.get("signal")}
    f_lo, f_hi, vowel_space = result["fLo"], result["fHi"], result["vowelSpace"]

    # 写入：同意有效 → 个人音域；否则会话临时音域（72h）
    kind = "personal" if consent_valid else "session"
    expires = None if consent_valid else audio.expires_at
    row = (
        db.query(PitchRangeRow)
        .filter(PitchRangeRow.owner_type == owner_type, PitchRangeRow.owner_id == owner_id)
        .one_or_none()
    )
    if row is None:
        row = PitchRangeRow(owner_type=owner_type, owner_id=owner_id)
        db.add(row)
    row.kind = kind
    row.f_lo, row.f_hi = f_lo, f_hi
    row.vowel_space = JSONText.dump(vowel_space)
    row.algorithm_version = analysis.ALGORITHM_VERSION
    row.expires_at = expires
    row.deleted_at = None
    row.updated_at = now()
    snap = create_snapshot(db, owner_type=owner_type, owner_id=owner_id, f_lo=f_lo, f_hi=f_hi,
                           vowel_space=vowel_space,
                           created_from={"kind": "calibration", "audioId": audio.id})
    row.basis_calibration_id = snap.id
    row.source_recording_ids = JSONText.dump([])
    # 标定音频算完即删（FR-1006）
    mark_audio_deleted(db, audio)
    db.commit()
    return {
        "ok": True,
        "status": "personal" if kind == "personal" else "session",
        "pitchRange": {"fLo": round(f_lo, 1), "fHi": round(f_hi, 1)},
        "vowelSpaceReady": True,
        "rangeSnapshotId": snap.id,
        "expiresAt": expires.isoformat() if expires else None,
        "updatedAt": row.updated_at.isoformat(),
    }


def _signal_advice(signal) -> str:  # noqa: ANN001
    for dim in (signal.volume, signal.noise, signal.clipping, signal.duration, signal.silence):
        if dim and dim.get("advice"):
            return dim["advice"]
    return "录音质量不达标，请换个安静环境重录"


def upgrade_session_range_on_transfer(db: Session, *, sid: str, user_id: str) -> bool:
    """同意转存时：未过期会话标定升级为个人音域；已有个人音域取较新标定。"""
    sess = (
        db.query(PitchRangeRow)
        .filter(PitchRangeRow.owner_type == "sid", PitchRangeRow.owner_id == sid,
                PitchRangeRow.deleted_at.is_(None))
        .one_or_none()
    )
    if sess is None or (sess.expires_at is not None and sess.expires_at < now()):
        return False
    personal = (
        db.query(PitchRangeRow)
        .filter(PitchRangeRow.owner_type == "user", PitchRangeRow.owner_id == user_id,
                PitchRangeRow.deleted_at.is_(None))
        .one_or_none()
    )
    if personal is None or (sess.updated_at and personal.updated_at and sess.updated_at > personal.updated_at):
        if personal is None:
            personal = PitchRangeRow(owner_type="user", owner_id=user_id)
            db.add(personal)
        personal.kind = "personal"
        personal.f_lo, personal.f_hi = sess.f_lo, sess.f_hi
        personal.vowel_space = sess.vowel_space
        personal.algorithm_version = sess.algorithm_version
        personal.expires_at = None
        personal.deleted_at = None
        personal.updated_at = now()
        personal.basis_calibration_id = sess.basis_calibration_id
        personal.source_recording_ids = sess.source_recording_ids
    # 会话行删除（已升级或已过期不用）
    sess.deleted_at = now()
    db.flush()
    return True


def recompute_personal_range(db: Session, *, user_id: str) -> None:
    """滚动更新/删除重算：标定基线 + 最近 N 条存档合格录音的 F0 统计；
    无剩余录音时回到标定基线。元音空间只随重新标定更新。"""
    from app.detection.models import RecordingRow

    personal = (
        db.query(PitchRangeRow)
        .filter(PitchRangeRow.owner_type == "user", PitchRangeRow.owner_id == user_id)
        .one_or_none()
    )
    if personal is None or personal.deleted_at is not None:
        return
    recs = (
        db.query(RecordingRow)
        .filter(RecordingRow.owner_type == "user", RecordingRow.owner_id == user_id,
                RecordingRow.storage == "archived", RecordingRow.outcome == "scored",
                RecordingRow.deleted_at.is_(None))
        .order_by(RecordingRow.created_at.desc())
        .limit(ROLLING_WINDOW_N)
        .all()
    )
    f_lo, f_hi = personal.f_lo, personal.f_hi
    basis = personal.basis_calibration_id
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


def delete_owner_ranges(db: Session, *, owner_type: str, owner_id: str) -> None:
    for row in db.query(PitchRangeRow).filter(
            PitchRangeRow.owner_type == owner_type,
            PitchRangeRow.owner_id == owner_id).all():
        row.deleted_at = now()


# ---------------- 评分缓存 ----------------

def _cache_key(*, owner_type, owner_id, audio: AudioRow, level_id: str,
               content_version: int) -> dict:
    return {
        "owner_type": owner_type, "owner_id": owner_id,
        "pcm_sha256": audio.pcm_sha256, "level_id": level_id,
        "content_version": content_version, "rule_version": config.RULE_VERSION,
        "provider_version": config.PROVIDER_VERSION,
    }


def read_score_cache(db: Session, *, owner_type: str, owner_id: str, audio: AudioRow,
                     level_id: str, content_version: int) -> dict | None:
    row = (
        db.query(ScoreCacheRow)
        .filter(
            ScoreCacheRow.owner_type == owner_type, ScoreCacheRow.owner_id == owner_id,
            ScoreCacheRow.pcm_sha256 == audio.pcm_sha256, ScoreCacheRow.level_id == level_id,
            ScoreCacheRow.content_version == content_version,
            ScoreCacheRow.rule_version == config.RULE_VERSION,
            ScoreCacheRow.provider_version == config.PROVIDER_VERSION,
        )
        .one_or_none()
    )
    if row is None:
        return None
    return JSONText.load(row.payload)


def write_score_cache(db: Session, *, owner_type: str, owner_id: str, audio_id: str,
                      pcm_sha256: str, level_id: str, content_version: int,
                      payload: dict) -> None:
    # 同键（所有者+音频内容+版本）可能已存在：登录迁移 sid→user 后重录同一
    # 内容会再写同键——串行流程能读到迁移行，但迁移前受理的旧管线会在
    # finalize 时经 db.refresh 取到迁移后的 user 归属，与新管线并发写同键；
    # 裸 INSERT 撞 UNIQUE 会使管线崩溃、录音滞留 processing——幂等更新处理
    row = (
        db.query(ScoreCacheRow)
        .filter(
            ScoreCacheRow.owner_type == owner_type, ScoreCacheRow.owner_id == owner_id,
            ScoreCacheRow.pcm_sha256 == pcm_sha256, ScoreCacheRow.level_id == level_id,
            ScoreCacheRow.content_version == content_version,
            ScoreCacheRow.rule_version == config.RULE_VERSION,
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
            owner_type=owner_type, owner_id=owner_id, audio_id=audio_id,
            pcm_sha256=pcm_sha256, level_id=level_id, content_version=content_version,
            rule_version=config.RULE_VERSION, provider_version=config.PROVIDER_VERSION,
            payload=JSONText.dump(payload), created_at=now(),
        ))
    db.flush()


def migrate_score_cache_owner(db: Session, *, from_type: str, from_id: str,
                              to_type: str, to_id: str) -> None:
    """登录绑定：评分缓存所有者键随资源迁移（docs/architecture/03 第 6 节）。"""
    rows = db.query(ScoreCacheRow).filter(
        ScoreCacheRow.owner_type == from_type, ScoreCacheRow.owner_id == from_id).all()
    for row in rows:
        dup = db.query(ScoreCacheRow).filter(
            ScoreCacheRow.owner_type == to_type, ScoreCacheRow.owner_id == to_id,
            ScoreCacheRow.pcm_sha256 == row.pcm_sha256, ScoreCacheRow.level_id == row.level_id,
            ScoreCacheRow.content_version == row.content_version,
            ScoreCacheRow.rule_version == row.rule_version,
            ScoreCacheRow.provider_version == row.provider_version).one_or_none()
        if dup is not None:
            db.delete(row)
        else:
            row.owner_type, row.owner_id = to_type, to_id
    db.flush()
