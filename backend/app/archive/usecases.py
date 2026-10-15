"""archive / learning 用例：自动转存（含音域升级）、档案查询与比较、
当前会话临时记录、学习事件与 D-24 只读派生进度、数据清理编排。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import config
from app.acoustics.models import AudioRow
from app.acoustics.usecases import mark_deleted as mark_audio_deleted
from app.archive.models import LearningEventRow
from app.content.models import LevelRow, LevelVersionRow
from app.db import JSONText, now
from app.detection.models import AssessmentResultRow, RecordingRow
from app.feedback.models import FeedbackRow
from app.platform.audit import audit, deletion_log
from app.platform.envelope import ApiError
from app.scoring.models import PitchRangeRow, ScoreCacheRow
from app.scoring.usecases import (
    recompute_personal_range,
    snapshot_dict,
    upgrade_session_range_on_transfer,
)
from app.identity.models import UserRow


# ---------------- 自动转存（D-14 / 5.3） ----------------

def transfer_session_records(db: Session, *, sid: str, user_id: str,
                             consent_id: str | None) -> dict:
    """单事务：本会话内本账号 session 记录（completed、未过期、未删除）→ archived，
    登记 consentId；会话标定升级为个人音域。失败整个回滚，重试天然幂等。"""
    rows = (db.query(RecordingRow)
            .filter(RecordingRow.owner_type == "user", RecordingRow.owner_id == user_id,
                    RecordingRow.storage == "session",
                    RecordingRow.status == "completed",
                    RecordingRow.deleted_at.is_(None))
            .all())
    transferred = 0
    for row in rows:
        if row.expires_at is not None and row.expires_at < now():
            continue
        row.storage = "archived"
        row.expires_at = None
        if consent_id:
            row.consent_id = consent_id
        transferred += 1
    upgraded = upgrade_session_range_on_transfer(db, sid=sid, user_id=user_id)
    # 转存后按「标定基线 + 最近存档合格录音」滚动更新
    recompute_personal_range(db, user_id=user_id)
    audit.log(db, action="transfer", object_type="user", object_id=user_id,
              actor_type="user", actor_id=user_id,
              after={"transferredCount": transferred, "calibrationUpgraded": upgraded})
    db.flush()
    return {"status": "completed" if transferred or upgraded else "none",
            "transferredCount": transferred, "calibrationUpgraded": upgraded}


# ---------------- 档案 ----------------

def recording_summary(rec: RecordingRow, result: AssessmentResultRow | None) -> dict:
    payload = JSONText.load(result.payload, {}) if result else {}
    quality = payload.get("quality") or {}
    return {
        "recordingId": rec.id,
        "audioId": rec.audio_id,
        "levelId": rec.level_id,
        "contentVersion": rec.content_version,
        "ruleVersion": rec.rule_version,
        "createdAt": rec.created_at.isoformat() if rec.created_at else None,
        "verdict": (quality.get("verdict") if quality else None) or rec.outcome,
        "score": payload.get("score"),
    }


def my_recordings(db: Session, *, user: UserRow, level_id: str | None,
                  cursor: str | None, limit: int = 20) -> dict:
    q = (db.query(RecordingRow)
         .filter(RecordingRow.owner_type == "user", RecordingRow.owner_id == user.id,
                 RecordingRow.storage == "archived",
                 RecordingRow.deleted_at.is_(None)))
    if level_id:
        q = q.filter(RecordingRow.level_id == level_id)
    q = q.order_by(RecordingRow.created_at.desc())
    rows = q.limit(limit + 1).all()
    next_cursor = rows[-1].id if len(rows) > limit else None
    rows = rows[:limit]
    if cursor:
        rows = [r for r in rows if r.id < cursor] or rows
    items = []
    for rec in rows:
        result = db.query(AssessmentResultRow).filter(
            AssessmentResultRow.recording_id == rec.id).one_or_none()
        items.append(recording_summary(rec, result))
    return {"recordings": items, "nextCursor": next_cursor}


def compare_recordings(db: Session, *, user: UserRow, a: str, b: str) -> dict:
    """本人同关 archived 两条比较：双方摘要与曲线、各自音域快照；
    可比维度与差异提示（FR-1103）。"""
    recs = []
    for rid in (a, b):
        rec = db.query(RecordingRow).filter(
            RecordingRow.id == rid, RecordingRow.owner_type == "user",
            RecordingRow.owner_id == user.id, RecordingRow.storage == "archived",
            RecordingRow.deleted_at.is_(None)).one_or_none()
        if rec is None:
            raise ApiError(404, "NOT_FOUND", f"录音不存在：{rid}")
        recs.append(rec)
    ra, rb = recs
    if ra.level_id != rb.level_id:
        raise ApiError(422, "VALIDATION_ERROR", "只能比较同一关卡的两条记录")
    comparable = {"score": False, "curve": False}
    reasons: list[str] = []
    if ra.content_version != rb.content_version or ra.rule_version != rb.rule_version:
        reasons.append("内容或规则版本不同，分数不可直接比较")
    else:
        comparable["score"] = True

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
    if comparable["score"] and sa is not None and sb is not None:
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


# ---------------- 会话临时记录 ----------------

def session_recordings(db: Session, *, owner_type: str, owner_id: str) -> dict:
    """当前 sid（访客）或当前绑定会话内本账号的临时录音摘要。"""
    rows = (db.query(RecordingRow)
            .filter(RecordingRow.owner_type == owner_type, RecordingRow.owner_id == owner_id,
                    RecordingRow.storage == "session", RecordingRow.deleted_at.is_(None),
                    RecordingRow.status == "completed")
            .order_by(RecordingRow.created_at.desc()).all())
    items = []
    transferable = 0
    for rec in rows:
        if rec.expires_at is None or rec.expires_at >= now():
            transferable += 1
        result = db.query(AssessmentResultRow).filter(
            AssessmentResultRow.recording_id == rec.id).one_or_none()
        items.append({
            "recordingId": rec.id,
            "audioId": rec.audio_id,
            "levelId": rec.level_id,
            "createdAt": rec.created_at.isoformat() if rec.created_at else None,
            "expiresAt": rec.expires_at.isoformat() if rec.expires_at else None,
            "verdict": rec.outcome,
            "score": (JSONText.load(result.payload, {}).get("score")
                      if result else None),
        })
    return {"recordings": items, "transferableCount": transferable}


def session_reset(db: Session, *, sid: str, owner_type: str, owner_id: str,
                  is_guest: bool) -> dict:
    """删除当前会话全部临时录音、未引用上传与会话标定；访客同时轮换 sid。"""
    from app.identity.usecases import rotate_sid
    from app.scoring.usecases import delete_owner_ranges

    recs = (db.query(RecordingRow)
            .filter(RecordingRow.owner_type == owner_type, RecordingRow.owner_id == owner_id,
                    RecordingRow.storage == "session", RecordingRow.deleted_at.is_(None))
            .all())
    for rec in recs:
        delete_recording(db, rec, request_id=None, reason="session_reset")
    # 未引用上传：无 recording 引用的 audio
    referenced = {r.audio_id for r in recs}
    orphans = (db.query(AudioRow)
               .filter(AudioRow.owner_type == owner_type, AudioRow.owner_id == owner_id,
                       AudioRow.deleted_at.is_(None)).all())
    for audio in orphans:
        if audio.id not in referenced:
            has_other_ref = db.query(RecordingRow).filter(
                RecordingRow.audio_id == audio.id,
                RecordingRow.deleted_at.is_(None)).count()
            if not has_other_ref:
                mark_audio_deleted(db, audio)
    if owner_type == "sid":
        delete_owner_ranges(db, owner_type="sid", owner_id=owner_id)
    db.commit()
    new_sid = rotate_sid(db, sid) if is_guest else None
    return {"reset": True, "newSidIssued": new_sid is not None}


# ---------------- 删除 ----------------

def delete_recording(db: Session, rec: RecordingRow, *, request_id: str | None,
                     reason: str | None) -> None:
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
        fb.recording_content_version = None
    for sc in db.query(ScoreCacheRow).filter(ScoreCacheRow.audio_id == rec.audio_id).all():
        deletion_log.append(kind="score_cache",
                            key=f"{sc.owner_type}:{sc.owner_id}:{sc.pcm_sha256}:{sc.level_id}")
        db.delete(sc)
    if rec.owner_type == "user":
        recompute_personal_range(db, user_id=rec.owner_id)
    audit.log(db, action="delete_recording", object_type="recording", object_id=rec.id,
              actor_type="user", actor_id=rec.owner_id, reason=reason,
              request_id=request_id)
    db.flush()


def clear_archive(db: Session, *, user: UserRow, request_id: str | None) -> dict:
    rows = (db.query(RecordingRow)
            .filter(RecordingRow.owner_type == "user", RecordingRow.owner_id == user.id,
                    RecordingRow.storage == "archived", RecordingRow.deleted_at.is_(None))
            .all())
    for rec in rows:
        delete_recording(db, rec, request_id=request_id, reason="clear_archive")
    recompute_personal_range(db, user_id=user.id)
    audit.log(db, action="clear_archive", object_type="user", object_id=user.id,
              actor_type="user", actor_id=user.id, request_id=request_id,
              after={"deleted": len(rows)})
    db.commit()
    return {"deleted": len(rows)}


def purge_user_data(db: Session, *, user_id: str, request_id: str | None,
                    include_learning: bool, include_ranges: bool) -> None:
    """撤回/注销范围的清理（D-17）：录音、结果、音频、缓存、事件/进度、音域。"""
    recs = (db.query(RecordingRow)
            .filter(RecordingRow.owner_type == "user", RecordingRow.owner_id == user_id)
            .all())
    for rec in recs:
        if rec.deleted_at is None:
            rec.deleted_at = now()
        audio = db.get(AudioRow, rec.audio_id)
        if audio is not None and audio.deleted_at is None:
            mark_audio_deleted(db, audio)
        deletion_log.append(kind="score_cache",
                            key=f"user:{user_id}:{audio.pcm_sha256 if audio else ''}:*")
    db.query(ScoreCacheRow).filter(ScoreCacheRow.owner_type == "user",
                                   ScoreCacheRow.owner_id == user_id).delete(
        synchronize_session=False)
    if include_learning:
        db.query(LearningEventRow).filter(LearningEventRow.user_id == user_id).delete(
            synchronize_session=False)
    if include_ranges:
        from app.scoring.usecases import delete_owner_ranges

        delete_owner_ranges(db, owner_type="user", owner_id=user_id)
    # sid 名下遗留（登录前上传未绑定）也一并清理
    for fb in db.query(FeedbackRow).filter(FeedbackRow.owner_type == "user",
                                           FeedbackRow.owner_id == user_id).all():
        fb.recording_id = None
        fb.recording_content_version = None
    db.flush()


# ---------------- 学习事件与 D-24 进度 ----------------

EVENT_BATCH_LIMIT = 50

def accept_learning_events(db: Session, *, user: UserRow, events: list[dict]) -> dict:
    """登录且同意；按 eventId 去重；服务端按公开版本校验并派生对错。"""
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
        if level is None or level.status != "published" or not level.current_version_id:
            rejected.append({"eventId": event_id, "code": "LEVEL_NOT_PUBLISHED"})
            continue
        version = db.get(LevelVersionRow, level.current_version_id)
        content = JSONText.load(version.content, {})
        detail = ev.get("detail") or {}
        correct = None
        if kind == "listen_quiz":
            quiz = next((q for q in content.get("quizzes") or []
                         if q.get("id") == detail.get("questionId")), None)
            if quiz is None:
                # 旧版本事件按稳定 id 计入：id 不在当前版本则拒
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
            content_version=version.version, kind=kind,
            detail=JSONText.dump(detail), correct=correct, created_at=now(),
        ))
        accepted += 1
    db.commit()
    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}


def derive_progress(db: Session, *, user: UserRow) -> dict:
    """D-24：当前公开版本全部听辨题各至少答对一次 + 全部练习步骤各至少一次；
    下一关 = 公开顺序中第一个未完成的已发布关，全部完成回落第一已发布关。"""
    from app.content.usecases import published_levels

    levels = published_levels(db)
    events = db.query(LearningEventRow).filter(LearningEventRow.user_id == user.id).all()
    out = []
    completed_ids = []
    for lv in levels:
        version = db.get(LevelVersionRow, lv.current_version_id)
        content = JSONText.load(version.content, {})
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
