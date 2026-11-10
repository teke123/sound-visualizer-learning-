"""声学图像提取（docs/声学图像提取/方案.md 的实现）。

输入一条录音（原始采样率 WAV）与其音节/音素对齐，按方案的三个层次生成图像与数值表：
通用层（波形、宽带/窄带/Mel 频谱、F0、强度、共振峰、谐波谱）、音素层（按声母发音方式
启动塞音/擦音/塞擦音/鼻音/近音专项分析）、发声态与声调层。共享约定见 common.py，
批量入口见 cli.py。
"""
from __future__ import annotations

import importlib
import time
import traceback
from pathlib import Path

from .common import Alignment, DbScales

# 按出图编号顺序执行：prosody 01/05/06，basic_spectra 02–04，formants 07–08，
# obstruents 09–11/14，sonorants 12–13，phonation 15–20
MODULES = ("prosody", "basic_spectra", "formants", "obstruents", "sonorants", "phonation")


def generate_all(x, sr: int, aln: Alignment, out_dir: str | Path, scales: DbScales | None = None,
                 context: dict | None = None, modules: tuple[str, ...] = MODULES) -> dict:
    """对一条录音依次运行各图像模块，返回 {模块名: 模块结果}。

    单个模块抛出异常时，异常信息记录在该模块结果的 "error" 中，其余模块照常运行，
    以免一条录音的个别问题中断整批处理。
    """
    results: dict = {}
    for name in modules:
        start = time.perf_counter()
        try:
            module = importlib.import_module(f"{__name__}.{name}")
            res = module.generate(x, sr, aln, Path(out_dir), scales=scales, context=context)
        except Exception as e:
            res = {"images": {}, "tables": {}, "params": {}, "warnings": [],
                   "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}
        res["seconds"] = round(time.perf_counter() - start, 2)
        results[name] = res
    return results
