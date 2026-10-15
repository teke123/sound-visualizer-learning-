"""SQLite（WAL、外键、busy_timeout）连接（ADR-1 / 技术选型）。

单进程单 worker；写事务保持短小，任何外部调用（Provider、ffmpeg、特征提取）
不得在事务内进行。sessionmaker 以 begin 语义提供，用例层自行提交。
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app import config


class Base(DeclarativeBase):
    pass


def _now() -> datetime.datetime:
    # SQLite 不保存时区；全库统一 naive UTC，避免 aware/naive 比较错误
    return _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)


def engine_for(path: Path | None = None):
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    eng = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
    )

    @event.listens_for(eng, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    return eng


_engine = None
_SessionLocal: sessionmaker | None = None


def init_engine():
    global _engine, _SessionLocal
    if _engine is None:
        config.ensure_dirs()
        _engine = engine_for()
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session() -> Session:
    init_engine()
    assert _SessionLocal is not None
    return _SessionLocal()


def create_all() -> None:
    # 1.0 以 create_all 建库（新库、无迁移历史）；引入 Alembic 是 2.0 演进项
    from app import models_registry  # noqa: F401  确保全部表已注册

    init_engine()
    Base.metadata.create_all(_engine)


# --- JSON 便捷序列化（SQLite 存 JSON 文本列）---
class JSONText:
    """列上的 JSON 编解码助手（存取用 dumps/loads，保持 UTC ISO 时间）。"""

    @staticmethod
    def dump(obj) -> str:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def load(text, default=None):
        if not text:
            return default
        try:
            return json.loads(text)
        except (TypeError, ValueError):
            return default


def now() -> datetime.datetime:
    return _now()
