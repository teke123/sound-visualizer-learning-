"""scoring 模块表：评分结论缓存、音域现行记录、只插入的音域快照。"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ScoreCacheRow(Base):
    __tablename__ = "score_cache"
    __table_args__ = (
        UniqueConstraint(
            "owner_type", "owner_id", "pcm_sha256", "level_id", "content_version",
            "rule_version", "provider_version",
            name="uq_score_cache",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_type: Mapped[str] = mapped_column(String(8))
    owner_id: Mapped[str] = mapped_column(String(64))
    audio_id: Mapped[str] = mapped_column(String(64), index=True)   # 随音频删除级联
    pcm_sha256: Mapped[str] = mapped_column(String(64))
    level_id: Mapped[str] = mapped_column(String(16))
    content_version: Mapped[int] = mapped_column(Integer)
    rule_version: Mapped[str] = mapped_column(String(32))
    provider_version: Mapped[str] = mapped_column(String(32))
    payload: Mapped[str] = mapped_column(Text)      # JSON：provider 分数+现象+四步
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class PitchRangeRow(Base):
    __tablename__ = "pitch_range"
    __table_args__ = (
        UniqueConstraint("owner_type", "owner_id", name="uq_pitch_range_owner"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_type: Mapped[str] = mapped_column(String(8))     # user | sid
    owner_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))          # personal | session
    f_lo: Mapped[float] = mapped_column(Float)
    f_hi: Mapped[float] = mapped_column(Float)
    vowel_space: Mapped[str | None] = mapped_column(Text)  # JSON：六元音 F1/F2 均值与总体统计
    algorithm_version: Mapped[str] = mapped_column(String(64))
    basis_calibration_id: Mapped[str | None] = mapped_column(String(64))  # 标定基线来源（快照 id）
    source_recording_ids: Mapped[str | None] = mapped_column(Text)        # JSON list：滚动更新来源
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)  # 仅 session
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)


class PitchRangeSnapshotRow(Base):
    __tablename__ = "pitch_range_snapshot"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_type: Mapped[str] = mapped_column(String(8))
    owner_id: Mapped[str] = mapped_column(String(64))
    f_lo: Mapped[float] = mapped_column(Float)
    f_hi: Mapped[float] = mapped_column(Float)
    vowel_space: Mapped[str | None] = mapped_column(Text)
    algorithm_version: Mapped[str] = mapped_column(String(64))
    created_from: Mapped[str | None] = mapped_column(Text)   # JSON：来源说明
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
