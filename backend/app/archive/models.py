"""archive / learning 模块表：学习事件（进度按 D-24 只读派生，不存完成标志）。"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LearningEventRow(Base):
    __tablename__ = "learning_event"
    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_learning_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    event_id: Mapped[str] = mapped_column(String(128))
    level_id: Mapped[str] = mapped_column(String(16), index=True)
    content_version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16))     # listen_quiz | practice_done
    detail: Mapped[str | None] = mapped_column(Text)  # JSON {questionId,choiceIndex} / {stepId}
    correct: Mapped[bool | None] = mapped_column()    # 仅 listen_quiz 服务端派生
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
