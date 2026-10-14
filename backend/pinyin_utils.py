# -*- coding: utf-8 -*-
"""拼音工具（重构占位骨架）。

意图：声母/韵母/声调拆分、字->拼音反查（诊断候选字集合）、多音字消歧。
拼写规则集中在此定义：v->ü、y/j/q/x 后的 u 实为 ü、y/w 零声母口径。
"""

# 声母表（拼写规格，长声母优先匹配）
INITIALS = (
    "zh", "ch", "sh",
    "b", "p", "m", "f", "d", "t", "n", "l",
    "g", "k", "h", "j", "q", "x",
    "r", "z", "c", "s", "y", "w",
)


def parse_pinyin(py: str) -> tuple[str, str, int]:
    """意图：解析拼音为 (声母, 韵母, 声调)；声调 1-4，0 表示轻声/无调。"""
    raise NotImplementedError("重构占位：拼音解析")


def strip_semivowel(initial: str, final: str) -> str:
    """意图：y/w 在 i/u/ü 前只是拼写形式，零声母音节声母记 ''。"""
    raise NotImplementedError("重构占位：半元音处理")


def char_pinyin(ch: str) -> str:
    """意图：单字 -> 拼音(带调)，多音字取默认读音。"""
    raise NotImplementedError("重构占位：字转拼音")


def char_pinyin_matching(ch: str, init: str, final: str, prefer_tone: int | None = None) -> str:
    """意图：多音字消歧——取与目标(声母, 韵母[, 声调])匹配的那条读音。"""
    raise NotImplementedError("重构占位：多音字消歧")


def chars_for_pinyin(py: str) -> list[str]:
    """意图：同拼音同声调的全部汉字（闭集候选）。"""
    raise NotImplementedError("重构占位：拼音反查")


def chars_for_base(initial: str, final: str) -> list[str]:
    """意图：同声母+韵母、任意声调的全部汉字（声调放宽时的候选）。"""
    raise NotImplementedError("重构占位：声韵反查")
