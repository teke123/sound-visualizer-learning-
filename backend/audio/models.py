"""声学特征、评分输入和评分结果的数据结构。"""
from pydantic import BaseModel, Field


class AcousticFeatures(BaseModel):
    """声学特征数组、发声标记及音频元数据。"""
    f0: list[float]
    f1: list[float]
    f2: list[float]
    energy: list[float]
    duration: float
    sample_rate: int
    mfcc: list[list[float]]
    voiced_flag: list[bool] = Field(default_factory=list)
    voiced_probs: list[float] = Field(default_factory=list)


class ScoringEvidence(BaseModel):
    """声调和音素的分项分数，取值范围为 0 到 100。"""
    tone_score: float
    phoneme_score: float

class ScoringReference(BaseModel):
    """评分使用的参考基频均值和标准差。"""
    f0_mean: float = Field(gt=0)
    f0_std: float = Field(gt=0)


class ScoreResult(BaseModel):
    """综合分、分项分数及反馈所需的基频统计。"""
    score: float
    accuracy: float
    fluency: float
    pronunciation: float
    tone_combined: float
    f0_mean: float
    f0_std: float
