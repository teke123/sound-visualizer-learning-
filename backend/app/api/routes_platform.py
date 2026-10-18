"""平台与内容公开路由：health、me/context、levels、search、articles、media。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app import config
from app.api.deps import Actor, db_session, get_actor
from app.api.files import serve_file
from app.archive import usecases as archive_uc
from app.content import usecases as content_uc
from app.api.schemas import (ArticleCategoriesResponse, ArticleDetail, ArticlesResponse,
                             Envelope, HealthData, LevelsResponse, LevelDetail, MeContext,
                             SearchResponse)
from app.platform.envelope import envelope
from app.scoring import usecases as scoring_uc

router = APIRouter(prefix="/api", tags=["platform-content"])


@router.get("/health", response_model=HealthData)
async def health():
    # 唯一不走 envelope 的端点：健康检查直返裸形状，response_model 按真实行为标注
    return {"status": "ok", "service": "svs-backend", "env": config.ENV}


@router.get("/me/context", response_model=Envelope[MeContext])
async def me_context(request: Request, actor: Actor = Depends(get_actor)):
    db = actor.db
    data: dict = {"authenticated": actor.user is not None}
    if actor.user is not None:
        data["accountId"] = actor.user.id
        data["username"] = actor.user.username
        if actor.user.dialect_background:
            data["dialectBackground"] = actor.user.dialect_background
    effective = (scoring_uc.get_personal_range(db, user_id=actor.user.id)
                 if actor.user is not None else None)
    if effective is None:
        data["calibration"] = {"status": "none"}
    else:
        data["calibration"] = {"status": effective["status"]}
    # nextLevelId：登录按服务端 D-24 派生；未登录第一已开放关
    levels = content_uc.open_levels(db)
    if actor.user is not None:
        progress = archive_uc.derive_progress(db, user=actor.user)
        data["nextLevelId"] = progress["nextLevelId"]
    else:
        data["nextLevelId"] = levels[0].id if levels else None
    return envelope(request, data)


@router.get("/levels", response_model=Envelope[LevelsResponse])
async def levels(request: Request, db: Session = Depends(db_session)):
    return envelope(request, content_uc.levels_response(db))


@router.get("/levels/{level_id}", response_model=Envelope[LevelDetail])
async def level_detail(request: Request, level_id: str,
                       db: Session = Depends(db_session)):
    return envelope(request, content_uc.level_detail(db, level_id))


@router.get("/search", response_model=Envelope[SearchResponse])
async def search(request: Request, q: str = "", db: Session = Depends(db_session)):
    return envelope(request, content_uc.search_levels(db, q))


@router.get("/article-categories", response_model=Envelope[ArticleCategoriesResponse])
async def article_categories(request: Request, db: Session = Depends(db_session)):
    return envelope(request, {"categories": content_uc.article_categories(db)})


@router.get("/articles", response_model=Envelope[ArticlesResponse])
async def articles(request: Request, category: str | None = None,
                   db: Session = Depends(db_session)):
    return envelope(request, content_uc.articles_list(db, category))


@router.get("/articles/{slug}", response_model=Envelope[ArticleDetail])
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
