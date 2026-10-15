"""不可猜测随机 ID（决策图第 4 节：UUIDv7 或 ULID 皆可，这里用 uuid4 截短 +
随机性即可；关卡保留业务 ID L01 起）。"""
from __future__ import annotations

import secrets
import uuid


def new_id(prefix: str = "") -> str:
    raw = uuid.uuid4().hex  # 122 bit 随机，不可猜测
    return f"{prefix}{raw}" if prefix else raw


def new_token(nbytes: int = 24) -> str:
    return secrets.token_urlsafe(nbytes)
