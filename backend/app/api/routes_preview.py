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

router = APIRouter(prefix="/api/preview", tags=["preview"])


class TokenBody(BaseModel):
    kind: str          # level | article
    id: str


@router.post("/tokens")
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


@router.get("/levels/{level_id}")
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

    level = db.get(LevelRow, level_id)
    content = JSONText.load(draft.content, {})
    from app.content.usecases import LAYER_LABEL, _nav

    demos = [
        {"mediaId": d["mediaId"], "speed": d.get("speed", "normal"),
         "voice": d.get("voice"), "text": d.get("text", "")}
        for d in (content.get("demos") or []) if d.get("mediaId")
    ]
    quizzes = [
        {"id": q["id"], "stimulusMediaId": q.get("stimulusMediaId"),
         "prompt": q.get("prompt", "听一听，这是哪个音？"),
         "options": [{"text": o.get("text", ""), "mediaId": o.get("mediaId")}
                     for o in (q.get("options") or [])],
         "answerIndex": q.get("answerIndex", 0), "explanation": q.get("explanation")}
        for q in (content.get("quizzes") or [])
    ]
    practice = [
        {"id": p["id"], "title": p.get("title", ""), "instruction": p.get("instruction", ""),
         "repeat": p.get("repeat"), "durationSec": p.get("durationSec"),
         "bodyCue": p.get("bodyCue", ""), "mediaId": p.get("mediaId"),
         "stopNote": p.get("stopNote", "不舒服就停止")}
        for p in (content.get("practice") or [])
    ]
    articulation_raw = content.get("articulation") or {}
    detection_raw = content.get("detection") or {}
    return {
        "id": level_id,
        "contentVersion": None,   # 草稿无公开版本号
        "ruleVersion": None,
        "draftRevision": draft.revision,
        "order": level.order if level else None,
        "layer": level.layer if level else None,
        "type": content.get("type") or LAYER_LABEL.get(level.layer if level else "", ""),
        "targetSound": content.get("targetSound"),
        "pinyin": content.get("pinyin"),
        "representativeChar": content.get("representativeChar"),
        "title": content.get("title"),
        "oneLiner": content.get("oneLiner"),
        "goal": content.get("goal"),
        "applicableIssues": content.get("applicableIssues"),
        "tags": content.get("tags") or [],
        "nav": _nav(db, level, content) if level else {"prev": None, "next": None, "confusables": []},
        "articulation": {
            "media": [{"mediaId": m.get("mediaId"), "kind": m.get("kind", "image"),
                       "altText": m.get("altText", "")}
                      for m in (articulation_raw.get("media") or []) if m.get("mediaId")],
            "description": articulation_raw.get("description", ""),
            "sagittal": articulation_raw.get("sagittal") or {"keyframes": []},
            "model3dMediaId": articulation_raw.get("model3dMediaId"),
        },
        "demos": demos,
        "quizzes": quizzes,
        "practice": practice,
        "misconceptions": content.get("misconceptions") or [],
        "professional": content.get("professional") or {},
        "detection": {
            "promptText": detection_raw.get("promptText", ""),
            "sampleMediaId": detection_raw.get("sampleMediaId"),
            "allowedMetrics": detection_raw.get("allowedMetrics", []),
            "reliabilityNote": detection_raw.get("reliabilityNote", ""),
            "available": False,   # 草稿预览关闭录音、听辨提交与学习事件
        },
    }


@router.get("/articles/{slug}")
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
