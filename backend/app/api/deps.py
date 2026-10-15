"""api 依赖：每请求 DB 会话、sid/认证解析（Actor）、限流助手、文件响应。

Cookie：svs_sid（签名 HttpOnly，覆盖 72h 临时期）、svs_auth（服务端会话表）。
有效所有者：已认证 → 账号；否则 sid。绑定后 sid 单独不再授予访问。
"""
from __future__ import annotations

import datetime

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app import config
from app.db import get_session as _db_session
from app.identity import usecases as identity_uc
from app.identity.models import UserRow
from app.platform.envelope import ApiError
from app.platform.rate_limit import client_ip, limiter
from app.platform.security import (
    ADMIN_COOKIE, AUTH_COOKIE, SID_COOKIE, sign_sid, verify_sid,
)

SID_COOKIE_MAX_AGE = int(datetime.timedelta(hours=config.TEMP_DATA_TTL_HOURS + 1).total_seconds())
AUTH_COOKIE_MAX_AGE = int(datetime.timedelta(days=30).total_seconds())


def db_session() -> Session:
    db = _db_session()
    try:
        yield db
    finally:
        db.close()


class Actor:
    def __init__(self, db: Session, request: Request):
        self.db = db
        self.request = request
        raw = request.cookies.get(SID_COOKIE)
        sid = verify_sid(raw)
        self.sid, issued = identity_uc.ensure_sid(db, sid)
        self.sid_issued = issued
        if issued:
            self._set_cookie(SID_COOKIE, sign_sid(self.sid), max_age=SID_COOKIE_MAX_AGE)
        self.user: UserRow | None = identity_uc.resolve_auth_user(
            db, request.cookies.get(AUTH_COOKIE))
        # 绑定后的 sid：临时资源已归账号；sid 单独不再授予访问
        if self.user is not None:
            self.owner_type, self.owner_id = "user", self.user.id
        else:
            self.owner_type, self.owner_id = "sid", self.sid

    @property
    def request_id(self) -> str | None:
        return getattr(self.request.state, "request_id", None)

    @property
    def is_guest(self) -> bool:
        return self.user is None

    def rate_limit(self, bucket: str) -> None:
        subject = (f"{self.owner_id}:{client_ip(self.request)}")
        limiter.check(bucket, subject)

    # --- Cookie 经由 request.state 交给中间件统一写入 ---
    # （端点直接返回 Response 对象时，FastAPI 会忽略依赖注入 Response 上的
    # Set-Cookie；scope["state"] 在中间件与端点间共享，是可靠通道。）

    def _set_cookie(self, name: str, value: str, max_age: int) -> None:
        pending = getattr(self.request.state, "pending_cookies", None)
        if pending is None:
            pending = []
            self.request.state.pending_cookies = pending
        pending.append({"op": "set", "name": name, "value": value, "max_age": max_age})

    def _delete_cookie(self, name: str) -> None:
        pending = getattr(self.request.state, "pending_cookies", None)
        if pending is None:
            pending = []
            self.request.state.pending_cookies = pending
        pending.append({"op": "delete", "name": name})

    def set_auth_cookie(self, token: str) -> None:
        self._set_cookie(AUTH_COOKIE, token, AUTH_COOKIE_MAX_AGE)

    def clear_auth_cookie(self) -> None:
        self._delete_cookie(AUTH_COOKIE)

    def rotate_sid(self) -> None:
        new_sid = identity_uc.rotate_sid(self.db, self.sid)
        self.sid = new_sid
        self.owner_type, self.owner_id = "sid", new_sid
        self._set_cookie(SID_COOKIE, sign_sid(new_sid), SID_COOKIE_MAX_AGE)


def get_actor(request: Request,
              db: Session = Depends(db_session)) -> Actor:
    return Actor(db, request)


def require_user(actor: Actor) -> UserRow:
    if actor.user is None:
        raise ApiError(401, "AUTH_REQUIRED", "需要登录后才能执行此操作",
                       next_step="请先登录")
    return actor.user


def require_consent(actor: Actor) -> UserRow:
    user = require_user(actor)
    if not identity_uc.consent_granted(actor.db, user):
        raise ApiError(403, "CONSENT_REQUIRED", "需要先同意保存，才能使用档案功能",
                       next_step="请先在账号页完成同意")
    return user


def admin_session_cookie(request: Request) -> str | None:
    return request.cookies.get(ADMIN_COOKIE)
