"""发音建议图像的测量层：每条录音只分析一遍，图像与 measurements.json 共用同一份结果。

- 采样率统一为 44.1 kHz；噪声谱上限取 12 kHz 与源录音有效带宽的较小值。
- F0 与评分、结果页共用 f0_pipeline（filtered AC + 四步清洗 + 五度值）。五度值按各自
  音域换算：调用方给出音域（个人标定结果、参考发音人的语料统计）时直接使用；否则按
  产品「跳过标定」路径（analysis.adaptive_range_from_hz）由本条录音估计，并在结果中注明。
- 音素边界沿用对齐结果；除阻、浊音起点、噪声起点、鼻音 murmur 起点是在边界附近检测的
  声学事件点，用于细分音段内部。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.acoustics import analysis as product_analysis
from app.acoustics import f0_pipeline, transcode
from app.acoustics.imagery.common import (PHONE_IPA, Alignment, PhoneSeg, final_type,
                                          initial_class, nasal_coda, read_mono)

SR = transcode.SAMPLE_RATE
DISPLAY_MARGIN_SEC = 0.100


def hz_to_bark(frequency):
    hz = np.asarray(frequency, dtype=float)
    return 13 * np.arctan(.00076 * hz) + 3.5 * np.arctan((hz / 7500) ** 2)


ANALYSIS_TOP_HZ = 12000.0
SIBILANT_BAND_START_HZ = 2000.0
FRICATION_BAND = (3000.0, 10000.0)
ASPIRATION_BAND = (800.0, 2500.0)
VOICING_LOW_BAND = (100.0, 1000.0)
VOICING_HIGH_BAND = (2000.0, 8000.0)
VOICING_HNR_DB = 3.0
VOICING_BAND_MARGIN_DB = 6.0
VOICING_MIN_SEC = 0.025
FRICATION_RATIO_DROP_DB = 10.0
OFFSET_LOW_BAND_DB = 12.0

LEVEL_WIN, LEVEL_HOP = 0.025, 0.005
SPEECH_LEVEL_DB = -35.0         # 相对录音峰值高于该值的帧视为语音（裁剪显示范围、有声终点）
LOW_LEVEL_DB = -30.0            # 共振峰测量的最低相对电平

MALE_F0_MEDIAN = 165.0          # 与 analysis.extract_formants 相同的声道上限判定
FORMANT_STEP, FORMANT_WINDOW = 0.005, 0.025
OUTLIER_FRAMES, OUTLIER_DEVIATION = 5, 0.2
VOWEL_POSITIONS = np.linspace(0.0, 1.0, 11)
FORMANT_SAMPLE_HALF_WIN = 0.010

HF_BAND = (2000.0, ANALYSIS_TOP_HZ)     # 除阻瞬态
HF_WIN, HF_HOP = 0.003, 0.001
RELEASE_SEARCH_BEFORE = 0.020   # 从声母起点前 20 ms 开始找除阻
RELEASE_RISE_SPAN = 0.002
RELEASE_RISE_FRACTION = 0.5     # 2 ms 上升量达到窗内最大上升量 50% 的最早帧
RELEASE_LEVEL_RANGE_DB = 25.0   # 上升后电平与窗内最大值之差的上限
RELEASE_PRIOR_NOISE_SEC = 0.020  # 除阻候选前持续强噪声的检测区间

PULSE_GAP_FACTOR = 1.25         # 同一段浊音内相邻声门脉冲间隔 < 1.25 / 脉冲下限
SUSTAINED_VOICING_SEC = 0.040   # 持续 ≥40 ms 的脉冲段才算规则声带振动
PREVOICING_MIN_SEC = 0.010

NOISE_BAND = (1000.0, ANALYSIS_TOP_HZ)  # 擦音/塞擦音噪声
NOISE_WIN, NOISE_HOP = 0.010, 0.002
NOISE_ONSET_DROP_DB = 25.0      # 噪声起点：电平升到段内最大值 −25 dB 的最早帧
NOISE_RISE_DROP_DB = 3.0        # 上升时间：噪声起点 → 电平达到最大值 −3 dB
SPECTRUM_WIN, SPECTRUM_HOP = 0.020, 0.005
SPECTRUM_NFFT = 1024            # 覆盖 44.1 kHz 下的 20 ms 窗
SPECTRUM_SMOOTH_HZ = 300.0
SPECTRUM_BAND = (500.0, ANALYSIS_TOP_HZ)
AFFRICATE_SPECTRUM_MAX_SEC = 0.060

NASAL_LOW_BAND, NASAL_HIGH_BAND = (100.0, 400.0), (800.0, 2500.0)
NASAL_WIN, NASAL_HOP = 0.025, 0.005
NASAL_DROP_DB = 10.0            # (1–4 kHz − 0–500 Hz) 电平差比元音前半段中位数低 10 dB 以上
NASAL_MIN_SEC = 0.030
VOWEL_ONSET_TOLERANCE = 0.080  # 韵母边界附近的起声搜索范围

SHORT_INITIAL_SEC = 0.040       # 边音/r 声母中点测量的最短区间


@dataclass
class Recording:
    x: np.ndarray                               # 44.1 kHz 单声道 float
    aln: Alignment
    f0_range: tuple[float, float] | None = None  # 五度音域（1 度、5 度对应的 Hz）
    f0_range_source: str | None = None
    vowel_norm: dict | None = None              # 个人标定结果，含 overall 与 i/u/a/ü 锚点
    formant_ceiling_hz: float | None = None
    source_sample_rate: int = SR
    signal_quality: dict | None = None


def to_standard_rate(x: np.ndarray, sr: int) -> np.ndarray:
    if sr == SR:
        return np.asarray(x, dtype=float)
    from scipy.signal import resample_poly

    g = math.gcd(int(sr), SR)
    return resample_poly(np.asarray(x, dtype=float), SR // g, int(sr) // g)


def load_recording(wav_path: str | Path, aln: Alignment, **kwargs) -> Recording:
    x, sr = read_mono(wav_path)
    quality = kwargs.pop("signal_quality", None)
    if quality is None:
        quality = product_analysis.check_signal(Path(wav_path), purpose="recording").to_dict()
    return Recording(to_standard_rate(x, sr), aln, source_sample_rate=sr,
                     signal_quality=quality, **kwargs)


# ---------------- 信号工具 ----------------

def _level_track(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """25 ms 短时 RMS 电平，相对录音峰值（dB，峰值为 0）。"""
    t = np.arange(0.0, len(x) / SR, LEVEL_HOP)
    half = int(round(LEVEL_WIN * SR / 2))
    c = np.round(t * SR).astype(int)
    a, b = np.clip(c - half, 0, len(x)), np.clip(c + half, 0, len(x))
    cum = np.concatenate(([0.0], np.cumsum(x ** 2)))
    level = 10.0 * np.log10(np.maximum((cum[b] - cum[a]) / np.maximum(b - a, 1), 1e-20))
    return t, level - level.max()


def _frame_power(x: np.ndarray, centers: np.ndarray, win: float,
                 nfft: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """以 centers 为中心的 Hann 窗功率谱（帧 × 频率）；越过录音边界处补零。"""
    half = int(round(win * SR / 2))
    n = 2 * half
    nfft = nfft or max(256, 1 << (n - 1).bit_length())
    if nfft < n:
        raise ValueError("FFT 长度须大于或等于分析窗长度")
    padded = np.pad(x, (half, half))
    idx = np.clip(np.round(np.asarray(centers) * SR).astype(int), 0, len(x))
    frames = padded[idx[:, None] + np.arange(n)[None, :]] * np.hanning(n)
    return np.fft.rfftfreq(nfft, 1.0 / SR), np.abs(np.fft.rfft(frames, nfft, axis=1)) ** 2


def _band_level(x: np.ndarray, centers: np.ndarray, win: float,
                band: tuple[float, float]) -> np.ndarray:
    freqs, power = _frame_power(x, centers, win)
    m = (freqs >= band[0]) & (freqs <= band[1])
    return 10.0 * np.log10(np.maximum(power[:, m].mean(axis=1), 1e-20))


def _grid(t0: float, t1: float, hop: float) -> np.ndarray:
    return np.arange(t0, t1 + hop / 2, hop) if t1 > t0 else np.array([t0])


def _interp(t: np.ndarray, src_t: np.ndarray, src_v: np.ndarray) -> np.ndarray:
    return np.interp(t, src_t, src_v)


def _rnd(v, nd: int = 1):
    if v is None:
        return None
    v = float(v)
    return round(v, nd) if np.isfinite(v) else None


def _ms(seconds) -> float | None:
    return None if seconds is None else _rnd(seconds * 1000.0)


# ---------------- 整条录音的分析 ----------------

@dataclass
class Analysis:
    rec: Recording
    duration: float
    track: f0_pipeline.PitchTrack
    f0_range: tuple[float, float]
    f0_range_source: str
    sex: str                        # 由 F0 中位数估计：male / female
    level_t: np.ndarray
    level_db: np.ndarray
    formant_t: np.ndarray
    formants: np.ndarray            # F1–F3（3 × n），低能量帧与离群点为 NaN
    formant_ceiling: float
    pulses: np.ndarray
    pulse_floor: float
    speech_t0: float
    speech_t1: float
    syllables: list[dict] = field(default_factory=list)
    spectra: dict[int, tuple[np.ndarray, np.ndarray]] = field(default_factory=dict)
    _snd: object = None
    _harmonicity: tuple[np.ndarray, np.ndarray] | None = None
    spectrogram: tuple | None = None
    narrow_spectrogram: tuple | None = None
    noise_envelopes: dict = field(default_factory=dict)
    formant_reasons: np.ndarray | None = None
    creaky_intervals: list[tuple[float, float]] = field(default_factory=list)

    @property
    def bandwidth_hz(self) -> float:
        return min(ANALYSIS_TOP_HZ, 0.475 * self.rec.source_sample_rate)

    @property
    def aln(self) -> Alignment:
        return self.rec.aln

    def level_at(self, t) -> np.ndarray:
        return _interp(np.asarray(t, dtype=float), self.level_t, self.level_db)

    def formants_at(self, t: float, bounds: tuple[float, float] | None = None) -> list[float | None]:
        """t ± 10 ms 内有效帧的中位数（F1、F2、F3）。"""
        m = np.abs(self.formant_t - t) <= FORMANT_SAMPLE_HALF_WIN
        if bounds is not None:
            m &= (self.formant_t >= bounds[0]) & (self.formant_t <= bounds[1])
        out = []
        for k in range(3):
            v = self.formants[k, m]
            v = v[np.isfinite(v)]
            out.append(float(np.median(v)) if v.size else None)
        return out

    def harmonicity(self) -> tuple[np.ndarray, np.ndarray]:
        if self._harmonicity is None:
            from parselmouth.praat import call

            h = call(self._snd, "To Harmonicity (cc)", 0.01, self.pulse_floor, 0.1, 1.0)
            v = np.asarray(h.values, dtype=float).ravel()
            self._harmonicity = (np.asarray(h.xs(), dtype=float), np.where(v > -199, v, np.nan))
        return self._harmonicity


def analyze(rec: Recording, *, track: f0_pipeline.PitchTrack | None = None) -> Analysis:
    import parselmouth
    from parselmouth.praat import call

    snd = parselmouth.Sound(rec.x, sampling_frequency=float(SR))
    duration = len(rec.x) / SR
    validate_alignment(rec.aln, duration)
    track = track if track is not None else f0_pipeline.extract_track_from_sound(snd)
    voiced_hz = track.f0[np.isfinite(track.f0)]
    sex = ("male" if float(np.median(voiced_hz)) < MALE_F0_MEDIAN else "female") if voiced_hz.size >= 12 else "unknown"

    if rec.f0_range:
        f0_range, range_source = tuple(rec.f0_range), rec.f0_range_source or "调用方提供"
        if not (0 < f0_range[0] < f0_range[1]):
            raise ValueError("音域必须满足 0 < fLo < fHi")
    else:
        f0_range = product_analysis.adaptive_range_from_hz(voiced_hz) or (95.0, 260.0)
        range_source = "estimated_from_this_recording"

    level_t, level_db = _level_track(rec.x)

    ceiling = rec.formant_ceiling_hz or (5000.0 if sex == "male" else 5500.0)
    fm = snd.to_formant_burg(time_step=FORMANT_STEP, max_number_of_formants=5.0,
                             maximum_formant=ceiling, window_length=FORMANT_WINDOW,
                             pre_emphasis_from=50.0)
    formant_t = np.asarray(fm.xs(), dtype=float)
    formants = np.array([[fm.get_value_at_time(k, t) for t in formant_t] for k in (1, 2, 3)],
                        dtype=float)
    formants[~(formants > 0)] = np.nan
    reasons = np.where(np.isfinite(formants), "", "无数据").astype(object)
    low = _interp(formant_t, level_t, level_db) < LOW_LEVEL_DB
    reasons[:, low] = "低能量"
    formants[:, low] = np.nan
    unvoiced = ~np.isfinite(_interp(formant_t, track.times, track.f0))
    reasons[:, unvoiced & ~low] = "无可靠浊音"
    formants[:, unvoiced] = np.nan
    for k in range(3):
        bad = _outliers(formants[k])
        reasons[k, bad] = "离群"
        formants[k, bad] = np.nan
        # 连续的 Burg 极点跳变按相邻共振峰次序与局部轨迹跨度标记。
        finite = np.isfinite(formants[k])
        for j in range(2, len(formant_t) - 2):
            if finite[j-2:j+3].all():
                nearby = np.r_[formants[k, j-2:j], formants[k, j+1:j+3]]
                if abs(formants[k, j] - np.median(nearby)) > max(250.0, .3 * np.median(nearby)):
                    reasons[k, j] = "轨迹跳变"
                    formants[k, j] = np.nan
    merged = ((formants[1] - formants[0] < 200) |
              (formants[2] - formants[1] < 180))
    reasons[1:, merged] = "共振峰合并"
    formants[1:, merged] = np.nan
    for k in range(3):
        track_values = formants[k]
        valid = np.flatnonzero(np.isfinite(track_values))
        for n in range(1, len(valid)):
            previous, first = valid[n-1], valid[n]
            if first - previous > 2:
                continue
            baseline = track_values[previous]
            if abs(track_values[first] - baseline) < max(500.0, .20 * baseline):
                continue
            for last in valid[n+1:]:
                if formant_t[last] - formant_t[first] > .20:
                    break
                if abs(track_values[last] - baseline) < max(200.0, .08 * baseline):
                    reasons[k, first:last] = "轨迹跳变"
                    track_values[first:last] = np.nan
                    break
    from scipy.interpolate import UnivariateSpline
    for k in range(3):
        valid = np.isfinite(formants[k])
        for start, end in f0_pipeline._runs(valid):
            if end-start < 4:
                continue
            values = formants[k, start:end+1].copy()
            values = np.asarray([np.median(values[max(0, j-2):min(len(values), j+3)])
                                 for j in range(len(values))])
            x = np.arange(len(values), dtype=float)
            formants[k, start:end+1] = UnivariateSpline(x, values, k=3, s=len(values)*25**2)(x)

    p5, p95 = np.percentile(voiced_hz, [5, 95]) if voiced_hz.size else (70.0, 400.0)
    pulse_floor = max(50.0, 0.7 * float(p5))
    pp = call(snd, "To PointProcess (periodic, cc)", pulse_floor, min(800.0, 1.3 * float(p95)))
    pulses = np.array([call(pp, "Get time from index", i)
                       for i in range(1, int(call(pp, "Get number of points")) + 1)])

    speech_t0 = max(0.0, min(s.t0 for s in rec.aln.syllables) - DISPLAY_MARGIN_SEC)
    speech_t1 = min(duration, max(s.t1 for s in rec.aln.syllables) + DISPLAY_MARGIN_SEC)

    a = Analysis(rec, duration, track, f0_range, range_source, sex, level_t, level_db,
                 formant_t, formants, ceiling, pulses, pulse_floor, speech_t0, speech_t1,
                 _snd=snd, formant_reasons=reasons)
    sg = snd.to_spectrogram(window_length=0.005, time_step=0.002,
                            frequency_step=40.0, maximum_frequency=ANALYSIS_TOP_HZ)
    db = 10 * np.log10(np.maximum(sg.values, 1e-20))
    peak_db = db.max()
    a.spectrogram = (np.asarray(sg.xs()), np.asarray(sg.ys()), db - peak_db)
    narrow = snd.to_spectrogram(window_length=0.0125, time_step=0.005,
                                frequency_step=20.0, maximum_frequency=ANALYSIS_TOP_HZ)
    narrow_db = 10 * np.log10(np.maximum(narrow.values, 1e-20))
    a.narrow_spectrogram = (np.asarray(narrow.xs()), np.asarray(narrow.ys()), narrow_db - peak_db)
    a.creaky_intervals = _creaky_intervals(a)
    for i in range(len(rec.aln.syllables)):
        a.syllables.append(_measure_syllable(a, i))
    speech_ms = sum(s["duration_ms"] for s in a.syllables)
    for s in a.syllables:
        s["duration_share"] = _rnd(s["duration_ms"] / speech_ms, 3) if speech_ms else None
    return a


def validate_alignment(aln: Alignment, duration: float) -> None:
    """检查音素边界的完整性、顺序及录音范围。"""
    if not aln.syllables:
        raise ValueError("缺少音节对齐")
    previous = 0.0
    for s in aln.syllables:
        if not (0 <= s.t0 < s.t1 <= duration + 0.011) or s.t0 < previous:
            raise ValueError("音节对齐越界或重叠")
        previous = s.t1
        if s.final is None:
            raise ValueError(f"{s.symbol} 缺少韵母时间戳")
        for p in s.phones:
            if not (s.t0 - 0.011 <= p.t0 < p.t1 <= s.t1 + 0.011):
                raise ValueError(f"{s.symbol} 音素边界越界")


def _outliers(track: np.ndarray) -> np.ndarray:
    """偏离 5 帧中值超过 20% 的帧。"""
    half = OUTLIER_FRAMES // 2
    mask = np.zeros(len(track), dtype=bool)
    for i in np.flatnonzero(np.isfinite(track)):
        nb = track[max(0, i - half):i + half + 1]
        med = float(np.median(nb[np.isfinite(nb)]))
        mask[i] = abs(track[i] - med) > OUTLIER_DEVIATION * med
    return mask


# ---------------- 声门脉冲与除阻 ----------------

def _pulse_runs(a: Analysis) -> list[tuple[float, float]]:
    """连续声门脉冲段 [(起, 止)]，只保留持续 ≥ SUSTAINED_VOICING_SEC 的段。"""
    p = a.pulses
    if p.size == 0:
        return []
    max_gap = PULSE_GAP_FACTOR / a.pulse_floor
    breaks = np.flatnonzero(np.diff(p) >= max_gap)
    starts = np.concatenate(([0], breaks + 1))
    ends = np.concatenate((breaks, [p.size - 1]))
    return [(float(p[s]), float(p[e])) for s, e in zip(starts, ends)
            if p[e] - p[s] >= SUSTAINED_VOICING_SEC]


def _creaky_intervals(a: Analysis) -> list[tuple[float, float]]:
    t, strength = a.track.times, a.track.strength
    if len(t) == 0:
        return []
    p = a.pulses
    irregular = np.zeros(len(t), dtype=bool)
    for i, center in enumerate(t):
        local = p[(p >= center - .025) & (p <= center + .025)]
        if len(local) >= 4:
            gaps = np.diff(local)
            irregular[i] = np.std(gaps) / np.mean(gaps) > .03
    low = a.level_at(t) > SPEECH_LEVEL_DB
    active = low & (irregular | ((strength < .6) & (strength > 0)))
    from app.acoustics.f0_pipeline import _runs
    return [(float(t[i]), float(t[j])) for i, j in _runs(active) if j - i >= 2]


def _periodic_onset(a: Analysis, final: PhoneSeg) -> float | None:
    """在韵母边界附近结合声门脉冲、谐噪比和频带能量定位周期起振。"""
    start = max(0.0, final.t0 - .04)
    end = min(a.duration, final.t0 + max(VOWEL_ONSET_TOLERANCE, .08))
    t = _grid(start, end, .005)
    low = _band_level(a.rec.x, t, .020, VOICING_LOW_BAND)
    high = _band_level(a.rec.x, t, .020, VOICING_HIGH_BAND)
    ht, hv = a.harmonicity()
    hnr = np.interp(t, ht, np.nan_to_num(hv, nan=-200.0))
    pulses = np.searchsorted(a.pulses, t + .0125) - np.searchsorted(a.pulses, t - .0125)
    periodic = (pulses >= 2) & (hnr > VOICING_HNR_DB) & (low - high > VOICING_BAND_MARGIN_DB)
    required = max(1, round(VOICING_MIN_SEC / .005))
    for i in range(len(periodic) - required + 1):
        if periodic[i:i+required].all():
            return float(t[i])
    return None


def _vowel_run(a: Analysis, final: PhoneSeg) -> tuple[float, float] | None:
    """覆盖韵母的那段持续浊音。"""
    onset = _periodic_onset(a, final)
    if onset is None:
        return None
    runs = [r for r in _pulse_runs(a) if r[1] > onset + .01 and r[0] <= onset + .03]
    return (onset, runs[0][1]) if runs else (onset, final.t1)


def _release(a: Analysis, initial: PhoneSeg, search_end: float) -> float | None:
    """除阻：[声母起点 − 20 ms, search_end] 内 2–12 kHz 电平 2 ms 上升量达到窗内最大上升量
    50%、且上升后电平与窗内最大值之差在 25 dB 以内的最早帧。"""
    t0 = max(HF_WIN / 2, initial.t0 - RELEASE_SEARCH_BEFORE)
    centers = _grid(t0, search_end + RELEASE_RISE_SPAN, HF_HOP)
    if centers.size < 4:
        return None
    env = _band_level(a.rec.x, centers, HF_WIN, (HF_BAND[0], a.bandwidth_hz))
    lag = int(round(RELEASE_RISE_SPAN / HF_HOP))
    rise = env[lag:] - env[:-lag]
    loud = env[lag:] >= env.max() - RELEASE_LEVEL_RANGE_DB
    rise = np.where(loud, rise, -np.inf)
    if not np.isfinite(rise).any() or rise.max() <= 0:
        return None
    index = int(np.flatnonzero(rise >= RELEASE_RISE_FRACTION * rise.max())[0])
    if np.count_nonzero(env[:index] >= env.max() - 15.0) * HF_HOP >= RELEASE_PRIOR_NOISE_SEC:
        return None
    return float(centers[index])


def _stop_timing(a: Analysis, initial: PhoneSeg, final: PhoneSeg) -> dict:
    """塞音、塞擦音的除阻、浊音起点与 VOT（负值为预发声）。"""
    run = _vowel_run(a, final)
    # 只有闭塞期内已有持续浊音时，才跨过浊音起点搜索除阻。
    # 普通送气音的除阻搜索范围截止于元音起点之前。
    early_voice = any(r[0] >= initial.t0 - RELEASE_SEARCH_BEFORE
                      and r[0] < final.t0 - SUSTAINED_VOICING_SEC
                      and r[1] > initial.t0 + SUSTAINED_VOICING_SEC for r in _pulse_runs(a))
    if run is None and early_voice:
        run = next((r for r in _pulse_runs(a) if r[1] > final.t0 + .01), None)
    search_end = initial.t1 if run is None or early_voice else run[0] - 0.002
    release = _release(a, initial, search_end)
    out = {"release_s": _rnd(release, 4), "voicing_onset_s": None, "vot_ms": None,
           "prevoiced": None}
    if release is None or run is None:
        return out
    # 除阻瞬态可能让脉冲短暂中断；允许爆破前后的两段浊音相接。
    before = [r for r in _pulse_runs(a) if r[0] >= initial.t0 - RELEASE_SEARCH_BEFORE
              and r[0] <= release - PREVOICING_MIN_SEC and r[1] <= release
              and release-r[1] <= max(0.020, 2/a.pulse_floor)
              and run[0]-release <= 0.030]
    if before:
        run = (before[-1][0], run[1])
    if run[0] <= release - PREVOICING_MIN_SEC:
        out.update(voicing_onset_s=_rnd(run[0], 4), vot_ms=_ms(run[0] - release), prevoiced=True)
    else:
        onset = max(run[0], release)
        out.update(voicing_onset_s=_rnd(onset, 4), vot_ms=_ms(onset - release), prevoiced=False)
    return out


# ---------------- 噪声段 ----------------

def _noise_timing(a: Analysis, start: float, end: float) -> dict:
    """噪声起点与上升时间：[start, end] 内 1–12 kHz 电平（10 ms 窗）。"""
    centers = _grid(max(NOISE_WIN / 2, start), end, NOISE_HOP)
    env = _band_level(a.rec.x, centers, NOISE_WIN, (SIBILANT_BAND_START_HZ, a.bandwidth_hz))
    peak = float(env.max())
    on = int(np.flatnonzero(env >= peak - NOISE_ONSET_DROP_DB)[0])
    top = on + int(np.flatnonzero(env[on:] >= peak - NOISE_RISE_DROP_DB)[0])
    return {"noise_onset_s": float(centers[on]), "rise_ms": _ms(centers[top] - centers[on]),
            "env_t": centers, "env_db": env - peak}


def _noise_spectrum(a: Analysis, t0: float, t1: float, low_hz: float) -> dict:
    """[t0, t1] 内 20 ms Hann 帧的平均功率谱；谱峰取 300 Hz 平滑后的最大值，
    谱重心按未平滑功率在 0.5–12 kHz 内计算。"""
    mid = 0.5 * (t0 + t1)
    centers = _grid(t0 + SPECTRUM_WIN / 2, t1 - SPECTRUM_WIN / 2, SPECTRUM_HOP) \
        if t1 - t0 >= SPECTRUM_WIN else np.array([mid])
    freqs, power = _frame_power(a.rec.x, centers, SPECTRUM_WIN, SPECTRUM_NFFT)
    mean = power.mean(axis=0)
    width = max(1, int(round(SPECTRUM_SMOOTH_HZ / (freqs[1] - freqs[0]))))
    smooth_db = 10.0 * np.log10(np.maximum(np.convolve(mean, np.ones(width) / width, "same"), 1e-20))
    band = (freqs >= low_hz) & (freqs <= a.bandwidth_hz)
    peak = float(freqs[band][np.argmax(smooth_db[band])])
    weights = mean[band]
    fb = freqs[band]
    cog = float(np.sum(fb * weights) / np.sum(weights))
    sd = float(np.sqrt(np.sum(weights * (fb-cog)**2) / np.sum(weights)))
    skew = float(np.sum(weights * ((fb-cog)/sd)**3) / np.sum(weights)) if sd else 0.0
    kurt = float(np.sum(weights * ((fb-cog)/sd)**4) / np.sum(weights) - 3) if sd else 0.0
    return {"freqs": freqs, "db": smooth_db, "peak_hz": peak, "cog_hz": cog,
            "sd_hz": sd, "skewness": skew, "kurtosis": kurt,
            "t0": t0, "t1": t1, "frames": int(centers.size)}


def _frication_end(a: Analysis, start: float, end: float) -> float | None:
    t = _grid(start + .010, end, .001)
    if len(t) < 15:
        return None
    hf = _band_level(a.rec.x, t, .005, FRICATION_BAND)
    mid = _band_level(a.rec.x, t, .005, ASPIRATION_BAND)
    ratio = hf - mid
    # 以早期摩擦频带比为基准，定位高频优势持续下降的转折。
    baseline = float(np.median(ratio[:min(20, len(ratio))]))
    threshold = baseline - FRICATION_RATIO_DROP_DB
    peak = int(np.argmax(ratio[:max(1, len(ratio)//2)]))
    for i in range(peak + 1, len(t) - 5):
        if ratio[i-1] > threshold and np.all(ratio[i:i+5] <= threshold):
            return float(t[i])
    return None


def _measure_noise(a: Analysis, i: int, initial: PhoneSeg, final: PhoneSeg,
                   consonant: dict, cls: str, voicing_end: float) -> float:
    run = _vowel_run(a, final)
    end = run[0] if run else None
    start = consonant.get("release_s") if cls == "affricate" else max(0.0, initial.t0 - 0.010)
    if end is None or start is None or end - start < SPECTRUM_WIN:
        return final.t0
    frication_end = _frication_end(a, start, end) if cls == "affricate" and initial.label in {"c", "ch", "q"} else None
    noise_end = frication_end or end
    timing = _noise_timing(a, start, noise_end)
    onset = start if cls == "affricate" else timing["noise_onset_s"]
    # 塞擦音上升时间从除阻计起，噪声段截止于韵母起声。
    peak_index = np.flatnonzero(timing["env_db"] >= -NOISE_RISE_DROP_DB)[0]
    consonant.update(noise_onset_s=_rnd(onset, 4), noise_ms=_ms(noise_end - onset),
                     noise_rise_ms=_ms(max(0.0, timing["env_t"][peak_index] - onset)),
                     voicing_onset_s=_rnd(end, 4))
    if cls == "affricate":
        consonant.update(frication_end_s=_rnd(frication_end, 4),
                         frication_ms=_ms(noise_end - onset),
                         aspiration_ms=_ms(end - frication_end) if frication_end else None)
    a.noise_envelopes[i] = (timing["env_t"], timing["env_db"])
    if cls == "fricative":
        region = (onset + 0.2 * (noise_end - onset), onset + 0.8 * (noise_end - onset))
    else:
        region = (onset + 0.005, min(noise_end, onset + 0.005 + min(0.6 * (noise_end - onset), AFFRICATE_SPECTRUM_MAX_SEC)))
    if region[1] - region[0] < SPECTRUM_WIN:
        return max(final.t0, end)
    band_start = SIBILANT_BAND_START_HZ if initial.label not in {"f", "h"} else 1500.0
    spec = _noise_spectrum(a, *region, band_start)
    a.spectra[i] = (spec["freqs"], spec["db"] - np.max(spec["db"]))
    samples = a.rec.x[int(region[0] * SR):int(region[1] * SR)]
    noise_db = 10 * np.log10(max(float(np.mean(samples ** 2)), 1e-20))
    vowel_samples = a.rec.x[int(max(final.t0, end) * SR):int(voicing_end * SR)]
    if len(vowel_samples) >= int(LEVEL_WIN * SR):
        size = int(LEVEL_WIN * SR)
        energy = np.convolve(vowel_samples ** 2, np.ones(size) / size, mode="valid")
        vowel_db = 10 * np.log10(max(float(energy.max()), 1e-20))
        amplitude = _rnd(noise_db - vowel_db)
    else:
        amplitude = None
    consonant["spectrum"] = {"t0": _rnd(region[0], 4), "t1": _rnd(region[1], 4),
                             "peak_hz": _rnd(spec["peak_hz"], 0), "cog_hz": _rnd(spec["cog_hz"], 0),
                             "sd_hz": _rnd(spec["sd_hz"], 0), "skewness": _rnd(spec["skewness"], 3),
                             "kurtosis": _rnd(spec["kurtosis"], 3),
                             "level_rel_vowel_db": amplitude, "band_hz": [band_start, a.bandwidth_hz],
                             "place_cue_available": initial.label not in {"f", "h"}}
    return max(final.t0, end)


# ---------------- 鼻音 ----------------

def _nasal_ratio(a: Analysis, t0: float, t1: float) -> tuple[np.ndarray, np.ndarray]:
    """(1–4 kHz − 50–500 Hz) 电平差：元音高，鼻音 murmur 明显降低。"""
    centers = _grid(t0, t1, NASAL_HOP)
    freqs, power = _frame_power(a.rec.x, centers, NASAL_WIN)

    def level(band):
        m = (freqs >= band[0]) & (freqs <= band[1])
        return 10.0 * np.log10(np.maximum(power[:, m].mean(axis=1), 1e-20))

    return centers, level(NASAL_HIGH_BAND) - level(NASAL_LOW_BAND)


def _nasalization_track(a: Analysis, t0: float, t1: float) -> dict:
    t, ratio = _nasal_ratio(a, t0, t1)
    freqs, power = _frame_power(a.rec.x, t, .025, 2048)
    difference = []
    for center, spectrum in zip(t, power):
        f1 = a.formants_at(float(center), (t0, t1))[0]
        if f1 is None:
            difference.append(None)
            continue
        a1 = spectrum[(freqs >= max(400, f1 - 100)) & (freqs <= f1 + 100)]
        p0 = spectrum[(freqs >= 250) & (freqs <= 350)]
        difference.append(_rnd(10*np.log10(max(float(a1.max()), 1e-20) / max(float(p0.max()), 1e-20))) if len(a1) and len(p0) else None)
    return {"time_s": [_rnd(v, 3) for v in t], "A1_minus_P0_db": difference,
            "mid_minus_low_db": [_rnd(v) for v in ratio]}


def _coda_murmur(a: Analysis, vowel_t0: float, voicing_end: float) -> tuple[float, float] | None:
    """定位元音中点之后持续至有声终点的鼻音低频优势区间。"""
    t, ratio = _nasal_ratio(a, vowel_t0, voicing_end)
    ref = float(np.median(ratio[t <= vowel_t0 + 0.5 * (voicing_end - vowel_t0)]))
    low = ratio < ref - NASAL_DROP_DB
    if not low[-1]:
        return None
    midpoint = vowel_t0 + .5 * (voicing_end - vowel_t0)
    starts = np.flatnonzero((t >= midpoint) & low)
    if len(starts) == 0:
        return None
    start = int(starts[0])
    later_high = np.flatnonzero((np.arange(len(t)) > start) & ~low)
    if len(later_high):
        start = int(later_high[-1]) + 1
    if t[-1] - t[start] < NASAL_MIN_SEC or t[start] <= vowel_t0 + 0.030:
        return None
    return float(t[start]), float(t[-1])


# ---------------- 单个音节 ----------------

def _voicing_end(a: Analysis, syll_index: int) -> float:
    """结合声学能量与脉冲延续情况定位韵母末端。"""
    syll = a.aln.syllables[syll_index]
    nxt = a.aln.syllables[syll_index + 1].t0 if syll_index + 1 < len(a.aln.syllables) else a.duration
    t = _grid(max(syll.final.t0, syll.final.t1 - .100), min(nxt, syll.final.t1 + .080), .005)
    low = _band_level(a.rec.x, t, .020, VOICING_LOW_BAND)
    quiet = a.level_t[a.level_db < SPEECH_LEVEL_DB]
    floor_t = quiet if len(quiet) >= 5 else a.level_t
    floor = float(np.percentile(_band_level(a.rec.x, floor_t, .020, VOICING_LOW_BAND), 20))
    f0 = np.isfinite(np.interp(t, a.track.times, np.nan_to_num(a.track.f0, nan=0.0)))
    f0 &= np.interp(t, a.track.times, np.nan_to_num(a.track.f0, nan=0.0)) > 0
    pulses = np.searchsorted(a.pulses, t + .010) - np.searchsorted(a.pulses, t - .010)
    active = ((f0 & (a.level_at(t) > SPEECH_LEVEL_DB)) |
              ((low > floor + OFFSET_LOW_BAND_DB) & (pulses >= 2)))
    return float(t[active][-1]) if active.any() else syll.final.t1


def _phone_info(p: PhoneSeg | None) -> dict | None:
    if p is None:
        return None
    return {"label": p.label, "ipa": "∅" if p.label.startswith("_") else PHONE_IPA.get(p.label, p.label),
            "t0": _rnd(p.t0, 3), "t1": _rnd(p.t1, 3), "duration_ms": _ms(p.duration)}


def _measure_syllable(a: Analysis, i: int) -> dict:
    syll = a.aln.syllables[i]
    initial, final = syll.initial, syll.final
    cls = initial_class(initial.label) if initial else "zero"
    voicing_end = _voicing_end(a, i)
    out = {"index": i, "symbol": syll.symbol, "text": syll.text, "tone_target": syll.tone,
           "initial": _phone_info(initial), "initial_class": cls,
           "final": _phone_info(final), "final_type": final_type(final.label)}
    out["final"]["aligned_t1"] = out["final"]["t1"]
    out["final"]["t1"] = _rnd(voicing_end, 3)
    out["final"]["duration_ms"] = _ms(voicing_end - final.t0)
    if initial:
        out["initial"]["aspirated_target"] = initial.label in {"p", "t", "k", "c", "ch", "q"}

    # 声母
    consonant: dict = {}
    vowel_t0 = final.t0
    if cls in ("stop", "affricate"):
        consonant = _stop_timing(a, initial, final)
        if consonant["voicing_onset_s"] is not None and not consonant["prevoiced"]:
            vowel_t0 = max(final.t0, consonant["voicing_onset_s"])
    if cls in ("affricate", "fricative"):
        vowel_t0 = _measure_noise(a, i, initial, final, consonant, cls, voicing_end)
    if cls == "nasal":
        consonant = {"murmur_ms": _ms(initial.duration),
                     "F2_vowel_onset_hz": _rnd(a.formants_at(final.t0 + 0.015)[1], 0)}
    if cls in ("lateral", "approximant"):
        mid = 0.5 * (initial.t0 + initial.t1)
        vmid = final.t0 + 0.5 * (voicing_end - final.t0)
        m = (a.formant_t >= initial.t0) & (a.formant_t <= vmid)
        f3 = a.formants[2, m]
        ht, hv = a.harmonicity()
        hm = (ht >= initial.t0) & (ht <= initial.t1)
        ft = a.track.times
        fm = (ft >= initial.t0) & (ft <= initial.t1)
        consonant = {"formants_consonant_mid_hz": [_rnd(v, 0) for v in a.formants_at(mid)],
                     "formants_vowel_mid_hz": [_rnd(v, 0) for v in a.formants_at(vmid)],
                     "F3_min_hz": _rnd(np.nanmin(f3), 0) if np.isfinite(f3).any() else None,
                     "voiced_fraction": _rnd(np.isfinite(a.track.f0[fm]).mean(), 2) if fm.any() else None,
                     "hnr_db": _rnd(np.nanmean(hv[hm])) if np.isfinite(hv[hm]).any() else None}
        points = _grid(initial.t0, min(voicing_end, vmid + .05), .010)
        hf = _band_level(a.rec.x, points, .020, (3000.0, min(8000.0, a.bandwidth_hz)))
        consonant["transition"] = {"time_s": [_rnd(v, 3) for v in points],
                                   "hnr_db": [_rnd(v) for v in np.interp(points, ht, np.nan_to_num(hv, nan=np.nan))],
                                   "high_frequency_db": [_rnd(v - np.max(hf)) for v in hf]}
        left_f1 = a.formants_at(max(initial.t0, final.t0-.015))[0]
        right_f1 = a.formants_at(final.t0+.015)[0]
        consonant["F1_boundary_change_hz"] = _rnd(right_f1-left_f1, 0) if left_f1 and right_f1 else None
    out["consonant"] = consonant or None

    # 鼻韵尾
    coda = nasal_coda(final.label)
    vowel_t1 = voicing_end
    out["nasal_coda"] = None
    if coda:
        murmur = _coda_murmur(a, vowel_t0, voicing_end)
        info = {"label": coda, "detected": murmur is not None,
                "status": "candidate" if murmur else "not_detected"}
        if murmur:
            vowel_t1 = murmur[0]
            info.update(murmur_t0=_rnd(murmur[0], 3), murmur_t1=_rnd(murmur[1], 3),
                        murmur_ms=_ms(murmur[1] - murmur[0]))
        mid = vowel_t0 + 0.5 * (vowel_t1 - vowel_t0)
        mid_values = a.formants_at(mid, (vowel_t0, vowel_t1))
        end_values = a.formants_at(vowel_t1 - .010, (vowel_t0, vowel_t1)) if murmur else [None] * 3
        changes = [_rnd(end_values[k] - mid_values[k], 0) if mid_values[k] and end_values[k] else None for k in range(3)]
        info.update(F2_vowel_mid_hz=_rnd(mid_values[1], 0), F2_before_murmur_hz=_rnd(end_values[1], 0),
                    F1_change_hz=changes[0], F2_change_hz=changes[1], F3_change_hz=changes[2],
                    F2_slope_hz_per_ms=_rnd(changes[1] / ((vowel_t1-mid)*1000), 2) if changes[1] is not None and vowel_t1 > mid else None,
                    murmur_share=_rnd((murmur[1]-murmur[0]) / max(voicing_end-vowel_t0, .001), 3) if murmur else None)
        out["nasal_coda"] = info
    if cls == "nasal" or coda:
        out["nasal_dynamics"] = _nasalization_track(a, vowel_t0, voicing_end)

    # 元音
    vowel_t1 = max(vowel_t0, vowel_t1)
    positions = vowel_t0 + VOWEL_POSITIONS * (vowel_t1 - vowel_t0)
    samples = np.array([[np.nan if v is None else v for v in a.formants_at(t, (vowel_t0, vowel_t1))] for t in positions]).T
    if vowel_t1 - vowel_t0 < 0.020:
        samples[:] = np.nan
    sample_reasons = []
    for pos, values in zip(positions, samples.T):
        reasons = []
        for k, value in enumerate(values):
            if np.isfinite(value):
                reasons.append(None)
            else:
                nearby = np.abs(a.formant_t - pos) <= FORMANT_SAMPLE_HALF_WIN
                missing = sorted(set(a.formant_reasons[k, nearby]) - {""})
                reasons.append("、".join(missing) or "无数据或区间过短")
        sample_reasons.append(reasons)
    steady_t = _grid(vowel_t0 + .3*(vowel_t1-vowel_t0), vowel_t0 + .7*(vowel_t1-vowel_t0), FORMANT_STEP)
    steady = np.asarray([[v if v is not None else np.nan for v in a.formants_at(t, (vowel_t0, vowel_t1))] for t in steady_t])
    steady_hz = [_rnd(np.nanmedian(steady[:, k]), 0) if np.isfinite(steady[:, k]).any() else None for k in range(3)]
    valid_xy = np.isfinite(samples[:2]).all(axis=0)
    xy = samples[:2, valid_xy].T
    distance = float(np.sum(np.linalg.norm(np.diff(xy, axis=0), axis=1))) if len(xy) > 1 else None
    angle = float(np.degrees(np.arctan2(xy[-1, 0]-xy[0, 0], xy[-1, 1]-xy[0, 1]))) if len(xy) > 1 else None
    vowel = {"t0": _rnd(vowel_t0, 3), "t1": _rnd(vowel_t1, 3), "duration_ms": _ms(vowel_t1 - vowel_t0),
             "end": "murmur_start" if vowel_t1 < voicing_end else "voicing_end",
             "F1_hz": [_rnd(v, 0) for v in samples[0]], "F2_hz": [_rnd(v, 0) for v in samples[1]],
             "F3_hz": [_rnd(v, 0) for v in samples[2]],
             "mid_hz": [_rnd(samples[k, 5], 0) for k in range(3)],
             "steady_hz": steady_hz, "trajectory_length_hz": _rnd(distance, 0),
             "trajectory_angle_degree": _rnd(angle, 1),
             "sample_reasons": sample_reasons}
    plotted_f1 = hz_to_bark(samples[0])
    plotted_distance = hz_to_bark(samples[1]) - plotted_f1
    plotted_distance[samples[1] <= samples[0]] = np.nan
    vowel["F1_bark"] = [_rnd(v, 2) for v in plotted_f1]
    vowel["F2_minus_F1_bark"] = [_rnd(v, 2) for v in plotted_distance]
    norm = (a.rec.vowel_norm or {}).get("overall", a.rec.vowel_norm or {})
    if norm and norm.get("f1Std", 0) > 0 and norm.get("f2Std", 0) > 0 and np.isfinite(samples[:2, 5]).all():
        vowel["mid_z"] = [_rnd((samples[0, 5] - norm["f1Mean"]) / norm["f1Std"], 2),
                          _rnd((samples[1, 5] - norm["f2Mean"]) / norm["f2Std"], 2)]
    out["vowel"] = vowel

    # 声调：音节起点到有声终点（覆盖对齐截掉的尾部）
    seg = f0_pipeline.process_syllables(a.track, [(syll.t0, voicing_end)], *a.f0_range)[0]
    points = seg["comparisonPoints"]
    fp = seg["featurePoints"] or {}
    out["tone"] = {"chao": seg["chao"], "shape": seg["shape"],
                   "analysis_t0": seg["analysisStart"], "analysis_t1": seg["analysisEnd"],
                   "start_degree": (fp.get("start") or {}).get("degree"),
                   "end_degree": (fp.get("end") or {}).get("degree"),
                   "turning": fp.get("turning"),
                   "contour_degree": [p["degree"] for p in points] if points else [None] * 21,
                   "contour_hz": [p.get("hz") for p in points] if points else [None] * 21,
                   "quality": seg["quality"],
                   "can_diagnose": (seg["quality"] or {}).get("canDiagnose", False)}
    out["_tone_frames"] = seg["frames"]
    out["_tone_segment"] = seg

    # 时长与强度
    out["duration_ms"] = _ms(voicing_end - syll.t0)
    out["voicing_end_s"] = _rnd(voicing_end, 3)
    out["timeline"] = {"syllable_start_s": _rnd(syll.t0, 3), "initial_end_s": _rnd(initial.t1, 3) if initial else None,
                       "vowel_start_s": _rnd(vowel_t0, 3), "nasal_start_s": (out["nasal_coda"] or {}).get("murmur_t0"),
                       "voicing_end_s": _rnd(voicing_end, 3),
                       "creaky_intervals_s": [[_rnd(max(x, syll.t0), 3), _rnd(min(y, voicing_end), 3)]
                                              for x, y in a.creaky_intervals if y >= syll.t0 and x <= voicing_end]}
    if i > 0 and cls in {"stop", "affricate"} and consonant.get("release_s") is not None:
        consonant["closure_ms"] = _ms(max(0.0, consonant["release_s"]-a.syllables[i-1]["voicing_end_s"]))
    out["intensity"] = {
        "peak_db": _rnd(np.max(a.level_at(_grid(syll.t0, voicing_end, LEVEL_HOP)))),
        "vowel_mean_db": _rnd(np.mean(a.level_at(_grid(vowel_t0, vowel_t1, LEVEL_HOP))))}
    quality_ok = a.rec.signal_quality is not None and a.rec.signal_quality.get("verdict") == "pass"
    out["reliability"] = {
        "tone_shape": quality_ok and out["tone"]["can_diagnose"],
        "absolute_pitch": quality_ok and out["tone"]["can_diagnose"] and a.f0_range_source not in {"estimated_from_this_recording", "recording_adaptive", "default_adult_range"},
        "vowel": quality_ok and not coda and bool(np.isfinite(samples[:2, 5]).all()),
        "vot": quality_ok and consonant.get("vot_ms") is not None,
        "noise_spectrum": quality_ok and "spectrum" in consonant,
        "noise_rise": False,
        "nasal_coda": False,
        "sonorant_midpoint": quality_ok and cls in {"nasal", "lateral", "approximant"} and initial.duration >= SHORT_INITIAL_SEC,
    }
    return out


def to_json(a: Analysis) -> dict:
    return {"duration_s": _rnd(a.duration, 3), "sex_estimated": a.sex,
            "f0_range_hz": [_rnd(v) for v in a.f0_range], "f0_range_source": a.f0_range_source,
            "formant_ceiling_hz": a.formant_ceiling, "vowel_space": a.rec.vowel_norm,
            "sample_rate_hz": SR, "source_sample_rate_hz": a.rec.source_sample_rate,
            "bandwidth_hz": a.bandwidth_hz, "signal_quality": a.rec.signal_quality,
            "syllables": [{k: v for k, v in s.items() if not k.startswith("_")} for s in a.syllables]}
