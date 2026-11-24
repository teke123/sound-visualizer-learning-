"""Build and run an optional multimodal request after the score is saved."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import update

from app.db import JSONText, get_session
from app.detection.models import PronunciationAdviceRow, RecordingRow
from app.llm.gemini import generate_json
from app.pinyin_utils import annotated_syllables
from app.platform.executor import BoundedExecutor

logger = logging.getLogger("svs")
_executor = BoundedExecutor(workers=2, queue_limit=8)
PARTS = ("initial", "final", "tone")
REASONS = ("poor_audio", "insufficient_evidence", "conflicting_evidence")

SYSTEM_PROMPT = """你是普通话发音教练。只处理输出 Schema 指定的音节和部位。键 sN_part 中 N 是从 0 开始的音节编号，initial、final、tone 分别表示声母、韵母、声调。passed 是讯飞判定通过的部位，无需点评。
practice 是页面上的发音要领。禁止重复通用说明中的标准定义。

先听录音，再用波形和语谱图核对。对齐边界、音高、共振峰、事件位置和声学数值都由程序自动估计，可能有误。归一化依赖自动测量和个人标定，也可能有误。它们仅供辅助；如果与录音或底图不符，可以忽略。有疑问的追踪结果及其归一化版本不能互相印证。

能辨认具体偏差时，返回 explained。analysis 用一句话描述本次录音中听到或看到的偏差；nextAction 给一个下一遍就能做的调整。可以建议怎样动舌或调整口型，但不要把录音无法确认的动作写成事实。

录音质量不足、可用证据不足，或证据矛盾且无法消解时，返回 unable_to_assess，选择最贴切的 reasonCode，不写分析或建议。逐项判断，一项无法判断不影响其他项。
用简明中文，只返回符合 Schema 的 JSON。"""


@dataclass
class AdviceRequest:
    context: dict
    targets: dict[str, dict]
    parts_by_index: dict[int, set[str]]


def plan_request(provider, detection: dict, practice: list[str]) -> AdviceRequest | None:
    """Use explicit phone results; missing diagnostics do not count as passed."""
    if not provider.provider_version.startswith("xfyun") or provider.reading.get("disordered"):
        return None
    try:
        expected = annotated_syllables(detection.get("evaluationText", ""),
                                       detection.get("evaluationPinyin", ""))
    except ValueError:
        return None
    if len(expected) != len(provider.syllables) or any(
            target["text"] != actual.text for target, actual in zip(expected, provider.syllables)
    ):
        return None
    syllables, targets, parts_by_index = [], {}, {}
    for index, (target, actual) in enumerate(zip(expected, provider.syllables)):
        phones = actual.detail.get("phones") or []
        checked = {}
        if not any(actual.detail.get(k) for k in ("dpMessage", "wordDpMessage", "syllableDpMessage")) and all(
                phone.get("dpMessage", 0) == 0 for phone in phones):
            initials = [p["perrMsg"] for p in phones if p.get("part") == "initial"
                        and not (p.get("content") or "").startswith("_")
                        and p.get("perrMsg") in (0, 1)]
            finals = [p["perrMsg"] for p in phones if p.get("part") == "final"
                      and p.get("perrMsg") in (0, 1, 2, 3)]
            if initials:
                checked["initial"] = any(initials)
            if finals:
                checked["final"] = any(code in (1, 3) for code in finals)
                checked["tone"] = any(code in (2, 3) for code in finals)
        syllable = {"index": index, "text": target["text"], "pinyin": target["pinyin"]}
        syllables.append({**syllable, "passed": [part for part in PARTS if checked.get(part) is False]})
        for part in PARTS:
            if checked.get(part) is True:
                targets[f"s{index}_{part}"] = {**syllable, "part": part}
                parts_by_index.setdefault(index, set()).add(part)
    if not targets:
        return None
    return AdviceRequest({"syllables": syllables, "practice": practice}, targets, parts_by_index)


def response_schema(targets: dict[str, dict]) -> dict:
    def object_of(properties: dict) -> dict:
        return {"type": "object", "required": list(properties), "additionalProperties": False,
                "properties": properties}

    def enum(*values: str) -> dict:
        return {"type": "string", "enum": list(values)}

    sentence = {"type": "string", "minLength": 1}
    branches = [
        object_of({"status": enum("explained"), "analysis": sentence, "nextAction": sentence}),
        object_of({"status": enum("unable_to_assess"), "reasonCode": enum(*REASONS)}),
    ]
    return object_of({key: {"anyOf": branches} for key in targets})


def generate(request: AdviceRequest, path: Path, measured) -> list[dict]:
    from app.acoustics.pronunciation_figures.render import render_advice

    # The feature uses its own credentials; never fall back to another model's key.
    base = os.environ["LLM_PRONUNCIATION_BASE_URL"].strip().rstrip("/")
    model = os.environ["LLM_PRONUNCIATION_MODEL"].strip()
    key = os.environ["LLM_PRONUNCIATION_API_KEY"].strip()
    context = dict(request.context)
    if measured is not None:
        numbers = []
        for index, parts in request.parts_by_index.items():
            s = measured.syllables[index]
            consonant = s["consonant"] or {}
            if "initial" in parts and s["reliability"]["vot"]:
                numbers.append({"syllableIndex": index, "estimatedVotMs": consonant["vot_ms"],
                                "intervalSec": [consonant["release_s"], consonant["voicing_onset_s"]]})
        if numbers:
            context["automaticMeasurements"] = numbers
    png = render_advice(measured, request.parts_by_index) if measured is not None else None
    response = generate_json(
        SYSTEM_PROMPT, json.dumps(context, ensure_ascii=False, allow_nan=False), path, png,
        schema=response_schema(request.targets), model=model, api_key=key, base_url=base,
        timeout=float(os.environ.get("LLM_PRONUNCIATION_TIMEOUT", "45")),
    )
    return [{**target, **response[key]} for key, target in request.targets.items()]


def configured() -> bool:
    return all(os.environ.get(f"LLM_PRONUNCIATION_{name}", "").strip()
               for name in ("BASE_URL", "MODEL", "API_KEY"))


def _pending_update(recording_id: str):
    return update(PronunciationAdviceRow).where(
        PronunciationAdviceRow.recording_id == recording_id,
        PronunciationAdviceRow.status == "pending",
        RecordingRow.__table__.select().where(
            RecordingRow.id == recording_id, RecordingRow.deleted_at.is_(None)).exists(),
    )


def _finish(recording_id: str, status: str, items: list[dict] | None = None) -> None:
    with get_session() as db:
        db.execute(_pending_update(recording_id).values(
            status=status, items=JSONText.dump(items) if items is not None else None))
        db.commit()


def _run(recording_id: str, request: AdviceRequest, path: Path, measured) -> None:
    with get_session() as db:
        rec = db.get(RecordingRow, recording_id)
        if rec is None or rec.deleted_at is not None:
            return
    try:
        items = generate(request, path, measured)
    except Exception as exc:
        # Model/provider errors can carry request or response content.
        logger.warning("录音 %s 的发音建议生成失败 (%s)", recording_id, type(exc).__name__)
        _finish(recording_id, "unavailable")
        return
    _finish(recording_id, "ready", items)


def enqueue(recording_id: str, request: AdviceRequest, path: Path, measured) -> None:
    if _executor.try_submit(_run, recording_id, request, path, measured) is None:
        _finish(recording_id, "unavailable")


def recover_pending(db) -> None:
    db.execute(update(PronunciationAdviceRow).where(
        PronunciationAdviceRow.status == "pending").values(status="unavailable"))
    db.commit()
