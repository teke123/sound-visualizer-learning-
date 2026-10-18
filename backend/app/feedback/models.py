"""feedback 模块表：反馈单、希望增加。"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FeedbackRow(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64))
    source_page: Mapped[str] = mapped_column(String(32))   # P01..P11
    type: Mapped[str] = mapped_column(String(32))          # clarity | result_match | content_error | wish
    subtype: Mapped[str | None] = mapped_column(String(32))  # 纠错：text|audio|image|subtitle
    content: Mapped[str | None] = mapped_column(Text)
    article_slug: Mapped[str | None] = mapped_column(String(128))
    level_id: Mapped[str | None] = mapped_column(String(16))
    recording_id: Mapped[str | None] = mapped_column(String(64))
    rating: Mapped[int | None] = mapped_column(Integer)    # 结果是否符合感受
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|adopted|rejected
    handled_by: Mapped[str | None] = mapped_column(String(64))
    handled_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class WishRow(Base):
    __tablename__ = "wish"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)             # 希望增加的音/字
    search_query: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    handled_by: Mapped[str | None] = mapped_column(String(64))
    handled_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
