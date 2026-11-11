"""detection 模块表：录音状态机记录（评估结果内联在录音行上）。"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RecordingRow(Base):
    __tablename__ = "recording"
    __table_args__ = (
        UniqueConstraint("user_id", "submission_id", name="uq_recording_submission"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("user.id", ondelete="CASCADE"), index=True)
    audio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("audio.id", ondelete="CASCADE"), index=True)
    level_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("level.id", ondelete="RESTRICT"), index=True)
    submission_id: Mapped[str] = mapped_column(String(128))
    submission_payload_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="processing")  # processing|completed|failed
    stage: Mapped[str | None] = mapped_column(String(16))   # queued|analyzing|scoring|finalizing
    outcome: Mapped[str | None] = mapped_column(String(16)) # completed→scored; failed→error code
    retryable: Mapped[bool | None] = mapped_column()
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    deadline_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    range_snapshot_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("pitch_range.id", ondelete="CASCADE"))
    accepted_request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    # 评估结果（服务商返回与四步反馈的快照 JSON），完成时一次写入
    result_payload: Mapped[str | None] = mapped_column(Text)
    result_created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
