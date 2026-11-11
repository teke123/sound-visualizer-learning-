"""个人标定会话：四元音各 2–3 条录音 + 一条音域短文的会话式标定（个人标定流程改造方案）。

- 会话持久化，刷新后从服务端恢复；会话创建时固定短文版本。
- 每条录音独立验收；同一元音的两条录音稳态共振峰差异超阈值时补录第三条，
  三条仍分散时提示重录该元音（替换差异最大的一条）。
- 任务齐备后发起最终计算：四元音稳态轨迹共同标定 Burg 共振峰上限，
  短文可靠基频帧计算音域；成功时同一事务写入个人标定值、快照与会话完成状态。
"""
from __future__ import annotations

import json

import numpy as np
from sqlalchemy.orm import Session

from app.acoustics import analysis, f0_pipeline, transcode
from app.acoustics.models import AudioRow
from app.acoustics.pronunciation_figures.vowel_space import (
    ANCHORS, calibrate_personal_vowel_space, measure_vowel_take,
)
from app.acoustics.usecases import audio_path, get_audio_for_read, mark_deleted as mark_audio_deleted
from app.db import JSONText, get_session, now
from app.ids import new_id
from app.scoring.models import (
    CalibrationSessionRow, CalibrationTakeRow, PitchRangeRow,
)
from app.scoring.usecases import _signal_advice, create_range_row, get_provider
from app.platform.executor import executor
from app.platform.envelope import ApiError
from app.content.usecases import _split_voiced_equal

PASSAGE_CATEGORY = "read_chapter"   # 短文评分显式题型
CONSISTENCY_F1_REL = 0.15           # 双条一致性：F1 相对差异阈值（占较大值比例）
CONSISTENCY_F2_REL = 0.10           # 双条一致性：F2 相对差异阈值

# 任务配置：四个边缘元音的展示文字与目标条数（方案 §录音任务）
VOWEL_TASKS: tuple[dict, ...] = tuple(
    {"key": key, "displayText": text, "pinyin": pinyin, "ipa": ipa, "targetTakes": 2}
    for key, text, pinyin, ipa in (
        ("i", "衣", "yī", "[i]"),
        ("u", "乌", "wū", "[u]"),
        ("a", "啊", "ā", "[a]"),
        ("ü", "迂", "yū", "[y]"),
    )
)

VOWEL_PURPOSE = "calibration_vowel"   # 短元音质检（独立时长阈值）
PASSAGE_PURPOSE = "calibration"       # 短文沿用语流录音质量参数


# ---------------- 一致性判定（纯函数，供单条验收与测试复用） ----------------

def _relative_diff(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-9)


def _pair_consistent(m1: dict, m2: dict) -> bool:
    return (_relative_diff(m1["f1"], m2["f1"]) <= CONSISTENCY_F1_REL
            and _relative_diff(m1["f2"], m2["f2"]) <= CONSISTENCY_F2_REL)


def _consistent_pair(measurements: list[dict]) -> tuple[int, int] | None:
    """满足阈值且 F1/F2 相对距离最近的两条；没有满足阈值的组合返回 None。"""
    pairs = [(i, j) for i in range(len(measurements))
             for j in range(i + 1, len(measurements))
             if _pair_consistent(measurements[i], measurements[j])]
    if not pairs:
        return None
    return min(pairs, key=lambda p: _relative_diff(measurements[p[0]]["f1"], measurements[p[1]]["f1"])
               + _relative_diff(measurements[p[0]]["f2"], measurements[p[1]]["f2"]))


def _most_dispersed(measurements: list[dict]) -> int:
    """与其它录音相对差异总和最大的一条（重录时替换它）。"""
    totals = [
        sum(_relative_diff(measurements[i][k], measurements[j][k])
            for j in range(len(measurements)) if j != i for k in ("f1", "f2"))
        for i in range(len(measurements))
    ]
    return max(range(len(measurements)), key=lambda i: totals[i])


def _measurements(takes: list[CalibrationTakeRow]) -> list[dict]:
    return [JSONText.load(t.result) for t in takes]


# ---------------- 会话与任务状态 ----------------

def _owned_session(db: Session, *, user_id: str, session_id: str) -> CalibrationSessionRow:
    session = db.get(CalibrationSessionRow, session_id)
    if session is None or session.user_id != user_id:
        raise ApiError(404, "NOT_FOUND", "标定会话不存在或不可见")
    return session


def _session_takes(db: Session, session_id: str) -> list[CalibrationTakeRow]:
    return (db.query(CalibrationTakeRow)
            .filter(CalibrationTakeRow.session_id == session_id)
            .order_by(CalibrationTakeRow.id).all())


def _takes_by_vowel(takes: list[CalibrationTakeRow], vowel: str) -> list[CalibrationTakeRow]:
    return [t for t in takes if t.kind == "vowel" and t.vowel == vowel]


def _pitch_take(takes: list[CalibrationTakeRow]) -> CalibrationTakeRow | None:
    for t in takes:
        if t.kind == "pitch":
            return t
    return None


def _vowel_progress(db: Session, takes: list[CalibrationTakeRow]) -> list[dict]:
    progress = []
    for cfg in VOWEL_TASKS:
        accepted = [t for t in _takes_by_vowel(takes, cfg["key"]) if t.status == "accepted"]
        measurements = _measurements(accepted)
        done = len(accepted) >= 2 and _consistent_pair(measurements) is not None
        progress.append({**cfg, "acceptedTakes": len(accepted), "done": done})
    return progress


def _next_task(takes: list[CalibrationTakeRow]) -> dict | None:
    """当前待办任务：按 元音 i→u→a→ü→短文 顺序推进。"""
    for cfg in VOWEL_TASKS:
        accepted = [t for t in _takes_by_vowel(takes, cfg["key"]) if t.status == "accepted"]
        measurements = _measurements(accepted)
        pair = _consistent_pair(measurements) if len(accepted) >= 2 else None
        if pair is not None:
            continue
        if len(accepted) < cfg["targetTakes"]:
            return {"kind": "vowel", "vowel": cfg["key"], "ordinal": len(accepted) + 1}
        # 条数达标但一致性未过：两条超差 → 补第三条；三条仍分散 → 重录（替换差异最大一条）
        return {"kind": "vowel", "vowel": cfg["key"], "ordinal": len(accepted) + 1,
                "additionalTake": len(accepted) == cfg["targetTakes"]}
    if _pitch_take([t for t in takes if t.status == "accepted"]) is None:
        return {"kind": "pitch"}
    return None


def _take_view(row: CalibrationTakeRow) -> dict:
    return {
        "audioId": row.audio_id,
        "kind": row.kind,
        "vowel": row.vowel,
        "ordinal": row.ordinal,
        "status": row.status,
        "measurements": JSONText.load(row.result),
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def session_view(db: Session, session: CalibrationSessionRow) -> dict:
    takes = _session_takes(db, session.id)
    accepted_pitch = _pitch_take([t for t in takes if t.status == "accepted"])
    completed = session.status == "completed"
    result = None
    if completed and session.snapshot_id:
        snap = db.get(PitchRangeRow, session.snapshot_id)
        if snap is not None:
            result = {
                "ok": True, "status": "personal",
                "pitchRange": {"fLo": round(snap.f_lo, 1), "fHi": round(snap.f_hi, 1)},
                "vowelSpaceReady": bool(snap.vowel_space),
                "rangeSnapshotId": snap.id,
                "updatedAt": snap.created_at.isoformat() if snap.created_at else None,
            }
    return {
        "sessionId": session.id,
        "textVersion": session.text_version,
        "passageText": session.passage_text,
        "status": session.status,
        "calcState": session.calc_state,
        **({"lastError": session.last_error} if session.last_error else {}),
        "vowels": _vowel_progress(db, takes),
        "passageAccepted": accepted_pitch is not None,
        "nextTask": None if completed else _next_task(takes),
        "takes": [_take_view(t) for t in takes],
        **({"result": result} if result else {}),
    }


def create_or_get_session(db: Session, *, user_id: str, text_row) -> dict:
    """创建或返回当前用户进行中的会话（一条 active 会话；完成后再标定建新会话）。"""
    session = (db.query(CalibrationSessionRow)
               .filter(CalibrationSessionRow.user_id == user_id,
                       CalibrationSessionRow.status == "active")
               .order_by(CalibrationSessionRow.created_at.desc()).first())
    if session is None:
        session = CalibrationSessionRow(
            id=new_id("cal_"),
            user_id=user_id,
            text_version=text_row.text_version,
            passage_text=text_row.text,
            passage_pinyin=text_row.syllables,
            status="active", calc_state="idle",
            created_at=now(), updated_at=now(),
        )
        db.add(session)
        db.commit()
    return session_view(db, session)


# ---------------- 单条录音验收 ----------------

def _reject_take(db: Session, audio: AudioRow, reason: str, signal: dict | None) -> dict:
    """验收不通过的录音立即失效（已上传的音频不再可用），不下会话记录。"""
    mark_audio_deleted(db, audio)
    db.commit()
    return {"outcome": "retry_take", "reason": reason, "signal": signal}


def _store_take(db: Session, *, session: CalibrationSessionRow, audio: AudioRow,
                kind: str, vowel: str | None, ordinal: int, measurements: dict) -> CalibrationTakeRow:
    row = CalibrationTakeRow(
        session_id=session.id, audio_id=audio.id, kind=kind, vowel=vowel,
        ordinal=ordinal, status="accepted",
        result=JSONText.dump(measurements), created_at=now(),
    )
    db.add(row)
    db.flush()
    return row


def _retire_take(db: Session, row: CalibrationTakeRow) -> None:
    """录音被替换/不再参与计算：标记 replaced 并按私有音频清理机制失效。"""
    row.status = "replaced"
    audio = db.get(AudioRow, row.audio_id)
    if audio is not None:
        mark_audio_deleted(db, audio)


def _vowel_outcome(db: Session, session: CalibrationSessionRow, take: CalibrationTakeRow) -> str:
    """元音一致性判定：通过（多余的条退场）/ 补第三条 / 仍分散（替换差异最大一条）。"""
    cfg = next(c for c in VOWEL_TASKS if c["key"] == take.vowel)
    accepted = [t for t in _takes_by_vowel(_session_takes(db, session.id), cfg["key"])
                if t.status == "accepted"]
    measurements = _measurements(accepted)
    pair = _consistent_pair(measurements)
    if pair is not None:
        for i, row in enumerate(accepted):
            if i not in pair:
                _retire_take(db, row)
        return "accepted"
    if len(accepted) > cfg["targetTakes"]:
        _retire_take(db, accepted[_most_dispersed(measurements)])
        return "vowel_dispersed"
    return "additional_take_required" if len(accepted) >= cfg["targetTakes"] else "accepted"


def accept_vowel_take(db: Session, *, user_id: str, session: CalibrationSessionRow,
                      audio_id: str, vowel: str) -> dict:
    audio = _take_audio(db, user_id=user_id, audio_id=audio_id)
    signal = analysis.check_signal(audio_path(audio), purpose=VOWEL_PURPOSE)
    if signal.verdict != "pass":
        return _reject_take(db, audio, _signal_advice(signal), signal.to_dict())
    try:
        measurements = measure_vowel_take(audio_path(audio))
    except f0_pipeline.F0PipelineError:
        return _reject_take(db, audio, "这段录音没有足够的稳定嗓音，请用正常说话的音量重录",
                            signal.to_dict())
    if not measurements.get("ok"):
        return _reject_take(db, audio, measurements["reason"], signal.to_dict())

    ordinal = max((t.ordinal for t in _takes_by_vowel(_session_takes(db, session.id), vowel)),
                  default=0) + 1
    take = _store_take(db, session=session, audio=audio, kind="vowel", vowel=vowel,
                       ordinal=ordinal, measurements=measurements)
    outcome = _vowel_outcome(db, session, take)
    _touch_session(session)
    db.commit()
    return {"outcome": outcome, "reason": None, "signal": None, "take": _take_view(take)}


def accept_pitch_take(db: Session, *, user_id: str, session: CalibrationSessionRow,
                      audio_id: str) -> dict:
    audio = _take_audio(db, user_id=user_id, audio_id=audio_id)
    # 短文使用语流录音的质量参数（沿用现有标定时长范围 1.5–40 s）
    signal = analysis.check_signal(audio_path(audio), purpose=PASSAGE_PURPOSE)
    if signal.verdict != "pass":
        return _reject_take(db, audio, _signal_advice(signal), signal.to_dict())
    try:
        track = f0_pipeline.extract_track(audio_path(audio))
    except f0_pipeline.F0PipelineError:
        return _reject_take(db, audio, "这段录音没有足够的稳定嗓音，请用正常说话的音量再读一遍",
                            signal.to_dict())

    segments = _passage_segments(session, audio, track)
    frequencies = f0_pipeline.calibration_frequencies(track, segments)
    rng = analysis.robust_pitch_range(frequencies)
    if rng is None:
        return _reject_take(db, audio,
                            "这段录音没有足够的稳定嗓音，请用正常说话的音量再读一遍",
                            signal.to_dict())
    f_lo, f_hi = rng
    measurements = {
        "fLo": round(f_lo, 1), "fHi": round(f_hi, 1),
        "f0Median": round(float(np.nanmedian(frequencies)), 1),
        "validFrames": int(len(frequencies)),
        "textVersion": session.text_version,
    }
    take = _store_take(db, session=session, audio=audio, kind="pitch", vowel=None,
                       ordinal=1, measurements=measurements)
    _touch_session(session)
    db.commit()
    return {"outcome": "accepted", "reason": None, "signal": None, "take": _take_view(take)}


def _take_audio(db: Session, *, user_id: str, audio_id: str) -> AudioRow:
    """会话录音校验：归属、未删除、标定用途、未被其它任务占用。"""
    audio = get_audio_for_read(db, audio_id=audio_id, user_id=user_id,
                               purposes=("calibration",))
    used = db.query(CalibrationTakeRow).filter(
        CalibrationTakeRow.audio_id == audio_id).one_or_none()
    if used is not None:
        raise ApiError(422, "VALIDATION_ERROR", "这条录音已被其它标定任务占用，请重新录制")
    return audio


def _passage_segments(session: CalibrationSessionRow, audio: AudioRow,
                      track: f0_pipeline.PitchTrack) -> list[tuple[float, float]]:
    """短文音节时间戳：评分服务（read_chapter 题型）优先，失败退回有声段等分。"""
    syllables = json.loads(session.passage_pinyin)
    text = "".join(s["text"] for s in syllables)
    pinyin = "|".join(s["pinyin"] for s in syllables)
    segments: list[tuple[float, float]] = []
    try:
        prov = get_provider().evaluate(str(audio_path(audio)), text, pinyin=pinyin,
                                       category=PASSAGE_CATEGORY)
        segments = [(s.t0, s.t1) for s in prov.syllables]
    except Exception:
        segments = []
    if not segments:
        voiced = [[float(track.times[a]), float(track.times[b])]
                  for a, b in f0_pipeline._runs(np.isfinite(track.f0)) if b > a]
        segments = _split_voiced_equal(voiced, max(1, len(syllables)))
    return segments


def _touch_session(session: CalibrationSessionRow) -> None:
    session.updated_at = now()


def accept_take(db: Session, *, user_id: str, session_id: str, audio_id: str,
                kind: str, vowel: str | None) -> dict:
    """单条录音验收入口：校验任务类型与顺序，按 kind 分派。"""
    session = _owned_session(db, user_id=user_id, session_id=session_id)
    if session.status != "active":
        raise ApiError(422, "VALIDATION_ERROR", "标定会话已完成，请重新发起标定")
    next_task = _next_task(_session_takes(db, session.id))
    if kind == "vowel":
        if vowel not in ANCHORS:
            raise ApiError(422, "VALIDATION_ERROR", "vowel 必须是 i、u、a、ü 之一")
        if next_task is None or next_task["kind"] != "vowel" or next_task["vowel"] != vowel:
            raise ApiError(422, "VALIDATION_ERROR", "请按当前任务顺序录音")
        return accept_vowel_take(db, user_id=user_id, session=session,
                                 audio_id=audio_id, vowel=vowel)
    if kind != "pitch":
        raise ApiError(422, "VALIDATION_ERROR", "kind 必须是 vowel 或 pitch")
    if next_task is None or next_task["kind"] != "pitch":
        raise ApiError(422, "VALIDATION_ERROR", "请按当前任务顺序录音")
    return accept_pitch_take(db, user_id=user_id, session=session, audio_id=audio_id)


# ---------------- 最终计算 ----------------

def request_completion(db: Session, *, user_id: str, session_id: str) -> dict:
    """任务齐备后启动最终计算；幂等，重复请求返回同一计算状态。"""
    session = _owned_session(db, user_id=user_id, session_id=session_id)
    if session.status == "completed" or session.calc_state == "processing":
        return session_view(db, session)
    takes = _session_takes(db, session.id)
    incomplete = [v["key"] for v in _vowel_progress(db, takes) if not v["done"]]
    if incomplete or _pitch_take([t for t in takes if t.status == "accepted"]) is None:
        missing = "、".join(incomplete) if incomplete else "音域短文"
        raise ApiError(422, "VALIDATION_ERROR", f"标定任务尚未完成（缺 {missing}）")
    claimed = (db.query(CalibrationSessionRow)
               .filter(CalibrationSessionRow.id == session.id,
                       CalibrationSessionRow.status == "active",
                       CalibrationSessionRow.calc_state.in_(("idle", "failed")))
               .update({"calc_state": "processing", "last_error": None,
                        "updated_at": now()}, synchronize_session="fetch"))
    db.commit()
    if not claimed:
        return session_view(db, session)
    if executor.try_submit(compute_session_calibration, session_id=session.id) is None:
        session.calc_state = "idle"
        db.commit()
        raise ApiError(503, "SERVER_BUSY", "当前处理排队已满，请稍后重试",
                       headers={"Retry-After": "5"})
    return session_view(db, session)


def compute_session_calibration(*, session_id: str) -> dict:
    """执行器线程内自建数据库会话（与 compute_calibration 同款约束）。

    成功：同一事务写个人标定值、不可变快照与会话完成状态，会话录音即删；
    失败：会话回到可重试状态（calc_state=failed），同一会话可重新发起计算。
    """
    db = get_session()
    try:
        try:
            return _compute_session(db, session_id)
        except Exception as exc:  # noqa: BLE001 计算失败须落库为可重试状态
            db.rollback()
            session = db.get(CalibrationSessionRow, session_id)
            if session is not None:
                session.calc_state = "failed"
                session.last_error = f"{type(exc).__name__}: {exc}"
                _touch_session(session)
                db.commit()
            return {"ok": False, "reason": "标定计算失败，请稍后重试"}
    finally:
        db.close()


def _compute_session(db: Session, session_id: str) -> dict:
    session = db.get(CalibrationSessionRow, session_id)
    if session is None or session.status == "completed":
        return {"ok": True}
    takes = [t for t in _session_takes(db, session_id) if t.status == "accepted"]

    takes_data: dict[str, list[dict]] = {v: [] for v in ANCHORS}
    for row in takes:
        if row.kind != "vowel":
            continue
        audio = db.get(AudioRow, row.audio_id)
        path = audio_path(audio)
        measurements = measure_vowel_take(path)
        if not measurements.get("ok"):
            raise ValueError(f"元音录音重新测量失败：{measurements.get('reason')}")
        x = transcode.read_pcm_samples(path)
        takes_data[row.vowel].append({"x": x, "sr": transcode.SAMPLE_RATE,
                                      "steady": measurements["steady"]})

    vowel_space = calibrate_personal_vowel_space(takes_data)

    pitch = _pitch_take(takes)
    if pitch is None:
        raise ValueError("会话缺少音域短文录音")
    pitch_measurements = JSONText.load(pitch.result)
    f_lo, f_hi = float(pitch_measurements["fLo"]), float(pitch_measurements["fHi"])

    range_row = create_range_row(db, user_id=session.user_id, kind="calibration",
                                 f_lo=f_lo, f_hi=f_hi, vowel_space=vowel_space,
                                 created_from={"kind": "calibration_session",
                                               "sessionId": session_id})
    session.status = "completed"
    session.calc_state = "done"
    session.snapshot_id = range_row.id
    _touch_session(session)
    # 会话录音按私有音频清理机制处理：完成即失效，物理删除走清理任务
    for row_take in _session_takes(db, session_id):
        audio = db.get(AudioRow, row_take.audio_id)
        if audio is not None:
            mark_audio_deleted(db, audio)
    db.commit()
    return {"ok": True, "rangeSnapshotId": range_row.id}
