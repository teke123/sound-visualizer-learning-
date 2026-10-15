"""账号与同意路由：注册、登录（绑定+转存）、退出、同意决定、撤回、注销。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.deps import Actor, get_actor
from app.archive import usecases as archive_uc
from app.identity import usecases as identity_uc
from app.platform.envelope import envelope

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterBody(BaseModel):
    username: str
    password: str


@router.post("/register")
async def register(request: Request, body: RegisterBody,
                   actor: Actor = Depends(get_actor)):
    actor.rate_limit("register")
    result = identity_uc.register_user(actor.db, username=body.username,
                                       password=body.password,
                                       request_id=actor.request_id)
    return envelope(request, result)


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(request: Request, body: LoginBody, actor: Actor = Depends(get_actor)):
    actor.rate_limit("login")
    # 已登录时先按退出处理（失效会话、轮换 sid）
    if actor.user is not None:
        identity_uc.logout(actor.db, auth_cookie=actor.request.cookies.get("svs_auth"),
                           sid=None)
        actor.clear_auth_cookie()
        actor.rotate_sid()
    user = identity_uc.verify_login(actor.db, username=body.username,
                                    password=body.password)
    # 绑定当前 sid：临时资源归属改为账号
    identity_uc.bind_sid_to_user(actor.db, sid=actor.sid, user_id=user.id)
    token = identity_uc.create_auth_session(actor.db, user_id=user.id)
    actor.set_auth_cookie(token)
    actor.user = user
    actor.owner_type, actor.owner_id = "user", user.id
    # 已有有效同意时自动转存（D-14）
    transfer = None
    if identity_uc.consent_granted(actor.db, user):
        from app.identity.usecases import grant_consent, _bound_sid

        sid = _bound_sid(actor.db, user.id)
        if sid:
            t = archive_uc.transfer_session_records(actor.db, sid=sid,
                                                    user_id=user.id, consent_id=None)
            transfer = {"status": t["status"], "transferredCount": t["transferredCount"],
                        "calibrationUpgraded": t["calibrationUpgraded"]}
            actor.db.commit()
    context = {"authenticated": True, "accountId": user.id, "username": user.username,
               "dataEpoch": user.data_epoch}
    return envelope(request, {"context": context, "transfer": transfer})


@router.post("/logout")
async def logout(request: Request, actor: Actor = Depends(get_actor)):
    identity_uc.logout(actor.db, auth_cookie=actor.request.cookies.get("svs_auth"),
                       sid=None)
    actor.clear_auth_cookie()
    actor.rotate_sid()   # 退出轮换 sid，断开旧账号关系
    return envelope(request, {"loggedOut": True})
