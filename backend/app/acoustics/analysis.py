"""声学分析内核：本地信号维质检（音量/噪声/截幅/时长/静音比）、F0 提取
（Praat/parselmouth 自相关法 + tone_py）、自适应声道长度共振峰提取（Burg）、
送气段/清辅音起始检测（VOT）与曲线可靠性把关。

F0 与归一化方法论结合 tone_py（Rose 1987; Zhu 1999; Xu & Zhang 2024）：
- 提取：Praat To Pitch (ac)，70–420 Hz / 10 ms，抑制送气/摩擦段高频伪有声；
- 标定音域：对数半音域稳健分位数（P3–P97 外扩 6%），兼顾四声全调域与抗喉化离群点；
- T 值换算：对数域 FOR，(log f - log lo)/(log hi - log lo) * 5，截断到 [0, 5]；
- 共振峰：按嗓音基频中位数自动选择声道 ceiling（男声 <165Hz 用 5000Hz，女声用 5500Hz），
  统计时取元音稳态中段（20%–80%）中位数，避开声母协同发音过渡段；
- 可靠性：有效有声帧数（≥12 帧）+ 八度跳变密度组合判定，兼容长清辅音+短促去声音节。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app import config
from app.acoustics import transcode

# F0 提取参数随算法版本进入缓存键
F0_MIN_HZ = 65.0
F0_MAX_HZ = 420.0
F0_HOP_MS = 10.0

# 信号维质量阈值（已在 FV1~3 / MV1~3 真人语料库标定）
VOLUME_DBFS_RANGE = (-38.0, -2.0)     # 音量
CLIP_RATIO_MAX = 0.005                # 截幅：|s|≥0.985 满幅占比
SNR_DB_MIN = 10.0                     # 噪声：语音峰值 vs 环境底噪
SILENCE_RATIO_MAX = 0.92              # 静音比
DURATION_RANGE_RECORDING = (0.3, 30.0)
DURATION_RANGE_CALIBRATION = (1.5, 40.0)


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
    """本地信号维质检（FR-1301 维度一）。仅作结果提示，不拦截评分与可视化。"""
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
    clip_ratio = float(np.mean(np.abs(samples) >= 0.985)) if len(samples) else 0.0
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

    # 环境底噪估计：对切分紧凑的录音（全段ほぼ都在发声，P10 落在元音内），
    # 取首尾边界帧与全局最静 3 帧的均值作为底噪估计，避免把饱满的干净录音误判为高噪
    speech_level = float(np.percentile(rms_db, 95))
    k_quiet = max(1, min(3, len(rms_db) // 6))
    quietest = float(np.mean(np.sort(rms_db)[:k_quiet]))
    noise_floor = min(float(np.percentile(rms_db, 10)), quietest, -42.0 if speech_level > -22.0 else quietest)
    snr = max(0.0, speech_level - noise_floor)
    noise_pass = snr >= SNR_DB_MIN and speech_level >= VOLUME_DBFS_RANGE[0]
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
    """Praat To Pitch (ac) 提取基频：
    使用 silence_threshold=0.05、voicing_threshold=0.52 抑制清辅音送气/摩擦段的
    高频伪周期（防止把 p/t/k 送气段误判为 450Hz+ 浊音），并对单帧孤立毛刺滤波。"""
    import parselmouth

    snd = parselmouth.Sound(str(wav_path))
    if snd.duration < 0.08:
        return F0Result([], [], 0.0, 0.0, False, "录音太短，无法提取音高")

    pitch = parselmouth.praat.call(
        snd, "To Pitch (ac)",
        F0_HOP_MS / 1000.0,   # time_step (10 ms)
        F0_MIN_HZ,            # pitch_floor (65 Hz)
        15,                   # max_number_of_candidates
        "no",                 # very_accurate
        0.05,                 # silence_threshold
        0.52,                 # voicing_threshold
        0.01,                 # octave_cost
        0.35,                 # octave_jump_cost
        0.14,                 # voiced_unvoiced_cost
        F0_MAX_HZ,            # pitch_ceiling (420 Hz)
    )
    t = np.asarray(pitch.xs(), dtype=float)
    f0 = np.asarray(pitch.selected_array["frequency"], dtype=float)
    f0 = np.where((f0 >= F0_MIN_HZ) & (f0 <= F0_MAX_HZ), f0, np.nan)

    # 剔除前后皆 unvoiced 的单帧孤立伪有声点
    for idx in range(len(f0)):
        if np.isfinite(f0[idx]):
            left_ok = idx > 0 and np.isfinite(f0[idx - 1])
            right_ok = idx + 1 < len(f0) and np.isfinite(f0[idx + 1])
            if not left_ok and not right_ok:
                f0[idx] = np.nan

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

    # 八度跳变密度（相邻有声帧跳 > 0.8 个八度）
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

    # 可靠性：有效有声帧 ≥ 12（120ms，兼容 ci4/si1 等长清辅音+短去声音节）且跳变密度 ≤ 0.12
    reliable = (n_voiced >= 12 and voiced_ratio >= 0.15) and jump_density <= 0.12
    note = None
    if not reliable:
        note = ("录音里稳定的嗓音太少，画不出可靠曲线" if n_voiced < 12 or voiced_ratio < 0.15
                else "音高曲线跳动较大")
    return F0Result(frames=frames, voiced_ranges=ranges, voiced_ratio=voiced_ratio,
                    jump_density=jump_density, reliable=reliable, note=note)


def robust_pitch_range(f0_hz: np.ndarray) -> tuple[float, float] | None:
    """标定音域：对数分位数 P3–P97 外扩 6%（覆盖五度 [0,5] 全调域，同时过滤
    四声末尾喉化/气泡音离群帧）；帧数下限 20。"""
    f = f0_hz[np.isfinite(f0_hz) & (f0_hz > 0)]
    if f.size < 20:
        return None
    p3, p97 = (float(v) for v in np.percentile(f, [3, 97]))
    lo = max(round(p3 * 0.94, 1), 55.0)
    hi = min(round(p97 * 1.06, 1), 520.0)
    if hi <= lo * 1.05:   # 范围过窄（几乎无起伏）不成有效音域
        return None
    return lo, hi


def to_t_values(f0_hz: np.ndarray, f_lo: float, f_hi: float) -> np.ndarray:
    """Hz → T 值 [0,5]（对数域 FOR，带 [0, 5] 边界钳制，防止超出统计音域的点溢出画布）。"""
    lo, hi = float(np.log(max(f_lo, 1e-3))), float(np.log(max(f_hi, 1e-3)))
    if hi <= lo:
        return np.full_like(f0_hz, np.nan, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = (np.log(np.where(f0_hz > 0, f0_hz, np.nan)) - lo) / (hi - lo) * 5.0
    return np.clip(raw, 0.0, 5.0)


# ---------------- 共振峰 ----------------

@dataclass
class FormantResult:
    frames: list[dict]        # [{t, f1?, f2?}]
    vowel_segments: list[list[float]]


def extract_formants(wav_path: Path, *, max_formant: float | None = None) -> FormantResult:
    """Praat Burg 共振峰（F1/F2），按有声段给出元音段。
    未显式指定 max_formant 时，根据音频基频中位数自动判定声道长度 ceiling：
    男声（median F0 < 165 Hz）用 5000 Hz，女声（≥ 165 Hz）用 5500 Hz。"""
    import parselmouth

    snd = parselmouth.Sound(str(wav_path))
    pitch = parselmouth.praat.call(
        snd, "To Pitch (ac)",
        F0_HOP_MS / 1000.0, F0_MIN_HZ, 15, "no",
        0.05, 0.52, 0.01, 0.35, 0.14, F0_MAX_HZ,
    )
    f0 = np.asarray(pitch.selected_array["frequency"], dtype=float)
    t = np.asarray(pitch.xs(), dtype=float)
    voiced = f0 > 0

    if max_formant is None:
        voiced_f0 = f0[voiced]
        med_f0 = float(np.median(voiced_f0)) if voiced_f0.size > 0 else 200.0
        max_formant = 5000.0 if med_f0 < 165.0 else 5500.0

    formant = snd.to_formant_burg(time_step=F0_HOP_MS / 1000.0,
                                  max_number_of_formants=5.0,
                                  maximum_formant=max_formant,
                                  window_length=0.025, pre_emphasis_from=50.0)

    frames = []
    for i, ti in enumerate(t):
        fr = {"t": round(float(ti), 3)}
        if voiced[i]:
            f1 = formant.get_value_at_time(1, float(ti))
            f2 = formant.get_value_at_time(2, float(ti))
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
    """给定时间段内的稳态元音 F1/F2 统计（元音空间标定与对比用）：
    取段内中间 20%–80% 稳态窗口并用中位数代表中心，消除声母除阻协同发音过渡段干扰。"""
    matched = []
    for fr in formants.frames:
        if "f1" in fr and "f2" in fr:
            for seg in segments:
                if seg[0] <= fr["t"] <= seg[1]:
                    matched.append(fr)
                    break
    if not matched:
        return {}
    if len(matched) >= 6:
        lo_idx = int(len(matched) * 0.2)
        hi_idx = max(lo_idx + 2, int(len(matched) * 0.8))
        core = matched[lo_idx:hi_idx]
    else:
        core = matched
    f1s = [fr["f1"] for fr in core]
    f2s = [fr["f2"] for fr in core]
    return {
        "f1Mean": round(float(np.median(f1s)), 1),
        "f2Mean": round(float(np.median(f2s)), 1),
        "f1Std": round(float(np.std(f1s)), 1),
        "f2Std": round(float(np.std(f2s)), 1),
        "nFrames": len(matched),
    }


# ---------------- 送气段 / VOT ----------------

VOT_FRAME_SEC = 0.005           # 5 ms 帧分辨率（教学对比 ±5 ms 足够）


@dataclass
class OnsetSpan:
    onset_sec: float        # 清辅音起始（burst/摩擦噪声起点，秒）
    voicing_sec: float      # 嗓音起始（首个稳定有声帧，秒）
    vot_ms: float           # VOT = 嗓音起始 − 清辅音起始（毫秒）


def detect_onset_span(wav_path: Path, f0: F0Result | None = None) -> OnsetSpan | None:
    """送气段/VOT 检测（FR-1005）：
    1. 先从 F0 序列定位首个连续稳定有声段起点 `voicing_sec`；
    2. 以首尾静音边缘估计环境底噪（不依赖全局 P10，防止紧凑剪辑录音把送气段当底噪）；
    3. 在 `[0, voicing_sec]` 区间内結合能量突增与过零率（ZCR，捕捉清擦音/除阻爆破高频噪声）
       定位辅音起始点 `onset_sec`。"""
    samples = transcode.read_pcm_samples(wav_path)
    frame = int(VOT_FRAME_SEC * transcode.SAMPLE_RATE)
    n_frames = len(samples) // frame
    if n_frames < 4:
        return None
    framed = samples[: n_frames * frame].reshape(n_frames, frame)
    rms = np.sqrt(np.mean(framed ** 2, axis=1))
    rms_db = np.array([_dbfs(v) for v in rms])
    signs = np.sign(framed)
    zcr = np.mean(np.abs(np.diff(signs, axis=1)) > 0, axis=1)

    f0 = f0 or extract_f0(wav_path)
    voicing_t = None
    for idx in range(len(f0.frames)):
        fr = f0.frames[idx]
        if "hz" in fr:
            # 要求至少连续 2 帧有声（若是极短音则单帧亦可）
            if idx + 1 < len(f0.frames) and "hz" in f0.frames[idx + 1]:
                voicing_t = fr["t"]
                break
    if voicing_t is None:
        for fr in f0.frames:
            if "hz" in fr:
                voicing_t = fr["t"]
                break
    if voicing_t is None:
        return None

    peak_db = float(np.max(rms_db))
    edge = np.concatenate([rms_db[:3], rms_db[-6:]])
    floor_db = min(float(np.percentile(edge, 25)), peak_db - 22.0, -35.0)
    thresh_db = max(floor_db + 8.0, peak_db - 28.0)

    voicing_idx = max(1, min(int(round(voicing_t / VOT_FRAME_SEC)), n_frames))
    onset_idx = None
    for i in range(voicing_idx):
        cond_energy = (rms_db[i] >= thresh_db) and (
            i + 1 >= voicing_idx or rms_db[i + 1] >= thresh_db - 3.0
        )
        cond_burst = (rms_db[i] >= floor_db + 6.0) and (zcr[i] >= 0.22)
        if cond_energy or cond_burst:
            onset_idx = i
            break

    onset_t = (onset_idx * VOT_FRAME_SEC) if onset_idx is not None else max(0.0, voicing_t - VOT_FRAME_SEC)
    if onset_t >= voicing_t:
        onset_t = max(0.0, voicing_t - VOT_FRAME_SEC)
    vot_ms = round(max(5.0, (voicing_t - onset_t) * 1000.0), 1)
    return OnsetSpan(
        onset_sec=round(onset_t, 3),
        voicing_sec=round(voicing_t, 3),
        vot_ms=vot_ms,
    )


def adaptive_f0_range(f0: F0Result) -> tuple[float, float] | None:
    """单次录音自适应音域（FR-1006 跳过标定路径）：
    - 若录音自身起伏充分（多音节或升降调，hi > lo*1.18），取 P5–P95 外扩 8%；
    - 若录音为单字平调（如阴平单韵母/声母关，起伏窄），以其中位数 F0 锚定该发音人的
      自然音高中心，按标准半音跨度（下探 7 半音、上浮 4 半音）构建个人自适应五度音域，
      避免回落到固定 95–260Hz 导致女高音全顶在 5 度或男低音全压在 1 度。"""
    hz = np.array([fr["hz"] for fr in f0.frames if "hz" in fr], dtype=float)
    if hz.size < 12:
        return None
    lo, hi = (float(v) for v in np.percentile(hz, [5, 95]))
    if hi > lo * 1.18:
        return round(max(lo * 0.92, 55.0), 1), round(min(hi * 1.08, 520.0), 1)
    med = float(np.median(hz))
    # 单音节窄跨度：以中位数作为中高音区（约 T=3.5~4.0），对称推算五度上下界
    est_lo = max(med * (2.0 ** (-7.0 / 12.0)), 60.0)
    est_hi = min(med * (2.0 ** (4.0 / 12.0)), 500.0)
    return round(est_lo, 1), round(est_hi, 1)


# ---------------- 频谱图 ----------------

# Praat 默认参数：Gaussian 窗 5ms / 2ms 帧移 / 20Hz 频率步长
SPECTRO_WINDOW_SEC = 0.005
SPECTRO_TIME_STEP_SEC = 0.002
SPECTRO_FREQ_STEP_HZ = 20.0
# Praat 绘图动态范围：从峰值向下 50 dB 之外不区分
SPECTRO_DYNAMIC_RANGE_DB = 50.0


@dataclass
class SpectrogramResult:
    values_db: np.ndarray    # dB 功率谱阵，形状 (频率格 × 时间格)
    tmin: float
    tmax: float
    fmax: float


def compute_spectrogram(wav_path: Path, *, max_freq: float = 8000.0) -> SpectrogramResult:
    """Praat Spectrogram（parselmouth，Gaussian 窗）→ dB 阵列，供热力图渲染。"""
    import parselmouth

    snd = parselmouth.Sound(str(wav_path))
    sg = snd.to_spectrogram(window_length=SPECTRO_WINDOW_SEC,
                            maximum_frequency=max_freq,
                            time_step=SPECTRO_TIME_STEP_SEC,
                            frequency_step=SPECTRO_FREQ_STEP_HZ)
    db = 10.0 * np.log10(np.maximum(sg.values, 1e-12))
    return SpectrogramResult(values_db=db, tmin=float(sg.xmin),
                             tmax=float(sg.xmax), fmax=max_freq)


ALGORITHM_VERSION = config.ALGORITHM_VERSION
