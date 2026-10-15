"""content 模块表：关卡/文章身份、草稿、不可变公开版本、分类、媒体与发布引用、
参考发音人、标定文本、检测熔断开关、声道剖面预设（docs/architecture/03 第 4 节）。"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LevelRow(Base):
    __tablename__ = "level"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)   # L01..
    order: Mapped[int] = mapped_column(Integer)
    layer: Mapped[str] = mapped_column(String(16))                  # vowel|initial|syllable
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft|published|unpublished
    current_version_id: Mapped[str | None] = mapped_column(String(64))
    skeleton_public: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class LevelDraftRow(Base):
    __tablename__ = "level_draft"

    level_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str] = mapped_column(Text)      # JSON 草稿（含稳定 quiz/practice id）
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    updated_by: Mapped[str | None] = mapped_column(String(64))


class LevelVersionRow(Base):
    __tablename__ = "level_version"
    __table_args__ = (UniqueConstraint("level_id", "version", name="uq_level_version"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    level_id: Mapped[str] = mapped_column(String(16), index=True)
    version: Mapped[int] = mapped_column(Integer)             # contentVersion，单调递增
    rule_version: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)                # 不可变快照（含冻结标准曲线）
    change_note: Mapped[str | None] = mapped_column(Text)
    published_by: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class ArticleRow(Base):
    __tablename__ = "article"

    slug: Mapped[str] = mapped_column(String(128), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    current_version_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class ArticleDraftRow(Base):
    __tablename__ = "article_draft"

    article_slug: Mapped[str] = mapped_column(String(128), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    updated_by: Mapped[str | None] = mapped_column(String(64))


class ArticleVersionRow(Base):
    __tablename__ = "article_version"
    __table_args__ = (UniqueConstraint("article_slug", "version", name="uq_article_version"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    article_slug: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    change_note: Mapped[str | None] = mapped_column(Text)
    published_by: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class CategoryRow(Base):
    __tablename__ = "category"

    id: Mapped[str] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class MediaAssetRow(Base):
    __tablename__ = "media_asset"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))      # audio|image|animation|video|subtitle|model|license_doc
    storage: Mapped[str] = mapped_column(String(16))   # public|draft
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


class MediaRefRow(Base):
    __tablename__ = "media_ref"
    __table_args__ = (UniqueConstraint("media_id", "version_id", name="uq_media_ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    media_id: Mapped[str] = mapped_column(String(64), index=True)
    version_id: Mapped[str] = mapped_column(String(64), index=True)  # 已发布 level/article version id


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


class DetectionSwitchRow(Base):
    __tablename__ = "detection_switch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level_id: Mapped[str | None] = mapped_column(String(16), index=True)  # null=全局
    enabled: Mapped[bool] = mapped_column(default=True)
    reason: Mapped[str | None] = mapped_column(Text)
    operated_by: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class SagittalPresetRow(Base):
    __tablename__ = "sagittal_preset"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)   # L01..L30 或音标名
    layer: Mapped[str] = mapped_column(String(16))
    target_sound: Mapped[str] = mapped_column(String(16))
    keyframes: Mapped[str] = mapped_column(Text)      # JSON
