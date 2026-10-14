"""声调曲线匹配、流利度计算与发音分数汇总（重构占位骨架）。

定位（对齐 SRS）：1.0 的分数与音节粒度检错来自外部普通话评分服务
（FR-1205）；本模块服务于曲线/声学工具层（FR-1005 曲线对比、FR-1006
音域换算）与 2.0 的专属纠音模型对比（FR-1605），不进 1.0 主评分链路。

意图（重构时重新设计公式，旧公式连同已知缺陷一并删除）：
- 流利度：由 VAD 停顿/语速计算；「静音」判定必须与 quality 模块同一口径；
- 声调形状：用户 F0 曲线与标准调形比较；比较必须在归一化（T 值）域进行，
  且要能区分「调形错误」与「曲线噪声」；平调 vs 单调曲线不得判及格；
- 综合分：各分项定义清晰、权重可解释，仅由本关已开放维度合成
  （FR-1003：未开放维度不计入分数；一个分项不得经另一个分项重复计入）。
"""
import numpy as np

from .models import AcousticFeatures, ScoringEvidence, ScoringReference, ScoreResult


def compute_fluency_score(y: np.ndarray, sr: int) -> float:
    """意图：按有效发声比例与停顿计算流利度（0-100）。"""
    raise NotImplementedError("重构占位：流利度评分")


def tone_shape_score(f0_voiced: np.ndarray, ref_tone: int) -> float:
    """意图：F0 调形与标准声调模板的相似度（0-100）。"""
    raise NotImplementedError("重构占位：声调形状评分")


def assess_pronunciation(
    features: AcousticFeatures,
    evidence: ScoringEvidence,
    reference: ScoringReference,
    fluency: float,
) -> ScoreResult:
    """意图：汇总声学、音素、声调与流利度得到综合分（权重可解释、不嵌套）。"""
    raise NotImplementedError("重构占位：综合评分")
