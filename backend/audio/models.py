"""声学特征、评分输入和评分结果的数据契约（重构占位骨架）。

这些模型是对外契约的一部分：字段增删必须与前端/接口文档同步。
"""
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
    # 各算法的帧中心时间（秒），不可按数组索引跨轨迹对齐。
    f0_times: list[float] = Field(default_factory=list)
    formant_times: list[float] = Field(default_factory=list)
    energy_times: list[float] = Field(default_factory=list)
    mfcc_times: list[float] = Field(default_factory=list)
    pitch_strength: list[float] = Field(default_factory=list)
    engine: str = ""
    engine_version: str = ""
    praat_version: str = ""
    pitch_method: str = "ac"
    formant_method: str = "burg"
    parameters: dict[str, float] = Field(default_factory=dict)


class ScoringEvidence(BaseModel):
    """分维度分数（FR-1010：按关卡类型只输出评分服务能稳定返回的项）。

    取值范围 0-100；本关未开放的维度不填充（页面记「暂不评价」，
    且不计入总分，FR-1003）。
    """
    initial_score: float | None = None   # 声韵分（声母/韵母发音质量）
    tone_score: float | None = None      # 调型分（音高走向）


class ScoringReference(BaseModel):
    """评分使用的参考基频统计（口径待重构重新定义）。"""
    f0_mean: float = Field(gt=0)
    f0_std: float = Field(gt=0)


class ScoreResult(BaseModel):
    """分数维度的结果契约（FR-1010 / SRS 07 章外部接口）。

    完整检测结果对象稳定包含：质量、分数、现象、四步、可靠性、版本号；
    本模型只承载分数维度，其余字段由检测提交管线组装。
    重构要求：各分数的定义与权重必须可解释、互不嵌套重复计入；
    质量不合格时不产生本对象（FR-1301：不填分数与检测现象）。
    """
    score: float                          # 总分（仅由本关已开放维度合成）
    initial_score: float | None = None    # 声韵分
    tone_score: float | None = None       # 调型分
    f0_mean: float
    f0_std: float
