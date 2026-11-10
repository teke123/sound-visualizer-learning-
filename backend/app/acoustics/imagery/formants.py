"""共振峰、元音动态与谐波谱（方案 §3、§7.1、§9、§10 B）。

- 共振峰：Praat "To Formant (burg)" 提取 F1–F4 与带宽 B1–B4（有效帧规则见下文）。
  formant ceiling 按韵母自动选择（方案 §3.1 L139
  「ceiling 根据说话人调整」；思路参考 Escudero et al. 2009 与 FastTrack）：
  在发音人初始值 ±500 Hz 内以 250 Hz 为步长取 5 个候选，用韵母有声帧 F1–F3
  轨迹对三次多项式拟合的残差打分，取最平滑者。打分只用来在一个合理的窄范围内
  修正换轨，不能用来大范围搜索：轨迹平滑度无法排除峰合并或伪峰（本语料
  yi1_FV1 在 4500 Hz 时 F2 落到约 1490 Hz 的伪峰上，得分反而最低）。
- 敏感性检查（方案 §9）：在所选 ceiling ±500 Hz 上重跑，比较韵母有声帧的 F1–F3。
- 元音区间：统一用 common.vowel_interval —— 起点为韵母内首个有声帧（对齐把送气段
  划进韵母时后移，送气噪声不参与元音分析），终点沿连续有效帧延伸（对齐漏掉的尾部）。
- 有效帧：元音区间内、非低能量帧（短时 RMS 电平比音节最大电平低 30 dB 以上）、
  非离群点即为有效帧。不再逐帧要求 F0——嘎裂/气声段 F0 常漏检但仍有共振峰结构，
  区间内无 F0 的帧只把 F0 记为 NaN，共振峰值保留。区间外的帧不画。
- 离群点：F1–F3 轨迹偏离 5 帧中值滤波超过 20% 的帧标为离群点，图上画灰色空心点、
  不连入轨迹，动态值与中位数等派生量排除；敏感性对照线（ceiling ±500）同样处理。
- 元音动态：每个韵母在 0%、10%、…、100% 共 11 个位置取 F1/F2/F3/F0（方案 §3.3）。
- 谐波谱：韵母 20%/50%/80% 的 40 ms Hann 频谱 + LPC 包络 + H1–H4（方案 §3.1 图 3、§3.2、§7.1）。
所有分析都在完整录音上计算后再按时间范围取用，时间轴不做归零或拉伸。
对外提供 vowel_formants()：返回单个韵母按上述规则计算的共振峰结果
（VowelFormants），发声态等模块导入它与 generate() 共用完全同一份计算。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import common

FORMANT_TIME_STEP = 0.005      # To Formant (burg) 时间步长（秒）
FORMANT_MAX_NUMBER = 5         # 最大共振峰数目
FORMANT_WINDOW = 0.025         # 分析窗长度（秒）
FORMANT_PRE_EMPHASIS = 50.0    # 预加重起始频率（Hz）
N_FORMANTS = 4                 # 提取 F1–F4 与 B1–B4

CEILING_STEP = 250.0           # 自动选择 formant ceiling 的候选步长（Hz）
CEILING_SEARCH_RANGE = 500.0   # 候选范围：发音人初始值 ±（Hz），只做窄范围修正
MIN_VALID_FRAMES = 5           # 候选有效性要求的最少有效帧数
SENSITIVITY_DELTA = 500.0      # 敏感性检查相对所选 ceiling 的偏移量（Hz）
SENSITIVITY_THRESHOLD = 15.0   # F1/F2 相对变化超过该百分比（%）时告警

OUTLIER_FILTER_FRAMES = 5      # 离群点判定的中值滤波窗长（帧）
OUTLIER_DEVIATION = 0.2        # 偏离中值超过该比例的帧为离群点

VOWEL_POSITIONS = np.linspace(0.0, 1.0, 11)   # 元音动态归一化位置 0%–100%
HARMONIC_WINDOW = 0.040        # 谐波谱分析窗（40 ms Hann）
HARMONIC_POSITIONS = (0.2, 0.5, 0.8)
HARMONIC_SEARCH_RATIO = 0.15   # 谐波峰搜索范围 ±0.15·F0
A_SEARCH_RATIO = 0.10          # A_k：F_k ± 10% 范围内最强谐波
SPECTRUM_FMAX = 5000.0         # 08 谐波谱显示上限（Hz）
DETAIL_FMAX_LOW = 2000.0       # 08b 低频谐波细节面板上限（Hz）
DETAIL_FMAX_HIGH = 8000.0      # 08b 中高频谐波结构面板上限（Hz）

FORMANT_COLORS = ("#d62728", "#1f77b4", "#2ca02c")   # F1/F2/F3


@dataclass
class _Tracks:
    """整条录音的共振峰轨迹（韵母段用所选 ceiling，其余帧用发音人初始值）。"""
    times: np.ndarray        # 帧中心时间（秒）
    freqs: np.ndarray        # 基准 F1–F4（4×n，Hz，无声帧为 NaN）
    bands: np.ndarray        # 基准 B1–B4（4×n，Hz，无声帧为 NaN）
    freqs_low: np.ndarray    # 所选 ceiling − 500 Hz 的 F1–F3（3×n）
    freqs_high: np.ndarray   # 所选 ceiling + 500 Hz 的 F1–F3（3×n）
    voiced: np.ndarray       # 有 F0 的帧（信息列；不再决定共振峰有效帧）
    outliers: np.ndarray     # 基准 F1–F3 各自的离群点（3×n）
    outliers_low: np.ndarray   # 敏感性低 ceiling 曲线的离群点（3×n）
    outliers_high: np.ndarray  # 敏感性高 ceiling 曲线的离群点（3×n）
    in_vowel: np.ndarray     # 位于某个元音区间内的帧（n）
    low_level: np.ndarray    # 短时电平比所在音节最大电平低 30 dB 以上的帧（n）
    f0_times: np.ndarray
    f0: np.ndarray           # F0 轨迹（无声帧为 NaN）

    @property
    def draw_mask(self) -> np.ndarray:
        """图上绘制共振峰点的帧：元音区间内且非低能量（F0 不再是必要条件）。"""
        return self.in_vowel & ~self.low_level


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


@dataclass
class _FinalSpan:
    """韵母的元音分析区间（common.vowel_interval 的结果）。"""
    final: common.PhoneSeg
    syll_index: int          # 所属音节在 aln.syllables 中的下标
    t0: float                # 元音区间起点（可能后移到首个有声帧）
    t1: float                # 元音区间终点（可能沿有效帧延伸）
    start_source: str        # "first_voiced" | "alignment"
    end_source: str          # "voicing_extended" | "alignment"


@dataclass
class _VowelSeries:
    """单个韵母的 11 点归一化动态数据（无声或离群位置为 NaN）。"""
    symbol: str              # 音节拼音（带调）
    label: str               # 韵母标签
    final_type: str
    duration_ms: float
    ceiling_hz: float        # 该韵母自动选中的 formant ceiling
    formants: np.ndarray     # F1–F3（3×11，Hz）
    f0: np.ndarray           # 11 点 F0（Hz）
    unreliable: np.ndarray   # 3×11，离群点或低能量帧（值保留，图上画空心点）
    t0: float                # 元音区间起点（秒）
    t1: float                # 元音区间终点（秒）
    start_source: str        # "first_voiced" | "alignment"
    end_source: str          # "voicing_extended" | "alignment"
    effective_ms: float      # 取样区间时长（t1 − t0，图例用）
    extension_ms: float      # 终点相对对齐终点的延伸量（0 表示未延伸）
    valid_points: int        # 11 点中有效点的个数（三点均非离群、非低能量且有值）
    f1_default_p50: float = np.nan   # 固定默认 ceiling 下韵母 50% 处的 F1（跨韵母可比）
    f2_default_p50: float = np.nan   # 同上，F2


def _num(value: float, digits: int = 2):
    """CSV 数值：NaN/Inf 写空字符串，其余保留 digits 位小数。"""
    return round(float(value), digits) if np.isfinite(value) else ""


def _formant_burg(snd, ceiling: float):
    """Praat "To Formant (burg)"；参数顺序：时间步长、最大共振峰数、ceiling、窗长、预加重。"""
    from parselmouth.praat import call

    return call(snd, "To Formant (burg)", FORMANT_TIME_STEP, FORMANT_MAX_NUMBER,
                ceiling, FORMANT_WINDOW, FORMANT_PRE_EMPHASIS)


def _formant_arrays(fm, n_formants: int) -> tuple[np.ndarray, np.ndarray]:
    """Formant 对象 → (频率 n×帧, 带宽 n×帧)；缺失的共振峰记为 NaN。"""
    times = np.asarray(fm.xs(), dtype=float)
    freqs = np.full((n_formants, len(times)), np.nan)
    bands = np.full((n_formants, len(times)), np.nan)
    for i, t in enumerate(times):
        for k in range(n_formants):
            f = fm.get_value_at_time(k + 1, t)
            b = fm.get_bandwidth_at_time(k + 1, t)
            if f is not None and np.isfinite(f):
                freqs[k, i] = f
            if b is not None and np.isfinite(b):
                bands[k, i] = b
    return freqs, bands


def _burg_cache(snd):
    """按 ceiling 缓存 Burg 的 (F1–F4, B1–B4)；帧网格与 ceiling 无关，各候选完全对齐。"""
    cache: dict[float, tuple[np.ndarray, np.ndarray]] = {}

    def get(ceiling: float) -> tuple[np.ndarray, np.ndarray]:
        key = round(float(ceiling), 6)
        if key not in cache:
            cache[key] = _formant_arrays(_formant_burg(snd, key), N_FORMANTS)
        return cache[key]

    return get


def _trajectory_score(t: np.ndarray, formants: np.ndarray) -> float:
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


def _outlier_mask(track: np.ndarray, window: int = OUTLIER_FILTER_FRAMES,
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


def _low_level_frames(x: np.ndarray, sr: int, aln: common.Alignment,
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


def _select_ceiling(burg, times: np.ndarray, frames: np.ndarray, default_ceiling: float,
                    label: str) -> tuple[float, dict[float, float | None], str | None]:
    """在默认 ceiling ±500 Hz 的候选中打分选值；返回 (所选 ceiling, 各候选得分, 告警文字或 None)。

    打分帧由 frames 给出（元音区间内且非低能量）；无合格候选时回退默认值并给出告警。
    """
    candidates = [default_ceiling + k * CEILING_STEP
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
        scores[candidate] = _trajectory_score(times[frames][valid], values)
    qualified = {c: s for c, s in scores.items() if s is not None}
    if qualified:
        return min(qualified, key=qualified.get), scores, None
    warning = (f"韵母 {label} 没有满足 F1<F2<F3 且有效帧 ≥ {MIN_VALID_FRAMES} 的 "
               f"ceiling 候选，回退默认 {default_ceiling:.0f} Hz")
    return default_ceiling, scores, warning


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
    times = np.asarray(_formant_burg(snd, profile.formant_ceiling).xs(), dtype=float)
    burg = _burg_cache(snd)
    low_level = _low_level_frames(x, sr, aln, times)
    label = final.label if final else syllable.symbol
    in_span = (times >= interval.t0) & (times <= interval.t1)
    chosen, _, _ = _select_ceiling(burg, times, in_span & ~low_level,
                                   profile.formant_ceiling, label)
    freqs, bands = (a[:, in_span].copy() for a in burg(chosen))
    outliers = np.vstack([_outlier_mask(freqs[k]) for k in range(3)])
    valid = ~low_level[in_span] & ~outliers.any(axis=0)
    return VowelFormants(label=label, ceiling_hz=chosen,
                         t0=interval.t0, t1=interval.t1,
                         start_source=interval.start_source, end_source=interval.end_source,
                         times=times[in_span], freqs=freqs, bands=bands, valid=valid,
                         f0=_f0_nearest(f0_times, f0, times[in_span]))


def _f0_nearest(f0_times: np.ndarray, f0: np.ndarray, t_query: np.ndarray) -> np.ndarray:
    """每个查询时刻取最近 F0 帧的值（无声帧为 NaN，不当作 0）。"""
    idx = np.abs(f0_times[:, None] - np.asarray(t_query)[None, :]).argmin(axis=0)
    return f0[idx]


def _phone_label_at(aln: common.Alignment, t: float) -> str:
    """t 时刻所属音素的标签（不在任何音素区间内时为空字符串）。"""
    for p in aln.phones:
        if p.t0 <= t < p.t1:
            return p.label
    return ""


def _band_peak(freqs: np.ndarray, spec_db: np.ndarray, fmin: float, fmax: float) -> tuple[float, float]:
    """在 [fmin, fmax] 内找谱峰，返回 (频率 Hz, dB)；区间内无数据点时返回 (NaN, NaN)。"""
    mask = (freqs >= fmin) & (freqs <= fmax)
    if not mask.any():
        return np.nan, np.nan
    i = np.where(mask)[0][np.argmax(spec_db[mask])]
    return float(freqs[i]), float(spec_db[i])


def _spectrum_peak_indices(freqs: np.ndarray, spec_db: np.ndarray, fmax: float) -> np.ndarray:
    """0–fmax 内频谱局部极大值的下标（用于 LPC 包络与谐波峰的对齐）。"""
    idx = np.where((freqs > 0) & (freqs <= fmax))[0]
    inner = idx[(idx > 0) & (idx < len(spec_db) - 1)]
    ok = (spec_db[inner] >= spec_db[inner - 1]) & (spec_db[inner] > spec_db[inner + 1])
    return inner[ok]


def _harmonic_peak(freqs: np.ndarray, spec_db: np.ndarray, f0: float, k: int) -> tuple[float, float]:
    """第 k 个谐波：在 k·F0 ± 0.15·F0 范围内找谱峰，返回 (频率 Hz, dB)。

    搜索带宽度固定为 ±0.15·F0，与 k 无关；若按 k·F0 的比例取带，高次谐波的搜索带
    会宽过谐波间距，抓到邻近谐波（旧实现即此错误）。
    """
    return _band_peak(freqs, spec_db, (k - HARMONIC_SEARCH_RATIO) * f0,
                      (k + HARMONIC_SEARCH_RATIO) * f0)


def _slice_spectrum(x: np.ndarray, sr: int, ceiling: float, center: float,
                    f0: float = np.nan) -> dict:
    """center 时刻的 40 ms Hann 频谱 + LPC 包络；包络整体平移到频谱谐波峰的水平。

    平移量取谐波峰（k·F0 ± 0.15·F0，k ≤ min(ceiling, 5000)/F0）处（频谱 − 包络）的中位数；
    无 F0 时退回所有局部极大值处的中位数。局部极大值含大量谷底纹波，中位数会比
    谐波峰低约 15–20 dB，导致包络整体偏低。
    """
    seg, window_complete = common.segment_at(x, sr, center, HARMONIC_WINDOW)
    freqs, power = common.power_spectrum(seg, sr)
    spec_db = common.db(power)
    seg_resampled, sr_resampled = common.resample_for_lpc(seg, sr, ceiling)
    order = common.lpc_order(ceiling)
    env_freqs, env_db = common.lpc_envelope(seg_resampled, sr_resampled, order)
    if np.isfinite(f0):
        differences = []
        for k in range(1, int(min(ceiling, SPECTRUM_FMAX) / f0) + 1):
            hz, db = _harmonic_peak(freqs, spec_db, f0, k)
            if np.isfinite(db):
                differences.append(db - float(np.interp(hz, env_freqs, env_db)))
        offset = float(np.median(differences)) if differences else 0.0
    else:
        peaks = _spectrum_peak_indices(freqs, spec_db, min(ceiling, SPECTRUM_FMAX))
        offset = float(np.median(spec_db[peaks] - np.interp(freqs[peaks], env_freqs, env_db))) \
            if len(peaks) else 0.0
    return {"freqs": freqs, "spec_db": spec_db, "env_freqs": env_freqs,
            "env_db": env_db + offset, "offset": offset, "order": order,
            "window_complete": window_complete, "n_fft": (len(freqs) - 1) * 2}


# ---------------- 表 ----------------

def _write_formant_tracks(tracks: _Tracks, aln: common.Alignment, out_dir: Path) -> Path:
    rows = []
    for i, t in enumerate(tracks.times):
        row = {"time": round(float(t), 4), "phone": _phone_label_at(aln, t),
               "voiced": bool(tracks.voiced[i]),
               "in_vowel": bool(tracks.in_vowel[i]),
               "outlier": bool(tracks.outliers[:, i].any()),
               "low_level": bool(tracks.low_level[i])}
        for k in range(1, N_FORMANTS + 1):
            row[f"F{k}"] = _num(tracks.freqs[k - 1, i])
            row[f"B{k}"] = _num(tracks.bands[k - 1, i])
        for k in range(1, 4):
            row[f"F{k}_ceiling_minus_{SENSITIVITY_DELTA:.0f}"] = _num(tracks.freqs_low[k - 1, i])
            row[f"F{k}_ceiling_plus_{SENSITIVITY_DELTA:.0f}"] = _num(tracks.freqs_high[k - 1, i])
        rows.append(row)
    return common.write_csv(rows, out_dir / "csv", "formant_tracks.csv")


def _write_vowel_dynamics(series: list[_VowelSeries], out_dir: Path) -> Path:
    rows = []
    for s in series:
        row = {"syllable": s.symbol, "final": s.label, "final_type": s.final_type,
               "duration_ms": round(s.duration_ms, 1), "ceiling_hz": round(s.ceiling_hz, 1),
               "vowel_t0": round(s.t0, 4), "vowel_start_source": s.start_source,
               "vowel_t1": round(s.t1, 4), "vowel_end_source": s.end_source,
               "F1_default_p50": _num(s.f1_default_p50, 1),
               "F2_default_p50": _num(s.f2_default_p50, 1)}
        for j, p in enumerate(VOWEL_POSITIONS):
            pct = int(round(p * 100))
            row[f"F1_p{pct}"] = _num(s.formants[0, j])
            row[f"F2_p{pct}"] = _num(s.formants[1, j])
            row[f"F3_p{pct}"] = _num(s.formants[2, j])
            row[f"F0_p{pct}"] = _num(s.f0[j])
        rows.append(row)
    return common.write_csv(rows, out_dir / "csv", "vowel_dynamics.csv")


def _write_harmonic_slices(slices: list[dict], out_dir: Path) -> Path:
    rows = []
    for e in slices:
        row = {"time": round(e["time"], 4), "position_percent": int(round(e["position"] * 100)),
               "F0": _num(e["f0"]), "F1": _num(e["F"][0]), "F2": _num(e["F"][1]),
               "F3": _num(e["F"][2])}
        for k in range(1, 5):
            hz, db = e["H"].get(k, (np.nan, np.nan))
            row[f"H{k}_dB"] = _num(db)
            row[f"H{k}_Hz"] = _num(hz)
        for k in range(3):
            row[f"A{k + 1}_dB"] = _num(e["A"][k])
        h1_db = e["H"].get(1, (np.nan, np.nan))[1]
        h2_db = e["H"].get(2, (np.nan, np.nan))[1]
        row["H1_minus_H2_dB"] = _num(h1_db - h2_db) if np.isfinite(h1_db) and np.isfinite(h2_db) else ""
        a1_db = e["A"][0]
        row["H1_minus_A1_dB"] = _num(h1_db - a1_db) if np.isfinite(h1_db) and np.isfinite(a1_db) else ""
        rows.append(row)
    return common.write_csv(rows, out_dir / "csv", "harmonic_slices.csv")


# ---------------- 图 ----------------

def _fig_formants(tracks: _Tracks, sg, ceiling: float, sensitivity_ref: float, ceiling_note: str,
                  scales: common.DbScales | None, aln: common.Alignment, stem: str,
                  out_dir: Path) -> Path:
    """上面板：宽带谱叠加 F1–F3 散点；下面板：F1–F3 轨迹 + 所选 ceiling ±500 的敏感性叠加。"""
    plt = common.setup_matplotlib()
    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(10, 6.6), sharex=True,
        gridspec_kw={"height_ratios": [1.7, 1.0]}, constrained_layout=True)
    vmax = scales.broadband_max_db if scales is not None else None
    times, freqs_axis, values_db = common.spectrogram_arrays(sg)
    mesh = common.plot_spectrogram(ax_top, times, freqs_axis, values_db, vmax, fmax=ceiling)
    fig.colorbar(mesh, ax=ax_top, pad=0.01).set_label("dB")
    draw = tracks.draw_mask
    for k in range(3):
        normal = draw & ~tracks.outliers[k]
        ax_top.plot(tracks.times[normal], tracks.freqs[k, normal], "o", ms=2.5,
                    color=FORMANT_COLORS[k], label=f"F{k + 1}")
        outlier = draw & tracks.outliers[k]
        ax_top.plot(tracks.times[outlier], tracks.freqs[k, outlier], "o", ms=3.5,
                    mfc="none", mec="#888888", mew=0.8,
                    label="离群点（偏离 5 帧中值 > 20%）" if k == 0 else None)
    ax_top.legend(loc="upper right", fontsize=7, ncol=4)
    ax_top.set_title(f"{stem} 共振峰轨迹（Burg：窗 {FORMANT_WINDOW * 1000:.0f} ms，"
                     f"步长 {FORMANT_TIME_STEP * 1000:.0f} ms，{ceiling_note}，仅有声帧）",
                     pad=18, fontsize=10)
    common.draw_boundaries(ax_top, aln)
    for k in range(3):
        color = FORMANT_COLORS[k]
        kept = draw & ~tracks.outliers[k]
        ax_bot.plot(tracks.times, np.where(kept, tracks.freqs[k], np.nan),
                    color=color, lw=1.5, label=f"F{k + 1}")
        outlier = draw & tracks.outliers[k]
        ax_bot.plot(tracks.times[outlier], tracks.freqs[k, outlier], "o", ms=3.5,
                    mfc="none", mec="#888888", mew=0.8)
        kept_low = kept & ~tracks.outliers_low[k]
        ax_bot.plot(tracks.times, np.where(kept_low, tracks.freqs_low[k], np.nan),
                    color=color, lw=1.0, ls="--", alpha=0.45,
                    label=f"F{k + 1}（ceiling {sensitivity_ref - SENSITIVITY_DELTA:.0f} Hz）")
        kept_high = kept & ~tracks.outliers_high[k]
        ax_bot.plot(tracks.times, np.where(kept_high, tracks.freqs_high[k], np.nan),
                    color=color, lw=1.0, ls=":", alpha=0.45,
                    label=f"F{k + 1}（ceiling {sensitivity_ref + SENSITIVITY_DELTA:.0f} Hz）")
    ax_bot.set_ylabel("频率 (Hz)")
    ax_bot.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), fontsize=7, ncol=3,
                  columnspacing=1.4, handlelength=2.4)
    common.draw_boundaries(ax_bot, aln, labels=False)
    common.set_time_axis(ax_bot, aln)
    return common.save_fig(fig, out_dir, "07_formants.png")


def _fig_vowel_space(tracks: _Tracks, series: list[_VowelSeries], in_finals: np.ndarray,
                     stem: str, out_dir: Path) -> Path:
    """F1-F2 元音空间：横轴 F2、纵轴 F1（两轴反向），韵母轨迹为折线并在 25/50/75/100% 加箭头。"""
    plt = common.setup_matplotlib()
    fig, ax = plt.subplots(figsize=(6.8, 5.6), constrained_layout=True)
    background = tracks.draw_mask & in_finals & ~tracks.outliers.any(axis=0)
    ax.plot(tracks.freqs[1, background], tracks.freqs[0, background], "o",
            ms=3, color="#c8c8c8", alpha=0.5, label="韵母有声帧")
    f1_all = np.concatenate([s.formants[0][np.isfinite(s.formants[0])] for s in series]) \
        if series else np.array([])
    f2_all = np.concatenate([s.formants[1][np.isfinite(s.formants[1])] for s in series]) \
        if series else np.array([])
    for si, s in enumerate(series):
        color = f"C{si}"
        valid = np.isfinite(s.formants[0]) & np.isfinite(s.formants[1])
        # 直接绘制含 NaN 的数组，缺失点处连线自然断开（不桥接）
        ax.plot(s.formants[1], s.formants[0], "-", color=color, lw=1.4,
                label=f"{s.label}（{s.effective_ms:.0f} ms，有效点 {s.valid_points}/11）")
        # 方向箭头只放在 25/50/75/100% 处，端点缺失时跳过
        for a, b in ((2, 3), (4, 5), (7, 8), (9, 10)):
            if valid[a] and valid[b]:
                ax.annotate("", xy=(s.formants[1, b], s.formants[0, b]),
                            xytext=(s.formants[1, a], s.formants[0, a]),
                            arrowprops=dict(arrowstyle="-|>", color=color, lw=1.6,
                                            shrinkA=0, shrinkB=0))
        # 0% 与最后一个有效点标在轨迹点上方、50% 标在下方；终点用实际有效位置（如 90%）
        last_valid = int(np.flatnonzero(valid)[-1]) if valid.any() else None
        for j, dy, va in ((0, 5, "bottom"), (5, -5, "top")):
            if valid[j]:
                ax.annotate(f"{s.label} {VOWEL_POSITIONS[j] * 100:.0f}%",
                            xy=(s.formants[1, j], s.formants[0, j]), xytext=(5, dy),
                            textcoords="offset points", fontsize=8, color=color,
                            ha="left", va=va)
        if last_valid is not None and last_valid != 0:
            ax.annotate(f"{s.label} {VOWEL_POSITIONS[last_valid] * 100:.0f}%",
                        xy=(s.formants[1, last_valid], s.formants[0, last_valid]),
                        xytext=(5, 5), textcoords="offset points", fontsize=8,
                        color=color, ha="left", va="bottom")
    if f1_all.size and f2_all.size:
        # 坐标范围按韵母轨迹确定并留出余量（两轴反向：大值在下/左）
        ax.set_xlim(float(f2_all.max()) + 300.0, float(f2_all.min()) - 300.0)
        ax.set_ylim(float(f1_all.max()) + 150.0, float(f1_all.min()) - 150.0)
    else:
        ax.invert_xaxis()
        ax.invert_yaxis()
    ax.set_xlabel("F2 (Hz)")
    ax.set_ylabel("F1 (Hz)")
    ax.legend(fontsize=8, loc="best")
    ax.set_title(f"{stem} F1-F2 元音空间（韵母 0%→100% 按 [起点, 有效终点] 取样，两轴反向）",
                 fontsize=10)
    return common.save_fig(fig, out_dir, "07b_vowel_space.png")


def _fig_formant_normalized(series: list[_VowelSeries], stem: str, out_dir: Path) -> Path:
    """韵母 0–100% 归一化位置上的 F1/F2/F3 轨迹；取样区间为 [起点, 有效终点]，图例注明区间时长。"""
    plt = common.setup_matplotlib()
    fig, ax = plt.subplots(figsize=(8, 4.6), constrained_layout=True)
    styles = ("-", "--", "-.", ":")
    for si, s in enumerate(series):
        for k in range(3):
            ax.plot(VOWEL_POSITIONS * 100, s.formants[k], styles[si % len(styles)],
                    color=FORMANT_COLORS[k], marker="o", ms=3,
                    label=f"{s.label} F{k + 1}（{s.effective_ms:.0f} ms）")
            hollow = s.unreliable[k] & np.isfinite(s.formants[k])   # 离群/低强度：空心点
            if hollow.any():
                ax.plot(VOWEL_POSITIONS[hollow] * 100, s.formants[k][hollow], "o",
                        ms=5, mfc="none", mec=FORMANT_COLORS[k], mew=1.0)
    ax.set_xlim(0, 100)
    ax.set_xlabel("韵母归一化位置 (%)")
    ax.set_ylabel("频率 (Hz)")
    ax.legend(fontsize=8)
    extended = [s for s in series if s.end_source == "voicing_extended"]
    title = f"{stem} 韵母共振峰归一化轨迹（0%–100% 取自 [vowel_t0, vowel_t1]，图例为区间时长"
    if extended:
        title += "；" + "、".join(
            f"{s.label} 有效终点 {s.t1:.3f} s（有声延伸 +{s.extension_ms:.0f} ms）"
            for s in extended)
    incomplete = [s for s in series if s.valid_points < len(VOWEL_POSITIONS)]
    if incomplete:
        title += "；有效点 " + "、".join(f"{s.label} {s.valid_points}/11" for s in incomplete)
    title += "）"
    ax.set_title(title, fontsize=10)
    return common.save_fig(fig, out_dir, "07c_formant_normalized.png")


def _fig_harmonic_spectrum(slices: list[dict], stem: str, label: str, ceiling: float,
                           out_dir: Path) -> Path:
    """韵母 20%/50%/80% 的 40 ms 频谱、LPC 包络、F1–F3 竖线与 H1–H4 标记。"""
    plt = common.setup_matplotlib()
    fig, axes = plt.subplots(1, len(HARMONIC_POSITIONS), figsize=(13.5, 4.2),
                             sharey=True, constrained_layout=True)
    top = max(float(np.max(e["spectrum"]["spec_db"][e["spectrum"]["freqs"] <= SPECTRUM_FMAX]))
              for e in slices)
    for ax, e in zip(axes, slices):
        sl = e["spectrum"]
        ax.plot(sl["freqs"], sl["spec_db"], color="#444444", lw=0.8, label="40 ms Hann 频谱")
        ax.plot(sl["env_freqs"], sl["env_db"], color="#d62728", lw=1.2, ls="--",
                label=f"LPC 包络（{sl['order']} 阶，平移 {sl['offset']:+.1f} dB）")
        for k in range(3):
            if np.isfinite(e["F"][k]):
                ax.axvline(e["F"][k], color=FORMANT_COLORS[k], lw=1.0, alpha=0.8)
                ax.text(e["F"][k], top - 2, f"F{k + 1}={e['F'][k]:.0f}", rotation=90,
                        fontsize=7, color=FORMANT_COLORS[k], ha="right", va="top")
        for k, (hz, db) in e["H"].items():
            if np.isfinite(db):
                ax.plot(hz, db, "v", ms=5, color="#1f77b4")
                ax.annotate(f"H{k}", xy=(hz, db), xytext=(0, 5), textcoords="offset points",
                            ha="center", fontsize=8, color="#1f77b4")
        ax.set_xlim(0, SPECTRUM_FMAX)
        ax.set_ylim(top - 70.0, top + 8.0)
        ax.set_xlabel("频率 (Hz)")
        ax.set_title(f"韵母 {e['position'] * 100:.0f}%（t = {e['time']:.3f} s）", fontsize=9)
    axes[0].set_ylabel("功率 (dB)")
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), fontsize=7, ncol=2)
    fig.suptitle(f"{stem} 韵母 {label} 谐波与 LPC 谱包络（40 ms Hann 窗，0–{SPECTRUM_FMAX:.0f} Hz，"
                 f"LPC 重采样至 {2 * ceiling:.0f} Hz）", fontsize=10)
    return common.save_fig(fig, out_dir, "08_harmonic_spectrum.png")


def _fig_harmonic_detail(e: dict, stem: str, label: str, out_dir: Path) -> Path:
    """韵母 50% 处的谐波结构：低频细节与中高频两个面板，谐波峰连线并标出 H1–H4。"""
    plt = common.setup_matplotlib()
    sl = e["spectrum"]
    f0 = e["f0"]
    harmonics = []
    for k in range(1, int(DETAIL_FMAX_HIGH / f0) + 1):
        hz, db = _harmonic_peak(sl["freqs"], sl["spec_db"], f0, k)
        if np.isfinite(db):
            harmonics.append((k, hz, db))
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2), constrained_layout=True)
    panels = ((axes[0], DETAIL_FMAX_LOW, "低频谐波细节（0–2000 Hz）"),
              (axes[1], DETAIL_FMAX_HIGH, "中高频谐波结构（0–8000 Hz）"))
    for ax, fmax, title in panels:
        ax.plot(sl["freqs"], sl["spec_db"], color="#444444", lw=0.8, label="40 ms Hann 频谱")
        ax.plot([h[1] for h in harmonics], [h[2] for h in harmonics], "o-", ms=3, lw=1.0,
                color="#1f77b4", label="谐波峰连线")
        for k, hz, db in harmonics:
            if k <= 4:
                ax.annotate(f"H{k}", xy=(hz, db), xytext=(0, 5), textcoords="offset points",
                            ha="center", fontsize=8, color="#1f77b4")
        band = sl["freqs"] <= fmax
        top = float(np.max(sl["spec_db"][band]))
        ax.set_xlim(0, fmax)
        ax.set_ylim(top - 70.0, top + 8.0)
        ax.set_xlabel("频率 (Hz)")
        ax.set_title(title, fontsize=9)
    axes[0].set_ylabel("功率 (dB)")
    axes[0].legend(fontsize=8)
    fig.suptitle(f"{stem} 韵母 {label} 谐波结构（韵母 50%，t = {e['time']:.3f} s，"
                 f"F0 = {f0:.1f} Hz，40 ms Hann 窗；谐波峰取 k·F0 ± 0.15·F0 内的最大谱点，"
                 f"k ≤ ⌊{DETAIL_FMAX_HIGH:.0f}/F0⌋）", fontsize=10)
    return common.save_fig(fig, out_dir, "08b_harmonic_detail.png")


# ---------------- 主入口 ----------------

def generate(x: np.ndarray, sr: int, aln: common.Alignment, out_dir: str | Path,
             scales: common.DbScales | None = None, context: dict | None = None) -> dict:
    """生成共振峰轨迹、元音动态与谐波谱的图表；context 为批次级信息，此处不使用。"""
    result = common.new_result()
    out_dir = Path(out_dir)
    warns = result["warnings"]
    profile = common.profile_for(aln.speaker)
    default_ceiling = profile.formant_ceiling
    stem = Path(aln.file).stem

    snd = common.to_sound(x, sr)
    pitch = common.pitch_filtered_ac(snd, profile)
    f0_times, f0 = common.pitch_arrays(pitch)
    reference = _formant_burg(snd, default_ceiling)   # 仅取帧网格与实际 dx 写入 params
    times = np.asarray(reference.xs(), dtype=float)
    burg = _burg_cache(snd)
    voiced = np.isfinite(_f0_nearest(f0_times, f0, times))
    if not voiced.any():
        warns.append("整条录音未检测到有声帧，共振峰轨迹全部为空")

    default_freqs = burg(default_ceiling)[0]          # 固定默认 ceiling 的原始轨迹（跨韵母可比）
    freqs = default_freqs.copy()
    bands = burg(default_ceiling)[1].copy()
    freqs_low = burg(default_ceiling - SENSITIVITY_DELTA)[0][:3].copy()
    freqs_high = burg(default_ceiling + SENSITIVITY_DELTA)[0][:3].copy()

    # 元音分析区间统一用 common.vowel_interval：起点可能后移到首个有声帧（跳过送气段），
    # 终点可能沿有效帧延伸（补上对齐截掉的尾部）
    spans: list[_FinalSpan] = []
    for si, syllable in enumerate(aln.syllables):
        final = syllable.final
        if final is None:
            continue
        interval = common.vowel_interval(aln, si, x, sr, profile)
        spans.append(_FinalSpan(final, si, interval.t0, interval.t1,
                                interval.start_source, interval.end_source))
        if interval.start_source == "first_voiced":
            warns.append(f"音节 {syllable.symbol} 的韵母 {final.label} 起点由 {final.t0:.3f} s "
                         f"后移至 {interval.t0:.3f} s（首个有声帧，送气段不参与元音分析）")
        if interval.end_source == "voicing_extended":
            warns.append(f"音节 {syllable.symbol} 的韵母 {final.label} 终点由 {final.t1:.3f} s "
                         f"延伸至 {interval.t1:.3f} s（沿有效帧 +"
                         f"{(interval.t1 - final.t1) * 1000:.0f} ms）")

    low_level = _low_level_frames(x, sr, aln, times)
    in_vowel = np.zeros(len(times), dtype=bool)
    for span in spans:
        in_vowel |= (times >= span.t0) & (times <= span.t1)

    # 每个韵母自动选择 formant ceiling：通过公开的 vowel_formants 取所选值，
    # 保证与本模块对外提供的结果（发声态模块等）完全是同一份计算
    choices: list[tuple[_FinalSpan, float, dict[float, float | None]]] = []
    for span in spans:
        in_span = (times >= span.t0) & (times <= span.t1)
        chosen = vowel_formants(x, sr, aln, span.syll_index, profile).ceiling_hz
        # 打分详情再算一遍（同一 _select_ceiling，结果一致），供 params 记录
        _, scores, score_warning = _select_ceiling(burg, times, in_span & ~low_level,
                                                   default_ceiling, span.final.label)
        if score_warning:
            warns.append(score_warning)
        freqs[:, in_span] = burg(chosen)[0][:, in_span]   # 拼接覆盖区间内全部帧
        bands[:, in_span] = burg(chosen)[1][:, in_span]
        freqs_low[:, in_span] = burg(chosen - SENSITIVITY_DELTA)[0][:3, in_span]
        freqs_high[:, in_span] = burg(chosen + SENSITIVITY_DELTA)[0][:3, in_span]
        choices.append((span, chosen, scores))

    # 离群点与低能量帧（规则见模块 docstring）。共振峰值不再按 F0 置 NaN：
    # 嘎裂/气声段 F0 常漏检但仍有共振峰结构，表中保留数值，由标志列区分。
    outliers = np.vstack([_outlier_mask(freqs[k]) for k in range(3)])
    default_outliers = np.vstack([_outlier_mask(default_freqs[k]) for k in range(3)])
    outliers_low = np.vstack([_outlier_mask(freqs_low[k]) for k in range(3)])
    outliers_high = np.vstack([_outlier_mask(freqs_high[k]) for k in range(3)])
    tracks = _Tracks(times, freqs, bands, freqs_low, freqs_high, voiced,
                     outliers, outliers_low, outliers_high, in_vowel, low_level,
                     f0_times, f0)

    # 敏感性（方案 §9）：所选 ceiling ±500 Hz，元音区间内非低能量且非离群的帧上，
    # F1/F2/F3 相对基准的中位数绝对变化
    sensitivity: dict[str, dict[str, float]] = {}
    frames_in_finals = False
    for k, name in enumerate(("F1", "F2", "F3")):
        base_parts: list[np.ndarray] = []
        delta_parts: list[np.ndarray] = []
        for span, _chosen, _scores in choices:
            m = (times >= span.t0) & (times <= span.t1) & ~low_level
            frames_in_finals = frames_in_finals or bool(m.any())
            m = m & ~outliers[k]            # 中位数等派生量排除离群点
            base_k = freqs[k, m]
            base_parts += [base_k, base_k]   # 与 low/high 两份差值一一对应
            delta_parts.append(np.abs(freqs_low[k, m] - base_k))
            delta_parts.append(np.abs(freqs_high[k, m] - base_k))
        base = np.concatenate(base_parts) if base_parts else np.array([])
        delta = np.concatenate(delta_parts) if delta_parts else np.array([])
        valid = np.isfinite(base) & np.isfinite(delta) & (base > 0)
        if valid.any():
            median_hz = float(np.median(delta[valid]))
            median_percent = float(np.median(delta[valid] / base[valid] * 100))
        else:
            median_hz, median_percent = np.nan, np.nan
        sensitivity[name] = {"median_abs_change_hz": _num(median_hz, 1),
                             "median_abs_change_percent": _num(median_percent, 1)}
        if name in ("F1", "F2") and np.isfinite(median_percent) \
                and median_percent > SENSITIVITY_THRESHOLD:
            warns.append(f"{name} 对 formant ceiling 敏感（所选 ceiling ±{SENSITIVITY_DELTA:.0f} Hz 时"
                         f"元音有效帧的中位数绝对变化为 {median_hz:.1f} Hz / {median_percent:.1f}%），"
                         f"该共振峰自动值不宜直接采信")
    if choices and not frames_in_finals:
        warns.append("元音区间内没有有效帧，formant ceiling 敏感性检查无有效数据")

    # 元音动态（方案 §3.3）：每个韵母 11 个归一化位置，区间为 [vowel_t0, vowel_t1]；
    # 共振峰不再因缺 F0 置 NaN（嘎裂段保留），仅离群点置 NaN
    series: list[_VowelSeries] = []
    for si, syllable in enumerate(aln.syllables):
        final = syllable.final
        if final is None:
            continue
        span = next(q for q in spans if q.final is final)
        chosen = next((c for q, c, _ in choices if q.final is final), default_ceiling)
        positions = span.t0 + VOWEL_POSITIONS * (span.t1 - span.t0)
        f0_at = _f0_nearest(f0_times, f0, positions)
        frame_index = np.abs(times[:, None] - positions[None, :]).argmin(axis=0)
        formants_at = freqs[:3, frame_index].copy()
        unreliable = np.vstack([outliers[k, frame_index] | low_level[frame_index]
                                for k in range(3)])
        for k in range(3):                 # 动态值排除离群点（低能量帧保留数值）
            formants_at[k, outliers[k, frame_index]] = np.nan
        unvoiced_positions = [f"{p * 100:.0f}%" for p, v in zip(VOWEL_POSITIONS, f0_at)
                              if not np.isfinite(v)]
        if unvoiced_positions:
            warns.append(f"音节 {syllable.symbol} 的韵母 {final.label} 在 "
                         f"{'、'.join(unvoiced_positions)} 处无 F0（嘎裂或漏检），"
                         f"F0 记为 NaN，共振峰值保留")
        valid_points = int(np.sum(np.isfinite(formants_at).all(axis=0)
                                  & ~low_level[frame_index]))
        # 固定默认 ceiling 下韵母 50% 处的 F1/F2（供跨韵母比较）
        mid_frame = int(frame_index[5])
        f1_default = float(default_freqs[0, mid_frame]) \
            if not default_outliers[0, mid_frame] else np.nan
        f2_default = float(default_freqs[1, mid_frame]) \
            if not default_outliers[1, mid_frame] else np.nan
        series.append(_VowelSeries(syllable.symbol, final.label, common.final_type(final.label),
                                   final.duration * 1000.0, chosen, formants_at, f0_at,
                                   unreliable, span.t0, span.t1,
                                   span.start_source, span.end_source,
                                   (span.t1 - span.t0) * 1000.0,
                                   (span.t1 - final.t1) * 1000.0,
                                   valid_points, f1_default, f2_default))

    # 谐波谱切片（方案 §3.1 图 3 / §3.2）：语料为单音节，取第一个韵母及其所选 ceiling；
    # 位置按 [vowel_t0, vowel_t1] 计算，可覆盖对齐漏掉的尾部弱衰减段
    analysis_ceiling = choices[0][1] if choices else default_ceiling
    slices: list[dict] = []
    first_span = spans[0] if spans else None
    if first_span is not None:
        final = first_span.final
        for position in HARMONIC_POSITIONS:
            t = first_span.t0 + position * (first_span.t1 - first_span.t0)
            entry = {"position": position, "time": t, "f0": np.nan,
                     "F": [np.nan] * 3, "H": {}, "A": [np.nan] * 3, "spectrum": None}
            frame_index = int(np.abs(times - t).argmin())
            entry["F"] = [float(v) if np.isfinite(v) else np.nan
                          for v in freqs[:3, frame_index]]
            f0_at = float(_f0_nearest(f0_times, f0, np.array([t]))[0])
            entry["f0"] = f0_at
            try:
                entry["spectrum"] = _slice_spectrum(x, sr, analysis_ceiling, t, f0_at)
            except Exception as exc:
                warns.append(f"谐波切片 t = {t:.3f} s 计算失败：{exc}")
                slices.append(entry)
                continue
            if not entry["spectrum"]["window_complete"]:
                warns.append(f"谐波切片 t = {t:.3f} s 的 40 ms 分析窗伸出录音边界，结果仅供参考")
            if np.isfinite(f0_at):
                sl = entry["spectrum"]
                for k in range(1, 5):
                    entry["H"][k] = _harmonic_peak(sl["freqs"], sl["spec_db"], f0_at, k)
                entry["A"] = [_band_peak(sl["freqs"], sl["spec_db"],
                                         fv * (1 - A_SEARCH_RATIO), fv * (1 + A_SEARCH_RATIO))[1]
                              if np.isfinite(fv) else np.nan for fv in entry["F"]]
            else:
                warns.append(f"韵母 {final.label} {position * 100:.0f}%（t = {t:.3f} s）处无 F0，"
                             f"跳过 H1–H4 与 A1–A3 标记")
            slices.append(entry)

    chosen_values = [c for _, c, _ in choices]
    display_ceiling = max(chosen_values + [default_ceiling])
    if len(set(chosen_values)) == 1:
        ceiling_note = f"ceiling {chosen_values[0]:.0f} Hz（自动）"
    else:
        ceiling_note = "ceiling " + ", ".join(f"{span.final.label}={c:.0f}"
                                              for span, c, _ in choices) + "（自动）"
    spectrogram = common.spectrogram(snd, "broadband", display_ceiling)
    in_finals = tracks.in_vowel

    def guarded(name: str, job) -> None:
        """单项输出失败时记录 warning 并继续（单张图的失败不能中断整批生成）。"""
        try:
            path = job()
        except Exception as exc:
            warns.append(f"{name} 生成失败：{exc}")
        else:
            key = "images" if path.suffix == ".png" else "tables"
            result[key][path.name] = path

    guarded("formant_tracks.csv", lambda: _write_formant_tracks(tracks, aln, out_dir))
    guarded("vowel_dynamics.csv", lambda: _write_vowel_dynamics(series, out_dir))
    guarded("harmonic_slices.csv", lambda: _write_harmonic_slices(slices, out_dir))
    guarded("07_formants.png", lambda: _fig_formants(tracks, spectrogram, display_ceiling,
                                                     analysis_ceiling, ceiling_note, scales,
                                                     aln, stem, out_dir))
    if series:
        guarded("07b_vowel_space.png",
                lambda: _fig_vowel_space(tracks, series, in_finals, stem, out_dir))
        guarded("07c_formant_normalized.png", lambda: _fig_formant_normalized(series, stem, out_dir))
    available = [e for e in slices if e["spectrum"] is not None]
    if first_span is not None and available:
        final = first_span.final
        guarded("08_harmonic_spectrum.png",
                lambda: _fig_harmonic_spectrum(available, stem, final.label, analysis_ceiling,
                                               out_dir))
    middle = next((e for e in slices if e["position"] == 0.5), None)
    if middle is not None and middle["spectrum"] is not None:
        if np.isfinite(middle["f0"]):
            guarded("08b_harmonic_detail.png",
                    lambda: _fig_harmonic_detail(middle, stem,
                                                 final.label if final else "", out_dir))
        else:
            warns.append("韵母 50% 处无 F0，跳过 08b_harmonic_detail.png")

    n_fft = available[0]["spectrum"]["n_fft"] if available else np.nan
    result["params"] = {
        "formant_ceiling": default_ceiling,
        "vowel_interval_rule": "元音区间 = common.vowel_interval（起点可后移到首个有声帧、终点沿"
                               "有效帧延伸）；11 点动态、谐波切片、ceiling 打分、敏感性检查与"
                               "07/07b/07c/08/08b 的绘制范围均按此区间",
        "valid_frame_rule": "有效帧 = 元音区间内 且 非低能量 且 非离群点；不再逐帧要求 F0"
                            "（嘎裂/气声段 F0 漏检时共振峰值保留），区间外的帧不画",
        "chosen_ceilings": {span.final.label: c for span, c, _ in choices},
        "ceiling_selection": {
            "search_range_hz": CEILING_SEARCH_RANGE, "step_hz": CEILING_STEP,
            "min_valid_frames": MIN_VALID_FRAMES,
            "note": "打分只用来在默认值 ±500 Hz 的窄范围内修正换轨，不能用于大范围搜索："
                    "轨迹平滑度无法排除峰合并或伪峰（本语料 yi1_FV1 在 4500 Hz 时 "
                    "F2 落到约 1490 Hz 的伪峰上，得分反而最低）",
            "per_final": [{"final": span.final.label, "ceiling_hz": c,
                           "vowel_t0": round(span.t0, 4), "start_source": span.start_source,
                           "vowel_t1": round(span.t1, 4), "end_source": span.end_source,
                           "scores": {f"{k:.0f}": (round(s, 5) if s is not None else None)
                                      for k, s in scores.items()}}
                          for span, c, scores in choices]},
        "outlier_rules": {
            "median_filter_frames": OUTLIER_FILTER_FRAMES,
            "relative_deviation": OUTLIER_DEVIATION,
            "derived_values_exclude": "离群点（11 点动态值、敏感性中位数排除；表中保留数值并标记）",
            "low_level_drop_db": common.LOW_LEVEL_DROP_DB,
            "low_level_handling": "短时 RMS 电平（common.short_time_level_db，25 ms 窗）比所在"
                                  "音节最大电平低 30 dB 以上的帧为低能量帧，不画共振峰点，"
                                  "表中保留数值并标记；敏感性对照线同样只画有效帧并做离群处理",
        },
        "outlier_summary": {"F1": int(outliers[0].sum()), "F2": int(outliers[1].sum()),
                            "F3": int(outliers[2].sum()),
                            "low_level": int(low_level.sum())},
        "formant": {"time_step": FORMANT_TIME_STEP, "max_number": FORMANT_MAX_NUMBER,
                    "window_length": FORMANT_WINDOW, "pre_emphasis_hz": FORMANT_PRE_EMPHASIS,
                    "dx": float(reference.dx), "first_frame_time": float(reference.x1),
                    "n_frames": int(reference.nx)},
        "sensitivity": {"delta_hz": SENSITIVITY_DELTA, "threshold_percent": SENSITIVITY_THRESHOLD,
                        "relative_to": "所选 ceiling",
                        "median_abs_change": sensitivity},
        "f0": {"floor": profile.f0_floor, "ceiling": profile.f0_ceiling,
               "dx": float(pitch.dx), "first_frame_time": float(pitch.x1)},
        "harmonic": {"window_sec": HARMONIC_WINDOW, "n_fft": n_fft,
                     "frequency_resolution_hz": sr / n_fft if np.isfinite(n_fft) else np.nan,
                     "lpc_order": common.lpc_order(analysis_ceiling),
                     "lpc_resampled_rate": int(round(2 * analysis_ceiling)),
                     "lpc_shift_method": "LPC 包络加上其在谐波峰处（k·F0 ± 0.15·F0）的"
                                         "（频谱 − 包络）中位数偏差，使包络经过频谱谐波峰；"
                                         "无 F0 时改用全部局部极大值处的中位数",
                     "lpc_shift_db": {f"{int(round(e['position'] * 100))}%": _num(e["spectrum"]["offset"], 1)
                                      for e in available}},
        "spectrogram_broadband": common.spectrogram_actual(spectrogram),
    }
    return result
