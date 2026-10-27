"""content 媒体用例：后台媒体登记（写盘 + 时长探测 + 资产登记）与软删
（内容引用校验 + 删除日志）；文件物理清理由调度任务按删除日志执行。"""
from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app import config
from app.content.models import ArticleRow, LevelRow, MediaAssetRow
from app.db import now
from app.ids import new_id
from app.platform.deletion_log import deletion_log
from app.platform.envelope import ApiError


def register_media_asset(db: Session, *, kind: str, filename: str | None,
                         mime: str | None, raw: bytes, purpose: str,
                         license_note: str, text: str,
                         uploaded_by: str) -> dict:
    """保存上传媒体到 MEDIA_DIR 并登记资产行；音频直接对已保存文件探测
    时长（非 WAV 或探测失败记 None，不阻断登记）。"""
    if not raw:
        raise ApiError(422, "VALIDATION_ERROR", "空文件")
    media_id = new_id("md_")
    ext = (filename or "bin").rsplit(".", 1)[-1].lower()[:8]
    out_dir = config.MEDIA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{media_id}.{ext}"
    path.write_bytes(raw)
    mime = mime or "application/octet-stream"
    duration = None
    if mime.startswith("audio/"):
        from app.acoustics.transcode import probe_duration

        duration = probe_duration(path) or None
    asset = MediaAssetRow(
        id=media_id, kind=kind, filename=filename or media_id,
        storage_path=str(path.relative_to(config.DATA_DIR)), mime=mime,
        size_bytes=len(raw), purpose=purpose, license_note=license_note or None,
        author=uploaded_by, sha256=hashlib.sha256(raw).hexdigest(),
        duration_sec=duration, text=text or None, uploaded_by=uploaded_by,
        created_at=now(),
    )
    db.add(asset)
    db.commit()
    return {"mediaId": media_id, "kind": kind, "sizeBytes": len(raw)}


def delete_media_asset(db: Session, media_id: str) -> dict:
    asset = db.get(MediaAssetRow, media_id)
    if asset is None:
        raise ApiError(404, "NOT_FOUND", "媒体不存在")
    # 仍被关卡或文章内容引用的媒体不可删
    referenced_ids: set[str] = set()
    for lv in db.query(LevelRow).all():
        if media_id in (lv.content or ""):
            referenced_ids.add(lv.id)
    for a in db.query(ArticleRow).all():
        if media_id in (a.content or ""):
            referenced_ids.add(a.slug)
    if referenced_ids:
        raise ApiError(409, "INVALID_STATE",
                       f"媒体仍被内容引用（{', '.join(sorted(referenced_ids))}），请先解除引用")
    asset.deleted_at = now()
    deletion_log.append(kind="file", key=asset.storage_path)
    db.commit()
    return {"deleted": True}
