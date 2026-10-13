"""质量、声学参数和评分接口的占位路由，统一返回 HTTP 501。"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/audio", tags=["音频处理（待实现）"])


@router.post("/quality", status_code=501)
def check_quality():
    """返回质量检测接口的未实现状态。"""
    raise HTTPException(501, "独立质量检测接口尚未实现")


@router.post("/features", status_code=501)
def extract_features():
    """返回声学参数接口的未实现状态。"""
    raise HTTPException(501, "独立声学参数接口尚未实现")


@router.post("/score", status_code=501)
def score_pronunciation():
    """返回评分接口的未实现状态。"""
    raise HTTPException(501, "独立评分接口尚未实现")
