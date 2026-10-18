"""安全原语：管理员会话（团队自用后台的简单口令登录）。

管理员凭据来自 config，会话 ID 存服务端行、Cookie 只存随机 ID，
不与学习账号互通。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import now
from app.platform.envelope import ApiError

AUTH_COOKIE = "svs_auth"
ADMIN_COOKIE = "svs_admin"


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
