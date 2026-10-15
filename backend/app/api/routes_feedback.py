"""反馈与希望增加路由（公开提交、限流）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.deps import Actor, get_actor
from app.feedback import usecases as feedback_uc
from app.platform.envelope import envelope

router = APIRouter(prefix="/api", tags=["feedback"])


class FeedbackBody(BaseModel):
    sourcePage: str | None = None
    type: str
    content: str | None = None
    articleSlug: str | None = None
    levelId: str | None = None
    recordingId: str | None = None
    subtype: str | None = None
    rating: int | None = None


@router.post("/feedback")
async def submit_feedback(request: Request, body: FeedbackBody,
                          actor: Actor = Depends(get_actor)):
    actor.rate_limit("feedback")
    result = feedback_uc.submit_feedback(actor.db, owner_type=actor.owner_type,
                                         owner_id=actor.owner_id,
                                         body=body.model_dump(exclude_none=True),
                                         request_id=actor.request_id)
    return envelope(request, result)


class WishBody(BaseModel):
    content: str
    searchQuery: str | None = None


@router.post("/wishes")
async def submit_wish(request: Request, body: WishBody,
                      actor: Actor = Depends(get_actor)):
    actor.rate_limit("wish")
    result = feedback_uc.submit_wish(actor.db, owner_type=actor.owner_type,
                                     owner_id=actor.owner_id, body=body.model_dump())
    return envelope(request, result)
