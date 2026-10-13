"""声调曲线匹配、流利度计算与发音分数汇总。"""
import numpy as np
import librosa
from .models import AcousticFeatures, ScoringEvidence, ScoringReference, ScoreResult

FRAME_LENGTH = 2048
HOP_LENGTH = 512


def compute_fluency_score(y: np.ndarray, sr: int) -> float:
    """根据能量阈值和停顿比例计算流利度分数。"""
    rms = librosa.feature.rms(
        y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH
    )[0]
    if len(rms) == 0 or rms.max() < 1e-8:
        return 0.0
    floor = float(np.percentile(rms, 20))
    peak = float(rms.max())
    threshold = max(floor * 2.0, peak * 0.08)
    voiced = rms >= threshold
    if not np.any(voiced):
        return 10.0
    frame_time = HOP_LENGTH / sr
    total_dur = len(voiced) * frame_time
    voiced_dur = float(np.sum(voiced)) * frame_time
    voice_ratio = voiced_dur / total_dur if total_dur > 0 else 0.0

    # 统计停顿次数与总停顿时长
    pauses = 0
    total_pause = 0.0
    in_pause = False
    for v in voiced:
        if not v:
            if not in_pause:
                pauses += 1
                in_pause = True
            total_pause += frame_time
        else:
            in_pause = False

    score = 100.0
    # 有效发声比例过低的惩罚
    if voice_ratio < 0.3:
        score -= 30
    # 停顿惩罚
    pause_ratio = total_pause / (voiced_dur + 1e-6)
    score -= min(40, pause_ratio * 40)
    return float(max(10.0, min(100.0, score)))


def standard_tone_curve(tone: int, n: int = 100) -> np.ndarray:
    """生成标准声调 F0 曲线模板"""
    t = np.linspace(0, 1, n)
    if tone == 1:      # 阴平：高平
        return np.full(n, 200.0)
    if tone == 2:      # 阳平：上升
        return 140 + 60 * t
    if tone == 3:      # 上声：先降后升
        return 185 - 65 * t + 105 * np.maximum(0, t - 0.5)
    if tone == 4:      # 去声：下降
        return 220 - 80 * t
    return np.full(n, 180.0)


def resample_1d(x: np.ndarray, n: int) -> np.ndarray:
    """按等间隔索引将一维数组采样到指定长度。"""
    if len(x) < 2:
        return np.full(n, float(x[0]) if len(x) else 0.0)
    idx = np.linspace(0, len(x) - 1, n).astype(int)
    return np.asarray(x, dtype=np.float64)[idx]


def tone_shape_score(f0_voiced: np.ndarray, ref_tone: int) -> float:
    """通过 F0 曲线形状与标准声调模板的相关系数评估声调准确性"""
    if len(f0_voiced) < 5:
        return 0.0
    standard = standard_tone_curve(ref_tone)
    user_curve = resample_1d(f0_voiced, len(standard))
    # 避免常数数组导致相关系数除零（出现 RuntimeWarning / NaN）
    if np.std(user_curve) < 1e-6 or np.std(standard) < 1e-6:
        return 50.0
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = np.corrcoef(user_curve, standard)[0, 1]
    if np.isnan(corr):
        corr = 0.0
    return float(max(0.0, min(100.0, 55 + corr * 45)))


def assess_pronunciation(
    features: AcousticFeatures,
    evidence: ScoringEvidence,
    reference: ScoringReference,
    fluency: float,
) -> ScoreResult:
    """结合基频统计、分项分数和参考参数计算综合分。"""
    # 计算基频相似度
    f0_array = np.array(features.f0)
    f0_voiced = f0_array[f0_array > 0]

    if len(f0_voiced) > 0:
        f0_mean = np.mean(f0_voiced)
        f0_std = np.std(f0_voiced)
        f0_similarity = max(0, 100 - abs(f0_mean - reference.f0_mean) / reference.f0_mean * 100)
        tone_stability = max(0, 100 - f0_std / reference.f0_std * 20)
    else:
        f0_mean = 0
        f0_std = 0
        f0_similarity = 0
        tone_stability = 0

    # 流利度：由调用方传入（真实VAD计算）
    fluency = fluency if fluency > 0 else 50.0

    # 发音准确度 = 音素级深度学习评分 与 基频相似度 加权
    phoneme_score = evidence.phoneme_score
    if phoneme_score > 0:
        accuracy = (phoneme_score * 0.5 + f0_similarity * 0.3 + tone_stability * 0.2)
    else:
        accuracy = (f0_similarity * 0.6 + tone_stability * 0.4)

    # 声调评估（深度学习声调评分 + 基频稳定性）
    tone_score = evidence.tone_score
    if tone_score > 0:
        tone_combined = tone_score * 0.6 + tone_stability * 0.4
    else:
        tone_combined = tone_stability

    pronunciation = (accuracy * 0.5 + tone_combined * 0.3 + fluency * 0.2)
    score = (accuracy * 0.35 + tone_combined * 0.25 + fluency * 0.2 + pronunciation * 0.2)

    return ScoreResult(
        score=round(score, 1),
        accuracy=round(accuracy, 1),
        fluency=round(fluency, 1),
        pronunciation=round(pronunciation, 1),
        tone_combined=tone_combined,
        f0_mean=float(f0_mean),
        f0_std=float(f0_std),
    )
