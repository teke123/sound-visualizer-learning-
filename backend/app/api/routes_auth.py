"""账号路由：注册、登录、退出。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.deps import Actor, get_actor
from app.api.schemas import (
    AuthLoginResponse, Envelope, LoggedOutResponse, ProfileResponse, RegisterResponse,
)
from app.identity import usecases as identity_uc
from app.platform.envelope import envelope

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterBody(BaseModel):
    username: str
    password: str
    dialectBackground: str | None = None


@router.post("/register", response_model=Envelope[RegisterResponse])
async def register(request: Request, body: RegisterBody,
                   actor: Actor = Depends(get_actor)):
    actor.rate_limit("register")
    result = identity_uc.register_user(actor.db, username=body.username,
                                       password=body.password,
                                       dialect_background=body.dialectBackground)
    return envelope(request, result)


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login", response_model=Envelope[AuthLoginResponse])
async def login(request: Request, body: LoginBody, actor: Actor = Depends(get_actor)):
    actor.rate_limit("login")
    # 已登录时先按退出处理（失效旧会话）
    if actor.user is not None:
        identity_uc.logout(actor.db, auth_cookie=actor.request.cookies.get("svs_auth"))
        actor.clear_auth_cookie()
    user = identity_uc.verify_login(actor.db, username=body.username,
                                    password=body.password)
    token = identity_uc.create_auth_session(actor.db, user_id=user.id)
    actor.set_auth_cookie(token)
    context = {"authenticated": True, "accountId": user.id, "username": user.username}
    return envelope(request, {"context": context})


@router.post("/logout", response_model=Envelope[LoggedOutResponse])
async def logout(request: Request, actor: Actor = Depends(get_actor)):
    identity_uc.logout(actor.db, auth_cookie=actor.request.cookies.get("svs_auth"))
    actor.clear_auth_cookie()
    return envelope(request, {"loggedOut": True})
