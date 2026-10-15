"""后台治理路由（单管理员、独立凭据；决策图「后台治理用例」）。

1.0 采用文档预案中的自建轻量后台（starlette-admin 自定义能力为 M0 待验证项，
风险预案为"治理动作改为后台内自建少量页面，仍调用同一用例"）；
全部动作只调用各模块用例并写审计，不直接改公开版本、不读私人录音。
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
    ArticleDraftRow, ArticleRow, CalibrationTextRow, CategoryRow, LevelDraftRow,
    LevelRow, LevelVersionRow, MediaAssetRow, MediaRefRow, ReferenceSpeakerRow,
)
from app.db import JSONText, now
from app.ids import new_id
from app.platform.audit import audit
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
    from app.platform.audit import deletion_log
    from app.identity.models import UserRow

    return envelope(request, {
        "levels": {
            "published": db.query(LevelRow).filter(LevelRow.status == "published").count(),
            "total": db.query(LevelRow).count(),
        },
        "articles": {
            "published": db.query(ArticleRow).filter(ArticleRow.status == "published").count(),
            "total": db.query(ArticleRow).count(),
        },
        "recordings": db.query(RecordingRow).count(),
        "users": db.query(UserRow).filter(UserRow.deleted_at.is_(None)).count(),
        "pendingFeedback": db.query(FeedbackRow).filter(FeedbackRow.status == "pending").count(),
        "pendingWishes": db.query(WishRow).filter(WishRow.status == "pending").count(),
        "executor": executor.stats(),
        "cleanupBacklog": len(deletion_log.read_pending()),
    })


# ---------------- 关卡治理 ----------------

@router.get("/levels")
async def admin_levels(request: Request, db: Session = Depends(db_session)):
    _admin(request, db)
    out = []
    for lv in db.query(LevelRow).order_by(LevelRow.order).all():
        draft = db.get(LevelDraftRow, lv.id)
        content = JSONText.load(draft.content, {}) if draft else {}
        version = db.get(LevelVersionRow, lv.current_version_id) if lv.current_version_id else None
        out.append({
            "id": lv.id, "order": lv.order, "layer": lv.layer, "status": lv.status,
            "skeletonPublic": lv.skeleton_public,
            "draftRevision": draft.revision if draft else None,
            "currentVersion": version.version if version else None,
            "title": content.get("title"), "targetSound": content.get("targetSound"),
        })
    return envelope(request, {"levels": out})


@router.get("/levels/{level_id}")
async def admin_level_detail(request: Request, level_id: str,
                             db: Session = Depends(db_session)):
    _admin(request, db)
    lv = db.get(LevelRow, level_id)
    draft = db.get(LevelDraftRow, level_id)
    if lv is None or draft is None:
        raise ApiError(404, "NOT_FOUND", "关卡不存在")
    versions = (db.query(LevelVersionRow).filter(LevelVersionRow.level_id == level_id)
                .order_by(LevelVersionRow.version.desc()).all())
    return envelope(request, {
        "level": {"id": lv.id, "order": lv.order, "layer": lv.layer,
                  "status": lv.status, "skeletonPublic": lv.skeleton_public,
                  "currentVersionId": lv.current_version_id},
        "draft": {"revision": draft.revision, "content": JSONText.load(draft.content, {}),
                  "updatedAt": draft.updated_at.isoformat()},
        "versions": [{"id": v.id, "version": v.version, "changeNote": v.change_note,
                      "publishedAt": v.published_at.isoformat()} for v in versions],
    })


class DraftBody(BaseModel):
    content: dict
    changeNote: str | None = None


@router.put("/levels/{level_id}/draft")
async def admin_save_level_draft(request: Request, level_id: str, body: DraftBody,
                                 db: Session = Depends(db_session)):
    actor = _admin(request, db)
    draft = db.get(LevelDraftRow, level_id)
    if draft is None:
        raise ApiError(404, "NOT_FOUND", "关卡草稿不存在")
    before_rev = draft.revision
    draft.content = JSONText.dump(body.content)
    draft.revision += 1
    draft.updated_at = now()
    draft.updated_by = actor
    audit.log(db, action="save_draft", object_type="level", object_id=level_id,
              actor_type="admin", actor_id=actor,
              before={"revision": before_rev}, after={"revision": draft.revision},
              reason=body.changeNote, request_id=request.state.request_id)
    db.commit()
    return envelope(request, {"levelId": level_id, "revision": draft.revision})


@router.post("/levels/{level_id}/precheck")
async def admin_precheck_level(request: Request, level_id: str,
                               db: Session = Depends(db_session)):
    _admin(request, db)
    draft = db.get(LevelDraftRow, level_id)
    if draft is None:
        raise ApiError(404, "NOT_FOUND", "关卡草稿不存在")
    missing = content_uc.precheck_level(db, JSONText.load(draft.content, {}))
    return envelope(request, {"levelId": level_id, "ok": not missing, "missing": missing})


class PublishBody(BaseModel):
    changeNote: str | None = None


@router.post("/levels/{level_id}/publish")
async def admin_publish_level(request: Request, level_id: str, body: PublishBody,
                              db: Session = Depends(db_session)):
    actor = _admin(request, db)
    result = content_uc.publish_level(db, level_id, admin_actor=actor,
                                      request_id=request.state.request_id,
                                      change_note=body.changeNote)
    return envelope(request, result)


class ReasonBody(BaseModel):
    reason: str


@router.post("/levels/{level_id}/unpublish")
async def admin_unpublish_level(request: Request, level_id: str, body: ReasonBody,
                                db: Session = Depends(db_session)):
    actor = _admin(request, db)
    result = content_uc.unpublish_level(db, level_id, admin_actor=actor,
                                        request_id=request.state.request_id,
                                        reason=body.reason)
    return envelope(request, result)


@router.post("/levels/{level_id}/rollback")
async def admin_rollback_level(request: Request, level_id: str,
                               db: Session = Depends(db_session)):
    actor = _admin(request, db)
    result = content_uc.rollback_level(db, level_id, admin_actor=actor,
                                       request_id=request.state.request_id)
    return envelope(request, result)


class SkeletonBody(BaseModel):
    skeletonPublic: bool


@router.put("/levels/{level_id}/skeleton")
async def admin_set_skeleton(request: Request, level_id: str, body: SkeletonBody,
                             db: Session = Depends(db_session)):
    actor = _admin(request, db)
    lv = db.get(LevelRow, level_id)
    if lv is None:
        raise ApiError(404, "NOT_FOUND", "关卡不存在")
    lv.skeleton_public = body.skeletonPublic
    lv.updated_at = now()
    audit.log(db, action="set_skeleton", object_type="level", object_id=level_id,
              actor_type="admin", actor_id=actor,
              after={"skeletonPublic": lv.skeleton_public},
              request_id=request.state.request_id)
    db.commit()
    return envelope(request, {"levelId": level_id, "skeletonPublic": lv.skeleton_public})


@router.get("/levels/{level_id}/diff")
async def admin_level_diff(request: Request, level_id: str,
                           db: Session = Depends(db_session)):
    """草稿与当前公开版本对比（字段级 diff）。"""
    _admin(request, db)
    draft = db.get(LevelDraftRow, level_id)
    lv = db.get(LevelRow, level_id)
    if draft is None or lv is None:
        raise ApiError(404, "NOT_FOUND", "关卡不存在")
    version = db.get(LevelVersionRow, lv.current_version_id) if lv.current_version_id else None
    published = JSONText.load(version.content, {}) if version else {}
    current = JSONText.load(draft.content, {})
    changes = []
    for key in sorted(set(published) | set(current)):
        a, b = published.get(key), current.get(key)
        if a != b:
            changes.append({"field": key, "published": a, "draft": b})
    return envelope(request, {"levelId": level_id, "changes": changes})


# ---------------- 文章与分类 ----------------

@router.get("/articles")
async def admin_articles(request: Request, db: Session = Depends(db_session)):
    _admin(request, db)
    out = []
    for a in db.query(ArticleRow).order_by(ArticleRow.slug).all():
        draft = db.get(ArticleDraftRow, a.slug)
        content = JSONText.load(draft.content, {}) if draft else {}
        out.append({"slug": a.slug, "status": a.status,
                    "draftRevision": draft.revision if draft else None,
                    "title": content.get("title"), "category": content.get("category")})
    return envelope(request, {"articles": out})


@router.get("/articles/{slug}")
async def admin_article_detail(request: Request, slug: str,
                               db: Session = Depends(db_session)):
    _admin(request, db)
    a = db.get(ArticleRow, slug)
    draft = db.get(ArticleDraftRow, slug)
    if a is None or draft is None:
        raise ApiError(404, "NOT_FOUND", "文章不存在")
    return envelope(request, {
        "article": {"slug": a.slug, "status": a.status},
        "draft": {"revision": draft.revision, "content": JSONText.load(draft.content, {})},
    })


class ArticleDraftBody(BaseModel):
    content: dict
    changeNote: str | None = None


@router.post("/articles")            # 新建草稿
async def admin_create_article(request: Request, body: ArticleDraftBody,
                               db: Session = Depends(db_session)):
    actor = _admin(request, db)
    slug = (body.content.get("slug") or "").strip()
    if not slug or db.get(ArticleRow, slug) is not None:
        raise ApiError(409, "INVALID_STATE", "slug 缺失或已存在")
    db.add(ArticleRow(slug=slug, status="draft", created_at=now(), updated_at=now()))
    db.add(ArticleDraftRow(article_slug=slug, revision=1,
                           content=JSONText.dump(body.content),
                           updated_at=now(), updated_by=actor))
    audit.log(db, action="create_article", object_type="article", object_id=slug,
              actor_type="admin", actor_id=actor, request_id=request.state.request_id)
    db.commit()
    return envelope(request, {"slug": slug})


@router.put("/articles/{slug}/draft")
async def admin_save_article_draft(request: Request, slug: str, body: ArticleDraftBody,
                                   db: Session = Depends(db_session)):
    actor = _admin(request, db)
    draft = db.get(ArticleDraftRow, slug)
    if draft is None:
        raise ApiError(404, "NOT_FOUND", "文章草稿不存在")
    draft.content = JSONText.dump(body.content)
    draft.revision += 1
    draft.updated_at = now()
    draft.updated_by = actor
    db.commit()
    return envelope(request, {"slug": slug, "revision": draft.revision})


@router.post("/articles/{slug}/publish")
async def admin_publish_article(request: Request, slug: str, body: PublishBody,
                                db: Session = Depends(db_session)):
    actor = _admin(request, db)
    result = content_uc.publish_article(db, slug, admin_actor=actor,
                                        request_id=request.state.request_id,
                                        change_note=body.changeNote)
    return envelope(request, result)


@router.post("/articles/{slug}/unpublish")
async def admin_unpublish_article(request: Request, slug: str, body: ReasonBody,
                                  db: Session = Depends(db_session)):
    actor = _admin(request, db)
    result = content_uc.unpublish_article(db, slug, admin_actor=actor,
                                          request_id=request.state.request_id,
                                          reason=body.reason)
    return envelope(request, result)


@router.post("/articles/{slug}/rollback")
async def admin_rollback_article(request: Request, slug: str,
                                 db: Session = Depends(db_session)):
    actor = _admin(request, db)
    result = content_uc.rollback_article(db, slug, admin_actor=actor,
                                         request_id=request.state.request_id)
    return envelope(request, result)


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
    actor = _admin(request, db)
    if db.query(CategoryRow).filter(CategoryRow.name == body.name).count():
        raise ApiError(409, "INVALID_STATE", "分类已存在")
    db.add(CategoryRow(name=body.name, sort=body.sort, created_at=now()))
    audit.log(db, action="create_category", object_type="category", object_id=body.name,
              actor_type="admin", actor_id=actor, request_id=request.state.request_id)
    db.commit()
    return envelope(request, {"created": True})


@router.put("/categories/{category_id}")
async def admin_rename_category(request: Request, category_id: int, body: CategoryBody,
                                db: Session = Depends(db_session)):
    """分类更名不穿透草稿立即公开：只改分类行，文章快照在重新发布时生效。"""
    actor = _admin(request, db)
    row = db.get(CategoryRow, category_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "分类不存在")
    old = row.name
    row.name = body.name
    row.sort = body.sort
    audit.log(db, action="rename_category", object_type="category", object_id=str(category_id),
              actor_type="admin", actor_id=actor, before={"name": old},
              after={"name": body.name}, request_id=request.state.request_id)
    db.commit()
    return envelope(request, {"id": row.id, "name": row.name})


@router.delete("/categories/{category_id}")
async def admin_delete_category(request: Request, category_id: int,
                                to_category: str,
                                db: Session = Depends(db_session)):
    """删除前迁移：仍有关联文章（草稿）的分类须先迁到其他分类。"""
    actor = _admin(request, db)
    row = db.get(CategoryRow, category_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "分类不存在")
    target = db.query(CategoryRow).filter(CategoryRow.name == to_category).one_or_none()
    if target is None:
        raise ApiError(422, "VALIDATION_ERROR", "目标分类不存在")
    moved = 0
    for draft in db.query(ArticleDraftRow).all():
        content = JSONText.load(draft.content, {})
        if content.get("category") == row.name:
            content["category"] = to_category
            draft.content = JSONText.dump(content)
            draft.revision += 1
            draft.updated_at = now()
            moved += 1
    audit.log(db, action="delete_category", object_type="category",
              object_id=str(category_id), actor_type="admin", actor_id=actor,
              after={"movedDrafts": moved}, request_id=request.state.request_id)
    db.delete(row)
    db.commit()
    return envelope(request, {"deleted": True, "movedDrafts": moved})


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
    out_dir = config.DATA_DIR / "media"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{media_id}.{ext}"
    path.write_bytes(raw)
    mime = file.content_type or "application/octet-stream"
    duration = None
    if mime.startswith("audio/"):
        from app.acoustics.transcode import probe_duration
        import shutil
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
        id=media_id, kind=kind, storage="draft", filename=file.filename or media_id,
        storage_path=str(path.relative_to(config.DATA_DIR)), mime=mime,
        size_bytes=len(raw), purpose=purpose, license_note=licenseNote or None,
        author=actor, sha256=hashlib.sha256(raw).hexdigest(),
        duration_sec=duration, text=text or None, uploaded_by=actor,
        created_at=now(),
    )
    db.add(asset)
    audit.log(db, action="upload_media", object_type="media", object_id=media_id,
              actor_type="admin", actor_id=actor,
              after={"kind": kind, "filename": asset.filename},
              request_id=request.state.request_id)
    db.commit()
    return envelope(request, {"mediaId": media_id, "kind": kind, "sizeBytes": len(raw)})


@router.get("/media")
async def admin_list_media(request: Request, db: Session = Depends(db_session)):
    _admin(request, db)
    out = []
    for m in db.query(MediaAssetRow).filter(MediaAssetRow.deleted_at.is_(None)) \
            .order_by(MediaAssetRow.created_at.desc()).limit(200).all():
        refs = db.query(MediaRefRow).filter(MediaRefRow.media_id == m.id).count()
        out.append({"id": m.id, "kind": m.kind, "filename": m.filename, "mime": m.mime,
                    "sizeBytes": m.size_bytes, "purpose": m.purpose,
                    "licenseNote": m.license_note, "text": m.text,
                    "createdAt": m.created_at.isoformat(), "refCount": refs})
    return envelope(request, {"media": out})


@router.delete("/media/{media_id}")
async def admin_delete_media(request: Request, media_id: str,
                             db: Session = Depends(db_session)):
    actor = _admin(request, db)
    asset = db.get(MediaAssetRow, media_id)
    if asset is None:
        raise ApiError(404, "NOT_FOUND", "媒体不存在")
    refs = db.query(MediaRefRow).filter(MediaRefRow.media_id == media_id).count()
    if refs:
        raise ApiError(409, "INVALID_STATE", f"媒体仍被 {refs} 个已发布版本引用，先下架相关内容")
    asset.deleted_at = now()
    from app.platform.audit import deletion_log

    deletion_log.append(kind="file", key=asset.storage_path)
    audit.log(db, action="delete_media", object_type="media", object_id=media_id,
              actor_type="admin", actor_id=actor, request_id=request.state.request_id)
    db.commit()
    return envelope(request, {"deleted": True})


# ---------------- 检测治理 ----------------

@router.get("/detection-switches")
async def admin_get_switches(request: Request, db: Session = Depends(db_session)):
    _admin(request, db)
    from app.content.models import DetectionSwitchRow

    rows = db.query(DetectionSwitchRow).all()
    return envelope(request, {"switches": [
        {"levelId": r.level_id, "enabled": r.enabled, "reason": r.reason,
         "updatedAt": r.updated_at.isoformat()} for r in rows]})


class SwitchBody(BaseModel):
    levelId: str | None = None
    enabled: bool
    reason: str


@router.post("/detection-switches")
async def admin_set_switch(request: Request, body: SwitchBody,
                           db: Session = Depends(db_session)):
    actor = _admin(request, db)
    if not body.reason:
        raise ApiError(422, "VALIDATION_ERROR", "熔断操作必须填写原因")
    result = content_uc.set_detection_switch(
        db, level_id=body.levelId, enabled=body.enabled, reason=body.reason,
        admin_actor=actor, request_id=request.state.request_id)
    return envelope(request, result)


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
    """标定文本配置：须覆盖六个单韵母（FR/CMS 首版范围）。"""
    actor = _admin(request, db)
    from app.scoring.usecases import _main_vowel, _expected_syllables

    found = set()
    for syl in body.syllables:
        exp = _expected_syllables(syl)
        if exp:
            v = _main_vowel(exp[0].get("plain", ""))
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
    audit.log(db, action="set_calibration_text", object_type="config", object_id="calibration_text",
              actor_type="admin", actor_id=actor, after={"textVersion": body.textVersion},
              request_id=request.state.request_id)
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
    actor = _admin(request, db)
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
    audit.log(db, action="register_reference_speaker", object_type="reference_speaker",
              object_id=row.id, actor_type="admin", actor_id=actor,
              after={"fLo": row.f_lo, "fHi": row.f_hi},
              request_id=request.state.request_id)
    db.commit()
    return envelope(request, {"registered": True, "speakerId": row.id,
                              "pitchRange": {"fLo": row.f_lo, "fHi": row.f_hi}})


# ---------------- 反馈 / 希望增加 / 审计 ----------------

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
         "recordingId": None,   # 处理视图不见私人录音引用正文
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
    _admin(request, db)
    from app.feedback.models import WishRow

    row = db.get(WishRow, wish_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "希望增加记录不存在")
    if body.status not in ("adopted", "rejected"):
        raise ApiError(422, "VALIDATION_ERROR", "状态只允许 adopted / rejected")
    row.status = body.status
    row.handled_by = _admin(request, db)
    row.handled_at = now()
    db.commit()
    return envelope(request, {"wishId": row.id, "status": row.status})


@router.get("/audit")
async def admin_audit(request: Request, object_type: str = "", action: str = "",
                      request_id: str = "", limit: int = 100,
                      db: Session = Depends(db_session)):
    _admin(request, db)
    from app.platform.models import AuditLogRow

    q = db.query(AuditLogRow)
    if object_type:
        q = q.filter(AuditLogRow.object_type == object_type)
    if action:
        q = q.filter(AuditLogRow.action == action)
    if request_id:
        q = q.filter(AuditLogRow.request_id == request_id)
    rows = q.order_by(AuditLogRow.id.desc()).limit(min(limit, 500)).all()
    return envelope(request, {"entries": [
        {"id": r.id, "requestId": r.request_id, "actorType": r.actor_type,
         "action": r.action, "objectType": r.object_type, "objectId": r.object_id,
         "reason": r.reason, "createdAt": r.created_at.isoformat()} for r in rows]})
