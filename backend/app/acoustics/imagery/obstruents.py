"""塞音、擦音、塞擦音与 /h/ 的专项声学分析（方案 §4.1–4.3、§4.6、§7.2、§8.3、§9）。

生成图像：
- 塞音：09a VOT 放大图、09b 爆破谱、09c 除阻后 F1–F3 过渡；
- 擦音：10a 双频率范围宽带谱、10b 平均谱（Hann 多帧平均 + multitaper）、
  10c 谱矩时间曲线（两套频带）、10d 频带能量与 HighLevelD 时间曲线；
  声母为 /h/ 时额外生成 14 与后接韵母的频谱连续性图；
- 塞擦音：11a 爆破—摩擦—送气—元音分阶段图（闭塞段不可测）、11b 爆破谱与摩擦段平均谱、
  11c 摩擦段谱矩。

数值表（out_dir/csv）：obstruent_params.csv（每个被分析声母一行）、
fricative_moments.csv（摩擦段逐帧谱矩，两套频带各一行）。

时间约定：音素边界沿用讯飞对齐；除阻时刻、浊音起点等是在讯飞声母区间附近检测的声学事件点，
用来细分声母内部的阶段，不替代音素边界。擦音的摩擦段终点取讯飞声母终点与浊音起点中较早者；
塞擦音的阶段以浊音起点为终点（除阻到浊音起点即标准 VOT 区间），因为讯飞有时把送气段划进韵母。
闭塞段在语料中不存在（录音紧贴语音起点裁剪），一律记 NaN。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from parselmouth.praat import call

from app.acoustics import formants as formant_core
from . import common
from .common import Alignment, DbScales, PhoneSeg, SpeakerProfile, SyllableSeg

# ---------------- 固定分析参数（整体写入 result["params"]） ----------------

RELEASE_SEARCH_S = 0.040          # 除阻检测曲线至少覆盖声母区间前 40 ms（爆破检测需要）
RELEASE_STEP_S = 0.001            # 步长 1 ms
RELEASE_WINDOW_S = 0.003          # 窗长 3 ms
RELEASE_BAND_HZ = (1000.0, 12000.0)
RELEASE_RISE_SPAN_S = 0.002       # 除阻 = 2 ms 内带内能量上升量达到阈值的首个帧（瞬态起点）
RELEASE_RISE_FRACTION = 0.5       # 阈值 = 区间最大上升量的 50%（避免被摩擦/送气起始的大上升吸走）
RELEASE_ONSET_MARGIN_S = 0.002    # 除阻搜索区间止于浊音起点 − 2 ms
BURST_MIN_DELAY_S = 0.003         # 爆破结束搜索：除阻后 3 ms 起
BURST_MAX_S = 0.020               # 爆破结束搜索：除阻后 20 ms 止
BURST_SMOOTH_S = 0.002            # 能量包络平滑宽度 2 ms（1 ms 步长 → 3 帧滑动平均）
TRUNCATED_HEAD_S = 0.003          # 浊音起点距文件起点 ≤ 3 ms 视为爆破可能被裁剪

FRICATION_END_TOLERANCE_S = 0.020  # 讯飞声母边界与浊音起点相差超过 20 ms 时提示
FRICTION_BODY_BAND_HZ = (2500.0, 12000.0)   # 塞擦音摩擦本体检测频带
FRICTION_BODY_DROP_DB = 10.0      # 摩擦本体终点：带内能量从段内峰值回落 10 dB 且不再回升
FRICTION_BODY_WINDOW_S = 0.010
FRICTION_BODY_STEP_S = 0.005

VOICING_PULSES = 4                # 浊音起点：至少连续 4 个声门脉冲
VOICING_INTERVAL_FACTOR = 1.25    # 相邻脉冲间隔上限 = 1.25 / floor
VOICING_MIN_SUSTAIN_S = 0.060     # 浊音起点：脉冲段须持续 ≥60 ms（排除送气噪声中的孤立伪脉冲簇）

BURST_SPECTRUM_S = 0.010          # 爆破谱：除阻时刻起 10 ms
BURST_MOMENT_BAND_HZ = (500.0, 12000.0)
BURST_ENERGY_BANDS_HZ = ((0.0, 2500.0), (2500.0, 5000.0), (5000.0, 12000.0))

FRAME_WINDOW_S = 0.025            # 摩擦段分帧：25 ms 窗、5 ms 步长
FRAME_STEP_S = 0.005
FRAME_REGION = (0.2, 0.8)         # 帧中心落在区间 20%–80%
MOMENT_BANDS_HZ = ((500.0, 12000.0), (500.0, 8000.0))   # §9 的频带敏感性检查
PEAK_BAND_HZ = (500.0, 12000.0)
MULTITAPER_NW = 4.0
MULTITAPER_K = 7

BAND_ENERGY_WINDOW_S = 0.010      # 频带能量时间曲线：10 ms 窗、5 ms 步长
BAND_ENERGY_STEP_S = 0.005
BAND_ENERGY_BANDS_HZ = ((0.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0))

# Shadle (2023) 一类参数的频带约定：对文献指标的近似，非原始定义
SECONDARY_PEAK_MIN_SEP_HZ = 1000.0
FM_BAND_HZ = (3000.0, 7000.0)     # 主峰 FM：中频段（Koenig 2013 / Shadle 2023 的频段划分近似）
AMPD_LOW_BAND_HZ = (500.0, 3000.0)   # AmpD 的低频谷搜索段
FH_BAND_HZ = (7000.0, 12000.0)    # 高频最大值 Fh
AMPRANGE_HIGH_HZ = (3000.0, 7000.0)
AMPRANGE_LOW_HZ = (500.0, 3000.0)
HIGH_LEVEL_D_HIGH_HZ = (8000.0, 12000.0)
HIGH_LEVEL_D_REF_HZ = (2000.0, 4000.0)

# 共振峰提取的固定参数见共振峰测量核心（app.acoustics.formants）
FORMANT_TRANSITION_WINDOW = 0.015  # 过渡分析单独用 15 ms 窗（方案 §3.1 默认 25 ms，首帧更早）
TRANSITION_SPAN_S = 0.060         # 过渡段：除阻（或摩擦结束）后 0–60 ms
TRANSITION_OFFSETS_S = (0.010, 0.020, 0.040)
TRANSITION_SHADE_S = (0.010, 0.040)
TRANSITION_FRAME_TOLERANCE_S = 0.015   # 取最近共振峰帧的容差（≈ 窗长一半 + 步长一半）

H_SLICE_POSITIONS = (0.3, 0.6, 0.9)         # /h/ 区间内的频谱切片位置
VOWEL_SLICE_POSITIONS = (0.1, 0.5)          # 韵母区间内的切片位置

_F1_F2_F3_COLORS = ("#1f77b4", "#ff7f0e", "#2ca02c")


def _params_dict(profile: SpeakerProfile) -> dict:
    """本模块实际使用的全部参数（含频带约定，便于核对敏感性设置）。"""
    return {
        "release_detection": {
            "rule": f"在 [讯飞声母起点, 浊音起点 − {RELEASE_ONSET_MARGIN_S * 1000:.0f} ms] 内，"
                    f"取 {RELEASE_BAND_HZ[0] / 1000:.0f}–{RELEASE_BAND_HZ[1] / 1000:.0f} kHz 带内能量"
                    f"（窗 {RELEASE_WINDOW_S * 1000:.0f} ms、步长 {RELEASE_STEP_S * 1000:.0f} ms）"
                    f"{RELEASE_RISE_SPAN_S * 1000:.0f} ms 内上升量首个达到区间最大上升量 "
                    f"{RELEASE_RISE_FRACTION * 100:.0f}% 的帧作为除阻（瞬态起点）；"
                    "分析窗伸出录音起点的帧不参与",
            "burst_end": f"包络做 {BURST_SMOOTH_S * 1000:.0f} ms 平滑后，在除阻后 "
                         f"{BURST_MIN_DELAY_S * 1000:.0f}–{BURST_MAX_S * 1000:.0f} ms 内取峰值之后的"
                         "第一个局部极小；找不到极小时记 NaN（塞擦音此时摩擦段起点取除阻时刻）",
            "truncated_rules": f"浊音起点距文件起点 ≤ {TRUNCATED_HEAD_S * 1000:.0f} ms，"
                               "或除阻搜索区间长度不足 2 ms",
        },
        "voicing_onset": {
            "method": "To PointProcess (periodic, cc)",
            "floor_hz": profile.f0_floor, "ceiling_hz": profile.f0_ceiling,
            "consecutive_pulses": VOICING_PULSES,
            "max_interval_s": VOICING_INTERVAL_FACTOR / profile.f0_floor,
            "min_sustain_s": VOICING_MIN_SUSTAIN_S,
            "note": "脉冲段须持续 ≥60 ms，排除送气噪声或倍频伪脉冲形成的孤立短簇",
        },
        "burst_spectrum": {
            "window_s": BURST_SPECTRUM_S, "window": "hann", "range_hz": [0.0, 12000.0],
            "moment_band_hz": list(BURST_MOMENT_BAND_HZ),
            "energy_bands_hz": [list(b) for b in BURST_ENERGY_BANDS_HZ],
            "spectrum": "10·log10(|FFT|²/(sr·Σw²))，窗能量归一，参考值 1",
        },
        "frication_frames": {
            "window_s": FRAME_WINDOW_S, "step_s": FRAME_STEP_S,
            "center_region": list(FRAME_REGION), "moment_bands_hz": [list(b) for b in MOMENT_BANDS_HZ],
            "peak_band_hz": list(PEAK_BAND_HZ), "window_function": "hann（对称）",
            "zero_padding": "4 ×（不小于片段长度的 2 的整数次幂）",
        },
        "multitaper": {"type": "dpss", "NW": MULTITAPER_NW, "tapers": MULTITAPER_K},
        "mean_spectrum_params": {
            "curve": "Hann 多帧平均功率谱（20%–80% 段），窗能量归一 10·log10(|FFT|²/(sr·Σw²))",
            "FM_band_hz": list(FM_BAND_HZ), "FM": "中频段内的最大谱峰，AmpM 为其幅度",
            "AmpD": "AmpM − 低频段内的最小值", "AmpD_low_band_hz": list(AMPD_LOW_BAND_HZ),
            "secondary_peak": "与 FM、Fh 均相距 ≥1 kHz 的最高局部峰",
            "secondary_peak_min_separation_hz": SECONDARY_PEAK_MIN_SEP_HZ,
            "Fh_band_hz": list(FH_BAND_HZ),
            "AmpRange_bands_hz": [list(AMPRANGE_LOW_HZ), list(AMPRANGE_HIGH_HZ)],
            "HighLevelD_bands_hz": [list(HIGH_LEVEL_D_HIGH_HZ), list(HIGH_LEVEL_D_REF_HZ)],
            "band_level": "10·log10(带内平均功率)，参考值 1",
            "note": "频带为近似 Koenig et al. (2013) / Shadle et al. (2023) 频段划分的约定实现",
        },
        "band_energy_series": {
            "window_s": BAND_ENERGY_WINDOW_S, "step_s": BAND_ENERGY_STEP_S,
            "bands_hz": [list(b) for b in BAND_ENERGY_BANDS_HZ],
            "HighLevelD_bands_hz": [list(HIGH_LEVEL_D_HIGH_HZ), list(HIGH_LEVEL_D_REF_HZ)],
        },
        "closure": "语料录音紧贴语音起点裁剪，闭塞段不可测，closure_ms 一律为 NaN",
        "frication_end": {
            "rule": "擦音：摩擦段终点 = min(讯飞声母结束, 浊音起点)（方案 Landmark 层的浊音起始事件，"
                    "仅细化摩擦段终点，音素边界仍以讯飞为准）；塞擦音统一取浊音起点，见 affricate 条目",
            "difference_tolerance_s": FRICATION_END_TOLERANCE_S,
            "source_column": "frication_end_source（alignment = 讯飞声母边界 / voicing_onset = 浊音起点）",
        },
        "affricate": {
            "segment": "除阻阶段统一定义为 [除阻, 浊音起点]（标准 VOT 区间），不受讯飞声母终点影响；"
                       "浊音起点缺失时才退回讯飞声母终点",
            "frication_body_end": f"摩擦本体终点：{FRICTION_BODY_BAND_HZ[0] / 1000:.0f}–"
                                  f"{FRICTION_BODY_BAND_HZ[1] / 1000:.0f} kHz 带内能量"
                                  f"（窗 {FRICTION_BODY_WINDOW_S * 1000:.0f} ms、步长 "
                                  f"{FRICTION_BODY_STEP_S * 1000:.0f} ms）从除阻（或爆破结束）→浊音起点"
                                  f"段内峰值回落 ≥{FRICTION_BODY_DROP_DB:.0f} dB 且此后一直保持在该水平"
                                  "以下的起点；找不到回落点时取段终点；保证 摩擦段起点 ≤ 本体终点 ≤ 浊音起点",
            "aspiration": "摩擦本体终点 → 浊音起点",
            "R_fric": "摩擦本体时长 /（浊音起点 − 讯飞声母起点）；浊音起点缺失时退回讯飞声母终点；"
                      "闭塞段不可测，分母不含闭塞",
            "self_check": "爆破 + 摩擦本体 + 送气 与 VOT 差值 ≤1 ms（爆破 NaN 时只算摩擦 + 送气），"
                          "且各阶段时序非负；不满足则 R_fric 记 NaN 并写 warning",
            "frication_start_source": "burst_end（爆破结束）或 release_inseparable（爆破与摩擦包络连续）",
            "formant_transition": "11a 下面板画 [浊音起点 −20 ms, 浊音起点 +60 ms]，"
                                  "浊音起点之前的帧为送气噪声激励，浅灰绘制仅供参考",
        },
    }


# ---------------- 通用小工具 ----------------

def _band_mask(freqs: np.ndarray, band: tuple[float, float]) -> np.ndarray:
    return (freqs >= band[0]) & (freqs <= band[1])


def _window_energy_spectrum(seg: np.ndarray, sr: int, n_fft: int) -> tuple[np.ndarray, np.ndarray]:
    """Hann 窗功率谱并除以 (sr·Σw²)：窗能量归一后不同窗长的估计才可直接叠加比较。"""
    freqs, power = common.power_spectrum(seg, sr, n_fft=n_fft)
    from scipy.signal import get_window

    window = get_window("hann", len(seg), fftbins=False)
    return freqs, power / (sr * float(np.sum(window ** 2)))


def _band_level(power: np.ndarray, mask: np.ndarray) -> float:
    """带内平均功率的 dB 值（参考值 1）；无能量时为 NaN。"""
    values = power[mask]
    if values.size == 0 or float(values.mean()) <= 0.0:
        return float("nan")
    return float(common.db(values.mean()))


def _moments(freqs: np.ndarray, power: np.ndarray, band: tuple[float, float]) -> tuple[float, float, float, float]:
    """方案 §8.3 的四个谱矩（功率谱权重）；无有效能量时全为 NaN。"""
    mask = _band_mask(freqs, band)
    f = freqs[mask]
    p = power[mask]
    total = float(p.sum())
    if f.size == 0 or total <= 0.0:
        return (float("nan"),) * 4
    w = p / total
    m1 = float(np.sum(w * f))
    m2 = float(np.sqrt(np.sum(w * (f - m1) ** 2)))
    if m2 <= 0.0:
        return (m1, float("nan"), float("nan"), float("nan"))
    m3 = float(np.sum(w * (f - m1) ** 3) / m2 ** 3)
    m4 = float(np.sum(w * (f - m1) ** 4) / m2 ** 4)
    return m1, m2, m3, m4


def _spectrum_peak(freqs: np.ndarray, power: np.ndarray, band: tuple[float, float]) -> tuple[float, float]:
    """带内功率谱峰（频率 Hz，dB）。"""
    mask = _band_mask(freqs, band)
    values = power[mask]
    if values.size == 0:
        return float("nan"), float("nan")
    index = int(np.argmax(values))
    return float(freqs[mask][index]), float(common.db(values[index]))


def _frame_segment(x: np.ndarray, sr: int, center: float, half_samples: int) -> np.ndarray:
    """以 center 为中心取 2·half_samples 长的帧；越界处以零补齐（保持窗对齐）。"""
    middle = int(round(center * sr))
    frame = np.zeros(2 * half_samples)
    a, b = middle - half_samples, middle + half_samples
    frame[max(0, -a):min(2 * half_samples, len(x) - a)] = x[max(a, 0):min(b, len(x))]
    return frame


def _band_power_curve(x: np.ndarray, sr: int, centers: np.ndarray, window_s: float,
                      bands: tuple[tuple[float, float], ...]) -> dict[str, np.ndarray]:
    """逐帧带内平均功率（dB，参考值 1）；键为 "低频起始-高频结束" 的 kHz 文本。"""
    from scipy.signal import get_window

    half = int(round(window_s * sr / 2))
    window = get_window("hann", 2 * half, fftbins=False)
    freqs = np.fft.rfftfreq(2 * half, 1.0 / sr)
    masks = [_band_mask(freqs, band) for band in bands]
    keys = [f"{band[0] / 1000:.0f}-{band[1] / 1000:.0f}kHz" for band in bands]
    out = {key: np.full(len(centers), np.nan) for key in keys}
    for i, center in enumerate(centers):
        frame = _frame_segment(x, sr, float(center), half)
        power = np.abs(np.fft.rfft(frame * window)) ** 2
        for key, mask in zip(keys, masks):
            out[key][i] = _band_level(power, mask)
    return out


# ---------------- 塞音：除阻、浊音起点与爆破谱 ----------------

def _pulse_train(snd, profile: SpeakerProfile) -> np.ndarray:
    """Praat 声门脉冲时刻（To PointProcess (periodic, cc)）。"""
    point_process = call(snd, "To PointProcess (periodic, cc)",
                         profile.f0_floor, profile.f0_ceiling)
    count = int(call(point_process, "Get number of points"))
    if count == 0:
        return np.array([])
    return np.array([call(point_process, "Get time from index", i)
                     for i in range(1, count + 1)])


def _voicing_onset(pulses: np.ndarray, profile: SpeakerProfile, search_from: float) -> float:
    """search_from 之后第一个满足连续性（≥4 个脉冲、间隔均 < 1.25/floor）且能持续
    ≥60 ms 的声门脉冲；孤立短脉冲簇（如送气噪声或倍频伪脉冲）不构成浊音起点。"""
    if len(pulses) == 0:
        return float("nan")
    max_interval = VOICING_INTERVAL_FACTOR / profile.f0_floor
    start = int(np.searchsorted(pulses, search_from, side="left"))
    for j in range(start, len(pulses) - VOICING_PULSES + 1):
        gaps = np.diff(pulses[j:j + VOICING_PULSES])
        if not np.all(gaps < max_interval):
            continue
        last = int(np.searchsorted(pulses, pulses[j] + VOICING_MIN_SUSTAIN_S, side="right")) - 1
        if last - j + 1 < VOICING_PULSES:
            continue
        # 60 ms 窗口内必须真的布满脉冲（容许缺失一个周期）：孤立短簇的跨度到不了
        if pulses[last] - pulses[j] < VOICING_MIN_SUSTAIN_S - max_interval:
            continue
        if np.all(np.diff(pulses[j:last + 1]) < max_interval):
            return float(pulses[j])
    return float("nan")


def _prevoicing(pulses: np.ndarray, profile: SpeakerProfile, release: float) -> float:
    """除阻前连续脉冲段的长度；无脉冲则为 0。"""
    if len(pulses) == 0 or not np.isfinite(release):
        return 0.0
    max_interval = VOICING_INTERVAL_FACTOR / profile.f0_floor
    start = int(np.searchsorted(pulses, release, side="right"))
    if start == 0:
        return 0.0
    k = start - 1
    while k > 0 and pulses[k] - pulses[k - 1] < max_interval:
        k -= 1
    return float(pulses[start - 1] - pulses[k])


def _release_and_burst(x: np.ndarray, sr: int, initial: PhoneSeg,
                       voicing_onset: float) -> dict:
    """除阻 = [讯飞声母起点, 浊音起点 − 2 ms] 内 1–12 kHz 能量 2 ms 上升量最大的帧（瞬态起点）；
    爆破结束点 = 除阻后 3–20 ms 内平滑包络峰值之后的第一个局部极小。"""
    truncated = False
    if not np.isfinite(voicing_onset) or voicing_onset <= TRUNCATED_HEAD_S:
        truncated = True
    search_end = voicing_onset - RELEASE_ONSET_MARGIN_S if np.isfinite(voicing_onset) \
        else initial.t0 + RELEASE_SEARCH_S
    if search_end - initial.t0 < RELEASE_RISE_SPAN_S:
        truncated = True
    # 曲线覆盖到除阻后 20 ms（爆破检测需要），但不越过浊音起点对应的搜索区间之外太多
    curve_end = max(search_end, initial.t0 + RELEASE_SEARCH_S)
    centers = np.arange(initial.t0, curve_end + 1e-9, RELEASE_STEP_S)
    energy_db = _band_power_curve(x, sr, centers, RELEASE_WINDOW_S, (RELEASE_BAND_HZ,))[
        f"{RELEASE_BAND_HZ[0] / 1000:.0f}-{RELEASE_BAND_HZ[1] / 1000:.0f}kHz"]

    release = float("nan")
    # 排除分析窗（±1.5 ms）伸出录音起点的帧；上升终点须落在搜索区间内
    eligible = (centers + RELEASE_RISE_SPAN_S <= search_end + 1e-9) \
        & (centers >= RELEASE_WINDOW_S / 2 - 1e-9)
    if np.any(eligible[:-2]):
        rises = energy_db[2:] - energy_db[:-2]
        masked = np.where(eligible[:-2], rises, -np.inf)
        threshold = RELEASE_RISE_FRACTION * float(np.max(masked))
        reached = np.where(masked >= threshold)[0]
        release = float(centers[reached[0]])

    burst = float("nan")
    if np.isfinite(release):
        taps = int(round(BURST_SMOOTH_S / RELEASE_STEP_S)) + 1     # 1 ms 步长 → 3 帧，跨度 2 ms
        envelope = np.convolve(energy_db, np.ones(taps) / taps, mode="same")
        window = np.where((centers >= release + BURST_MIN_DELAY_S)
                          & (centers <= release + BURST_MAX_S + 1e-9))[0]
        if window.size:
            peak_index = window[0] + int(np.argmax(envelope[window[0]:window[-1] + 1]))
            for j in range(peak_index + 1, len(envelope) - 1):
                if centers[j] - release > BURST_MAX_S:
                    break
                left_lower = envelope[j] <= envelope[j - 1]
                right_lower = envelope[j] <= envelope[j + 1]
                strictly_lower = envelope[j] < envelope[j - 1] or envelope[j] < envelope[j + 1]
                if left_lower and right_lower and strictly_lower:
                    burst = float(centers[j] - release)
                    break
    return {"release": release, "truncated": truncated, "burst_s": burst}


def _frication_end(initial: PhoneSeg, voicing_onset: float, file_name: str,
                   warnings: list[str]) -> tuple[float, str]:
    """擦音摩擦段终点：讯飞声母结束与浊音起点中较早者；返回 (终点秒, 终点来源 alignment / voicing_onset)。"""
    if not np.isfinite(voicing_onset):
        warnings.append(f"{file_name}：未找到浊音起点，摩擦段终点沿用讯飞声母边界")
        return initial.t1, "alignment"
    if voicing_onset < initial.t1 - FRICATION_END_TOLERANCE_S:
        difference_ms = (initial.t1 - voicing_onset) * 1000.0
        warnings.append(f"{file_name}：讯飞声母边界晚于浊音起点 {difference_ms:.0f} ms，"
                        f"摩擦段终点改用浊音起点")
        return float(voicing_onset), "voicing_onset"
    if voicing_onset > initial.t1 + FRICATION_END_TOLERANCE_S:
        difference_ms = (voicing_onset - initial.t1) * 1000.0
        warnings.append(f"{file_name}：浊音起点晚于讯飞声母边界 {difference_ms:.0f} ms，"
                        f"摩擦段终点沿用讯飞边界")
    return (float(min(initial.t1, voicing_onset)),
            "alignment" if initial.t1 <= voicing_onset else "voicing_onset")


def _frication_body_end(x: np.ndarray, sr: int, segment_start: float, segment_end: float,
                        voicing_onset: float) -> float:
    """塞擦音摩擦本体终点：2.5–12 kHz 带内能量从除阻（或爆破结束）→浊音起点段内峰值回落
    ≥10 dB 且此后一直保持在该水平以下的起点；找不到回落点时取段终点。"""
    curve_end = voicing_onset if np.isfinite(voicing_onset) else segment_end
    centers = np.arange(segment_start, curve_end + FRICTION_BODY_STEP_S / 2, FRICTION_BODY_STEP_S)
    if len(centers) == 0:
        return segment_end
    levels = _band_power_curve(x, sr, centers, FRICTION_BODY_WINDOW_S,
                               (FRICTION_BODY_BAND_HZ,))[
        f"{FRICTION_BODY_BAND_HZ[0] / 1000:.0f}-{FRICTION_BODY_BAND_HZ[1] / 1000:.0f}kHz"]
    below = levels <= float(np.nanmax(levels)) - FRICTION_BODY_DROP_DB
    if not below.any() or not below[-1]:
        return segment_end
    if not (~below).any():        # 整段都低于门限：起点处摩擦已结束
        return segment_start
    last_above = int(np.where(~below)[0][-1])
    if last_above + 1 >= len(centers):
        return segment_end
    return float(min(centers[last_above + 1], segment_end))   # 5 ms 网格可能越过段终点，钳制回来


def _burst_spectrum(x: np.ndarray, sr: int, release: float) -> dict | None:
    """除阻时刻起 10 ms 的 Hann 功率谱（0–12 kHz）及谱峰、谱矩、频带能量占比。"""
    if not np.isfinite(release):
        return None
    n_fft = 4 * 2 ** int(np.ceil(np.log2(BURST_SPECTRUM_S * sr)))
    start = int(round(release * sr))
    seg = x[start:start + int(round(BURST_SPECTRUM_S * sr))]
    if len(seg) < 16:
        return None
    freqs, power = _window_energy_spectrum(seg, sr, n_fft)
    peak_hz, peak_db = _spectrum_peak(freqs, power, (0.0, 12000.0))
    m1, m2, m3, m4 = _moments(freqs, power, BURST_MOMENT_BAND_HZ)
    total = float(power[_band_mask(freqs, (0.0, 12000.0))].sum())
    ratios = [float(power[_band_mask(freqs, band)].sum()) / total if total > 0 else float("nan")
              for band in BURST_ENERGY_BANDS_HZ]
    return {"freqs": freqs, "power": power, "peak_hz": peak_hz, "peak_db": peak_db,
            "M1": m1, "M2": m2, "M3": m3, "M4": m4,
            "energy_ratios": dict(zip(("low", "mid", "high"), ratios))}


# ---------------- 摩擦段：谱矩、平均谱与 Shadle 类参数 ----------------

def _frication_analysis(x: np.ndarray, sr: int, t0: float, t1: float) -> dict:
    """对 [t0, t1] 区间按擦音方法分析：20%–80% 分帧谱矩（两套频带）与平均谱。"""
    duration = t1 - t0
    a = t0 + FRAME_REGION[0] * duration
    b = t0 + FRAME_REGION[1] * duration
    centers = np.arange(a, b + FRAME_STEP_S / 2, FRAME_STEP_S) if duration > 0 else np.array([])
    n_fft = 4 * 2 ** int(np.ceil(np.log2(FRAME_WINDOW_S * sr)))
    band_keys = [f"{lo:.0f}_{hi:.0f}" for lo, hi in MOMENT_BANDS_HZ]

    times: list[float] = []
    powers: list[np.ndarray] = []
    moments: dict[str, list[tuple[float, float, float, float]]] = {key: [] for key in band_keys}
    peaks: list[float] = []
    incomplete = False
    freqs: np.ndarray | None = None
    for center in centers:
        seg, complete = common.segment_at(x, sr, float(center), FRAME_WINDOW_S)
        if not complete:
            incomplete = True
        if len(seg) < 16:
            continue
        freqs, power = _window_energy_spectrum(seg, sr, n_fft)
        times.append(float(center))
        powers.append(power)
        peaks.append(_spectrum_peak(freqs, power, PEAK_BAND_HZ)[0])
        for band, key in zip(MOMENT_BANDS_HZ, band_keys):
            moments[key].append(_moments(freqs, power, band))

    # multitaper 单次估计：对同一 20%–80% 区间整体加 7 个 DPSS 窗
    multitaper: tuple[np.ndarray, np.ndarray] | None = None
    seg = x[int(round(a * sr)):int(round(b * sr))]
    if len(seg) >= 16:
        from scipy.signal.windows import dpss

        seg = seg - seg.mean()
        n_fft_multitaper = 4 * 2 ** int(np.ceil(np.log2(len(seg))))
        tapers = dpss(len(seg), MULTITAPER_NW, MULTITAPER_K)
        taper_energy = float(np.dot(tapers[0], tapers[0]))   # 各 DPSS 窗能量相同
        accumulated = np.zeros(n_fft_multitaper // 2 + 1)
        for taper in tapers:
            accumulated += np.abs(np.fft.rfft(seg * taper, n=n_fft_multitaper)) ** 2
        multitaper = (np.fft.rfftfreq(n_fft_multitaper, 1.0 / sr),
                      accumulated / (len(tapers) * sr * taper_energy))

    mean_spectrum = (freqs, np.mean(powers, axis=0)) if powers else None
    shadle = _mean_spectrum_params(*mean_spectrum) if mean_spectrum is not None else {}
    return {"t0": a, "t1": b, "times": np.array(times), "moment_values": moments,
            "peak_hz": np.array(peaks), "mean_spectrum": mean_spectrum,
            "multitaper": multitaper, "shadle": shadle,
            "incomplete": incomplete, "band_keys": band_keys}


def _mean_spectrum_params(freqs: np.ndarray, power: np.ndarray) -> dict:
    """在平均谱上提取 Shadle (2023) 一类参数（频带划分见模块常量，近似文献定义）。"""
    from scipy.signal import find_peaks

    spectrum_db = common.db(power)
    band = _band_mask(freqs, (500.0, 12000.0))
    f_band, p_band = freqs[band], power[band]
    db_band = spectrum_db[band]

    # 主峰 FM：中频段（3–7 kHz）内的最大峰，AmpM 为其幅度
    fm_hz, fm_db = _spectrum_peak(freqs, power, FM_BAND_HZ)
    fh_hz, fh_db = _spectrum_peak(freqs, power, FH_BAND_HZ)

    # 次峰：与 FM、Fh 均相距 ≥1 kHz 的最高局部峰（在 0.5–12 kHz 内搜索，避免与 Fh 重复标记）
    peak_indices, _ = find_peaks(p_band)
    candidates = [i for i in peak_indices
                  if min(abs(f_band[i] - fm_hz), abs(f_band[i] - fh_hz)) >= SECONDARY_PEAK_MIN_SEP_HZ]
    if candidates:
        best = max(candidates, key=lambda i: p_band[i])
        peak2_hz, peak2_db = float(f_band[best]), float(db_band[best])
    else:
        peak2_hz, peak2_db = float("nan"), float("nan")

    # AmpD = AmpM − 低频段（0.5–3 kHz）内的最小值
    low_mask = _band_mask(freqs, AMPD_LOW_BAND_HZ)
    amp_d = fm_db - float(np.min(spectrum_db[low_mask])) if low_mask.any() else float("nan")
    amp_range = _band_level(power, _band_mask(freqs, AMPRANGE_HIGH_HZ)) - \
        _band_level(power, _band_mask(freqs, AMPRANGE_LOW_HZ))
    high_level_d = _band_level(power, _band_mask(freqs, HIGH_LEVEL_D_HIGH_HZ)) - \
        _band_level(power, _band_mask(freqs, HIGH_LEVEL_D_REF_HZ))
    return {"FM_hz": fm_hz, "FM_dB": fm_db, "peak2_hz": peak2_hz, "peak2_dB": peak2_db,
            "AmpD_dB": amp_d, "Fh_hz": fh_hz, "Fh_dB": fh_db,
            "AmpRange_dB": amp_range, "HighLevelD_dB": high_level_d}


# ---------------- 共振峰轨迹与过渡取样 ----------------

def _formant_track(snd, profile: SpeakerProfile):
    """全录音的 Burg F1–F3 轨迹（未定义帧为 NaN）；过渡分析用 15 ms 窗。"""
    track = formant_core.extract(snd, profile.formant_ceiling,
                                 window_length=FORMANT_TRANSITION_WINDOW)
    tracks = [track.freqs[k] for k in range(3)]
    actual = {"dx": track.time_step, "x1": track.first_time, "n_frames": int(len(track.times))}
    return track.times, tracks, actual


def _nearest_formant(times: np.ndarray, values: np.ndarray, target: float) -> float:
    """最近共振峰帧的取值；帧距超过容差时为 NaN。"""
    if len(times) == 0:
        return float("nan")
    index = int(np.argmin(np.abs(times - target)))
    if abs(times[index] - target) > TRANSITION_FRAME_TOLERANCE_S:
        return float("nan")
    return float(values[index])


def _transition_values(times: np.ndarray, tracks: list[np.ndarray], reference: float) -> dict:
    """过渡段参考点后 +10/+20/+40 ms 的 F1–F3。"""
    out: dict[str, float] = {}
    for offset in TRANSITION_OFFSETS_S:
        for number, track in zip((1, 2, 3), tracks):
            out[f"F{number}_plus{int(offset * 1000)}ms"] = _nearest_formant(
                times, track, reference + offset)
    return out


# ---------------- 各类别分析 ----------------

def _analyze_stop(x, sr, snd, aln: Alignment, syll: SyllableSeg, initial: PhoneSeg,
                  profile: SpeakerProfile, formant_track: Callable, warnings: list[str]) -> dict:
    file_name = aln.file
    pulses = _pulse_train(snd, profile)
    onset = _voicing_onset(pulses, profile, 0.0)
    if not np.isfinite(onset):
        warnings.append(f"{file_name}：未找到满足连续性条件的声门脉冲，浊音起点与 VOT 记为 NaN")

    release_data = _release_and_burst(x, sr, initial, onset)
    release, burst = release_data["release"], release_data["burst_s"]
    if release_data["truncated"]:
        warnings.append(f"{file_name}：爆破可能被录音裁剪截断（浊音起点距文件起点 "
                        f"{onset * 1000:.1f} ms 或除阻搜索区间不足 2 ms）")
    if not np.isfinite(release):
        warnings.append(f"{file_name}：除阻搜索区间内无法定位瞬态起点，release_time_s 记为 NaN")
    warnings.append(f"{file_name}：塞音闭塞段不可测（录音紧贴语音起点裁剪），closure_ms 记为 NaN")

    prevoicing = _prevoicing(pulses, profile, release)
    vot = onset - release if np.isfinite(onset) and np.isfinite(release) else float("nan")
    # 爆破与送气在平滑包络上连续（无局部极小）时无法分开：送气时长取整个 VOT（含爆破），
    # 与塞擦音「爆破与摩擦不可分时摩擦段从除阻开始」的处理一致
    if np.isfinite(burst):
        aspiration = max(vot - burst, 0.0) if np.isfinite(vot) else float("nan")
        aspiration_source = "vot_minus_burst"
    else:
        aspiration = vot
        aspiration_source = "vot_burst_inseparable"
        warnings.append(f"{file_name}：除阻后 3–20 ms 内未找到爆破结束点（平滑包络无局部极小），"
                        f"爆破与送气在包络上连续：burst_ms 记为 NaN，aspiration_ms 取整个 VOT（含爆破）")

    burst_spectrum = _burst_spectrum(x, sr, release)
    if burst_spectrum is None:
        warnings.append(f"{file_name}：除阻位置不可用或过于贴近录音末尾，爆破谱不可计算")

    times, tracks, _ = formant_track()
    transition = _transition_values(times, tracks, release) if np.isfinite(release) else {}
    missing = [key for key, value in transition.items() if not np.isfinite(value)]
    if missing:
        warnings.append(f"{file_name}：Burg 共振峰轨迹未覆盖部分过渡取样点（{', '.join(missing)}），记为 NaN")

    row = _base_row(aln, syll, initial, "stop")
    row.update({
        "release_time_s": release, "release_truncated": release_data["truncated"],
        "burst_ms": burst * 1000.0, "voicing_onset_s": onset, "VOT_ms": vot * 1000.0,
        "prevoicing_ms": prevoicing * 1000.0, "aspiration_ms": aspiration * 1000.0,
        "aspiration_source": aspiration_source,
        "closure_ms": float("nan"), "transition_ref_s": release,
    })
    _fill_burst_fields(row, burst_spectrum)
    _fill_transition_fields(row, transition)
    return {"row": row, "moment_rows": [], "release": release, "truncated": release_data["truncated"],
            "burst_s": burst, "onset": onset, "vot_s": vot, "aspiration_s": aspiration,
            "burst_spectrum": burst_spectrum, "transition": transition,
            "formant_times": times, "formant_tracks": tracks}


def _analyze_fricative(x, sr, snd, aln: Alignment, syll: SyllableSeg, initial: PhoneSeg,
                       profile: SpeakerProfile, formant_track: Callable, warnings: list[str]) -> dict:
    file_name = aln.file
    pulses = _pulse_train(snd, profile)
    voicing_onset = _voicing_onset(pulses, profile, initial.t0)
    frication_end, frication_end_source = _frication_end(initial, voicing_onset, file_name, warnings)
    frication = _frication_analysis(x, sr, initial.t0, frication_end)
    if frication["incomplete"]:
        warnings.append(f"{file_name}：部分摩擦段分析窗越出录音边界，对应帧仅供参考")
    if len(frication["times"]) == 0:
        warnings.append(f"{file_name}：摩擦段 20%–80% 区间内没有有效帧，谱矩与平均谱记为 NaN")

    syllable_t0 = syll.t0
    syllable_t1 = syll.final.t1 if syll.final else syll.t1
    band_centers = np.arange(syllable_t0, syllable_t1 + BAND_ENERGY_STEP_S / 2, BAND_ENERGY_STEP_S)
    band_levels = _band_power_curve(x, sr, band_centers, BAND_ENERGY_WINDOW_S,
                                    BAND_ENERGY_BANDS_HZ + (HIGH_LEVEL_D_HIGH_HZ, HIGH_LEVEL_D_REF_HZ))
    high_level_key = f"{HIGH_LEVEL_D_HIGH_HZ[0] / 1000:.0f}-{HIGH_LEVEL_D_HIGH_HZ[1] / 1000:.0f}kHz"
    ref_level_key = f"{HIGH_LEVEL_D_REF_HZ[0] / 1000:.0f}-{HIGH_LEVEL_D_REF_HZ[1] / 1000:.0f}kHz"
    high_level_d = band_levels[high_level_key] - band_levels[ref_level_key]

    times, tracks, _ = formant_track()
    transition = _transition_values(times, tracks, frication_end)

    if initial.label == "h":
        final_phone = syll.final
        slice_positions = [initial.t0 + fraction * initial.duration for fraction in H_SLICE_POSITIONS]
        if final_phone is not None:
            slice_positions += [final_phone.t0 + fraction * final_phone.duration
                                for fraction in VOWEL_SLICE_POSITIONS]
        if any(not common.segment_at(x, sr, center, FRAME_WINDOW_S)[1] for center in slice_positions):
            warnings.append(f"{file_name}：/h/ 连续性图的部分频谱切片越出录音边界，对应曲线仅供参考")

    row = _base_row(aln, syll, initial, "fricative")
    row.update({"frication_t0_s": initial.t0, "frication_t1_s": frication_end,
                "frication_end_source": frication_end_source,
                "transition_ref_s": frication_end})
    _fill_frication_fields(row, frication)
    _fill_transition_fields(row, transition)
    return {"row": row, "moment_rows": _moment_rows(aln, initial, frication),
            "frication": frication, "frication_end": frication_end,
            "band_centers": band_centers, "band_levels": band_levels,
            "high_level_d": high_level_d, "transition": transition,
            "formant_times": times, "formant_tracks": tracks}


def _analyze_affricate(x, sr, snd, aln: Alignment, syll: SyllableSeg, initial: PhoneSeg,
                       profile: SpeakerProfile, formant_track: Callable, warnings: list[str]) -> dict:
    file_name = aln.file
    pulses = _pulse_train(snd, profile)
    onset = _voicing_onset(pulses, profile, 0.0)
    if not np.isfinite(onset):
        warnings.append(f"{file_name}：未找到满足连续性条件的声门脉冲，浊音起点与 VOT 记为 NaN")

    release_data = _release_and_burst(x, sr, initial, onset)
    release, burst = release_data["release"], release_data["burst_s"]
    if release_data["truncated"]:
        warnings.append(f"{file_name}：爆破可能被录音裁剪截断（浊音起点距文件起点 "
                        f"{onset * 1000:.1f} ms 或除阻搜索区间不足 2 ms）")
    warnings.append(f"{file_name}：塞擦音闭塞段不可测（录音紧贴语音起点裁剪），closure_ms 记为 NaN")

    prevoicing = _prevoicing(pulses, profile, release)
    vot = onset - release if np.isfinite(onset) and np.isfinite(release) else float("nan")

    # 段终点：塞擦音统一取浊音起点（除阻阶段即标准 VOT 区间），不受讯飞声母终点影响；
    # 浊音起点缺失时才退回讯飞声母终点。讯飞终点只用于方向提示。
    if np.isfinite(onset):
        segment_end = float(onset)
        frication_end_source = "voicing_onset"
        difference_ms = (onset - initial.t1) * 1000.0
        if onset < initial.t1 - FRICATION_END_TOLERANCE_S:
            warnings.append(f"{file_name}：讯飞声母边界晚于浊音起点 {-difference_ms:.0f} ms，"
                            f"摩擦段终点取浊音起点")
        elif onset > initial.t1 + FRICATION_END_TOLERANCE_S:
            warnings.append(f"{file_name}：讯飞声母边界早于浊音起点 {difference_ms:.0f} ms"
                            f"（送气被划入韵母），摩擦段终点取浊音起点")
    else:
        segment_end = initial.t1
        frication_end_source = "alignment"
        warnings.append(f"{file_name}：未找到浊音起点，摩擦段终点沿用讯飞声母边界")

    # 摩擦段起点：爆破结束；包络上爆破与摩擦连续时取除阻时刻
    if np.isfinite(burst) and np.isfinite(release):
        frication_t0 = release + burst
        frication_start_source = "burst_end"
    else:
        frication_t0 = release
        frication_start_source = "release_inseparable"
        warnings.append(f"{file_name}：爆破与摩擦在能量包络上连续，无法分开，"
                        f"摩擦段起点取除阻时刻（burst_ms 记为 NaN）")

    # 摩擦本体终点（谱分析区间）与送气段：只在 [摩擦段起点, 段终点] 内搜索
    frication_t1 = segment_end if not np.isfinite(frication_t0) else \
        _frication_body_end(x, sr, frication_t0, segment_end, segment_end)
    aspiration = onset - frication_t1 if np.isfinite(onset) and np.isfinite(frication_t1) \
        else float("nan")
    denominator = segment_end - initial.t0
    r_fric = (frication_t1 - frication_t0) / denominator \
        if np.isfinite(frication_t0) and denominator > 0 else float("nan")

    # 自检：爆破 + 摩擦本体 + 送气 ≈ VOT（爆破 NaN 时只算摩擦 + 送气），且各阶段时序非负；
    # 不满足说明阶段划分不自洽，R_fric 记为 NaN
    if np.isfinite(vot) and np.isfinite(frication_t0) and np.isfinite(frication_t1):
        accounted = (burst if np.isfinite(burst) else 0.0) \
            + (frication_t1 - frication_t0) + (aspiration if np.isfinite(aspiration) else 0.0)
        ordered = frication_t0 <= frication_t1 + 1e-9 and frication_t1 <= segment_end + 1e-9
        if abs(accounted - vot) > 0.001 or not ordered:
            warnings.append(f"{file_name}：阶段时长之和 {accounted * 1000:.1f} ms 与 VOT "
                            f"{vot * 1000:.1f} ms 不一致（或阶段时序越界），R_fric 记为 NaN")
            r_fric = float("nan")

    frication = _frication_analysis(x, sr, frication_t0, frication_t1)
    if frication["incomplete"]:
        warnings.append(f"{file_name}：部分摩擦段分析窗越出录音边界，对应帧仅供参考")
    if len(frication["times"]) == 0:
        warnings.append(f"{file_name}：摩擦本体 20%–80% 区间内没有有效帧，谱矩与平均谱记为 NaN")

    burst_spectrum = _burst_spectrum(x, sr, release)
    if burst_spectrum is None:
        warnings.append(f"{file_name}：除阻位置不可用或过于贴近录音末尾，爆破谱不可计算")

    times, tracks, _ = formant_track()
    transition = _transition_values(times, tracks, onset) if np.isfinite(onset) else {}
    missing = [key for key, value in transition.items() if not np.isfinite(value)]
    if missing:
        warnings.append(f"{file_name}：Burg 共振峰轨迹未覆盖部分过渡取样点（{', '.join(missing)}），记为 NaN")

    row = _base_row(aln, syll, initial, "affricate")
    row.update({
        "release_time_s": release, "release_truncated": release_data["truncated"],
        "burst_ms": burst * 1000.0, "voicing_onset_s": onset, "VOT_ms": vot * 1000.0,
        "prevoicing_ms": prevoicing * 1000.0, "aspiration_ms": aspiration * 1000.0,
        "closure_ms": float("nan"),
        "frication_t0_s": frication_t0, "frication_t1_s": frication_t1,
        "frication_start_source": frication_start_source, "R_fric": r_fric,
        "frication_end_source": frication_end_source, "transition_ref_s": onset,
    })
    _fill_burst_fields(row, burst_spectrum)
    _fill_frication_fields(row, frication)
    _fill_transition_fields(row, transition)
    return {"row": row, "moment_rows": _moment_rows(aln, initial, frication),
            "release": release, "burst_s": burst, "onset": onset, "vot_s": vot,
            "frication_t0": frication_t0, "frication_t1": frication_t1,
            "frication_end": segment_end, "aspiration_s": aspiration, "r_fric": r_fric,
            "frication": frication, "burst_spectrum": burst_spectrum, "transition": transition,
            "formant_times": times, "formant_tracks": tracks}


# ---------------- 数值表字段 ----------------

def _optional_field_names() -> list[str]:
    """所有按类别才有数值的字段；缺省 NaN，保证不同类别的行共享同一表结构。"""
    band_keys = [f"{lo:.0f}_{hi:.0f}" for lo, hi in MOMENT_BANDS_HZ]
    fields = ["release_time_s", "release_truncated", "burst_ms", "voicing_onset_s", "VOT_ms",
              "prevoicing_ms", "aspiration_ms", "aspiration_source", "closure_ms",
              "frication_t0_s", "frication_t1_s", "frication_start_source",
              "frication_end_source", "R_fric", "n_frames"]
    fields += [f"{moment}_{stat}_{key}" for key in band_keys
               for moment in ("M1", "M2", "M3", "M4") for stat in ("mean", "sd")]
    fields += ["FM_hz", "FM_dB", "peak2_hz", "peak2_dB", "AmpD_dB", "Fh_hz", "Fh_dB",
               "AmpRange_dB", "HighLevelD_dB"]
    fields += ["burst_peak_hz", "burst_M1_hz", "burst_M2_hz", "burst_M3", "burst_M4",
               "burst_energy_low_ratio", "burst_energy_mid_ratio", "burst_energy_high_ratio"]
    fields += ["transition_ref_s"]
    fields += [f"F{number}_plus{int(offset * 1000)}ms" for offset in TRANSITION_OFFSETS_S
               for number in (1, 2, 3)]
    return fields


def _base_row(aln: Alignment, syll: SyllableSeg, initial: PhoneSeg, kind: str) -> dict:
    row = {"sample": aln.file, "speaker": aln.speaker, "symbol": syll.symbol,
           "label": initial.label, "class": kind,
           "aspirated": initial.label in common.ASPIRATED,
           "t0_s": initial.t0, "t1_s": initial.t1}
    row.update({name: float("nan") for name in _optional_field_names()})
    return row


def _fill_burst_fields(row: dict, burst_spectrum: dict | None) -> None:
    if burst_spectrum is None:
        row.update({"burst_peak_hz": float("nan"), "burst_M1_hz": float("nan"),
                    "burst_M2_hz": float("nan"), "burst_M3": float("nan"),
                    "burst_M4": float("nan"), "burst_energy_low_ratio": float("nan"),
                    "burst_energy_mid_ratio": float("nan"), "burst_energy_high_ratio": float("nan")})
        return
    low, mid, high = burst_spectrum["energy_ratios"]["low"], \
        burst_spectrum["energy_ratios"]["mid"], burst_spectrum["energy_ratios"]["high"]
    row.update({"burst_peak_hz": burst_spectrum["peak_hz"], "burst_M1_hz": burst_spectrum["M1"],
                "burst_M2_hz": burst_spectrum["M2"], "burst_M3": burst_spectrum["M3"],
                "burst_M4": burst_spectrum["M4"], "burst_energy_low_ratio": low,
                "burst_energy_mid_ratio": mid, "burst_energy_high_ratio": high})


def _fill_frication_fields(row: dict, frication: dict) -> None:
    row["n_frames"] = len(frication["times"])
    for key in frication["band_keys"]:
        values = np.array(frication["moment_values"][key], dtype=float)
        if values.size:
            row[f"M1_mean_{key}"] = float(np.nanmean(values[:, 0]))
            row[f"M1_sd_{key}"] = float(np.nanstd(values[:, 0]))
            row[f"M2_mean_{key}"] = float(np.nanmean(values[:, 1]))
            row[f"M2_sd_{key}"] = float(np.nanstd(values[:, 1]))
            row[f"M3_mean_{key}"] = float(np.nanmean(values[:, 2]))
            row[f"M3_sd_{key}"] = float(np.nanstd(values[:, 2]))
            row[f"M4_mean_{key}"] = float(np.nanmean(values[:, 3]))
            row[f"M4_sd_{key}"] = float(np.nanstd(values[:, 3]))
        else:
            for moment in ("M1", "M2", "M3", "M4"):
                row[f"{moment}_mean_{key}"] = float("nan")
                row[f"{moment}_sd_{key}"] = float("nan")
    shadle = frication["shadle"]
    for name in ("FM_hz", "FM_dB", "peak2_hz", "peak2_dB", "AmpD_dB",
                 "Fh_hz", "Fh_dB", "AmpRange_dB", "HighLevelD_dB"):
        row[name] = shadle.get(name, float("nan"))


def _fill_transition_fields(row: dict, transition: dict) -> None:
    for key, value in transition.items():
        row[key] = value


def _moment_rows(aln: Alignment, initial: PhoneSeg, frication: dict) -> list[dict]:
    rows = []
    for i, time in enumerate(frication["times"]):
        for key in frication["band_keys"]:
            m1, m2, m3, m4 = frication["moment_values"][key][i]
            rows.append({"sample": aln.file, "phone": initial.label, "class": initial_class_of(initial),
                         "band": key, "time_s": float(time), "M1_hz": m1, "M2_hz": m2,
                         "M3": m3, "M4": m4, "peak_hz": float(frication["peak_hz"][i])})
    return rows


def initial_class_of(initial: PhoneSeg) -> str:
    return common.initial_class(initial.label)


# ---------------- 绘图 ----------------

@dataclass
class _FigureContext:
    plt: object
    x: np.ndarray
    sr: int
    aln: Alignment
    profile: SpeakerProfile
    scales: DbScales | None
    out_dir: Path
    broadband: Callable[[float], tuple[np.ndarray, np.ndarray, np.ndarray]]


def _vmax(ctx: _FigureContext, *spectrograms: tuple[np.ndarray, np.ndarray, np.ndarray]) -> float:
    """dB 显示上限：优先取调用方的统一标尺，否则由本组语谱图自行确定。"""
    if ctx.scales is not None and ctx.scales.broadband_max_db is not None:
        return float(ctx.scales.broadband_max_db)
    return float(max(np.nanmax(values) for _, _, values in spectrograms))


def _plot_formants(ax, times: np.ndarray, tracks: list[np.ndarray], label_prefix: str = "") -> None:
    for number, track in zip((1, 2, 3), tracks):
        ax.plot(times, track, marker=".", ms=3, lw=1.0,
                color=_F1_F2_F3_COLORS[number - 1], label=f"{label_prefix}F{number}")


def _plot_formants_split(ax, times: np.ndarray, tracks: list[np.ndarray], boundary: float,
                         prelude_label: str) -> None:
    """boundary（浊音起点）之前的帧以浅灰绘制（噪声激励，仅供参考），之后正常配色。"""
    prelude_drawn = False
    for number, track in zip((1, 2, 3), tracks):
        finite = np.isfinite(track)
        if np.isfinite(boundary):
            before = finite & (times < boundary)
            after = finite & (times >= boundary)
            if before.any():
                ax.plot(times[before], track[before], color="#aaaaaa", lw=1.0, marker=".", ms=3,
                        label=prelude_label if not prelude_drawn else None)
                prelude_drawn = True
            ax.plot(times[after], track[after], marker=".", ms=3, lw=1.0,
                    color=_F1_F2_F3_COLORS[number - 1], label=f"F{number}")
        else:
            ax.plot(times[finite], track[finite], marker=".", ms=3, lw=1.0,
                    color=_F1_F2_F3_COLORS[number - 1], label=f"F{number}")


def _ms_text(seconds: float) -> str:
    """秒 → 毫秒文本；NaN 原样显示。"""
    return f"{seconds * 1000:.0f}" if np.isfinite(seconds) else "NaN"


def _clip_boundary_labels(ax) -> None:
    """隐藏落在当前 x 轴范围之外的音素标签（紧随 draw_boundaries 之后调用，避免放大图标签悬空）。"""
    left, right = ax.get_xlim()
    for text in list(ax.texts):
        x = float(text.get_position()[0])
        if x < left or x > right:
            text.set_visible(False)


def _spectrum_ylim(ax, curves: list[np.ndarray], span_db: float = 90.0) -> None:
    """谱曲线 y 轴范围：按传入（应限于显示频段）的数据留 5 dB 余量，总跨度不超过 span_db。"""
    top = max(float(np.nanmax(curve)) for curve in curves)
    bottom = float(np.nanmin(np.concatenate([np.asarray(curve) for curve in curves])))
    ax.set_ylim(max(bottom - 5.0, top - span_db), top + 5.0)


def _figure_09a(ctx: _FigureContext, syll: SyllableSeg, initial: PhoneSeg, data: dict) -> Path:
    plt = ctx.plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.transforms import blended_transform_factory

    times = np.arange(len(ctx.x)) / ctx.sr
    release, onset, burst = data["release"], data["onset"], data["burst_s"]
    end = onset if np.isfinite(onset) else initial.t1
    fig, (ax_wave, ax_spec) = plt.subplots(
        2, 1, figsize=(8.5, 6.2), sharex=True, layout="constrained",
        gridspec_kw={"height_ratios": [1, 2]})
    ax_wave.plot(times, ctx.x, color="black", lw=0.5)
    ax_wave.set_ylabel("振幅")
    common.draw_boundaries(ax_wave, ctx.aln, labels=False)

    handles = [Line2D([], [], color="#333333", ls="--", lw=0.8, label="讯飞音素边界")]
    aspiration_start = release if np.isfinite(release) else float("nan")
    if np.isfinite(release) and np.isfinite(burst):
        for ax in (ax_wave, ax_spec):
            ax.axvspan(release, release + burst, color="#d64545", alpha=0.30)
        handles.append(Patch(facecolor="#d64545", alpha=0.5, label=f"爆破 {_ms_text(burst)} ms"))
        aspiration_start = release + burst
    if np.isfinite(onset) and np.isfinite(aspiration_start) and onset - aspiration_start >= 0.001:
        for ax in (ax_wave, ax_spec):
            ax.axvspan(aspiration_start, onset, color="#f4a582", alpha=0.45)
        span_name = f"送气 {_ms_text(data['aspiration_s'])} ms" if np.isfinite(burst) \
            else f"送气（与爆破不可分，含爆破）{(onset - aspiration_start) * 1000:.0f} ms"
        handles.append(Patch(facecolor="#f4a582", alpha=0.7, label=span_name))
    for ax in (ax_wave, ax_spec):
        if np.isfinite(release):
            ax.axvline(release, color="#d64545", lw=1.2)
        if np.isfinite(onset):
            ax.axvline(onset, color="#4a90d9", lw=1.2)

    transform = blended_transform_factory(ax_wave.transData, ax_wave.transAxes)
    label_box = dict(facecolor="white", edgecolor="none", alpha=0.7)
    if np.isfinite(release):
        # 除阻靠近时间轴左缘时文字左对齐并右移，避免贴住坐标框
        if release < 0.02:
            text_x, ha = release + 0.004, "left"
        else:
            text_x, ha = release, "center"
        ax_wave.annotate("除阻", xy=(release, 1.0), xytext=(text_x, 0.99), xycoords=transform,
                         textcoords=transform, ha=ha, va="top", fontsize=8, color="#d64545",
                         bbox=label_box,
                         arrowprops=dict(arrowstyle="-", color="#d64545", lw=0.8))
    if np.isfinite(onset):
        ax_wave.annotate("浊音起点", xy=(onset, 1.0), xytext=(onset, 0.86), xycoords=transform,
                         textcoords=transform, ha="center", va="top", fontsize=8, color="#4a90d9",
                         bbox=label_box,
                         arrowprops=dict(arrowstyle="-", color="#4a90d9", lw=0.8))
    if np.isfinite(release) and np.isfinite(onset):
        arrow_y = 0.72
        vot_ms = (onset - release) * 1000.0
        if vot_ms >= 3.0:      # 更短的区间画不出可辨箭头，仅保留文字
            ax_wave.annotate("", xy=(release, arrow_y), xytext=(onset, arrow_y),
                             xycoords=transform, textcoords=transform,
                             arrowprops=dict(arrowstyle="<->", color="black", lw=1.0))
        if vot_ms < 15.0:      # 区间太窄时文字右移，避免与箭头端点重叠
            ax_wave.text(onset + 0.002, arrow_y, f"VOT {vot_ms:.0f} ms", transform=transform,
                         ha="left", va="center", fontsize=9)
        else:
            ax_wave.text((release + onset) / 2, arrow_y + 0.03, f"VOT {vot_ms:.0f} ms",
                         transform=transform, ha="center", va="bottom", fontsize=9)
    ax_wave.legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8)

    mesh = common.plot_spectrogram(ax_spec, *ctx.broadband(8000.0),
                                   vmax=_vmax(ctx, ctx.broadband(8000.0)), fmax=8000.0)
    ctx.plt.colorbar(mesh, ax=ax_spec, pad=0.01, label="dB")
    ax_spec.set_xlim(0.0, end + 0.060)
    common.draw_boundaries(ax_spec, ctx.aln)
    _clip_boundary_labels(ax_spec)
    ax_spec.set_xlabel("时间 (s)")
    aspirated = initial.label in common.ASPIRATED
    burst_text = f"爆破={_ms_text(burst)} ms" if np.isfinite(burst) else "爆破：与送气不可分"
    fig.suptitle(f"{ctx.aln.file} 塞音 {initial.label}"
                 f"（{'送气' if aspirated else '不送气'}）  VOT={_ms_text(data['vot_s'])} ms  "
                 f"{burst_text}  送气={_ms_text(data['aspiration_s'])} ms  "
                 f"预发声={_row_value(data, 'prevoicing_ms'):.0f} ms", fontsize=10)
    return common.save_fig(fig, ctx.out_dir, "09a_stop_vot.png")


def _row_value(data: dict, key: str) -> float:
    value = data["row"].get(key, float("nan"))
    return value if np.isfinite(value) else 0.0


def _figure_09b(ctx: _FigureContext, syll: SyllableSeg, initial: PhoneSeg, data: dict) -> Path:
    plt = ctx.plt
    burst = data["burst_spectrum"]
    if burst is None:
        raise ValueError("爆破谱不可用")
    freqs, power = burst["freqs"], burst["power"]
    spectrum_db = common.db(power)
    fig, ax = plt.subplots(figsize=(8.5, 4.8), layout="constrained")
    ax.plot(freqs, spectrum_db, color="black", lw=0.9)
    ax.set_xlim(0, 12000)
    _spectrum_ylim(ax, [spectrum_db[freqs <= 12000.0]])
    ax.axvline(burst["peak_hz"], color="#d64545", ls="--", lw=1.0,
               label=f"谱峰 {burst['peak_hz']:.0f} Hz")
    if np.isfinite(burst["M1"]):
        ax.axvline(burst["M1"], color="#4a90d9", ls=":", lw=1.2,
                   label=f"谱重心 M1 {burst['M1']:.0f} Hz")
    low, mid, high = (burst["energy_ratios"][name] for name in ("low", "mid", "high"))
    from matplotlib.lines import Line2D

    handles, labels = ax.get_legend_handles_labels()
    ratio_text = (f"能量占比  低 0–2.5k {low * 100:.1f}%"
                  f"  中 2.5–5k {mid * 100:.1f}%  高 5–12k {high * 100:.1f}%")
    ax.legend(handles + [Line2D([], [], color="none")], labels + [ratio_text],
              loc="upper right", fontsize=8)
    ax.set_xlabel("频率 (Hz)")
    ax.set_ylabel("功率谱密度 (dB, ref=1)")
    ax.set_title(f"{ctx.aln.file} 爆破谱 {initial.label}（除阻起 10 ms，Hann 窗，0–12 kHz）", fontsize=10)
    return common.save_fig(fig, ctx.out_dir, "09b_burst_spectrum.png")


def _figure_09c(ctx: _FigureContext, syll: SyllableSeg, initial: PhoneSeg, data: dict) -> Path:
    plt = ctx.plt
    release = data["release"]
    top = min(ctx.profile.formant_ceiling, 5500.0)
    fig, ax = plt.subplots(figsize=(8.5, 4.8), layout="constrained")
    mesh = common.plot_spectrogram(ax, *ctx.broadband(top), vmax=_vmax(ctx, ctx.broadband(top)), fmax=top)
    ctx.plt.colorbar(mesh, ax=ax, pad=0.01, label="dB")
    _plot_formants_split(ax, data["formant_times"], data["formant_tracks"], data["onset"],
                         "送气段（噪声激励，仅供参考）")
    ax.axvspan(release + TRANSITION_SHADE_S[0], release + TRANSITION_SHADE_S[1],
               color="#f4a582", alpha=0.35, label="10–40 ms")
    ax.axvline(release, color="#d64545", lw=1.2, label="除阻")
    ax.set_xlim(max(release - 0.005, 0.0), release + TRANSITION_SPAN_S)
    ax.set_ylim(0, top)
    ax.set_xlabel("时间 (s)")
    ax.set_ylabel("频率 (Hz)")
    ax.legend(loc="upper right", fontsize=8, ncol=2)
    ax.set_title(f"{ctx.aln.file} 塞音 {initial.label} 除阻后 0–60 ms 的 F1–F3 过渡"
                 f"（Burg 窗 {FORMANT_TRANSITION_WINDOW * 1000:.0f} ms，"
                 f"上限 {ctx.profile.formant_ceiling:.0f} Hz）", fontsize=10)
    return common.save_fig(fig, ctx.out_dir, "09c_stop_transition.png")


def _figure_10a(ctx: _FigureContext, syll: SyllableSeg, initial: PhoneSeg, data: dict) -> Path:
    plt = ctx.plt
    sg_12k = ctx.broadband(12000.0)
    sg_15k = ctx.broadband(15000.0)
    vmax = _vmax(ctx, sg_12k, sg_15k)
    fig, axes = plt.subplots(2, 1, figsize=(8.5, 7.0), sharex=True, layout="constrained")
    mesh_12k = common.plot_spectrogram(axes[0], *sg_12k, vmax=vmax, fmax=12000.0)
    mesh_15k = common.plot_spectrogram(axes[1], *sg_15k, vmax=vmax, fmax=15000.0)
    axes[0].set_title("0–12 kHz", fontsize=9)
    axes[1].set_title("0–15 kHz", fontsize=9)
    common.draw_boundaries(axes[0], ctx.aln)
    common.draw_boundaries(axes[1], ctx.aln, labels=False)
    common.set_time_axis(axes[1], ctx.aln)
    fig.colorbar(mesh_15k, ax=list(axes), pad=0.01, label="dB")
    fig.suptitle(f"{ctx.aln.file} 擦音 {initial.label} 宽带谱（窗口 5 ms）", fontsize=10)
    return common.save_fig(fig, ctx.out_dir, "10a_fricative_spectrogram.png")


def _figure_10b(ctx: _FigureContext, syll: SyllableSeg, initial: PhoneSeg, data: dict) -> Path:
    plt = ctx.plt
    frication = data["frication"]
    if frication["mean_spectrum"] is None:
        raise ValueError("平均谱不可用")
    freqs, power = frication["mean_spectrum"]
    shadle = frication["shadle"]
    fig, ax = plt.subplots(figsize=(8.5, 5.2), layout="constrained")
    curves = [common.db(power)]
    ax.plot(freqs, curves[0], color="black", lw=1.0,
            label="Hann 多帧平均（20%–80% 段）")
    if frication["multitaper"] is not None:
        mt_freqs, mt_power = frication["multitaper"]
        curves.append(common.db(mt_power))
        ax.plot(mt_freqs, curves[1], color="#4a90d9", lw=1.0, ls="--",
                label=f"multitaper NW={MULTITAPER_NW:.0f} K={MULTITAPER_K} 单次估计")
    ax.set_xlim(0, 12000)
    visible = [curves[0][freqs <= 12000.0]]
    if frication["multitaper"] is not None:
        visible.append(curves[1][frication["multitaper"][0] <= 12000.0])
    _spectrum_ylim(ax, visible)

    fm_hz, fm_db = shadle["FM_hz"], shadle["FM_dB"]
    if np.isfinite(shadle["Fh_hz"]):     # 先画 Fh 空心环，主峰倒三角叠在其上
        ax.plot(shadle["Fh_hz"], shadle["Fh_dB"], marker="D", ms=11, mfc="none",
                mec="#7a5195", mew=1.4, ls="none", label=f"Fh {shadle['Fh_hz']:.0f} Hz")
    if np.isfinite(shadle["peak2_hz"]):
        ax.plot(shadle["peak2_hz"], shadle["peak2_dB"], marker="^", ms=8,
                color="#e8a33d", ls="none", label=f"次峰 {shadle['peak2_hz']:.0f} Hz")
    ax.plot(fm_hz, fm_db, marker="v", ms=8, color="#d64545", ls="none",
            label=f"主峰 FM（3–7k）{fm_hz:.0f} Hz")
    if np.isfinite(shadle["AmpD_dB"]):
        low_mask = _band_mask(freqs, AMPD_LOW_BAND_HZ)
        low_db = common.db(power)[low_mask]
        valley_db = float(np.min(low_db))
        bracket_x = fm_hz + 300.0
        ax.annotate("", xy=(bracket_x, fm_db), xytext=(bracket_x, valley_db),
                    arrowprops=dict(arrowstyle="<->", color="#2ca02c", lw=1.2))
        ax.text(bracket_x + 150, (fm_db + valley_db) / 2,
                f"AmpD {shadle['AmpD_dB']:.1f} dB", color="#2ca02c", fontsize=9,
                ha="left", va="center",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7))
    ax.set_xlabel("频率 (Hz)")
    ax.set_ylabel("功率谱密度 (dB, ref=1)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=9)
    ax.set_title(f"{ctx.aln.file} 擦音 {initial.label} 平均谱  AmpRange={shadle['AmpRange_dB']:.1f} dB  "
                 f"HighLevelD={shadle['HighLevelD_dB']:.1f} dB", fontsize=10)
    return common.save_fig(fig, ctx.out_dir, "10b_fricative_mean_spectrum.png")


_MOMENT_LABELS = (("M1", "谱重心 (Hz)"), ("M2", "标准差 (Hz)"), ("M3", "偏度"), ("M4", "峰度"))
_MOMENT_LINE_STYLES = ("-", "--")


def _figure_moments(ctx: _FigureContext, initial: PhoneSeg, frication: dict, name: str) -> Path:
    plt = ctx.plt
    times = frication["times"]
    if len(times) == 0:
        raise ValueError("没有谱矩帧")
    fig, axes = plt.subplots(4, 1, figsize=(8.5, 8.0), sharex=True, layout="constrained")
    for row, (moment, label) in zip(axes, _MOMENT_LABELS):
        for style, key in zip(_MOMENT_LINE_STYLES, frication["band_keys"]):
            index = int(moment[1]) - 1
            values = np.array([frame[index] for frame in frication["moment_values"][key]], dtype=float)
            row.plot(times, values, style, lw=1.1, marker=".", ms=3,
                     label=f"{moment}（{key.replace('_', '–')} Hz）")
        row.set_ylabel(label)
        row.grid(alpha=0.3)
    common.draw_boundaries(axes[0], ctx.aln)
    axes[0].legend(loc="upper right", fontsize=8, ncol=2)
    common.set_time_axis(axes[-1], ctx.aln)
    fig.suptitle(f"{ctx.aln.file} {initial.label} 谱矩随时间变化（实线 500–12000 Hz，虚线 500–8000 Hz）",
                 fontsize=10)
    return common.save_fig(fig, ctx.out_dir, name)


def _figure_10c(ctx: _FigureContext, syll: SyllableSeg, initial: PhoneSeg, data: dict) -> Path:
    return _figure_moments(ctx, initial, data["frication"], "10c_spectral_moments.png")


def _figure_10d(ctx: _FigureContext, syll: SyllableSeg, initial: PhoneSeg, data: dict) -> Path:
    plt = ctx.plt
    fig, (ax_bands, ax_difference) = plt.subplots(2, 1, figsize=(8.5, 6.2), sharex=True,
                                                   layout="constrained")
    band_keys = [f"{band[0] / 1000:.0f}-{band[1] / 1000:.0f}kHz" for band in BAND_ENERGY_BANDS_HZ]
    for key in band_keys:
        ax_bands.plot(data["band_centers"], data["band_levels"][key], lw=1.1, marker=".", ms=3,
                      label=f"{key.replace('kHz', ' kHz')}")
    ax_bands.set_ylabel("带内平均功率 (dB)")
    ax_bands.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=9)
    ax_bands.grid(alpha=0.3)
    ax_difference.plot(data["band_centers"], data["high_level_d"], lw=1.1, color="#7a5195",
                       marker=".", ms=3, label="HighLevelD（8–12k − 2–4k）")
    ax_difference.axhline(0, color="#999999", lw=0.8)
    ax_difference.set_ylabel("电平差 (dB)")
    ax_difference.legend(loc="upper right", fontsize=9)
    ax_difference.grid(alpha=0.3)
    common.draw_boundaries(ax_bands, ctx.aln)
    common.set_time_axis(ax_difference, ctx.aln)
    fig.suptitle(f"{ctx.aln.file} 擦音 {initial.label} 频带能量随时间变化（10 ms 窗，5 ms 步长）",
                 fontsize=10)
    return common.save_fig(fig, ctx.out_dir, "10d_band_energy.png")


def _figure_14_h_continuity(ctx: _FigureContext, syll: SyllableSeg, initial: PhoneSeg, data: dict) -> Path:
    plt = ctx.plt
    final = syll.final
    if final is None:
        raise ValueError("缺少韵母段")
    n_fft = 4 * 2 ** int(np.ceil(np.log2(FRAME_WINDOW_S * ctx.sr)))
    display_max = min(ctx.profile.formant_ceiling, 5000.0)
    fig, ax = plt.subplots(figsize=(8.5, 5.2), layout="constrained")

    def slice_curve(center: float, color: str, linestyle: str, label: str) -> np.ndarray:
        seg, _ = common.segment_at(ctx.x, ctx.sr, center, FRAME_WINDOW_S)
        freqs, power = _window_energy_spectrum(seg, ctx.sr, n_fft)
        spectrum_db = common.db(power)
        ax.plot(freqs, spectrum_db, color=color, ls=linestyle, lw=1.0, label=label)
        return spectrum_db[freqs <= display_max]

    curves = []
    h_colors = ("#fdae61", "#f46d43", "#d73027")
    for position, color in zip(H_SLICE_POSITIONS, h_colors):
        curves.append(slice_curve(initial.t0 + position * initial.duration, color, "-",
                                   f"/h/ {position * 100:.0f}%"))
    vowel_line_styles = ("--", "-.")
    for position, linestyle in zip(VOWEL_SLICE_POSITIONS, vowel_line_styles):
        curves.append(slice_curve(final.t0 + position * final.duration, "#4a90d9", linestyle,
                                   f"韵母 {common.display_label(final)} {position * 100:.0f}%"))

    # F1–F3 竖线与顶部标签（轴坐标系，不压低 y 轴下限）
    from matplotlib.transforms import blended_transform_factory

    transform = blended_transform_factory(ax.transData, ax.transAxes)
    for position in VOWEL_SLICE_POSITIONS:
        center = final.t0 + position * final.duration
        for number, track in zip((1, 2, 3), data["formant_tracks"]):
            value = _nearest_formant(data["formant_times"], track, center)
            if np.isfinite(value):
                ax.axvline(value, color=_F1_F2_F3_COLORS[number - 1], ls=":", lw=1.0)
                ax.text(value, 0.99, f"F{number}", transform=transform, ha="center", va="top",
                        fontsize=8, color=_F1_F2_F3_COLORS[number - 1])
    ax.set_xlim(0, display_max)
    _spectrum_ylim(ax, curves)
    ax.set_xlabel("频率 (Hz)")
    ax.set_ylabel("功率谱密度 (dB, ref=1)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=9)
    ax.set_title(f"{ctx.aln.file} /h/ 噪声谱与后接韵母的频谱连续性（25 ms 切片）", fontsize=10)
    return common.save_fig(fig, ctx.out_dir, "14_h_continuity.png")


def _figure_11a(ctx: _FigureContext, syll: SyllableSeg, initial: PhoneSeg, data: dict) -> Path:
    plt = ctx.plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    final = syll.final
    times = np.arange(len(ctx.x)) / ctx.sr
    release, burst = data["release"], data["burst_s"]
    onset = data["onset"]
    frication_t0, frication_t1 = data["frication_t0"], data["frication_t1"]
    fig, (ax_wave, ax_spec, ax_formants) = plt.subplots(
        3, 1, figsize=(8.5, 7.6), layout="constrained",
        gridspec_kw={"height_ratios": [1, 2, 1.4]})
    ax_wave.plot(times, ctx.x, color="black", lw=0.5)
    ax_wave.set_ylabel("振幅")
    common.draw_boundaries(ax_wave, ctx.aln, labels=False)

    handles = [Line2D([], [], color="#333333", ls="--", lw=0.8, label="讯飞音素边界"),
               Line2D([], [], color="#d64545", lw=1.2, label="除阻")]
    if np.isfinite(release) and np.isfinite(burst):
        for ax in (ax_wave, ax_spec):
            ax.axvspan(release, release + burst, color="#d64545", alpha=0.30)
        handles.append(Patch(facecolor="#d64545", alpha=0.5, label=f"爆破 {_ms_text(burst)} ms"))
    if np.isfinite(frication_t0) and np.isfinite(frication_t1):
        for ax in (ax_wave, ax_spec):
            ax.axvspan(frication_t0, frication_t1, color="#e8a33d", alpha=0.30)
        aspiration_span = onset - frication_t1 if np.isfinite(onset) else float("nan")
        span_text = f"摩擦+送气 {(frication_t1 - frication_t0) * 1000:.0f} ms" \
            if np.isfinite(aspiration_span) and aspiration_span < 0.001 \
            else f"摩擦 {(frication_t1 - frication_t0) * 1000:.0f} ms"
        handles.append(Patch(facecolor="#e8a33d", alpha=0.5, label=span_text))
    if np.isfinite(frication_t1) and np.isfinite(onset) and onset - frication_t1 >= 0.001:
        for ax in (ax_wave, ax_spec):
            ax.axvspan(frication_t1, onset, color="#f4a582", alpha=0.45)
        handles.append(Patch(facecolor="#f4a582", alpha=0.7,
                             label=f"送气 {_ms_text(data['aspiration_s'])} ms"))
    if final is not None:
        for ax in (ax_wave, ax_spec):
            ax.axvspan(final.t0, final.t1, color="#4a90d9", alpha=0.18)
        handles.append(Patch(facecolor="#4a90d9", alpha=0.35,
                             label=f"元音（讯飞韵母段）{(final.t1 - final.t0) * 1000:.0f} ms"))
    for ax in (ax_wave, ax_spec):
        if np.isfinite(release):
            ax.axvline(release, color="#d64545", lw=1.2)
    ax_wave.legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8)

    mesh = common.plot_spectrogram(ax_spec, *ctx.broadband(8000.0),
                                   vmax=_vmax(ctx, ctx.broadband(8000.0)), fmax=8000.0)
    ctx.plt.colorbar(mesh, ax=ax_spec, pad=0.01, label="dB")
    common.draw_boundaries(ax_spec, ctx.aln)
    common.set_time_axis(ax_spec, ctx.aln)
    ax_spec.set_ylabel("频率 (Hz)")

    # 过渡面板：以浊音起点（元音起始）为参照，窗口 [浊音起点 −20 ms, +60 ms]；
    # 起点之前的帧为送气噪声激励，浅灰绘制
    transition_reference = onset if np.isfinite(onset) else frication_t1
    _plot_formants_split(ax_formants, data["formant_times"], data["formant_tracks"], onset,
                         "送气段（噪声激励）")
    ax_formants.set_xlim(max(transition_reference - 0.020, 0.0),
                         transition_reference + TRANSITION_SPAN_S)
    ax_formants.set_ylim(0, 4000)
    ax_formants.set_xlabel("时间 (s)")
    ax_formants.set_ylabel("频率 (Hz)")
    ax_formants.legend(loc="upper right", fontsize=8, ncol=3)
    ax_formants.grid(alpha=0.3)
    vot_text = f"  VOT={_ms_text(data['vot_s'])} ms" if np.isfinite(data["vot_s"]) else ""
    aspiration_text = f"  送气={_ms_text(data['aspiration_s'])} ms" \
        if np.isfinite(data["aspiration_s"]) else ""
    fig.suptitle(f"{ctx.aln.file} 塞擦音 {initial.label}{vot_text}{aspiration_text}  "
                 f"R_fric={data['r_fric']:.2f}（摩擦本体 / 讯飞声母起点到摩擦段终点）", fontsize=10)
    return common.save_fig(fig, ctx.out_dir, "11a_affricate_stages.png")


def _figure_11b(ctx: _FigureContext, syll: SyllableSeg, initial: PhoneSeg, data: dict) -> Path:
    plt = ctx.plt
    burst = data["burst_spectrum"]
    frication = data["frication"]
    if burst is None or frication["mean_spectrum"] is None:
        raise ValueError("爆破谱或摩擦段平均谱不可用")
    fig, ax = plt.subplots(figsize=(8.5, 5.0), layout="constrained")
    curves = [common.db(burst["power"]), common.db(frication["mean_spectrum"][1])]
    ax.axvline(burst["peak_hz"], color="#d64545", ls="--", lw=1.0)
    ax.plot(burst["freqs"], curves[0], color="#d64545", lw=1.0,
            label=f"爆破谱（除阻起 10 ms，峰 {burst['peak_hz']:.0f} Hz）")
    ax.plot(burst["peak_hz"], burst["peak_db"], marker="^", ms=8, color="#8b1a1a", ls="none")
    frication_freqs, frication_power = frication["mean_spectrum"]
    peak_hz, peak_db = _spectrum_peak(frication_freqs, frication_power, (0.0, 12000.0))
    ax.axvline(peak_hz, color="#4a90d9", ls="--", lw=1.0,
               label=f"摩擦段平均谱 谱峰 {peak_hz:.0f} Hz")
    ax.plot(frication_freqs, curves[1], color="#4a90d9", lw=1.0,
            label=f"摩擦段平均谱 FM（3–7 kHz）{frication['shadle']['FM_hz']:.0f} Hz")
    fm_hz, fm_db = frication["shadle"]["FM_hz"], frication["shadle"]["FM_dB"]
    ax.plot(fm_hz, fm_db, marker="v", ms=8, color="#1f4e79", ls="none")
    ax.set_xlim(0, 12000)
    _spectrum_ylim(ax, [curve[frication["mean_spectrum"][0] <= 12000.0] if i == 1
                        else curve[burst["freqs"] <= 12000.0] for i, curve in enumerate(curves)])
    ax.set_xlabel("频率 (Hz)")
    ax.set_ylabel("功率谱密度 (dB, ref=1)")
    ax.legend(loc="upper right", fontsize=9)
    ax.set_title(f"{ctx.aln.file} 塞擦音 {initial.label} 爆破谱与摩擦段平均谱", fontsize=10)
    return common.save_fig(fig, ctx.out_dir, "11b_affricate_spectra.png")


def _figure_11c(ctx: _FigureContext, syll: SyllableSeg, initial: PhoneSeg, data: dict) -> Path:
    return _figure_moments(ctx, initial, data["frication"], "11c_affricate_moments.png")


# ---------------- 入口 ----------------

def generate(x: np.ndarray, sr: int, aln: Alignment, out_dir: str | Path,
             scales: DbScales | None = None, context: dict | None = None) -> dict:
    """按录音中实际出现的声母类别生成塞音/擦音/塞擦音（含 /h/）专项图像与数值表。"""
    result = common.new_result()
    plt = common.setup_matplotlib()
    profile = common.profile_for(aln.speaker)
    snd = common.to_sound(x, sr)
    out_dir = Path(out_dir)
    result["params"].update(_params_dict(profile))

    rows: list[dict] = []
    moment_rows: list[dict] = []
    figure_kinds: set[str] = set()

    spectrogram_cache: dict[float, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

    def broadband(max_frequency: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        key = float(max_frequency)
        if key not in spectrogram_cache:
            spectrogram = common.spectrogram(snd, "broadband", key)
            spectrogram_cache[key] = common.spectrogram_arrays(spectrogram)
            result["params"].setdefault("spectrogram_broadband_actual", {})[f"{key:.0f}Hz"] = \
                common.spectrogram_actual(spectrogram)
        return spectrogram_cache[key]

    formant_data = None

    def formant_track():
        nonlocal formant_data
        if formant_data is None:
            times, tracks, actual = _formant_track(snd, profile)
            formant_data = (times, tracks, actual)
            result["params"]["formants"] = {
                "method": "To Formant (burg)", "time_step_s": formant_core.TIME_STEP,
                "max_formants": formant_core.MAX_NUMBER_OF_FORMANTS,
                "window_s": FORMANT_TRANSITION_WINDOW,
                "window_note": "辅音过渡分析单独采用 15 ms 窗（方案 §3.1 默认 25 ms），"
                               "使首帧提前覆盖除阻后 10–40 ms",
                "transition_reference": "塞音取除阻时刻（方案 §4.1 爆破后过渡）；"
                                        "塞擦音取浊音起点（方案 §4.3 向后续元音过渡），"
                                        "+10/+20/+40 ms 取样相对各自参照点",
                "pre_emphasis_hz": formant_core.PRE_EMPHASIS_FROM,
                "ceiling_hz": profile.formant_ceiling, "actual": actual,
            }
        return formant_data

    for syllable in aln.syllables:
        initial = syllable.initial
        if initial is None:
            continue
        kind = common.initial_class(initial.label)
        if kind not in ("stop", "fricative", "affricate"):
            result["warnings"].append(
                f"{aln.file}：声母 {initial.label}（{syllable.symbol}）为 {kind} 类，由其他模块负责")
            continue

        if kind == "stop":
            data = _analyze_stop(x, sr, snd, aln, syllable, initial, profile,
                                 formant_track, result["warnings"])
        elif kind == "fricative":
            data = _analyze_fricative(x, sr, snd, aln, syllable, initial, profile,
                                      formant_track, result["warnings"])
        else:
            data = _analyze_affricate(x, sr, snd, aln, syllable, initial, profile,
                                      formant_track, result["warnings"])
        rows.append(data["row"])
        moment_rows.extend(data["moment_rows"])

        if kind in figure_kinds:
            result["warnings"].append(
                f"{aln.file}：{kind} 类声母多于一个，仅第一个生成图像")
            continue
        figure_kinds.add(kind)

        context_figure = _FigureContext(plt, np.asarray(x, dtype=float), sr, aln, profile,
                                        scales, out_dir, broadband)
        figures: list[tuple[str, Callable]] = []
        if kind == "stop":
            figures = [("09a_stop_vot.png", _figure_09a),
                       ("09b_burst_spectrum.png", _figure_09b),
                       ("09c_stop_transition.png", _figure_09c)]
        elif kind == "fricative":
            figures = [("10a_fricative_spectrogram.png", _figure_10a),
                       ("10b_fricative_mean_spectrum.png", _figure_10b),
                       ("10c_spectral_moments.png", _figure_10c),
                       ("10d_band_energy.png", _figure_10d)]
            if initial.label == "h":
                figures.append(("14_h_continuity.png", _figure_14_h_continuity))
        else:
            figures = [("11a_affricate_stages.png", _figure_11a),
                       ("11b_affricate_spectra.png", _figure_11b),
                       ("11c_affricate_moments.png", _figure_11c)]
        for name, builder in figures:
            try:
                result["images"][name] = builder(context_figure, syllable, initial, data)
            except Exception as error:      # 单张图失败不影响其余输出
                result["warnings"].append(f"{aln.file}：图像 {name} 生成失败（{error}）")

    if rows:
        result["tables"]["obstruent_params.csv"] = common.write_csv(
            rows, out_dir / "csv", "obstruent_params.csv")
    if moment_rows:
        result["tables"]["fricative_moments.csv"] = common.write_csv(
            moment_rows, out_dir / "csv", "fricative_moments.csv")
    if not result["images"]:
        result["warnings"].append(f"{aln.file}：录音中没有塞音/擦音/塞擦音声母，本模块未生成图像")
    return result
