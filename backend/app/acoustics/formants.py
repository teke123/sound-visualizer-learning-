"""共振峰测量核心：产品线（发音证据、特征读取接口、个人标定）与批处理线（声学图像）
共用的 Praat Burg 共振峰提取实现，各处不再自行调用 Praat。

- 提取（extract）：Praat "To Formant (burg)"，5 ms 帧移、最多 5 个共振峰、25 ms 分析窗、
  50 Hz 预加重，一次读出 F1–F4 与带宽 B1–B4；未定义的共振峰与带宽记 NaN；
- 共振峰上限（maximum formant）：未取得个人标定值时按有声帧基频中位数分档（default_ceiling）；
- 带宽（bandwidth_plausible）：取值范围外的带宽视为该共振峰不可信，发声态模块的幅度修正
  也用同一范围；
- 离群点（outlier_mask）：偏离 5 帧中值超过 20% 的帧；
- 逐韵母的上限选择（select_ceiling）与 vowel_formants()：批处理线在每个韵母上重新选择上限，
  发声态等模块与出图共用同一份结果。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.acoustics.imagery import common

N_FORMANTS = 4                       # 提取 F1–F4 与带宽 B1–B4
TIME_STEP = 0.005                    # Burg 时间步长（秒）
MAX_NUMBER_OF_FORMANTS = 5           # 最大共振峰数目
WINDOW_LENGTH = 0.025                # 分析窗长度（秒）
PRE_EMPHASIS_FROM = 50.0             # 预加重起始频率（Hz）
BANDWIDTH_RANGE_HZ = (30.0, 600.0)   # 带宽的合理取值范围（Hz）

MALE_F0_MEDIAN = 165.0               # 有声帧基频中位数低于该值按男声选择共振峰上限
CEILING_MALE_HZ, CEILING_FEMALE_HZ = 5000.0, 5500.0

CEILING_STEP = 250.0                 # 逐韵母选择上限的候选步长（Hz）
CEILING_SEARCH_RANGE = 500.0         # 候选范围：发音人初始值 ±（Hz），只做窄范围修正
MIN_VALID_FRAMES = 5                 # 候选有效性要求的最少有效帧数
OUTLIER_FILTER_FRAMES = 5            # 离群点判定的中值滤波窗长（帧）
OUTLIER_DEVIATION = 0.2              # 偏离中值超过该比例的帧为离群点


# ---------------- 提取 ----------------

@dataclass
class FormantTrack:
    """整条录音的一次 Burg 提取结果。"""
    times: np.ndarray          # 帧中心时间（秒）
    freqs: np.ndarray          # F1–F4 频率（4 × n，Hz；未定义帧为 NaN）
    bandwidths: np.ndarray     # B1–B4 带宽（4 × n，Hz；未定义帧为 NaN）
    time_step: float           # 实际帧步长（秒）
    first_time: float          # 首帧中心时间（秒）


def default_ceiling(median_f0_hz: float) -> float:
    """未取得个人标定值时的共振峰上限：按有声帧基频中位数分档。"""
    return CEILING_MALE_HZ if median_f0_hz < MALE_F0_MEDIAN else CEILING_FEMALE_HZ


def to_formant_burg(snd, ceiling: float, *, time_step: float = TIME_STEP,
                    window_length: float = WINDOW_LENGTH):
    """Praat "To Formant (burg)"；除共振峰上限、时间步长与窗长外用固定参数。"""
    return snd.to_formant_burg(time_step=time_step, max_number_of_formants=MAX_NUMBER_OF_FORMANTS,
                               maximum_formant=ceiling, window_length=window_length,
                               pre_emphasis_from=PRE_EMPHASIS_FROM)


def formant_arrays(fm, n_formants: int = N_FORMANTS) -> tuple[np.ndarray, np.ndarray]:
    """Formant 对象 → (频率, 带宽)，形状均为 n_formants × 帧数；未定义的共振峰与带宽记 NaN。"""
    times = np.asarray(fm.xs(), dtype=float)
    freqs = np.full((n_formants, len(times)), np.nan)
    bandwidths = np.full((n_formants, len(times)), np.nan)
    for i, t in enumerate(times):
        for k in range(n_formants):
            f = fm.get_value_at_time(k + 1, t)
            if f is not None and np.isfinite(f) and f > 0:
                freqs[k, i] = f
                b = fm.get_bandwidth_at_time(k + 1, t)
                if b is not None and np.isfinite(b):
                    bandwidths[k, i] = b
    return freqs, bandwidths


def extract(snd, ceiling: float, *, time_step: float = TIME_STEP,
            window_length: float = WINDOW_LENGTH) -> FormantTrack:
    """整条录音的 F1–F4 与带宽 B1–B4。"""
    fm = to_formant_burg(snd, ceiling, time_step=time_step, window_length=window_length)
    freqs, bandwidths = formant_arrays(fm)
    return FormantTrack(times=np.asarray(fm.xs(), dtype=float), freqs=freqs, bandwidths=bandwidths,
                        time_step=float(fm.dx), first_time=float(fm.x1))


def bandwidth_plausible(bandwidths: np.ndarray) -> np.ndarray:
    """带宽取值在 BANDWIDTH_RANGE_HZ 内的帧（NaN 视为不可信）。"""
    low, high = BANDWIDTH_RANGE_HZ
    bandwidths = np.asarray(bandwidths, dtype=float)
    return np.isfinite(bandwidths) & (bandwidths >= low) & (bandwidths <= high)


# ---------------- 有效帧与上限选择 ----------------

def outlier_mask(track: np.ndarray, window: int = OUTLIER_FILTER_FRAMES,
                 deviation: float = OUTLIER_DEVIATION) -> np.ndarray:
    """离群点：偏离 5 帧中值滤波超过 20% 的帧（NaN 帧不参与也不判为离群）。"""
    n = len(track)
    half = window // 2
    mask = np.zeros(n, dtype=bool)
    for i in range(n):
        if not np.isfinite(track[i]):
            continue
        neighborhood = track[max(0, i - half):i + half + 1]
        median = float(np.median(neighborhood[np.isfinite(neighborhood)]))
        if np.isfinite(median) and abs(track[i] - median) > deviation * median:
            mask[i] = True
    return mask


def trajectory_score(t: np.ndarray, formants: np.ndarray) -> float:
    """候选打分：每个共振峰对时间做三次多项式拟合，残差均方根 ÷ 该共振峰中位数，三个相加。

    得分越低轨迹越平滑；用于在 ceiling 候选中挑选共振峰轨迹最一致的分析结果。
    """
    total = 0.0
    for k in range(formants.shape[0]):
        y = formants[k]
        coefficients = np.polyfit(t, y, 3)
        residuals = np.polyval(coefficients, t) - y
        total += float(np.sqrt(np.mean(residuals ** 2))) / float(np.median(y))
    return total


def burg_cache(snd):
    """按 ceiling 缓存 Burg 的 (F1–F4, B1–B4)；帧网格与 ceiling 无关，各候选完全对齐。"""
    cache: dict[float, tuple[np.ndarray, np.ndarray]] = {}

    def get(ceiling: float) -> tuple[np.ndarray, np.ndarray]:
        key = round(float(ceiling), 6)
        if key not in cache:
            cache[key] = formant_arrays(to_formant_burg(snd, key))
        return cache[key]

    return get


def select_ceiling(burg, times: np.ndarray, frames: np.ndarray, default: float,
                   label: str) -> tuple[float, dict[float, float | None], str | None]:
    """在默认 ceiling ±500 Hz 的候选中打分选值；返回 (所选 ceiling, 各候选得分, 告警文字或 None)。

    打分帧由 frames 给出（元音区间内且非低能量）；无合格候选时回退默认值并给出告警。
    """
    candidates = [default + k * CEILING_STEP
                  for k in range(int(-CEILING_SEARCH_RANGE / CEILING_STEP),
                                 int(CEILING_SEARCH_RANGE / CEILING_STEP) + 1)]
    scores: dict[float, float | None] = {}
    for candidate in candidates:
        formant3 = burg(candidate)[0][:3, frames]
        valid = np.isfinite(formant3).all(axis=0)
        if int(valid.sum()) < MIN_VALID_FRAMES:
            scores[candidate] = None
            continue
        values = formant3[:, valid]
        if not np.all((values[0] < values[1]) & (values[1] < values[2])):
            scores[candidate] = None
            continue
        scores[candidate] = trajectory_score(times[frames][valid], values)
    qualified = {c: s for c, s in scores.items() if s is not None}
    if qualified:
        return min(qualified, key=qualified.get), scores, None
    warning = (f"韵母 {label} 没有满足 F1<F2<F3 且有效帧 ≥ {MIN_VALID_FRAMES} 的 "
               f"ceiling 候选，回退默认 {default:.0f} Hz")
    return default, scores, warning


def low_level_frames(x: np.ndarray, sr: int, aln: common.Alignment,
                     times: np.ndarray) -> np.ndarray:
    """低能量帧（common.short_time_level_db + low_level_mask）：电平比所在音节最大电平
    低 30 dB 以上；不在任何音节内的帧按全录音最大电平比较。"""
    level = common.short_time_level_db(x, sr, times)
    mask = common.low_level_mask(level, times, 0.0, aln.duration)
    for si, syllable in enumerate(aln.syllables):
        limit = aln.syllables[si + 1].t0 if si + 1 < len(aln.syllables) else aln.duration
        inside = (times >= syllable.t0) & (times < limit)
        if inside.any():
            mask[inside] = common.low_level_mask(level, times, syllable.t0, limit)[inside]
    return mask


def f0_nearest(f0_times: np.ndarray, f0: np.ndarray, t_query: np.ndarray) -> np.ndarray:
    """每个查询时刻取最近 F0 帧的值（无声帧为 NaN，不当作 0）。"""
    idx = np.abs(f0_times[:, None] - np.asarray(t_query)[None, :]).argmin(axis=0)
    return f0[idx]


# ---------------- 单个韵母 ----------------

@dataclass
class VowelFormants:
    """单个韵母的共振峰分析结果（vowel_formants 的返回值，供发声态等模块复用）。

    所有数组只含元音区间（common.vowel_interval）内的 Burg 帧，按时间升序。
    """
    label: str              # 韵母标签（无韵母段时为音节拼音）
    ceiling_hz: float       # 该韵母自动选中的 formant ceiling（Hz）
    t0: float               # 元音区间起点（秒，可能后移到首个有声帧）
    t1: float               # 元音区间终点（秒，可能沿有效帧延伸）
    start_source: str       # 起点来源："first_voiced" | "alignment"
    end_source: str         # 终点来源："voicing_extended" | "alignment"
    times: np.ndarray       # 帧中心时间（秒）
    freqs: np.ndarray       # F1–F4 频率（4×n，Hz；Burg 缺失的峰为 NaN）
    bands: np.ndarray       # B1–B4 带宽（4×n，Hz；缺失为 NaN）
    valid: np.ndarray       # 有效帧标志（n）：非低能量且 F1–F3 均非离群点，
                            # 与 07 图的有效帧同一规则；无效帧的值仅供参考
    f0: np.ndarray          # 每帧 F0（Hz，最近 F0 帧取值；无声/嘎裂帧为 NaN）


def vowel_formants(x: np.ndarray, sr: int, aln: common.Alignment, syll_index: int,
                   profile: common.SpeakerProfile) -> VowelFormants:
    """第 syll_index 个音节韵母的共振峰（发声态等模块与本模块 generate 共用的同一份计算）。

    区间用 common.vowel_interval，ceiling 在 profile.formant_ceiling ±500 Hz 内自动选择，
    有效帧 = 区间内 且 非低能量 且 非离群点（与 07 图同一规则）。
    """
    syllable = aln.syllables[syll_index]
    final = syllable.final
    interval = common.vowel_interval(aln, syll_index, x, sr, profile)
    snd = common.to_sound(x, sr)
    pitch = common.pitch_filtered_ac(snd, profile)
    f0_times, f0 = common.pitch_arrays(pitch)
    times = np.asarray(to_formant_burg(snd, profile.formant_ceiling).xs(), dtype=float)
    burg = burg_cache(snd)
    low_level = low_level_frames(x, sr, aln, times)
    label = final.label if final else syllable.symbol
    in_span = (times >= interval.t0) & (times <= interval.t1)
    chosen, _, _ = select_ceiling(burg, times, in_span & ~low_level,
                                  profile.formant_ceiling, label)
    freqs, bands = (a[:, in_span].copy() for a in burg(chosen))
    outliers = np.vstack([outlier_mask(freqs[k]) for k in range(3)])
    valid = ~low_level[in_span] & ~outliers.any(axis=0)
    return VowelFormants(label=label, ceiling_hz=chosen,
                         t0=interval.t0, t1=interval.t1,
                         start_source=interval.start_source, end_source=interval.end_source,
                         times=times[in_span], freqs=freqs, bands=bands, valid=valid,
                         f0=f0_nearest(f0_times, f0, times[in_span]))
