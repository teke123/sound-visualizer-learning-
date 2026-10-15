"""统一错误与 envelope（决策图「HTTP 与契约」）。

JSON 响应统一 {code, message, data, requestId, nextStep?}；标准状态码。
QUALITY_FAIL / CALIBRATION_FAIL 是 200 的有效业务结果，不是错误。
文件成功直接返回媒体类型，不套 envelope。
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import config


class ApiError(Exception):
    """携带业务 code 的可控错误；status 必须是真实 HTTP 语义。"""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        next_step: str | None = None,
        headers: dict[str, str] | None = None,
        data: Any = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.next_step = next_step
        self.headers = headers or {}
        self.data = data


def envelope(request: Request, data: Any = None, *, code: str = "OK",
             message: str = "ok", status: int = 200,
             next_step: str | None = None,
             headers: dict[str, str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {
        "code": code,
        "message": message,
        "data": data,
        "requestId": getattr(request.state, "request_id", None),
    }
    if next_step:
        body["nextStep"] = next_step
    resp = JSONResponse(body, status_code=status)
    for k, v in (headers or {}).items():
        resp.headers[k] = v
    return resp


def register_exception_handlers(app) -> None:  # noqa: ANN001
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return envelope(
            request, exc.data, code=exc.code, message=exc.message,
            status=exc.status, next_step=exc.next_step, headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        detail = "; ".join(
            f"{'.'.join(str(l) for l in e.get('loc', [])[1:])}: {e.get('msg', '')}"
            for e in exc.errors()[:5]
        ) or "请求结构非法"
        return envelope(request, None, code="VALIDATION_ERROR",
                        message=f"请求结构非法：{detail}", status=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        known = {
            401: ("AUTH_REQUIRED", "需要登录"),
            403: ("FORBIDDEN", "没有权限执行此操作"),
            404: ("NOT_FOUND", "资源不存在或不可见"),
            413: ("FILE_TOO_LARGE", "文件过大"),
            429: ("RATE_LIMITED", "请求过于频繁，请稍后再试"),
            500: ("INTERNAL_ERROR", "服务器内部错误"),
        }
        code, default_msg = known.get(exc.status_code, ("HTTP_ERROR", str(exc.detail)))
        detail = str(exc.detail) if exc.detail else ""
        message = detail if detail not in ("", "Not Found", "Internal Server Error") else default_msg
        return envelope(request, None, code=code, message=message,
                        status=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        import logging

        logging.getLogger("svs").exception("unhandled error: %s", exc)
        rid = getattr(request.state, "request_id", None)
        return envelope(request, None, code="INTERNAL_ERROR",
                        message=f"服务器内部错误，请稍后重试（requestId: {rid}）", status=500)


# 常用错误构造
def auth_required(msg: str = "需要登录后才能执行此操作") -> ApiError:
    return ApiError(401, "AUTH_REQUIRED", msg, next_step="请先登录")


def invalid_credentials() -> ApiError:
    return ApiError(401, "INVALID_CREDENTIALS", "用户名或密码不正确")


def forbidden(msg: str = "没有权限执行此操作") -> ApiError:
    return ApiError(403, "FORBIDDEN", msg)


def consent_required() -> ApiError:
    return ApiError(403, "CONSENT_REQUIRED", "需要先同意保存，才能使用档案功能",
                    next_step="请先在账号页完成同意")


def not_found(msg: str = "资源不存在或不可见") -> ApiError:
    return ApiError(404, "NOT_FOUND", msg)


def csrf_failed() -> ApiError:
    return ApiError(403, "CSRF_FAILED", "请求来源校验失败，请从本站页面发起操作")


def rate_limited(retry_after: int) -> ApiError:
    return ApiError(429, "RATE_LIMITED", "请求过于频繁，请稍后再试",
                    headers={"Retry-After": str(retry_after)})
