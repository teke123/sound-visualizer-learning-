"""模型状态、模型加载、上传诊断和关卡查询的 HTTP 路由。"""
from dataclasses import asdict
import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.asr_analyzer import DEFAULT_MODEL_ID, get_analyzer
from backend.audio.diagnosis import diagnose_upload
from backend.levels import FROZEN_SINCE, LEVELS, LEVELS_BY_ID

router = APIRouter(tags=["ASR 诊断"])


class LoadModelRequest(BaseModel):
    model_id: str = DEFAULT_MODEL_ID
    force: bool = False


@router.get("/api/asr/status")
def asr_status():
    return {"service": "asr", "version": "1.0", **get_analyzer().status()}


@router.post("/api/asr/load")
def asr_load(payload: LoadModelRequest | None = None):
    request = payload or LoadModelRequest()
    started_at = time.perf_counter()
    result = get_analyzer().load(model_id=request.model_id, force=request.force)
    result["api_ms"] = round((time.perf_counter() - started_at) * 1000, 1)
    return result


@router.post("/api/asr/diagnose")
def asr_diagnose(
    file: UploadFile = File(...),
    level_id: str = Form(""),
    target_pinyin: str = Form(""),
):
    """校验目标参数，调用上传诊断流程并返回结果。"""
    if not level_id and not target_pinyin:
        raise HTTPException(422, "需要 level_id 或 target_pinyin")
    if level_id and level_id not in LEVELS_BY_ID:
        raise HTTPException(422, f"未知关卡：{level_id}")
    return diagnose_upload(
        file.file.read(), file.filename,
        level_id=level_id or None, target_pinyin=target_pinyin or None,
    )


@router.get("/api/levels")
def levels():
    return {"frozen_since": FROZEN_SINCE, "count": len(LEVELS),
            "levels": [asdict(level) for level in LEVELS]}
