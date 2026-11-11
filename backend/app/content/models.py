"""content 模块表：关卡/文章（单一开放开关，保存即生效）、分类、媒体、
参考发音人、标定文本、关卡混淆项关联。

拆列原则：只有需要搜索的与需要外键引用的字段拆成普通列，
其余内容留在 content JSON 文档中（读写整篇、保存时抽列拼装）。
"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LevelRow(Base):
    __tablename__ = "level"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)   # L01..
    order: Mapped[int] = mapped_column(Integer)
    layer: Mapped[str] = mapped_column(String(16))                  # vowel|initial|syllable
    published: Mapped[bool] = mapped_column(default=False)          # 已开放 / 未开放
    skeleton_public: Mapped[bool] = mapped_column(default=True)     # 未开放时是否在地图显示骨架
    # 搜索列（search_levels）
    title: Mapped[str | None] = mapped_column(String(128))
    target_sound: Mapped[str | None] = mapped_column(String(32))
    pinyin: Mapped[str | None] = mapped_column(String(32))
    # 外键引用列
    sample_media_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("media_asset.id", ondelete="RESTRICT"))
    reference_speaker_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("reference_speaker.id", ondelete="RESTRICT"))
    # 内容文档 JSON（demos/quizzes/practice/articulation/detection/tags 等整篇）
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class LevelConfusableRow(Base):
    """关卡混淆项（对称关系，按各关卡提交的列表原样存储）。"""

    __tablename__ = "level_confusable"

    level_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("level.id", ondelete="CASCADE"), primary_key=True)
    confusable_level_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("level.id", ondelete="CASCADE"), primary_key=True)


class ArticleRow(Base):
    __tablename__ = "article"

    slug: Mapped[str] = mapped_column(String(128), primary_key=True)
    published: Mapped[bool] = mapped_column(default=False)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("category.id", ondelete="RESTRICT"))
    # 文章内容文档 JSON（title/summary/markdown/demo/relatedLevelIds 等整篇）
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
