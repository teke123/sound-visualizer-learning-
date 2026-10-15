"""requestId 中间件 + Origin/CSRF 校验 + 访问日志。

- 每次 HTTP 请求生成/校验 requestId 并写 X-Request-Id（决策图「HTTP 与契约」）。
- 写请求（非 GET/HEAD/OPTIONS）校验 Origin（缺失时 Referer）为本站；
  Cookie SameSite=Lax 兜底；不使用 CSRF 令牌。
"""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app import config

logger = logging.getLogger("svs.request")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
JSON_PREFIXES = ("/api",)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        rid = rid[:64]
        request.state.request_id = rid
        start = time.perf_counter()

        # CSRF：写请求校验 Origin（缺失时 Referer）为本站
        if config.CSRF_ENFORCED and request.method not in SAFE_METHODS:
            origin = request.headers.get("Origin")
            referer = request.headers.get("Referer")
            candidate = origin or referer
            if not candidate:
                from app.platform.envelope import csrf_failed

                err = csrf_failed()
                from app.platform.envelope import envelope

                return envelope(request, None, code=err.code, message=err.message,
                                status=err.status, next_step="请从本站页面发起操作")
            if not any(candidate == o or candidate.startswith(o + "/") for o in config.ALLOWED_ORIGINS):
                # Origin 为 "null" 或第三方：拒绝
                from app.platform.envelope import csrf_failed, envelope

                err = csrf_failed()
                return envelope(request, None, code=err.code, message=err.message,
                                status=err.status)

        response = await call_next(request)
        # 依赖层（Actor）通过共享 state 交付的 Cookie 统一写回响应
        for ck in getattr(request.state, "pending_cookies", []) or []:
            if ck.get("op") == "set":
                response.set_cookie(
                    ck["name"], ck["value"], max_age=ck["max_age"],
                    httponly=True, samesite="lax",
                    secure=config.ENV == "prod",
                )
            elif ck.get("op") == "delete":
                response.delete_cookie(ck["name"])
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-Id"] = rid
        if request.url.path.startswith(JSON_PREFIXES) or request.url.path.startswith("/admin"):
            logger.info(
                "%s %s -> %s %.1fms rid=%s",
                request.method, request.url.path, response.status_code,
                elapsed_ms, rid,
            )
        return response
