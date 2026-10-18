"""团队自用维护后台路由（简单口令登录；D-09 / FR-1401–1409）。

后台修改保存即生效，前端直接读最新数据；关卡只有「已开放 / 未开放」
一个开关。全部动作只调用各模块用例，不读用户私人录音。
"""
from __future__ import annotations

import asyncio
import hashlib

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import config
from app.api.deps import admin_session_cookie, db_session
from app.content import usecases as content_uc
from app.content.models import (
    ArticleRow, CalibrationTextRow, CategoryRow, LevelRow, MediaAssetRow,
    ReferenceSpeakerRow,
)
from app.db import JSONText, now
from app.ids import new_id
from app.platform.deletion_log import deletion_log
from app.platform.envelope import ApiError, envelope
from app.platform.rate_limit import client_ip, limiter
from app.platform.security import ADMIN_COOKIE, require_admin, revoke_admin_session

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _admin(request: Request, db: Session) -> str:
    return require_admin(db, admin_session_cookie(request))


# ---------------- 认证 ----------------

class AdminLoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
async def admin_login(request: Request, body: AdminLoginBody,
                      db: Session = Depends(db_session)):
    limiter.check("login", f"admin:{client_ip(request)}")
    if body.username != config.ADMIN_USERNAME or body.password != config.ADMIN_PASSWORD:
        raise ApiError(401, "INVALID_CREDENTIALS", "管理员用户名或密码不正确")
    session_id = new_id(24)
    from app.security_models import AdminSessionRow

    import datetime as _dt

    db.add(AdminSessionRow(session_id=session_id, expires_at=now() + _dt.timedelta(hours=8),
                           created_at=now()))
    db.commit()
    resp = envelope(request, {"loggedIn": True})
    resp.set_cookie(ADMIN_COOKIE, session_id, max_age=8 * 3600, httponly=True,
                    samesite="lax", secure=config.ENV == "prod")
    return resp


@router.post("/logout")
async def admin_logout(request: Request, db: Session = Depends(db_session)):
    revoke_admin_session(db, admin_session_cookie(request))
    resp = envelope(request, {"loggedOut": True})
    resp.delete_cookie(ADMIN_COOKIE)
    return resp


@router.get("/overview")
async def admin_overview(request: Request, db: Session = Depends(db_session)):
    _admin(request, db)
    from app.detection.models import RecordingRow
    from app.feedback.models import FeedbackRow, WishRow
    from app.platform.executor import executor
    from app.identity.models import UserRow

    return envelope(request, {
        "levels": {
            "published": db.query(LevelRow).filter(LevelRow.published.is_(True)).count(),
            "total": db.query(LevelRow).count(),
        },
        "articles": {
            "published": db.query(ArticleRow).filter(ArticleRow.published.is_(True)).count(),
            "total": db.query(ArticleRow).count(),
        },
        "recordings": db.query(RecordingRow).count(),
        "users": db.query(UserRow).filter(UserRow.deleted_at.is_(None)).count(),
        "pendingFeedback": db.query(FeedbackRow).filter(FeedbackRow.status == "pending").count(),
        "pendingWishes": db.query(WishRow).filter(WishRow.status == "pending").count(),
        "executor": executor.stats(),
        "cleanupBacklog": len(deletion_log.read_pending()),
    })


# ---------------- 关卡维护 ----------------

@router.get("/levels")
async def admin_levels(request: Request, db: Session = Depends(db_session)):
    _admin(request, db)
    out = []
    for lv in db.query(LevelRow).order_by(LevelRow.order).all():
        content = JSONText.load(lv.content, {})
        out.append({
            "id": lv.id, "order": lv.order, "layer": lv.layer,
            "published": lv.published, "skeletonPublic": lv.skeleton_public,
            "title": content.get("title"), "targetSound": content.get("targetSound"),
            "updatedAt": lv.updated_at.isoformat(),
        })
    return envelope(request, {"levels": out})


@router.get("/levels/{level_id}")
async def admin_level_detail(request: Request, level_id: str,
                             db: Session = Depends(db_session)):
    _admin(request, db)
    lv = db.get(LevelRow, level_id)
    if lv is None:
        raise ApiError(404, "NOT_FOUND", "关卡不存在")
    return envelope(request, {
        "level": {"id": lv.id, "order": lv.order, "layer": lv.layer,
                  "published": lv.published, "skeletonPublic": lv.skeleton_public},
        "content": JSONText.load(lv.content, {}),
    })


class LevelContentBody(BaseModel):
    content: dict


@router.put("/levels/{level_id}")
async def admin_save_level(request: Request, level_id: str, body: LevelContentBody,
                           db: Session = Depends(db_session)):
    _admin(request, db)
    return envelope(request, content_uc.save_level(db, level_id, body.content))


@router.post("/levels/{level_id}/precheck")
async def admin_precheck_level(request: Request, level_id: str,
                               db: Session = Depends(db_session)):
    _admin(request, db)
    lv = db.get(LevelRow, level_id)
    if lv is None:
        raise ApiError(404, "NOT_FOUND", "关卡不存在")
    missing = content_uc.precheck_level(db, JSONText.load(lv.content, {}))
    return envelope(request, {"levelId": level_id, "ok": not missing, "missing": missing})


class PublishedBody(BaseModel):
    published: bool


@router.put("/levels/{level_id}/published")
async def admin_set_level_published(request: Request, level_id: str, body: PublishedBody,
                                    db: Session = Depends(db_session)):
    _admin(request, db)
    return envelope(request, content_uc.set_level_published(db, level_id, body.published))


# ---------------- 文章与分类 ----------------

@router.get("/articles")
async def admin_articles(request: Request, db: Session = Depends(db_session)):
    _admin(request, db)
    out = []
    for a in db.query(ArticleRow).order_by(ArticleRow.slug).all():
        content = JSONText.load(a.content, {})
        out.append({"slug": a.slug, "published": a.published,
                    "title": content.get("title"), "category": content.get("category")})
    return envelope(request, {"articles": out})


@router.get("/articles/{slug}")
async def admin_article_detail(request: Request, slug: str,
                               db: Session = Depends(db_session)):
    _admin(request, db)
    a = db.get(ArticleRow, slug)
    if a is None:
        raise ApiError(404, "NOT_FOUND", "文章不存在")
    return envelope(request, {
        "article": {"slug": a.slug, "published": a.published},
        "content": JSONText.load(a.content, {}),
    })


class ArticleContentBody(BaseModel):
    content: dict


@router.post("/articles")
async def admin_create_article(request: Request, body: ArticleContentBody,
                               db: Session = Depends(db_session)):
    _admin(request, db)
    return envelope(request, content_uc.save_article(
        db, body.content.get("slug"), body.content, create=True))


@router.put("/articles/{slug}")
async def admin_save_article(request: Request, slug: str, body: ArticleContentBody,
                             db: Session = Depends(db_session)):
    _admin(request, db)
    return envelope(request, content_uc.save_article(db, slug, body.content))


@router.put("/articles/{slug}/published")
async def admin_set_article_published(request: Request, slug: str, body: PublishedBody,
                                      db: Session = Depends(db_session)):
    _admin(request, db)
    return envelope(request, content_uc.set_article_published(db, slug, body.published))


@router.delete("/articles/{slug}")
async def admin_delete_article(request: Request, slug: str,
                               db: Session = Depends(db_session)):
    _admin(request, db)
    return envelope(request, content_uc.delete_article(db, slug))


@router.get("/categories")
async def admin_categories(request: Request, db: Session = Depends(db_session)):
    _admin(request, db)
    return envelope(request, {"categories": content_uc.article_categories(db)})


class CategoryBody(BaseModel):
    name: str
    sort: int = 0


@router.post("/categories")
async def admin_create_category(request: Request, body: CategoryBody,
                                db: Session = Depends(db_session)):
    _admin(request, db)
    if db.query(CategoryRow).filter(CategoryRow.name == body.name).count():
        raise ApiError(409, "INVALID_STATE", "分类已存在")
    db.add(CategoryRow(name=body.name, sort=body.sort, created_at=now()))
    db.commit()
    return envelope(request, {"created": True})


@router.put("/categories/{category_id}")
async def admin_rename_category(request: Request, category_id: int, body: CategoryBody,
                                db: Session = Depends(db_session)):
    _admin(request, db)
    row = db.get(CategoryRow, category_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "分类不存在")
    row.name = body.name
    row.sort = body.sort
    db.commit()
    return envelope(request, {"id": row.id, "name": row.name})


@router.delete("/categories/{category_id}")
async def admin_delete_category(request: Request, category_id: int,
                                db: Session = Depends(db_session)):
    _admin(request, db)
    row = db.get(CategoryRow, category_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "分类不存在")
    used = sum(
        1 for a in db.query(ArticleRow).all()
        if (JSONText.load(a.content, {}) or {}).get("category") == row.name)
    if used:
        raise ApiError(409, "INVALID_STATE", f"仍有 {used} 篇文章使用该分类，请先改分类")
    db.delete(row)
    db.commit()
    return envelope(request, {"deleted": True})


# ---------------- 媒体 ----------------

@router.post("/media")
async def admin_upload_media(request: Request, kind: str = Form(...),
                             purpose: str = Form("content"),
                             licenseNote: str = Form(""), text: str = Form(""),
                             file: UploadFile = File(...),
                             db: Session = Depends(db_session)):
    actor = _admin(request, db)
    raw = await file.read()
    if not raw:
        raise ApiError(422, "VALIDATION_ERROR", "空文件")
    media_id = new_id("md_")
    ext = (file.filename or "bin").rsplit(".", 1)[-1].lower()[:8]
    out_dir = config.MEDIA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{media_id}.{ext}"
    path.write_bytes(raw)
    mime = file.content_type or "application/octet-stream"
    duration = None
    if mime.startswith("audio/"):
        from app.acoustics.transcode import probe_duration
        import tempfile
        import contextlib
        import os as _os

        fd, tmp = tempfile.mkstemp(suffix=".bin")
        _os.close(fd)
        with open(tmp, "wb") as f:
            f.write(raw)
        try:
            duration = probe_duration(__import__("pathlib").Path(tmp)) or None
        finally:
            with contextlib.suppress(OSError):
                _os.unlink(tmp)
    asset = MediaAssetRow(
        id=media_id, kind=kind, filename=file.filename or media_id,
        storage_path=str(path.relative_to(config.DATA_DIR)), mime=mime,
        size_bytes=len(raw), purpose=purpose, license_note=licenseNote or None,
        author=actor, sha256=hashlib.sha256(raw).hexdigest(),
        duration_sec=duration, text=text or None, uploaded_by=actor,
        created_at=now(),
    )
    db.add(asset)
    db.commit()
    return envelope(request, {"mediaId": media_id, "kind": kind, "sizeBytes": len(raw)})


@router.get("/media")
async def admin_list_media(request: Request, db: Session = Depends(db_session)):
    _admin(request, db)
    out = []
    for m in db.query(MediaAssetRow).filter(MediaAssetRow.deleted_at.is_(None)) \
            .order_by(MediaAssetRow.created_at.desc()).limit(200).all():
        out.append({"id": m.id, "kind": m.kind, "filename": m.filename, "mime": m.mime,
                    "sizeBytes": m.size_bytes, "purpose": m.purpose,
                    "licenseNote": m.license_note, "text": m.text,
                    "createdAt": m.created_at.isoformat()})
    return envelope(request, {"media": out})


@router.delete("/media/{media_id}")
async def admin_delete_media(request: Request, media_id: str,
                             db: Session = Depends(db_session)):
    _admin(request, db)
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
    return envelope(request, {"deleted": True})


# ---------------- 标定文本与参考发音人 ----------------

@router.get("/calibration-text")
async def admin_get_calibration(request: Request, db: Session = Depends(db_session)):
    _admin(request, db)
    row = content_uc.get_active_calibration_text(db)
    return envelope(request, {
        "text": row.text if row else None,
        "textVersion": row.text_version if row else None,
        "syllables": JSONText.load(row.syllables) if row else [],
    })


class CalibrationTextBody(BaseModel):
    textVersion: str
    text: str
    syllables: list[str]


@router.put("/calibration-text")
async def admin_set_calibration(request: Request, body: CalibrationTextBody,
                                db: Session = Depends(db_session)):
    """标定文本配置：须覆盖六个单韵母（FR-1403）。"""
    _admin(request, db)
    from app.pinyin_utils import expected_syllables, main_vowel

    found = set()
    for syl in body.syllables:
        exp = expected_syllables(syl)
        if exp:
            v = main_vowel(exp[0].get("plain", ""))
            if v:
                found.add(v)
    missing = {"a", "o", "e", "i", "u", "ü"} - found
    if missing:
        raise ApiError(422, "VALIDATION_ERROR",
                       "标定文本须覆盖六个单韵母（缺 " + "、".join(sorted(missing)) + "）")
    for row in db.query(CalibrationTextRow).all():
        row.active = False
    db.add(CalibrationTextRow(text_version=body.textVersion, text=body.text,
                              syllables=JSONText.dump(body.syllables), active=True,
                              updated_at=now()))
    db.commit()
    return envelope(request, {"textVersion": body.textVersion})


@router.get("/reference-speakers")
async def admin_list_speakers(request: Request, db: Session = Depends(db_session)):
    _admin(request, db)
    rows = db.query(ReferenceSpeakerRow).all()
    return envelope(request, {"speakers": [
        {"id": r.id, "name": r.name, "gender": r.gender,
         "fLo": r.f_lo, "fHi": r.f_hi,
         "vowelSpace": JSONText.load(r.vowel_space),
         "registeredAt": r.registered_at.isoformat()} for r in rows]})


class SpeakerBody(BaseModel):
    name: str
    gender: str
    mediaId: str


@router.post("/reference-speakers")
async def admin_register_speaker(request: Request, body: SpeakerBody,
                                 db: Session = Depends(db_session)):
    """参考发音人登记：上传其朗读标定文本的音频 → 同一标定计算 → 登记音域。"""
    _admin(request, db)
    asset = db.get(MediaAssetRow, body.mediaId)
    if asset is None or not (config.DATA_DIR / asset.storage_path).exists():
        raise ApiError(404, "NOT_FOUND", "参考音频不存在")
    text_row = content_uc.get_active_calibration_text(db)
    if text_row is None:
        raise ApiError(422, "VALIDATION_ERROR", "请先配置标定文本")
    from app.scoring.usecases import calibrate_path
    from app import config as cfg

    path = cfg.DATA_DIR / asset.storage_path
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, lambda: calibrate_path(path, JSONText.load(text_row.syllables)))
    if not result.get("ok"):
        return envelope(request, {"registered": False, "reason": result["reason"]},
                        code="CALIBRATION_FAIL", message=result["reason"])
    row = ReferenceSpeakerRow(
        id=new_id("spk_"), name=body.name, gender=body.gender,
        f_lo=result["fLo"], f_hi=result["fHi"],
        vowel_space=JSONText.dump(result["vowelSpace"]),
        algorithm_version=cfg.ALGORITHM_VERSION,
        registered_at=now(),
    )
    db.add(row)
    db.commit()
    return envelope(request, {"registered": True, "speakerId": row.id,
                              "pitchRange": {"fLo": row.f_lo, "fHi": row.f_hi}})


# ---------------- 反馈 / 希望增加 ----------------

@router.get("/feedback")
async def admin_feedback(request: Request, status: str = "",
                         db: Session = Depends(db_session)):
    _admin(request, db)
    from app.feedback.models import FeedbackRow

    q = db.query(FeedbackRow)
    if status:
        q = q.filter(FeedbackRow.status == status)
    rows = q.order_by(FeedbackRow.created_at.desc()).limit(200).all()
    return envelope(request, {"feedback": [
        {"id": r.id, "sourcePage": r.source_page, "type": r.type, "subtype": r.subtype,
         "content": r.content, "levelId": r.level_id, "articleSlug": r.article_slug,
         "rating": r.rating, "status": r.status,
         "createdAt": r.created_at.isoformat()} for r in rows]})


class HandleBody(BaseModel):
    status: str


@router.put("/feedback/{feedback_id}")
async def admin_handle_feedback(request: Request, feedback_id: str, body: HandleBody,
                                db: Session = Depends(db_session)):
    actor = _admin(request, db)
    from app.feedback import usecases as feedback_uc

    result = feedback_uc.handle_feedback(db, feedback_id=feedback_id,
                                         status=body.status, admin_actor=actor)
    return envelope(request, result)


@router.get("/wishes")
async def admin_wishes(request: Request, db: Session = Depends(db_session)):
    _admin(request, db)
    from app.feedback.models import WishRow

    rows = db.query(WishRow).order_by(WishRow.created_at.desc()).limit(200).all()
    return envelope(request, {"wishes": [
        {"id": r.id, "content": r.content, "searchQuery": r.search_query,
         "status": r.status, "createdAt": r.created_at.isoformat()} for r in rows]})


@router.put("/wishes/{wish_id}")
async def admin_handle_wish(request: Request, wish_id: str, body: HandleBody,
                            db: Session = Depends(db_session)):
    actor = _admin(request, db)
    from app.feedback.models import WishRow

    row = db.get(WishRow, wish_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "希望增加记录不存在")
    if body.status not in ("adopted", "rejected"):
        raise ApiError(422, "VALIDATION_ERROR", "状态只允许 adopted / rejected")
    row.status = body.status
    row.handled_by = actor
    row.handled_at = now()
    db.commit()
    return envelope(request, {"wishId": row.id, "status": row.status})
