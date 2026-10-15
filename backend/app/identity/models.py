"""identity 模块（docs/architecture/03 第 4 节）：
用户、认证会话、匿名 sid、只追加的同意决定、用户名墓碑。"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserRow(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    username_lower: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    data_epoch: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)


class AuthSessionRow(Base):
    __tablename__ = "auth_session"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)


class AnonSessionRow(Base):
    __tablename__ = "anon_session"

    sid: Mapped[str] = mapped_column(String(64), primary_key=True)
    bound_user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class ConsentDecisionRow(Base):
    __tablename__ = "consent_decision"
    __table_args__ = (UniqueConstraint("id", name="uq_consent_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    decision: Mapped[str] = mapped_column(String(16))    # granted | rejected | revoked
    consent_text_version: Mapped[str] = mapped_column(String(16))
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class UsernameTombstoneRow(Base):
    __tablename__ = "username_tombstone"

    username_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
