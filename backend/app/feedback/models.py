"""feedback 模块表：反馈单与「希望增加」共用一张表（kind 判别）。"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FeedbackRow(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("user.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(8))           # issue | wish
    source_page: Mapped[str | None] = mapped_column(String(32))   # P01..P11（wish 行为空）
    type: Mapped[str | None] = mapped_column(String(32))   # issue：clarity | result_match | content_error
    subtype: Mapped[str | None] = mapped_column(String(32))  # 纠错：text|audio|image|subtitle
    content: Mapped[str | None] = mapped_column(Text)
    search_query: Mapped[str | None] = mapped_column(String(255))  # wish：提交时的搜索词
    article_slug: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("article.slug", ondelete="CASCADE"))
    level_id: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("level.id", ondelete="CASCADE"))
    recording_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("recording.id", ondelete="CASCADE"))
    rating: Mapped[int | None] = mapped_column(Integer)    # 结果是否符合感受
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|adopted|rejected
    handled_by: Mapped[str | None] = mapped_column(String(64))
    handled_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
