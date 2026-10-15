"""平台与内容公开路由：health、me/context、levels、search、articles、media。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app import config
from app.api.deps import Actor, db_session, get_actor
from app.api.files import serve_file
from app.archive import usecases as archive_uc
from app.content import usecases as content_uc
from app.identity import usecases as identity_uc
from app.platform.envelope import envelope
from app.scoring import usecases as scoring_uc

router = APIRouter(prefix="/api", tags=["platform-content"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "svs-backend", "env": config.ENV}


@router.get("/me/context")
async def me_context(request: Request, actor: Actor = Depends(get_actor)):
    db = actor.db
    data: dict = {"authenticated": actor.user is not None}
    consent_status = "none"
    if actor.user is not None:
        data["accountId"] = actor.user.id
        data["username"] = actor.user.username
        data["dataEpoch"] = actor.user.data_epoch
        consent_status = identity_uc.consent_status(db, actor.user)
        if consent_status != "granted":
            session = archive_uc.session_recordings(
                db, owner_type="user", owner_id=actor.user.id)
            data["pendingTransfer"] = session["transferableCount"]
    data["consent"] = {"status": consent_status,
                       "consentTextVersion": config.CONSENT_TEXT_VERSION
                       if consent_status == "granted" else None}
    data["currentConsentTextVersion"] = config.CONSENT_TEXT_VERSION
    effective = scoring_uc.get_effective_range(db, owner_type=actor.owner_type,
                                               owner_id=actor.owner_id)
    if effective is None:
        data["calibration"] = {"status": "none"}
    else:
        data["calibration"] = {
            "status": effective["status"],
            "expiresAt": effective.get("expiresAt"),
        }
    # nextLevelId：登录且同意按服务端 D-24 派生；否则第一已发布关
    levels = content_uc.published_levels(db)
    if actor.user is not None and consent_status == "granted":
        progress = archive_uc.derive_progress(db, user=actor.user)
        data["nextLevelId"] = progress["nextLevelId"]
    else:
        data["nextLevelId"] = levels[0].id if levels else None
    return envelope(request, data)


@router.get("/levels")
async def levels(request: Request, db: Session = Depends(db_session)):
    return envelope(request, content_uc.levels_response(db))


@router.get("/levels/{level_id}")
async def level_detail(request: Request, level_id: str,
                       db: Session = Depends(db_session)):
    return envelope(request, content_uc.level_detail(db, level_id))


@router.get("/search")
async def search(request: Request, q: str = "", db: Session = Depends(db_session)):
    return envelope(request, content_uc.search_levels(db, q))


@router.get("/article-categories")
async def article_categories(request: Request, db: Session = Depends(db_session)):
    return envelope(request, {"categories": content_uc.article_categories(db)})


@router.get("/articles")
async def articles(request: Request, category: str | None = None,
                   db: Session = Depends(db_session)):
    return envelope(request, content_uc.articles_list(db, category))


@router.get("/articles/{slug}")
async def article_detail(request: Request, slug: str,
                         db: Session = Depends(db_session)):
    return envelope(request, content_uc.article_detail(db, slug))


@router.get("/media/{media_id}")
async def media_file(request: Request, media_id: str,
                     db: Session = Depends(db_session)):
    asset = content_uc.media_publicly_readable(db, media_id)
    if asset is None:
        return serve_file(request, config.DATA_DIR / "_missing", "application/octet-stream",
                          cache_control="no-store")
    return serve_file(request, config.DATA_DIR / asset.storage_path, asset.mime,
                      cache_control="no-cache")
