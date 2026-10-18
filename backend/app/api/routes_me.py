"""档案、学习事件与进度、注销路由（均要求登录）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.deps import Actor, get_actor, require_user
from app.api.schemas import (
    ArchiveCompareResponse, ArchiveListResponse, ClearArchiveResponse, DeletedResponse,
    Envelope, LearningEventsResponse, MeProgress,
)
from app.archive import usecases as archive_uc
from app.identity import usecases as identity_uc
from app.platform.envelope import envelope

router = APIRouter(prefix="/api", tags=["session-archive"])


# ---------------- 档案 ----------------

@router.get("/me/recordings", response_model=Envelope[ArchiveListResponse])
async def my_recordings(request: Request, levelId: str | None = None,
                        cursor: str | None = None, actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    return envelope(request, archive_uc.my_recordings(actor.db, user=user,
                                                      level_id=levelId, cursor=cursor))


@router.delete("/me/recordings", response_model=Envelope[ClearArchiveResponse])
async def clear_my_recordings(request: Request, actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    result = archive_uc.clear_archive(actor.db, user=user)
    return envelope(request, result)


@router.get("/me/recordings/compare", response_model=Envelope[ArchiveCompareResponse])
async def compare_recordings(request: Request, a: str, b: str,
                             actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    return envelope(request, archive_uc.compare_recordings(actor.db, user=user, a=a, b=b))


# ---------------- 学习事件与进度 ----------------

class EventItem(BaseModel):
    eventId: str
    levelId: str
    kind: str
    detail: dict


class LearningEventsBody(BaseModel):
    events: list[EventItem]


@router.post("/learning-events", response_model=Envelope[LearningEventsResponse])
async def learning_events(request: Request, body: LearningEventsBody,
                          actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    if not body.events or len(body.events) > archive_uc.EVENT_BATCH_LIMIT:
        from app.platform.envelope import ApiError

        raise ApiError(422, "VALIDATION_ERROR", "事件批次须为 1–50 条")
    result = archive_uc.accept_learning_events(
        actor.db, user=user,
        events=[e.model_dump() for e in body.events])
    return envelope(request, result)


@router.get("/me/progress", response_model=Envelope[MeProgress])
async def my_progress(request: Request, actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    return envelope(request, archive_uc.derive_progress(actor.db, user=user))


# ---------------- 注销 ----------------

class DeleteAccountBody(BaseModel):
    password: str


@router.delete("/me/account", response_model=Envelope[DeletedResponse])
async def delete_account(request: Request, body: DeleteAccountBody,
                         actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    identity_uc.delete_account(actor.db, user=user, password=body.password)
    actor.clear_auth_cookie()
    return envelope(request, {"deleted": True})
