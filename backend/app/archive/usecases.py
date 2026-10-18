"""archive / learning 用例：档案查询与比较、学习事件与 D-24 只读派生进度、
数据清理编排（删除录音 / 清空档案 / 注销清空）。"""
from __future__ import annotations

import base64
import datetime

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.acoustics.models import AudioRow
from app.acoustics.usecases import mark_deleted as mark_audio_deleted
from app.archive.models import LearningEventRow
from app.content.models import LevelRow
from app.db import JSONText, now
from app.detection.models import AssessmentResultRow, RecordingRow
from app.feedback.models import FeedbackRow
from app.platform.deletion_log import deletion_log
from app.platform.envelope import ApiError
from app.identity.models import UserRow
from app.scoring.models import ScoreCacheRow
from app.scoring.usecases import recompute_personal_range, snapshot_dict


# ---------------- 档案 ----------------

def recording_summary(rec: RecordingRow, result: AssessmentResultRow | None) -> dict:
    payload = JSONText.load(result.payload, {}) if result else {}
    quality = payload.get("quality") or {}
    return {
        "recordingId": rec.id,
        "audioId": rec.audio_id,
        "levelId": rec.level_id,
        "createdAt": rec.created_at.isoformat() if rec.created_at else None,
        "verdict": rec.outcome,
        "qualityAdvice": quality.get("advice"),
        "score": payload.get("score"),
    }


def _page_cursor(rec: RecordingRow) -> str:
    """不透明分页游标：客户端原样回传 nextCursor，不解读内容。"""
    payload = f"{rec.created_at.isoformat()}|{rec.id}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def _parse_page_cursor(cursor: str) -> tuple[datetime.datetime, str]:
    try:
        payload = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        created_at, _, rec_id = payload.rpartition("|")
        if not created_at or not rec_id:
            raise ValueError(cursor)
        return datetime.datetime.fromisoformat(created_at), rec_id
    except (ValueError, UnicodeError) as e:
        raise ApiError(422, "VALIDATION_ERROR", "分页游标无效") from e


def my_recordings(db: Session, *, user: UserRow, level_id: str | None,
                  cursor: str | None, limit: int = 20) -> dict:
    q = (db.query(RecordingRow)
         .filter(RecordingRow.user_id == user.id,
                 RecordingRow.deleted_at.is_(None)))
    if level_id:
        q = q.filter(RecordingRow.level_id == level_id)
    # created_at 不唯一：以 id 并列排序，按 (created_at, id) 键集分页，
    # 游标过滤必须在 LIMIT 之前，否则第二页永远取回最新一页
    q = q.order_by(RecordingRow.created_at.desc(), RecordingRow.id.desc())
    if cursor:
        marker_at, marker_id = _parse_page_cursor(cursor)
        q = q.filter(or_(
            RecordingRow.created_at < marker_at,
            and_(RecordingRow.created_at == marker_at, RecordingRow.id < marker_id),
        ))
    rows = q.limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = []
    for rec in rows:
        result = db.query(AssessmentResultRow).filter(
            AssessmentResultRow.recording_id == rec.id).one_or_none()
        items.append(recording_summary(rec, result))
    next_cursor = _page_cursor(rows[-1]) if has_more and rows else None
    return {"recordings": items, "nextCursor": next_cursor}


def compare_recordings(db: Session, *, user: UserRow, a: str, b: str) -> dict:
    """本人同关两条比较：双方摘要与曲线、各自音域快照；
    可比维度与差异提示（FR-1103）。"""
    recs = []
    for rid in (a, b):
        rec = db.query(RecordingRow).filter(
            RecordingRow.id == rid, RecordingRow.user_id == user.id,
            RecordingRow.deleted_at.is_(None)).one_or_none()
        if rec is None:
            raise ApiError(404, "NOT_FOUND", f"录音不存在：{rid}")
        recs.append(rec)
    ra, rb = recs
    if ra.level_id != rb.level_id:
        raise ApiError(422, "VALIDATION_ERROR", "只能比较同一关卡的两条记录")
    comparable = {"score": True, "curve": False}
    reasons: list[str] = []

    def full(rec: RecordingRow) -> dict:
        result = db.query(AssessmentResultRow).filter(
            AssessmentResultRow.recording_id == rec.id).one_or_none()
        payload = JSONText.load(result.payload, {}) if result else {}
        return {"recording": recording_summary(rec, result),
                "result": payload,
                "rangeSnapshot": _snapshot_of(db, payload)}

    fa, fb = full(ra), full(rb)
    curve_a = (fa["result"].get("curve") or {}).get("status")
    curve_b = (fb["result"].get("curve") or {}).get("status")
    if curve_a == "ok" and curve_b == "ok":
        comparable["curve"] = True
    else:
        reasons.append("至少一条记录无有效曲线，曲线对比不可用")
    sa, sb = fa["result"].get("score"), fb["result"].get("score")
    differences = []
    if sa is not None and sb is not None:
        differences.append({
            "dimension": "score",
            "description": f"分数从 {sa} 变为 {sb}" + ("（有进步）" if sb > sa else "（保持或退步）"),
        })
    if comparable["curve"]:
        differences.append({
            "dimension": "curve",
            "description": "两条曲线已并排展示，可对比形状与起点变化",
        })
    return {"a": fa, "b": fb, "comparable": comparable, "reasons": reasons,
            "differences": differences}


def _snapshot_of(db: Session, payload: dict) -> dict | None:
    curve = payload.get("curve") or {}
    snap_id = curve.get("rangeSnapshotId")
    if not snap_id:
        return None
    from app.scoring.models import PitchRangeSnapshotRow

    row = db.get(PitchRangeSnapshotRow, snap_id)
    return snapshot_dict(row) if row else None


# ---------------- 删除 ----------------

def delete_recording(db: Session, rec: RecordingRow) -> None:
    """单删：立即逻辑失效；独占 audio 同时失效；音域引用该录音则重算；
    反馈去引用。重复删除幂等。"""
    if rec.deleted_at is not None:
        return
    rec.deleted_at = now()
    others = db.query(RecordingRow).filter(
        RecordingRow.audio_id == rec.audio_id, RecordingRow.id != rec.id,
        RecordingRow.deleted_at.is_(None)).count()
    if others == 0:
        audio = db.get(AudioRow, rec.audio_id)
        if audio is not None:
            mark_audio_deleted(db, audio)
    for fb in db.query(FeedbackRow).filter(FeedbackRow.recording_id == rec.id).all():
        fb.recording_id = None
    for sc in db.query(ScoreCacheRow).filter(ScoreCacheRow.audio_id == rec.audio_id).all():
        deletion_log.append(kind="score_cache",
                            key=f"{sc.user_id}:{sc.pcm_sha256}:{sc.level_id}")
        db.delete(sc)
    recompute_personal_range(db, user_id=rec.user_id)
    db.flush()


def clear_archive(db: Session, *, user: UserRow) -> dict:
    rows = (db.query(RecordingRow)
            .filter(RecordingRow.user_id == user.id,
                    RecordingRow.deleted_at.is_(None))
            .all())
    for rec in rows:
        delete_recording(db, rec)
    db.commit()
    return {"deleted": len(rows)}


def purge_user_data(db: Session, *, user_id: str) -> None:
    """注销清理（D-17/FR-108）：录音、结果、音频、缓存、事件/进度、音域。"""
    recs = db.query(RecordingRow).filter(RecordingRow.user_id == user_id).all()
    for rec in recs:
        if rec.deleted_at is None:
            rec.deleted_at = now()
        audio = db.get(AudioRow, rec.audio_id)
        if audio is not None and audio.deleted_at is None:
            mark_audio_deleted(db, audio)
        deletion_log.append(kind="score_cache",
                            key=f"{user_id}:{audio.pcm_sha256 if audio else ''}:*")
    db.query(ScoreCacheRow).filter(ScoreCacheRow.user_id == user_id).delete(
        synchronize_session=False)
    db.query(LearningEventRow).filter(LearningEventRow.user_id == user_id).delete(
        synchronize_session=False)
    from app.scoring.usecases import delete_owner_ranges

    delete_owner_ranges(db, user_id=user_id)
    for fb in db.query(FeedbackRow).filter(FeedbackRow.user_id == user_id).all():
        fb.recording_id = None
    db.flush()


# ---------------- 学习事件与 D-24 进度 ----------------

EVENT_BATCH_LIMIT = 50

def accept_learning_events(db: Session, *, user: UserRow, events: list[dict]) -> dict:
    """按 eventId 去重；服务端按关卡内容校验并派生对错。"""
    accepted, duplicates, rejected = 0, 0, []
    for ev in events[:EVENT_BATCH_LIMIT]:
        event_id = str(ev.get("eventId") or "")
        level_id = ev.get("levelId")
        kind = ev.get("kind")
        if not event_id or not level_id or kind not in ("listen_quiz", "practice_done"):
            rejected.append({"eventId": event_id, "code": "VALIDATION_ERROR"})
            continue
        if db.query(LearningEventRow).filter(LearningEventRow.user_id == user.id,
                                             LearningEventRow.event_id == event_id).count():
            duplicates += 1
            continue
        level = db.get(LevelRow, level_id)
        if level is None or not level.published:
            rejected.append({"eventId": event_id, "code": "LEVEL_NOT_OPEN"})
            continue
        content = JSONText.load(level.content, {})
        detail = ev.get("detail") or {}
        correct = None
        if kind == "listen_quiz":
            quiz = next((q for q in content.get("quizzes") or []
                         if q.get("id") == detail.get("questionId")), None)
            if quiz is None:
                rejected.append({"eventId": event_id, "code": "QUESTION_NOT_FOUND"})
                continue
            correct = isinstance(detail.get("choiceIndex"), int) and \
                detail["choiceIndex"] == quiz.get("answerIndex")
        else:
            valid_step = any(p.get("id") == detail.get("stepId")
                             for p in content.get("practice") or [])
            if not valid_step:
                rejected.append({"eventId": event_id, "code": "STEP_NOT_FOUND"})
                continue
        db.add(LearningEventRow(
            user_id=user.id, event_id=event_id, level_id=level_id,
            kind=kind,
            detail=JSONText.dump(detail), correct=correct, created_at=now(),
        ))
        accepted += 1
    db.commit()
    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}


def derive_progress(db: Session, *, user: UserRow) -> dict:
    """D-24：全部听辨题各至少答对一次 + 全部练习步骤各至少一次；
    下一关 = 顺序中第一个未完成的已开放关，全部完成回落第一已开放关。"""
    from app.content.usecases import open_levels

    levels = open_levels(db)
    events = db.query(LearningEventRow).filter(LearningEventRow.user_id == user.id).all()
    out = []
    completed_ids = []
    for lv in levels:
        content = JSONText.load(lv.content, {})
        quiz_ids = {q["id"] for q in content.get("quizzes") or [] if q.get("id")}
        step_ids = {p["id"] for p in content.get("practice") or [] if p.get("id")}
        lv_events = [e for e in events if e.level_id == lv.id]
        passed_quizzes: set[str] = set()
        done_steps: set[str] = set()
        for e in lv_events:
            d = JSONText.load(e.detail, {}) or {}
            if e.kind == "listen_quiz" and e.correct and d.get("questionId"):
                passed_quizzes.add(d["questionId"])
            if e.kind == "practice_done" and d.get("stepId"):
                done_steps.add(d["stepId"])
        completed = quiz_ids and quiz_ids <= passed_quizzes and step_ids and step_ids <= done_steps
        out.append({
            "levelId": lv.id,
            "completed": completed,
            "quiz": {"passed": len(passed_quizzes & quiz_ids), "total": len(quiz_ids)},
            "practice": {"done": len(done_steps & step_ids), "total": len(step_ids)},
        })
        if completed:
            completed_ids.append(lv.id)
    next_level_id = None
    for lv in levels:
        if lv.id not in completed_ids:
            next_level_id = lv.id
            break
    if next_level_id is None and levels:
        next_level_id = levels[0].id
    return {"levels": out, "nextLevelId": next_level_id}
