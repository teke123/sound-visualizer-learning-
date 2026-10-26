# -*- coding: utf-8 -*-
"""冻结的 30 关目标音(L01-L30)。

冻结说明(2026-09-27,全员任务 CON-02):
  L01-L06  单韵母 a o e i u ü(6 个)
  L07-L29  声母 b p m f d t n l g k h j q x zh ch sh r z c s y w(21 + y + w = 23 个)
  L30      "妈"拼读 m+a,四声 mā/má/mǎ/mà 均判正确,同时报告实测声调
ID / 顺序 / 目标音一经冻结,不得为凑数改动或插空关;如需调整须全组确认后整体改本文件。
P01-P10 十页结构属前端页面冻结,不在本文件范围内。
"""
from __future__ import annotations

from dataclasses import dataclass

from .pinyin_utils import chars_for_base, chars_for_pinyin, parse_pinyin, strip_semivowel

FROZEN_SINCE = "2026-09-27"


@dataclass(frozen=True)
class Level:
    level_id: str
    order: int
    category: str        # 单韵母 / 声母 / 拼读
    target_name: str     # 界面展示名: a / ü / b / zh / 妈
    target_pinyin: str   # 标准读音(带声调),诊断基准
    initial: str         # 期望声母('' = 零声母)
    final: str
    tone: int | None     # None = 不限定声调
    tone_strict: bool    # 是否严格要求声调
    note: str = ""


def _mk(level_id: str, order: int, name: str, py: str, note: str = "") -> Level:
    i, f, t = parse_pinyin(py)
    # 声母关(L07-L29)训练目标是声母本身,呼读音声调不作为评分依据 → 声调放宽;
    # 单韵母关(L01-L06)按标准读音(带声调)严格比对。
    tone_strict = order <= 6
    return Level(level_id, order, "单韵母" if order <= 6 else "声母", name, py,
                 strip_semivowel(i, f), f, t, tone_strict, note)


LEVELS: list[Level] = [
    # ---- 单韵母 6 ----
    _mk("L01", 1, "a", "ā"),
    _mk("L02", 2, "o", "ō"),
    _mk("L03", 3, "e", "ē"),
    _mk("L04", 4, "i", "yī", "读作 yī/一"),
    _mk("L05", 5, "u", "wū", "读作 wū/乌"),
    _mk("L06", 6, "ü", "yū", "读作 yū/迂"),
    # ---- 声母 23(21 + y + w) ----
    _mk("L07", 7, "b", "bō"), _mk("L08", 8, "p", "pō"),
    _mk("L09", 9, "m", "mō"), _mk("L10", 10, "f", "fō"),
    _mk("L11", 11, "d", "dē"), _mk("L12", 12, "t", "tē"),
    _mk("L13", 13, "n", "nē"), _mk("L14", 14, "l", "lē"),
    _mk("L15", 15, "g", "gē"), _mk("L16", 16, "k", "kē"),
    _mk("L17", 17, "h", "hē"),
    _mk("L18", 18, "j", "jī"), _mk("L19", 19, "q", "qī"),
    _mk("L20", 20, "x", "xī"),
    _mk("L21", 21, "zh", "zhī"), _mk("L22", 22, "ch", "chī"),
    _mk("L23", 23, "sh", "shī"), _mk("L24", 24, "r", "rī"),
    _mk("L25", 25, "z", "zī"), _mk("L26", 26, "c", "cī"),
    _mk("L27", 27, "s", "sī"),
    Level("L28", 28, "声母", "y", "yī", "y", "i", 1, False, "呼读音 yī(声母计 y);声调放宽"),
    Level("L29", 29, "声母", "w", "wū", "w", "u", 1, False, "呼读音 wū(声母计 w);声调放宽"),
    # ---- 拼读 ----
    Level("L30", 30, "拼读", "妈", "mā", "m", "a", None, False,
          "m+a 拼读;四声 mā/má/mǎ/mà 均判正确并报告实测声调"),
]

LEVELS_BY_ID: dict[str, Level] = {lv.level_id: lv for lv in LEVELS}
LEVEL_ORDER: list[str] = [lv.level_id for lv in LEVELS]


def candidate_chars(level: Level) -> tuple[list[str], bool]:
    """目标音的候选字集合 + 是否声调严格。

    呼读音 rī/nē/dē 等无同调汉字 → 自动放宽为"同声韵任意调"(返回 tone_strict=False)。
    """
    if level.tone is None or not level.tone_strict:
        return chars_for_base(level.initial, level.final), False
    exact = chars_for_pinyin(level.target_pinyin)
    if exact:
        return exact, True
    return chars_for_base(level.initial, level.final), False
