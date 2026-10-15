"""ScoringProvider 协议与结果类型（ADR-2：外部评分 + Provider 隔离）。

Provider 只做「对指定评测文本的评分与检错」；质量两维判定、规则四步、
曲线与换算都在本模块内。发给 Provider 的只有规范化音频与评测文本。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SyllableEval:
    text: str                       # 期望音节（汉字）
    pinyin: str | None = None       # 带调拼音
    t0: float = 0.0                 # 音节时间戳（秒，音频内）
    t1: float = 0.0
    initial_ok: bool = True
    final_ok: bool = True
    tone_ok: bool = True
    tone_value: int | None = None   # 期望声调 1-4
    detail: dict = field(default_factory=dict)


@dataclass
class ProviderResult:
    provider_version: str
    overall_score: float = 100.0
    initial_score: float | None = None
    final_score: float | None = None
    tone_score: float | None = None
    # 朗读维检错（FR-1301 维度二）：漏读/增读/回读/替换/乱读
    reading: dict = field(default_factory=lambda: {
        "missing": [],        # 漏读音节文本
        "extra": [],          # 增读文本
        "repeated": [],       # 回读文本
        "replaced": [],       # 替换文本
        "disordered": False,  # 乱读（胡乱朗读）
    })
    syllables: list[SyllableEval] = field(default_factory=list)
    raw: dict = field(default_factory=dict)   # 原始响应骨架（诊断用，不下发用户）


class ProviderError(Exception):
    """Provider 不可达/超时/返回不可解析。"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind    # down | timeout | bad_response


class ScoringProvider:
    """实现须线程安全；调用不在数据库事务内。"""

    name: str = "base"
    version: str = "base-0"

    def evaluate(self, wav_path: str, evaluation_text: str) -> ProviderResult:
        raise NotImplementedError
