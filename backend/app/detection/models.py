"""detection 模块表：录音状态机记录、结果快照。"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RecordingRow(Base):
    __tablename__ = "recording"
    __table_args__ = (
        UniqueConstraint("user_id", "submission_id", name="uq_recording_submission"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    audio_id: Mapped[str] = mapped_column(String(64), index=True)
    level_id: Mapped[str] = mapped_column(String(16), index=True)
    submission_id: Mapped[str] = mapped_column(String(128))
    submission_payload_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="processing")  # processing|completed|failed
    stage: Mapped[str | None] = mapped_column(String(16))   # queued|analyzing|scoring|finalizing
    outcome: Mapped[str | None] = mapped_column(String(16)) # completed→scored; failed→error code
    retryable: Mapped[bool | None] = mapped_column()
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    deadline_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    range_snapshot_id: Mapped[str | None] = mapped_column(String(64))
    accepted_request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)


class AssessmentResultRow(Base):
    __tablename__ = "assessment_result"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    recording_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    payload: Mapped[str] = mapped_column(Text)   # 结果对象 JSON（契约见 schemas）
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
