"""模型状态、模型加载与上传诊断的 HTTP 路由（重构占位骨架）。"""
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["ASR 诊断"])


@router.get("/api/asr/status")
def asr_status():
    """意图：模型加载状态、设备与推理统计。"""
    raise HTTPException(501, "重构占位：ASR 状态")


@router.post("/api/asr/load")
def asr_load():
    """意图：加载/切换模型（本地 -> 缓存 -> 远程逐级降级），返回耗时。"""
    raise HTTPException(501, "重构占位：ASR 模型加载")


@router.post("/api/asr/diagnose")
def asr_diagnose():
    """意图：上传音频 + 目标（关卡或拼音），返回结构化诊断结果。"""
    raise HTTPException(501, "重构占位：ASR 诊断")
