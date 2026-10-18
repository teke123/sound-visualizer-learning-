"""acoustics 模块表：audio（用户上传）、feature_cache（F0/共振峰/图片缓存）。"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AudioRow(Base):
    __tablename__ = "audio"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    purpose: Mapped[str] = mapped_column(String(16))       # recording | calibration
    original_filename: Mapped[str | None] = mapped_column(String(255))
    original_mime: Mapped[str | None] = mapped_column(String(128))
    storage_path: Mapped[str] = mapped_column(String(512))
    duration_sec: Mapped[float] = mapped_column(Float)
    pcm_sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)


class FeatureCacheRow(Base):
    __tablename__ = "feature_cache"
    __table_args__ = (
        UniqueConstraint("audio_id", "kind", "algorithm_version", name="uq_feature_cache"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audio_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(16))          # f0 | formants | formants_png | spectrogram_png
    algorithm_version: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text)             # JSON（图片则文件相对路径）
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
