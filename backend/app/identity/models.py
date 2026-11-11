"""identity 模块表：用户与服务端会话（学习账号与管理员共用一张表，kind 判别）。"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserRow(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # 仅小写字母与数字（identity.usecases.USERNAME_RE），注册时已规范化
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    # 方言区/母语背景（FR-107，可选）：取值见 identity.usecases.DIALECT_CODES；
    # 用于针对性提示（FR-1007）与后续分组统计
    dialect_background: Mapped[str | None] = mapped_column(String(32))
    # 性别（FR-107，可选）：取值见 identity.usecases.GENDER_CODES；
    # 用于音高参考范围与后续分组统计
    gender: Mapped[str | None] = mapped_column(String(16))


class SessionRow(Base):
    """服务端会话：Cookie 只存随机 id。管理员会话无所属用户（user_id 为空）。"""

    __tablename__ = "session"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8))  # user | admin
    user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("user.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
