"""LLM 发音建议输入包及离线导出。"""
from __future__ import annotations

import base64
from importlib.metadata import version
import json
from pathlib import Path

from . import measure
from .compare import compare
from .render import render, select_kinds

VERSION = "pronunciation-evidence-2.0"
SYSTEM_PROMPT = """你帮助外语学习者练习普通话。目标文本和用户背景提供本次练习的上下文。
按“观察事实、定位练习环节、给出一个可执行练习、说明复练目标”四步组织话术。
从 measurements 引用音节、字段和数值，结合所选图像解释发音过程。
根据 reliability=true 的指标和 can_use=true 的对比项提出针对性建议。
参考对比采用 comparison 中的有效差值；reference=null 时围绕本次测量和评分检错组织练习。
结合音域来源、频谱带宽及元音空间标定解释相应数值。录音质量需要改善时给出具体重录步骤。
依据本次发音表现选择练习，结合母语或方言背景调整讲解方式。
沿用输入中的评分、现象标签和检错结果，用简洁易懂的语言说明练习动作和复练目标。
"""


def metadata() -> dict:
    return {"schema_version": VERSION, "sample_rate_hz": measure.SR,
            "spectrogram_top_hz": measure.ANALYSIS_TOP_HZ,
            "sibilant_spectrum_start_hz": measure.SIBILANT_BAND_START_HZ,
            "parameters": {key: value for key, value in vars(measure).items()
                           if key.isupper() and isinstance(value, (str, int, float, tuple))},
            "software": {name: version(name) for name in ("numpy", "scipy", "praat-parselmouth", "matplotlib")},
            "units": {"time": "seconds; *_ms in milliseconds", "frequency": "Hz", "intensity": "relative dB"},
            "validation": {"learner_recordings": "pending", "noise_rise_diagnostic": False,
                           "nasal_coda_diagnostic": False}}


def _recording_json(a):
    data = measure.to_json(a)
    data["boundaries"] = []
    for left, right in zip(a.syllables, a.syllables[1:]):
        end, start = left["tone"]["end_degree"], right["tone"]["start_degree"]
        data["boundaries"].append({"left_index": left["index"], "right_index": right["index"],
                                   "end_degree": end, "start_degree": start,
                                   "difference": measure._rnd(start-end, 3) if start is not None and end is not None else None})
    return data


def build_bundle(learner: measure.Analysis, reference: measure.Analysis | None = None, *,
                 goal="general", context: dict | None = None, all_figures=False) -> dict:
    measurements = {"metadata": metadata(), "learner": _recording_json(learner),
                    "reference": _recording_json(reference) if reference else None,
                    "comparison": compare(learner, reference)}
    kinds = None if all_figures else select_kinds(learner, goal)
    images = render(learner, reference, kinds=kinds)
    result = {"status": "ready", "measurements": measurements,
              "images": [{"name": name, "mime_type": "image/png",
                          "data_url": "data:image/png;base64,"+base64.b64encode(data).decode("ascii")}
                         for name, data in images.items()],
              "llm_input": {"system_prompt": SYSTEM_PROMPT, "context": context or {},
                            "goal": goal, "image_names": list(images),
                            "measurements_key": "measurements"}}
    # 使用严格 JSON 校验持久化结果与 LLM 输入。
    json.dumps(result, ensure_ascii=False, allow_nan=False)
    return result


def export_bundle(bundle: dict, output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "measurements.json").write_text(json.dumps(bundle["measurements"], ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    for image in bundle["images"]:
        (out / image["name"]).write_bytes(base64.b64decode(image["data_url"].split(",", 1)[1]))
    llm_input = {**bundle["llm_input"], "measurements": bundle["measurements"]}
    (out / "llm_input.json").write_text(json.dumps(llm_input, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return out
