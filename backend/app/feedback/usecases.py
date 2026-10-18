"""feedback 用例：登录用户提交（限流在路由层）、本人引用校验、后台处理。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import now
from app.ids import new_id
from app.platform.envelope import ApiError
from app.feedback.models import FeedbackRow, WishRow

VALID_TYPES = {"clarity", "result_match", "content_error", "wish_more"}
VALID_SUBTYPES = {"text", "audio", "image", "subtitle"}


def submit_feedback(db: Session, *, user_id: str, body: dict) -> dict:
    source_page = body.get("sourcePage") or ""
    ftype = body.get("type") or ""
    if ftype not in VALID_TYPES:
        raise ApiError(422, "VALIDATION_ERROR", "反馈类型不合法")
    if not (body.get("content") or body.get("rating") is not None):
        raise ApiError(422, "VALIDATION_ERROR", "请填写反馈内容或感受评分")
    subtype = body.get("subtype")
    if subtype is not None and subtype not in VALID_SUBTYPES:
        raise ApiError(422, "VALIDATION_ERROR", "纠错子类型不合法")

    recording_id = body.get("recordingId")
    if recording_id:
        from app.detection.models import RecordingRow

        rec = db.get(RecordingRow, recording_id)
        if rec is None or rec.deleted_at is not None or rec.user_id != user_id:
            raise ApiError(404, "NOT_FOUND", "关联的录音不存在")

    level_id = body.get("levelId")
    if level_id:
        from app.content.models import LevelRow

        if db.get(LevelRow, level_id) is None:
            raise ApiError(404, "NOT_FOUND", "关联的关卡不存在")

    row = FeedbackRow(
        id=new_id("fb_"), user_id=user_id,
        source_page=source_page[:32], type=ftype, subtype=subtype,
        content=(body.get("content") or "")[:2000],
        article_slug=body.get("articleSlug"), level_id=level_id,
        recording_id=recording_id,
        rating=body.get("rating") if isinstance(body.get("rating"), int) else None,
        status="pending", created_at=now(),
    )
    db.add(row)
    db.commit()
    return {"feedbackId": row.id}


def submit_wish(db: Session, *, user_id: str, body: dict) -> dict:
    content = (body.get("content") or "").strip()
    if not content:
        raise ApiError(422, "VALIDATION_ERROR", "请写清希望增加的音或字")
    row = WishRow(
        id=new_id("w_"), user_id=user_id,
        content=content[:200], search_query=(body.get("searchQuery") or "")[:255],
        status="pending", created_at=now(),
    )
    db.add(row)
    db.commit()
    return {"wishId": row.id}


def handle_feedback(db: Session, *, feedback_id: str, status: str,
                    admin_actor: str) -> dict:
    row = db.get(FeedbackRow, feedback_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "反馈不存在")
    if status not in ("adopted", "rejected"):
        raise ApiError(422, "VALIDATION_ERROR", "处理状态只允许 adopted / rejected")
    if row.status != "pending":
        raise ApiError(409, "INVALID_STATE", "该反馈已处理")
    row.status = status
    row.handled_by = admin_actor
    row.handled_at = now()
    db.commit()
    return {"feedbackId": row.id, "status": row.status}
