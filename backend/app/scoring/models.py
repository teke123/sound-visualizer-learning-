"""scoring 模块表：评分结论缓存、个人音域现行记录、只插入的音域快照。"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ScoreCacheRow(Base):
    __tablename__ = "score_cache"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "pcm_sha256", "level_id", "provider_version",
            name="uq_score_cache",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64))
    audio_id: Mapped[str] = mapped_column(String(64), index=True)   # 随音频删除级联
    pcm_sha256: Mapped[str] = mapped_column(String(64))
    level_id: Mapped[str] = mapped_column(String(16))
    provider_version: Mapped[str] = mapped_column(String(32))
    payload: Mapped[str] = mapped_column(Text)      # JSON：provider 分数+现象+四步
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class PitchRangeRow(Base):
    __tablename__ = "pitch_range"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_pitch_range_owner"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64))
    f_lo: Mapped[float] = mapped_column(Float)
    f_hi: Mapped[float] = mapped_column(Float)
    vowel_space: Mapped[str | None] = mapped_column(Text)  # JSON：六元音 F1/F2 均值与总体统计
    algorithm_version: Mapped[str] = mapped_column(String(64))
    basis_calibration_id: Mapped[str | None] = mapped_column(String(64))  # 标定基线来源（快照 id）
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)


class PitchRangeSnapshotRow(Base):
    __tablename__ = "pitch_range_snapshot"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64))
    f_lo: Mapped[float] = mapped_column(Float)
    f_hi: Mapped[float] = mapped_column(Float)
    vowel_space: Mapped[str | None] = mapped_column(Text)
    algorithm_version: Mapped[str] = mapped_column(String(64))
    created_from: Mapped[str | None] = mapped_column(Text)   # JSON：来源说明
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class CalibrationSessionRow(Base):
    """个人标定会话：四元音各 2–3 条 + 一条短文的多录音标定进度与最终结果。

    会话创建时固定短文版本；最终计算成功时在同一事务写入个人标定值、
    不可变快照与会话完成状态。
    """
    __tablename__ = "calibration_session"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    text_version: Mapped[str] = mapped_column(String(16))
    passage_text: Mapped[str] = mapped_column(Text)        # 会话创建时固定的短文正文
    passage_pinyin: Mapped[str] = mapped_column(Text)      # JSON：逐字 [{text, pinyin}]
    status: Mapped[str] = mapped_column(String(16), default="active")   # active | completed
    calc_state: Mapped[str] = mapped_column(String(16), default="idle")  # idle | processing | done | failed
    last_error: Mapped[str | None] = mapped_column(Text)
    snapshot_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class CalibrationTakeRow(Base):
    """会话内的单条标定录音：一条有效录音只归属一个任务，替换时标记前条为 replaced。"""
    __tablename__ = "calibration_take"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    audio_id: Mapped[str] = mapped_column(String(64), index=True)   # 随会话完成级联清理
    kind: Mapped[str] = mapped_column(String(8))                    # vowel | pitch
    vowel: Mapped[str | None] = mapped_column(String(4))            # i | u | a | ü
    ordinal: Mapped[int] = mapped_column(Integer)                   # 该任务内的序号（1 起）
    status: Mapped[str] = mapped_column(String(16), default="accepted")  # accepted | replaced
    result: Mapped[str] = mapped_column(Text)                       # JSON：验收结果与测量摘要
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
