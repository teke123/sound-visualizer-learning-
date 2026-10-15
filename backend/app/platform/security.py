"""安全原语：sid/管理员会话 Cookie 签名、管理员认证、预览令牌签发校验。

- sid：随机 ID + HMAC 签名的 HttpOnly Cookie（有效期覆盖 72 小时临时期）。
- 管理员：独立凭据（config），会话 ID 存服务端行、Cookie 只存随机 ID，
  Path 限定 /admin 与 /api/preview，不与学习账号互通（ADR-13）。
- 预览令牌：绑定 (admin_session, kind, object, draft_revision, exp)，
  以 query 传递，使 <audio>/<img> 可直接引用（决策图 #21）。
"""
from __future__ import annotations

import hashlib
import hmac
import datetime

from sqlalchemy.orm import Session

from app import config
from app.db import now
from app.ids import new_token
from app.platform.envelope import ApiError

SID_COOKIE = "svs_sid"
AUTH_COOKIE = "svs_auth"
ADMIN_COOKIE = "svs_admin"


def _sign(value: str) -> str:
    return hmac.new(config.SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()[:32]


def sign_sid(sid: str) -> str:
    return f"{sid}.{_sign(sid)}"


def verify_sid(cookie_value: str | None) -> str | None:
    if not cookie_value or "." not in cookie_value:
        return None
    sid, sig = cookie_value.rsplit(".", 1)
    if not sid or not hmac.compare_digest(sig, _sign(sid)):
        return None
    return sid


# --- 管理员会话 ---
def check_admin_session(db: Session, cookie_value: str | None) -> str | None:
    """返回有效管理员 session_id；无效返回 None。"""
    if not cookie_value:
        return None
    from app.security_models import AdminSessionRow

    row = db.get(AdminSessionRow, cookie_value)
    if row is None or row.revoked_at is not None or row.expires_at < now():
        return None
    return row.session_id


def revoke_admin_session(db: Session, cookie_value: str | None) -> None:
    from app.security_models import AdminSessionRow

    if not cookie_value:
        return
    row = db.get(AdminSessionRow, cookie_value)
    if row and row.revoked_at is None:
        row.revoked_at = now()
        db.commit()


def require_admin(db: Session, cookie_value: str | None) -> str:
    sid = check_admin_session(db, cookie_value)
    if sid is None:
        raise ApiError(401, "AUTH_REQUIRED", "需要管理员登录", next_step="请先登录后台")
    return sid


# --- 预览令牌 ---
def issue_preview_token(db: Session, *, kind: str, object_id: str,
                        draft_revision: int, admin_session_id: str) -> dict:
    from app.platform.models import PreviewTokenRow

    token_id = new_token(18)
    expires_at = now() + datetime.timedelta(minutes=config.PREVIEW_TOKEN_TTL_MINUTES)
    db.add(PreviewTokenRow(
        token_id=token_id,
        kind=kind,
        object_id=object_id,
        draft_revision=draft_revision,
        admin_session_id=admin_session_id,
        expires_at=expires_at,
        created_at=now(),
    ))
    db.commit()
    base = {"level": "/preview/levels", "article": "/preview/articles"}[kind]
    return {
        "token": token_id,
        "expiresAt": expires_at.isoformat(),
        "url": f"{base}/{object_id}?token={token_id}",
    }


def verify_preview_token(db: Session, *, token: str | None, kind: str,
                         object_id: str, admin_cookie: str | None) -> "PreviewTokenRow":
    from app.platform.models import PreviewTokenRow

    if not token:
        raise ApiError(404, "NOT_FOUND", "预览令牌缺失")
    admin_session = check_admin_session(db, admin_cookie)
    if admin_session is None:
        raise ApiError(401, "AUTH_REQUIRED", "预览需要管理员会话")
    row = db.get(PreviewTokenRow, token)
    if (row is None or row.kind != kind or row.object_id != object_id
            or row.expires_at < now() or row.admin_session_id != admin_session):
        raise ApiError(404, "NOT_FOUND", "预览令牌无效或已过期，请回后台重新签发")
    return row
