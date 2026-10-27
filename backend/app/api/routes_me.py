"""档案、进度与注销路由（均要求登录）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.deps import Actor, get_actor, require_user
from app.api.schemas import (
    ArchiveListResponse, ClearArchiveResponse, DeletedResponse,
    Envelope, MeProgress, ProfileResponse,
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


# ---------------- 进度 ----------------

@router.get("/me/progress", response_model=Envelope[MeProgress])
async def my_progress(request: Request, actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    return envelope(request, archive_uc.derive_progress(actor.db, user=user))


# ---------------- 个人资料 ----------------

class ProfileBody(BaseModel):
    """dialectBackground / gender 传 null 或空串清除（FR-106 / FR-107）"""
    dialectBackground: str | None = None
    gender: str | None = None


@router.patch("/me/profile", response_model=Envelope[ProfileResponse])
async def update_profile(request: Request, body: ProfileBody,
                         actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    result = identity_uc.update_profile(actor.db, user=user,
                                        dialect_background=body.dialectBackground,
                                        gender=body.gender)
    return envelope(request, result)


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
