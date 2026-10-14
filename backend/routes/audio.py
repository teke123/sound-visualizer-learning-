"""音频处理路由（重构占位骨架）——工具端点，非评分主链路。

1.0 的评分主链路是「录音提交 → 质量两维 → 外部普通话评分服务」
（FR-1205）；本组端点只承担声学工具能力：
- POST /api/audio/features：上传录音，返回声学特征（F0/F1/F2/能量/MFCC + 时间轴）；
- POST /api/audio/quality ：录音质量检查（两维中的维度一，FR-1301）；
- POST /api/audio/score   ：本地声学栈评分（2.0 专属纠音模型对比用，FR-1605）。
上传约束沿用旧口径：限 20 MiB、文件名只取后缀。
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/audio", tags=["音频处理"])


@router.post("/features")
def extract_features():
    raise HTTPException(501, "重构占位：声学特征提取")


@router.post("/quality")
def check_quality():
    raise HTTPException(501, "重构占位：录音质量检测")


@router.post("/score")
def score_pronunciation():
    raise HTTPException(501, "重构占位：发音评分")
