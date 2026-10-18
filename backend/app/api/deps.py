"""api 依赖：每请求 DB 会话、认证解析（Actor）、限流助手。

Cookie：svs_auth（服务端会话表）。学习、录音检测与档案均要求登录。
"""
from __future__ import annotations

import datetime

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session as _db_session
from app.identity import usecases as identity_uc
from app.identity.models import UserRow
from app.platform.envelope import ApiError
from app.platform.rate_limit import client_ip, limiter
from app.platform.security import ADMIN_COOKIE, AUTH_COOKIE

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
        self.user: UserRow | None = identity_uc.resolve_auth_user(
            db, request.cookies.get(AUTH_COOKIE))

    @property
    def request_id(self) -> str | None:
        return getattr(self.request.state, "request_id", None)

    def rate_limit(self, bucket: str) -> None:
        subject = (self.user.id if self.user else "anon") + ":" + client_ip(self.request)
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


def get_actor(request: Request,
              db: Session = Depends(db_session)) -> Actor:
    return Actor(db, request)


def require_user(actor: Actor) -> UserRow:
    if actor.user is None:
        raise ApiError(401, "AUTH_REQUIRED", "需要登录后才能执行此操作",
                       next_step="请先登录")
    return actor.user


def admin_session_cookie(request: Request) -> str | None:
    return request.cookies.get(ADMIN_COOKIE)
