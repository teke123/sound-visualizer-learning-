"""archive 用例：档案查询、进度只读派生、录音删除。注销清理在 identity.delete_account，
由外键级联一次完成。"""
from __future__ import annotations

import base64
import datetime

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.acoustics.models import AudioRow
from app.acoustics.usecases import mark_deleted as mark_audio_deleted
from app.db import JSONText, now
from app.detection.models import RecordingRow
from app.platform.envelope import ApiError
from app.identity.models import UserRow


# ---------------- 档案 ----------------

def recording_summary(rec: RecordingRow) -> dict:
    payload = JSONText.load(rec.result_payload, {}) if rec.result_payload else {}
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
    items = [recording_summary(rec) for rec in rows]
    next_cursor = _page_cursor(rows[-1]) if has_more and rows else None
    return {"recordings": items, "nextCursor": next_cursor}


# ---------------- 删除 ----------------

def delete_recording(db: Session, rec: RecordingRow) -> None:
    """单删：立即逻辑失效；独占 audio 同时失效（音频文件异步物理删除）。
    重复删除幂等。"""
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


# ---------------- 进度派生 ----------------

def derive_progress(db: Session, *, user: UserRow) -> dict:
    """关卡完成 = 本关至少有一条未删除的检测录音；
    下一关 = 顺序中第一个未完成的已开放关，全部完成回落第一已开放关。"""
    from app.content.usecases import open_levels

    levels = open_levels(db)
    recorded_level_ids = {
        rec.level_id for rec in db.query(RecordingRow).filter(
            RecordingRow.user_id == user.id,
            RecordingRow.deleted_at.is_(None),
        ).all()
    }
    out = [{"levelId": lv.id, "completed": lv.id in recorded_level_ids} for lv in levels]
    next_level_id = next((item["levelId"] for item in out if not item["completed"]), None)
    if next_level_id is None and levels:
        next_level_id = levels[0].id
    return {"levels": out, "nextLevelId": next_level_id}
