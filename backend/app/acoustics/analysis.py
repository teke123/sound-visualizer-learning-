"""声学分析内核：本地信号维质检（音量/噪声/截幅/时长/静音比）、F0 提取
（tone_py + Praat/parselmouth）、共振峰提取（Burg）与曲线可靠性把关。

F0 与可靠性方法论来自 tone_py（docs/04-产品应用映射.md）：
- 提取：extract_f0，75–600 Hz / 10 ms，Praat 语义（unvoiced = NaN）；
- 标定音域：稳健中心 ± 稳健尺度（median±2σ），不用全局 min/max；
- T 值换算：对数域 FOR，(log f - log lo)/(log hi - log lo) * 5；
- 可靠性：有声占比 + 八度跳变密度组合判定 not_available。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app import config
from app.acoustics import transcode

# F0 提取参数随算法版本进入缓存键
F0_MIN_HZ = 75.0
F0_MAX_HZ = 600.0
F0_HOP_MS = 10.0

# 信号维质量阈值（上线前用真实录音标定；M0 验证项）
VOLUME_DBFS_RANGE = (-38.0, -3.0)     # 音量
CLIP_RATIO_MAX = 0.002                # 截幅：|s|≥0.985 满幅占比
SNR_DB_MIN = 10.0                     # 噪声：语音带 vs 底噪
SILENCE_RATIO_MAX = 0.90              # 静音比
DURATION_RANGE_RECORDING = (0.4, 30.0)
DURATION_RANGE_CALIBRATION = (2.0, 40.0)


@dataclass
class SignalCheckResult:
    verdict: str                      # pass | fail
    volume: dict = field(default_factory=dict)
    noise: dict = field(default_factory=dict)
    clipping: dict = field(default_factory=dict)
    duration: dict = field(default_factory=dict)
    silence: dict = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "volume": self.volume,
            "noise": self.noise,
            "clipping": self.clipping,
            "duration": self.duration,
            "silence": self.silence,
            "failedDimensions": self.failures,
        }


def _dbfs(x: float) -> float:
    return float(20 * np.log10(max(x, 1e-10)))


def check_signal(wav_path: Path, *, purpose: str, expected_duration: float | None = None) -> SignalCheckResult:
    """本地信号维质检（FR-1301 维度一）。不合格不调用 Provider。"""
    samples = transcode.read_pcm_samples(wav_path)
    duration = len(samples) / float(transcode.SAMPLE_RATE)

    result = SignalCheckResult(verdict="pass")

    # 时长
    lo, hi = (DURATION_RANGE_CALIBRATION if purpose == "calibration"
              else DURATION_RANGE_RECORDING)
    dur_pass = lo <= duration <= hi
    result.duration = {
        "valueSec": round(duration, 2),
        "expectedSec": expected_duration,
        "pass": dur_pass,
    }
    if not dur_pass:
        result.failures.append("duration")
        if duration < lo:
            result.duration["advice"] = "录音太短，请等提示读完再停止录音"
        else:
            result.duration["advice"] = "录音过长，请只朗读提示的内容"

    # 截幅
    clip_ratio = float(np.mean(np.abs(samples) >= 0.985))
    clip_pass = clip_ratio <= CLIP_RATIO_MAX
    result.clipping = {
        "ratio": round(clip_ratio, 6),
        "pass": clip_pass,
        "advice": None if clip_pass else "录音有爆音（离麦克风太近或音量太大），请离麦克风约一拳距离重录",
    }
    if not clip_pass:
        result.failures.append("clipping")

    # 音量 / 噪声 / 静音比：20ms 帧 RMS
    frame = int(0.02 * transcode.SAMPLE_RATE)
    n_frames = len(samples) // frame
    if n_frames >= 2:
        framed = samples[: n_frames * frame].reshape(n_frames, frame)
        rms = np.sqrt(np.mean(framed ** 2, axis=1))
        rms_db = np.array([_dbfs(v) for v in rms])
        overall_db = _dbfs(float(np.sqrt(np.mean(samples ** 2))))
    else:
        rms_db = np.array([_dbfs(float(np.sqrt(np.mean(samples ** 2)) if len(samples) else 0.0))])
        overall_db = rms_db[0]

    vol_pass = VOLUME_DBFS_RANGE[0] <= overall_db <= VOLUME_DBFS_RANGE[1]
    result.volume = {
        "dbfs": round(float(overall_db), 1),
        "pass": vol_pass,
        "advice": None if vol_pass else (
            "录音音量太小，请靠近麦克风一些重录" if overall_db < VOLUME_DBFS_RANGE[0]
            else "录音音量过大，请离远一些重录"),
    }
    if not vol_pass:
        result.failures.append("volume")

    noise_floor = float(np.percentile(rms_db, 10))
    speech_level = float(np.percentile(rms_db, 95))
    snr = speech_level - noise_floor
    noise_pass = snr >= SNR_DB_MIN
    result.noise = {
        "snrDb": round(float(snr), 1),
        "pass": noise_pass,
        "advice": None if noise_pass else "环境噪声较大，请找安静的地方重录",
    }
    if not noise_pass:
        result.failures.append("noise")

    silence_ratio = float(np.mean(rms_db < -45.0))
    sil_pass = silence_ratio <= SILENCE_RATIO_MAX
    result.silence = {
        "ratio": round(silence_ratio, 3),
        "pass": sil_pass,
        "advice": None if sil_pass else "录音几乎全是静音，请确认麦克风正常后重录",
    }
    if not sil_pass:
        result.failures.append("silence")

    # 「能解码但过短/静音」属于质量不合格（SRS 04 FR-1301）
    if result.failures:
        result.verdict = "fail"
    return result


# ---------------- F0 ----------------

@dataclass
class F0Result:
    frames: list[dict]        # [{t: 秒, hz: Hz?}]（unvoiced 无 hz 键）
    voiced_ranges: list[list[float]]
    voiced_ratio: float
    jump_density: float       # 八度跳变帧占比
    reliable: bool            # not_available 判定
    note: str | None


def extract_f0(wav_path: Path) -> F0Result:
    """tone_py extract_f0（Praat/parselmouth 语义）。"""
    from app.acoustics.tone_py.extract import extract_f0 as tp_extract

    df = tp_extract(str(wav_path), f0_min=F0_MIN_HZ, f0_max=F0_MAX_HZ,
                    step_ms=F0_HOP_MS, engine="parselmouth", with_intensity=False)
    if df.empty:
        return F0Result([], [], 0.0, 0.0, False, "录音太短，无法提取音高")
    t = df["time"].to_numpy(dtype=float)
    f0 = df["f0"].to_numpy(dtype=float)
    voiced = np.isfinite(f0)
    total = len(f0)
    voiced_ratio = float(voiced.mean()) if total else 0.0

    # 有声区段（连续 voiced 帧合并，间隙 ≤ 80ms 视为同段）
    ranges: list[list[float]] = []
    gap = 0.08
    i = 0
    while i < total:
        if voiced[i]:
            j = i
            last_voiced = i
            while j + 1 < total and (voiced[j + 1] or (t[j + 1] - t[last_voiced]) <= gap):
                if voiced[j + 1]:
                    last_voiced = j + 1
                j += 1
            ranges.append([round(float(t[i]), 3), round(float(t[last_voiced]), 3)])
            i = last_voiced + 1
        else:
            i += 1

    # 八度跳变密度（tone_py flag_pitch_jumps 思想：相邻有声帧跳 > 0.8 个八度）
    jumps = 0
    voiced_idx = np.where(voiced)[0]
    for a, b in zip(voiced_idx[:-1], voiced_idx[1:]):
        if b - a == 1 and abs(np.log2(f0[b] / f0[a])) > 0.8:
            jumps += 1
    n_voiced = len(voiced_idx)
    jump_density = float(jumps / n_voiced) if n_voiced else 0.0

    frames = []
    for ti, fi, v in zip(t, f0, voiced):
        fr = {"t": round(float(ti), 3)}
        if v:
            fr["hz"] = round(float(fi), 1)
        frames.append(fr)

    reliable = voiced_ratio >= 0.5 and jump_density <= 0.10
    note = None
    if not reliable:
        note = ("录音里稳定的嗓音太少，画不出可靠曲线" if voiced_ratio < 0.5
                else "音高曲线跳动较大，仅供参考")
    return F0Result(frames=frames, voiced_ranges=ranges, voiced_ratio=voiced_ratio,
                    jump_density=jump_density, reliable=reliable, note=note)


def robust_pitch_range(f0_hz: np.ndarray) -> tuple[float, float] | None:
    """标定音域：median ± 2σ（稳健，防一次跑调撑爆范围）；帧数下限 50。"""
    f = f0_hz[np.isfinite(f0_hz)]
    if f.size < 50:
        return None
    med = float(np.nanmedian(f))
    std = float(np.nanstd(f))
    lo = max(med - 2 * std, 40.0)
    hi = min(med + 2 * std, 1000.0)
    if hi <= lo * 1.05:   # 范围过窄（几乎无起伏）不成有效音域
        return None
    return lo, hi


def to_t_values(f0_hz: np.ndarray, f_lo: float, f_hi: float) -> np.ndarray:
    """Hz → T 值 [0,5]（对数域 FOR，tone_py docs §2.2）。"""
    lo, hi = float(np.log(max(f_lo, 1e-3))), float(np.log(max(f_hi, 1e-3)))
    if hi <= lo:
        return np.full_like(f0_hz, np.nan, dtype=float)
    return (np.log(np.where(f0_hz > 0, f0_hz, np.nan)) - lo) / (hi - lo) * 5.0


# ---------------- 共振峰 ----------------

@dataclass
class FormantResult:
    frames: list[dict]        # [{t, f1?, f2?}]
    vowel_segments: list[list[float]]


def extract_formants(wav_path: Path, *, max_formant: float = 5500.0) -> FormantResult:
    """Praat Burg 共振峰（F1/F2），按有声段给出元音段。"""
    import parselmouth

    snd = parselmouth.Sound(str(wav_path))
    formant = snd.to_formant_burg(time_step=F0_HOP_MS / 1000.0,
                                  max_number_of_formants=5.0,
                                  maximum_formant=max_formant,
                                  window_length=0.025, pre_emphasis_from=50.0)
    pitch = snd.to_pitch(time_step=F0_HOP_MS / 1000.0,
                         pitch_floor=F0_MIN_HZ, pitch_ceiling=F0_MAX_HZ)
    f0 = np.asarray(pitch.selected_array["frequency"], dtype=float)
    t = np.asarray(pitch.xs(), dtype=float)
    voiced = f0 > 0

    frames = []
    for i, ti in enumerate(t):
        fr = {"t": round(float(ti), 3)}
        if voiced[i]:
            f1 = formant.get_value_at_time(1, float(ti))
            f2 = formant.get_value_at_time(2, float(ti))
            # Praat 未定义值（NaN/0）视为缺帧
            f1 = None if (f1 is None or f1 != f1 or f1 <= 0) else round(float(f1), 1)
            f2 = None if (f2 is None or f2 != f2 or f2 <= 0) else round(float(f2), 1)
            if f1:
                fr["f1"] = f1
            if f2:
                fr["f2"] = f2
        frames.append(fr)

    segments: list[list[float]] = []
    i = 0
    while i < len(t):
        if voiced[i]:
            j = i
            while j + 1 < len(t) and voiced[j + 1]:
                j += 1
            segments.append([round(float(t[i]), 3), round(float(t[j]), 3)])
            i = j + 1
        else:
            i += 1
    return FormantResult(frames=frames, vowel_segments=segments)


def formant_stats_in_segments(formants: FormantResult, segments: list[list[float]]) -> dict:
    """给定时间段内的 F1/F2 均值（元音空间统计用）。"""
    f1s, f2s = [], []
    for fr in formants.frames:
        if "f1" in fr and "f2" in fr:
            for seg in segments:
                if seg[0] <= fr["t"] <= seg[1]:
                    f1s.append(fr["f1"])
                    f2s.append(fr["f2"])
                    break
    if not f1s:
        return {}
    return {
        "f1Mean": round(float(np.mean(f1s)), 1),
        "f2Mean": round(float(np.mean(f2s)), 1),
        "f1Std": round(float(np.std(f1s)), 1),
        "f2Std": round(float(np.std(f2s)), 1),
        "nFrames": len(f1s),
    }


ALGORITHM_VERSION = config.ALGORITHM_VERSION
