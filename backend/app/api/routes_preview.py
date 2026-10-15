"""预览路由：令牌签发（管理员）与草稿预览（关卡/文章/媒体，no-store）。

令牌以 query 传递（决策图 #21），同时要求管理员会话 Cookie；
草稿修订号变化或管理员退出即失效。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import config
from app.api.deps import admin_session_cookie, db_session
from app.api.files import serve_file
from app.content import usecases as content_uc
from app.db import JSONText
from app.content.models import ArticleDraftRow, LevelDraftRow
from app.platform.envelope import ApiError, envelope
from app.platform.security import (
    issue_preview_token, require_admin, verify_preview_token,
)

from app.api.schemas import ArticleDetail, Envelope, LevelDetail, PreviewTokenResponse

router = APIRouter(prefix="/api/preview", tags=["preview"])


class TokenBody(BaseModel):
    kind: str          # level | article
    id: str


@router.post("/tokens", response_model=Envelope[PreviewTokenResponse])
async def create_token(request: Request, body: TokenBody,
                       db: Session = Depends(db_session)):
    admin_sid = require_admin(db, admin_session_cookie(request))
    if body.kind not in ("level", "article"):
        raise ApiError(422, "VALIDATION_ERROR", "kind 只允许 level / article")
    if body.kind == "level":
        draft = db.get(LevelDraftRow, body.id)
        revision, object_id = (draft.revision, draft.level_id) if draft else (None, body.id)
    else:
        draft = db.get(ArticleDraftRow, body.id)
        revision, object_id = (draft.revision, draft.article_slug) if draft else (None, body.id)
    if draft is None:
        raise ApiError(404, "NOT_FOUND", "草稿不存在")
    from app.platform.audit import audit

    audit.log(db, action="issue_preview_token", object_type=body.kind,
              object_id=object_id, actor_type="admin", actor_id=admin_sid,
              after={"draftRevision": revision}, request_id=request.state.request_id)
    db.commit()
    return envelope(request, issue_preview_token(
        db, kind=body.kind, object_id=object_id, draft_revision=revision,
        admin_session_id=admin_sid))


@router.get("/levels/{level_id}", response_model=Envelope[LevelDetail])
async def preview_level(request: Request, level_id: str, token: str = "",
                        db: Session = Depends(db_session)):
    verify_preview_token(db, token=token, kind="level", object_id=level_id,
                         admin_cookie=admin_session_cookie(request))
    draft = db.get(LevelDraftRow, level_id)
    if draft is None:
        raise ApiError(404, "NOT_FOUND", "草稿不存在")
    # 预览与公开详情同结构，来源为草稿
    return envelope(request, _draft_level_detail(db, draft, level_id),
                    headers={"Cache-Control": "no-store"})


def _draft_level_detail(db: Session, draft: LevelDraftRow, level_id: str) -> dict:
    from app.content.models import LevelRow
    from app.content.usecases import LAYER_LABEL, _nav, level_sections

    level = db.get(LevelRow, level_id)
    content = JSONText.load(draft.content, {})
    layer = level.layer if level else None
    return {
        "id": level_id,
        "contentVersion": None,   # 草稿无公开版本号
        "ruleVersion": None,
        "draftRevision": draft.revision,
        "order": level.order if level else None,
        "layer": layer,
        "type": content.get("type") or LAYER_LABEL.get(layer or "", ""),
        "targetSound": content.get("targetSound"),
        "pinyin": content.get("pinyin"),
        "representativeChar": content.get("representativeChar"),
        "title": content.get("title"),
        "oneLiner": content.get("oneLiner"),
        "goal": content.get("goal"),
        "applicableIssues": content.get("applicableIssues"),
        "tags": content.get("tags") or [],
        "nav": _nav(db, level, content) if level else {"prev": None, "next": None, "confusables": []},
        "misconceptions": content.get("misconceptions") or [],
        "professional": content.get("professional") or {},
        # 草稿预览关闭录音、听辨提交与学习事件
        **level_sections(content, detection_available=False),
    }


@router.get("/articles/{slug}", response_model=Envelope[ArticleDetail])
async def preview_article(request: Request, slug: str, token: str = "",
                          db: Session = Depends(db_session)):
    verify_preview_token(db, token=token, kind="article", object_id=slug,
                         admin_cookie=admin_session_cookie(request))
    draft = db.get(ArticleDraftRow, slug)
    if draft is None:
        raise ApiError(404, "NOT_FOUND", "草稿不存在")
    content = JSONText.load(draft.content, {})
    return envelope(request, {
        "slug": slug, "draftRevision": draft.revision,
        "title": content.get("title"), "category": content.get("category"),
        "summary": content.get("summary"), "markdown": content.get("markdown"),
        "demo": {"mediaId": content.get("demoMediaId"), "text": content.get("demoText", "")},
        "practice": content.get("practice") or [],
        "references": content.get("references") or [],
        "relatedLevels": [{"levelId": lid, "available": False}
                          for lid in (content.get("relatedLevelIds") or [])],
    }, headers={"Cache-Control": "no-store"})


@router.get("/media/{media_id}")
async def preview_media(request: Request, media_id: str, token: str = "",
                        kind: str = "level", object_id: str = "",
                        db: Session = Depends(db_session)):
    """仅令牌绑定草稿引用的媒体可预览；不授权私人录音。"""
    verify_preview_token(db, token=token, kind=kind, object_id=object_id,
                         admin_cookie=admin_session_cookie(request))
    if not content_uc.media_in_draft(db, kind=kind, object_id=object_id, media_id=media_id):
        return serve_file(request, config.DATA_DIR / "_missing", "application/octet-stream",
                          cache_control="no-store")
    from app.content.models import MediaAssetRow

    asset = db.get(MediaAssetRow, media_id)
    if asset is None or asset.deleted_at is not None:
        return serve_file(request, config.DATA_DIR / "_missing", "application/octet-stream",
                          cache_control="no-store")
    return serve_file(request, config.DATA_DIR / asset.storage_path, asset.mime,
                      cache_control="no-store")
