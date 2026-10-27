"""content 模块表：关卡/文章（单一开放开关，保存即生效）、分类、媒体、
参考发音人、标定文本、声道剖面预设。"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LevelRow(Base):
    __tablename__ = "level"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)   # L01..
    order: Mapped[int] = mapped_column(Integer)
    layer: Mapped[str] = mapped_column(String(16))                  # vowel|initial|syllable
    published: Mapped[bool] = mapped_column(default=False)          # 已开放 / 未开放
    skeleton_public: Mapped[bool] = mapped_column(default=True)     # 未开放时是否在地图显示骨架
    content: Mapped[str] = mapped_column(Text)                      # JSON（含 quiz/practice 稳定 id）
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class ArticleRow(Base):
    __tablename__ = "article"

    slug: Mapped[str] = mapped_column(String(128), primary_key=True)
    published: Mapped[bool] = mapped_column(default=False)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class CategoryRow(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class MediaAssetRow(Base):
    __tablename__ = "media_asset"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))      # audio|image|animation|video|subtitle|model|license_doc
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(512))
    mime: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    purpose: Mapped[str] = mapped_column(String(32), default="content")  # content|demo|quiz|article|license
    license_note: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(128))
    sha256: Mapped[str | None] = mapped_column(String(64))
    duration_sec: Mapped[float | None] = mapped_column(Float)
    text: Mapped[str | None] = mapped_column(Text)     # 音频对应文字（字幕）
    uploaded_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)


class ReferenceSpeakerRow(Base):
    __tablename__ = "reference_speaker"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    gender: Mapped[str] = mapped_column(String(16))    # male|female
    f_lo: Mapped[float] = mapped_column(Float)
    f_hi: Mapped[float] = mapped_column(Float)
    vowel_space: Mapped[str | None] = mapped_column(Text)   # JSON
    algorithm_version: Mapped[str] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
    registered_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class CalibrationTextRow(Base):
    __tablename__ = "calibration_text"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text_version: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    syllables: Mapped[str] = mapped_column(Text)       # JSON list
    active: Mapped[bool] = mapped_column(default=True)
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime)
