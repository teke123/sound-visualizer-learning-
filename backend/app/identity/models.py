"""identity 模块：用户与服务端认证会话。"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserRow(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    username_lower: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    # 方言区/母语背景（FR-107，可选）：取值见 identity.usecases.DIALECT_CODES；
    # 用于针对性提示（FR-1007）与后续分组统计，注销时随账号一起失效
    dialect_background: Mapped[str | None] = mapped_column(String(32))


class AuthSessionRow(Base):
    __tablename__ = "auth_session"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
