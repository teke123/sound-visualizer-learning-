"""声学图像提取的共享基础层（对应 docs/声学图像提取/方案.md）。

各图像模块共用的约定集中在这里：
- 对齐数据模型：音节 → 音素（讯飞返回的声母/韵母两段），时间为原始录音时间轴（秒）；
- 音频读取：保留原始采样率与振幅；双声道只取一个声道，不混音
  （声道间存在采样级延迟时，混音会在高频产生梳状滤波）；
- 发音人参数：F0 范围与共振峰上限（方案 §3.1 / §5.1 的初始值）；
- 公共分析：F0（Praat filtered autocorrelation）、短时功率谱、LPC 包络；
- 绘图：完整时间轴、音素边界虚线、跨样本统一的 dB 标尺（DbScales）。
"""
from __future__ import annotations

import csv
import json
import wave
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np

OUT_DPI = 150
ANALYSIS_CHANNEL = 0


# ---------------- 对齐数据模型 ----------------

@dataclass
class PhoneSeg:
    label: str      # 讯飞音素符号：声母 b/p/…，零声母伪声母 _a/_i/…，韵母 a/ii/iii/v/iao/…
    part: str       # "initial" | "final"
    t0: float
    t1: float

    @property
    def duration(self) -> float:
        return self.t1 - self.t0


@dataclass
class SyllableSeg:
    text: str
    symbol: str     # 带调拼音，如 "ma3"
    t0: float
    t1: float
    phones: list[PhoneSeg]

    @property
    def initial(self) -> PhoneSeg | None:
        return next((p for p in self.phones if p.part == "initial"), None)

    @property
    def final(self) -> PhoneSeg | None:
        return next((p for p in self.phones if p.part == "final"), None)

    @property
    def tone(self) -> int | None:
        return int(self.symbol[-1]) if self.symbol and self.symbol[-1].isdigit() else None


@dataclass
class Alignment:
    file: str       # wav 文件名
    speaker: str
    duration: float
    syllables: list[SyllableSeg]

    @property
    def phones(self) -> list[PhoneSeg]:
        return [p for s in self.syllables for p in s.phones]


def load_alignment(path: str | Path) -> dict[str, Alignment]:
    """读取对齐汇总 JSON（docs/声学图像提取/对齐结果/alignment.json 的格式），按 wav 文件名索引。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, Alignment] = {}
    for s in data["samples"]:
        if "error" in s:
            continue
        sylls = []
        for sy in s["syllables"]:
            phones = [PhoneSeg(p["label"], p["part"], p["t0"], p["t1"]) for p in sy["phones"]
                      if p["t0"] is not None and p["t1"] is not None and p["t1"] > p["t0"]]
            sylls.append(SyllableSeg(sy["text"], sy["symbol"], sy["t0"], sy["t1"], phones))
        name = Path(s["file"]).name
        out[name] = Alignment(name, s["speaker"], s["durationSec"], sylls)
    return out


# ---------------- 音素分类与标签 ----------------

# 普通话声母按发音方式分类；零声母伪声母（以 "_" 开头）单独归为 "zero"
INITIAL_CLASS = {
    "b": "stop", "p": "stop", "d": "stop", "t": "stop", "g": "stop", "k": "stop",
    "z": "affricate", "c": "affricate", "zh": "affricate", "ch": "affricate",
    "j": "affricate", "q": "affricate",
    "f": "fricative", "s": "fricative", "sh": "fricative", "x": "fricative", "h": "fricative",
    "m": "nasal", "n": "nasal",
    "l": "lateral",
    "r": "approximant",   # 普通话 r 兼有浊擦音与近音表现，按近音分析 F1–F3，并附噪声频谱
}
ASPIRATED = {"p", "t", "k", "c", "ch", "q"}
SIBILANTS = {"s", "sh", "x", "z", "c", "zh", "ch", "j", "q"}

MONOPHTHONG_FINALS = {"a", "o", "e", "i", "u", "v", "ii", "iii", "er", "ea"}
TRIPHTHONG_FINALS = {"iao", "iou", "iu", "uai", "uei", "ui"}

PHONE_IPA = {
    "b": "p", "p": "pʰ", "d": "t", "t": "tʰ", "g": "k", "k": "kʰ",
    "z": "ts", "c": "tsʰ", "zh": "tʂ", "ch": "tʂʰ", "j": "tɕ", "q": "tɕʰ",
    "f": "f", "s": "s", "sh": "ʂ", "x": "ɕ", "h": "x", "r": "ʐ",
    "m": "m", "n": "n", "l": "l",
    "a": "a", "o": "o", "e": "ɤ", "i": "i", "u": "u", "v": "y", "ii": "ɿ", "iii": "ʅ", "er": "ɚ",
    "ai": "ai", "ei": "ei", "ao": "au", "ou": "ou",
    "an": "an", "en": "ən", "ang": "aŋ", "eng": "əŋ", "ong": "ʊŋ",
    "ia": "ia", "ie": "iɛ", "iao": "iau", "iou": "iou", "iu": "iou",
    "ian": "iɛn", "in": "in", "iang": "iaŋ", "ing": "iŋ", "iong": "iʊŋ",
    "ua": "ua", "uo": "uo", "uai": "uai", "uei": "uei", "ui": "uei",
    "uan": "uan", "uen": "uən", "un": "uən", "uang": "uaŋ", "ueng": "uəŋ",
    "ve": "yɛ", "van": "yɛn", "vn": "yn",
}


def initial_class(label: str) -> str:
    """声母发音方式：stop / affricate / fricative / nasal / lateral / approximant / zero / unknown。"""
    if label.startswith("_"):
        return "zero"
    return INITIAL_CLASS.get(label, "unknown")


def nasal_coda(final_label: str) -> str | None:
    """韵母的鼻韵尾（"n" / "ng"），无则 None。"""
    if final_label.endswith("ng"):
        return "ng"
    if final_label.endswith("n"):
        return "n"
    return None


def final_type(final_label: str) -> str:
    """韵母结构：monophthong / diphthong / triphthong / nasal_final。"""
    if nasal_coda(final_label):
        return "nasal_final"
    if final_label in MONOPHTHONG_FINALS:
        return "monophthong"
    if final_label in TRIPHTHONG_FINALS:
        return "triphthong"
    return "diphthong"


def display_label(phone: PhoneSeg) -> str:
    """图上显示用标签：讯飞符号 + IPA（零声母显示为 ∅）。"""
    if phone.label.startswith("_"):
        return "∅"
    ipa = PHONE_IPA.get(phone.label)
    return f"{phone.label} [{ipa}]" if ipa and ipa != phone.label else phone.label


# ---------------- 发音人参数 ----------------

@dataclass(frozen=True)
class SpeakerProfile:
    name: str
    f0_floor: float         # Hz
    f0_ceiling: float       # Hz
    formant_ceiling: float  # Hz，Burg 共振峰上限


FEMALE = SpeakerProfile("female", 100.0, 500.0, 5500.0)
MALE = SpeakerProfile("male", 60.0, 300.0, 5000.0)
WIDE_F0_RANGE = (50.0, 600.0)   # 方案 §5.1：先用宽范围做初步检查，再按实际录音收窄

_SPEAKER_PROFILES: dict[str, SpeakerProfile] = {}


def set_speaker_profiles(profiles: dict[str, SpeakerProfile]) -> None:
    """登记按语料统计得到的发音人参数（批处理第一遍调用）；profile_for 优先返回登记值。"""
    _SPEAKER_PROFILES.clear()
    _SPEAKER_PROFILES.update(profiles)


def profile_for(speaker: str) -> SpeakerProfile:
    """发音人参数：优先取 set_speaker_profiles 登记的实测值，否则按编号 FV*/MV* 取女声/男声初始值。"""
    if speaker in _SPEAKER_PROFILES:
        return _SPEAKER_PROFILES[speaker]
    return MALE if speaker.upper().startswith("M") else FEMALE


def estimate_profile(speaker: str, f0_hz: np.ndarray) -> SpeakerProfile:
    """由宽范围（WIDE_F0_RANGE）提取的有声帧 F0 收窄 F0 范围（方案 §5.1：按说话人实际最低/最高 F0 设定）。

    floor = 0.75 × 第 1 百分位，ceiling = 1.25 × 第 99 百分位，均取 5 Hz 的整数倍。
    下限按第 1 百分位取，以保留去声、上声真实的低尾（样本中女声去声尾部约 100 Hz）；
    混入的半频错误由 prosody 模块的倍频/半频分段检测标出，不靠抬高下限回避。
    共振峰上限沿用性别初始值（ceiling 的窄范围选择与敏感性检查由共振峰模块负责）。
    """
    base = MALE if speaker.upper().startswith("M") else FEMALE
    lo, hi = np.percentile(f0_hz, [1, 99])
    floor = max(WIDE_F0_RANGE[0], 5.0 * np.floor(0.75 * lo / 5.0))
    ceiling = min(WIDE_F0_RANGE[1], 5.0 * np.ceil(1.25 * hi / 5.0))
    return SpeakerProfile(f"{base.name}:{speaker}", float(floor), float(ceiling), base.formant_ceiling)


# ---------------- 音频读取 ----------------

def read_mono(path: str | Path, channel: int = ANALYSIS_CHANNEL) -> tuple[np.ndarray, int]:
    """读取 16-bit PCM WAV 的单个声道，返回 float64 样本（[-1, 1)）与采样率；不重采样、不归一化。"""
    with wave.open(str(path), "rb") as w:
        nch, width, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width != 2:
        raise ValueError(f"仅支持 16-bit PCM WAV：{path}")
    data = np.frombuffer(raw, dtype="<i2").reshape(-1, nch)
    return data[:, min(channel, nch - 1)].astype(np.float64) / 32768.0, sr


def to_sound(x: np.ndarray, sr: int):
    import parselmouth

    return parselmouth.Sound(np.asarray(x, dtype=np.float64), sampling_frequency=float(sr))


# ---------------- 公共分析 ----------------

def pitch_filtered_ac(snd, profile: SpeakerProfile, time_step: float = 0.005,
                      floor: float | None = None, ceiling: float | None = None):
    """Praat "To Pitch (filtered ac)"；除 floor/ceiling 外的参数与 f0_pipeline 主趟一致。"""
    from parselmouth.praat import call

    return call(snd, "To Pitch (filtered ac)", time_step,
                floor or profile.f0_floor, ceiling or profile.f0_ceiling,
                15, False, 0.03, 0.09, 0.50, 0.055, 0.35, 0.14)


def pitch_arrays(pitch) -> tuple[np.ndarray, np.ndarray]:
    """Pitch 对象 → (帧时间, F0 Hz)；无声帧为 NaN，不当作 0 Hz。"""
    t = np.asarray(pitch.xs(), dtype=float)
    f0 = np.asarray(pitch.selected_array["frequency"], dtype=float)
    f0[f0 <= 0] = np.nan
    return t, f0


MIN_VOICED_EXTENSION = 0.010    # 有声段越过对齐终点不足 10 ms 时不视为延伸
F0_CONTINUITY_ST = 7.0          # 延伸时相邻有效帧 F0 相差达到该半音数即视为发声不连续
LOW_LEVEL_DROP_DB = 30.0        # 比所在音节最大电平低 30 dB 以上的帧视为低能量帧
LEVEL_WINDOW_SEC = 0.025


def short_time_level_db(x: np.ndarray, sr: int, times: np.ndarray,
                        window: float = LEVEL_WINDOW_SEC) -> np.ndarray:
    """各时刻的短时 RMS 电平（dBFS，窗在录音边界处截短、不补零）。

    低能量帧统一用它判定，而不用 Praat To Intensity：后者的有效窗长约 3.2 / 最低基频，
    会把音节尾部的快速衰减抹平，使弱尾段达不到低能量判据。
    """
    half = int(round(window * sr / 2))
    centers = np.round(np.asarray(times, dtype=float) * sr).astype(int)
    a = np.clip(centers - half, 0, len(x))
    b = np.clip(centers + half, 0, len(x))
    cumulative = np.concatenate(([0.0], np.cumsum(np.asarray(x, dtype=float) ** 2)))
    energy = (cumulative[b] - cumulative[a]) / np.maximum(b - a, 1)
    return 10.0 * np.log10(np.maximum(energy, 1e-20))


def low_level_mask(level_db: np.ndarray, times: np.ndarray, ref_t0: float, ref_t1: float,
                   drop_db: float = LOW_LEVEL_DROP_DB) -> np.ndarray:
    """True 表示低能量帧：电平比 [ref_t0, ref_t1]（通常取整个音节）内的最大电平低 drop_db 以上。"""
    ref = (times >= ref_t0) & (times <= ref_t1)
    peak = float(np.max(level_db[ref] if ref.any() else level_db))
    return level_db < peak - drop_db


@dataclass
class VowelInterval:
    """韵母的声学分析区间（各模块共用，保证同一录音的元音区间口径一致）。

    t0：韵母内首个「有 F0 且非低能量」的帧。对齐可能把送气段划进韵母（样本中 chi1 的讯飞声母
        只有 50–70 ms），送气噪声不应参与元音分析；首帧距对齐起点不足 10 ms 时沿用对齐起点。
    t1：有效终点。对齐终点常早于发声结束（样本中最多约 110 ms）：从韵母终点前最后一个
        有效帧起，沿连续有效帧（允许 1 帧缺口，且相邻有效帧 F0 相差小于 7 st）向后延伸，
        上限为下一音节起点或录音结束；延伸不足 10 ms 时沿用对齐终点。
    区间内部没有 F0 的帧（嘎裂、漏检）仍属于区间，由各模块标为缺失，不做插值。
    """
    t0: float
    t1: float
    start_source: str   # "first_voiced" | "alignment"
    end_source: str     # "voicing_extended" | "alignment"

    @property
    def duration(self) -> float:
        return self.t1 - self.t0


def vowel_interval(aln: Alignment, syll_index: int, x: np.ndarray, sr: int,
                   profile: SpeakerProfile) -> VowelInterval:
    """计算第 syll_index 个音节韵母的声学分析区间（规则见 VowelInterval）。"""
    syll = aln.syllables[syll_index]
    final = syll.final
    if final is None:
        return VowelInterval(syll.t0, syll.t1, "alignment", "alignment")
    times, f0 = pitch_arrays(pitch_filtered_ac(to_sound(x, sr), profile))
    limit = aln.syllables[syll_index + 1].t0 if syll_index + 1 < len(aln.syllables) else aln.duration
    level = short_time_level_db(x, sr, times)
    good = np.isfinite(f0) & ~low_level_mask(level, times, syll.t0, limit)
    inside = np.flatnonzero(good & (times >= final.t0) & (times <= final.t1))
    if inside.size == 0:
        return VowelInterval(final.t0, final.t1, "alignment", "alignment")

    first = float(times[inside[0]])
    t0, start_source = (first, "first_voiced") if first - final.t0 >= MIN_VOICED_EXTENSION \
        else (final.t0, "alignment")
    end, gap = float(times[inside[-1]]), 0
    last_f0 = float(f0[inside[-1]])
    for j in range(int(inside[-1]) + 1, len(times)):
        if times[j] > limit:
            break
        if good[j]:
            if abs(12.0 * np.log2(f0[j] / last_f0)) >= F0_CONTINUITY_ST:
                break   # F0 不连续：不是同一段发声的延续（多为嘎裂段的倍频/半频误检）
            end, gap, last_f0 = float(times[j]), 0, float(f0[j])
        else:
            gap += 1
            if gap > 1:
                break
    t1, end_source = (end, "voicing_extended") if end - final.t1 >= MIN_VOICED_EXTENSION \
        else (final.t1, "alignment")
    return VowelInterval(t0, t1, start_source, end_source)



def segment_at(x: np.ndarray, sr: int, center: float, win_sec: float) -> tuple[np.ndarray, bool]:
    """以 center（秒）为中心取 win_sec 长度的片段；越过录音边界时截短而不补零，并返回窗是否完整。"""
    half = int(round(win_sec * sr / 2))
    c = int(round(center * sr))
    a, b = c - half, c + half
    return x[max(a, 0):min(b, len(x))], (a >= 0 and b <= len(x))


def power_spectrum(seg: np.ndarray, sr: int, n_fft: int | None = None,
                   window: str = "hann") -> tuple[np.ndarray, np.ndarray]:
    """去直流 + 加窗后的单边功率谱 (频率 Hz, 功率)；n_fft 默认取不小于片段长度的 2 的整数次幂。"""
    from scipy.signal import get_window

    x = np.asarray(seg, dtype=float)
    x = x - x.mean()
    x = x * get_window(window, len(x), fftbins=False)
    n = n_fft or int(2 ** np.ceil(np.log2(max(len(x), 2))))
    return np.fft.rfftfreq(n, 1.0 / sr), np.abs(np.fft.rfft(x, n=n)) ** 2


def db(power: np.ndarray, ref: float = 1.0, floor: float = 1e-20) -> np.ndarray:
    """功率 → dB（10·log10，固定参考值，不按单个文件最大值归一化）。"""
    return 10.0 * np.log10(np.maximum(np.asarray(power, dtype=float), floor) / ref)


def resample_for_lpc(x: np.ndarray, sr: int, formant_ceiling: float) -> tuple[np.ndarray, int]:
    """重采样到 2 × 共振峰上限，使 LPC 只拟合 0–ceiling 频段（与 Praat Burg 的做法一致）。"""
    from scipy.signal import resample_poly

    target = int(round(2 * formant_ceiling))
    ratio = Fraction(target, sr).limit_denominator(1000)
    return resample_poly(x, ratio.numerator, ratio.denominator), target


def lpc_envelope(seg: np.ndarray, sr: int, order: int, n_points: int = 1024,
                 pre_emphasis_hz: float = 50.0) -> tuple[np.ndarray, np.ndarray]:
    """自相关法 LPC 谱包络 (频率 Hz, dB)。全极点模型，不能表达鼻音等的谱零点。

    LPC 在预加重后的信号上估计（使高频共振峰得到拟合），返回前扣除预加重滤波器的幅度响应，
    使包络与未预加重的原始频谱处在同一谱倾斜上，可直接叠加比较。
    """
    from scipy.linalg import solve_toeplitz
    from scipy.signal import freqz

    x = np.asarray(seg, dtype=float)
    alpha = np.exp(-2 * np.pi * pre_emphasis_hz / sr) if pre_emphasis_hz else 0.0
    if alpha:
        x = np.append(x[0], x[1:] - alpha * x[:-1])
    x = x * np.hanning(len(x))
    r = np.correlate(x, x, mode="full")[len(x) - 1:len(x) + order]
    if r[0] <= 0:
        raise ValueError("片段能量为零，无法计算 LPC")
    a = solve_toeplitz(r[:order], -r[1:order + 1])
    err = max(r[0] + float(np.dot(a, r[1:order + 1])), 1e-20)
    w, h = freqz([np.sqrt(err)], np.concatenate(([1.0], a)), worN=n_points, fs=sr)
    env_db = 20 * np.log10(np.abs(h) + 1e-12)
    if alpha:
        pre_db = 20 * np.log10(np.abs(1 - alpha * np.exp(-2j * np.pi * w / sr)) + 1e-12)
        env_db = env_db - pre_db
    return w, env_db


def lpc_order(formant_ceiling: float) -> int:
    """LPC 阶数：每 1 kHz 一对极点 + 2（重采样到 2 × ceiling 之后使用）。"""
    return int(2 * formant_ceiling / 1000) + 2


# ---------------- 语谱图 ----------------

# 方案 §2.3 的宽带/窄带参数（Gaussian 窗为 Praat 默认）；Praat 可能调整实际步长，以对象的 dx/dy 为准
BROADBAND = {"window_length": 0.005, "time_step": 0.002, "frequency_step": 20.0}
NARROWBAND = {"window_length": 0.030, "time_step": 0.005, "frequency_step": 10.0}
PRAAT_POWER_REF = 4e-10   # Praat 语谱图绘图的 dB 参考：(2·10⁻⁵ Pa)²/Hz


def spectrogram(snd, kind: str, max_freq: float):
    """kind = "broadband" | "narrowband"；max_freq 会被限制在奈奎斯特频率以内。"""
    params = BROADBAND if kind == "broadband" else NARROWBAND
    return snd.to_spectrogram(maximum_frequency=min(max_freq, snd.sampling_frequency / 2), **params)


def spectrogram_arrays(sg) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Praat Spectrogram → (帧时间 nx, 频率 ny, dB 值 ny×nx)；dB 参考与 Praat 绘图一致。"""
    return np.asarray(sg.xs()), np.asarray(sg.ys()), db(np.asarray(sg.values), ref=PRAAT_POWER_REF)


def spectrogram_actual(sg) -> dict:
    """Praat 实际采用的网格参数（方案 §2.3 要求检查 dx/dy，而非界面输入值）。"""
    return {"dx": float(sg.dx), "dy": float(sg.dy), "firstFrameTime": float(sg.x1),
            "nx": int(sg.nx), "ny": int(sg.ny)}


def plot_spectrogram(ax, times: np.ndarray, freqs: np.ndarray, values_db: np.ndarray,
                     vmax: float | None, dynamic_range: float = 50.0, fmax: float | None = None,
                     cmap: str = "Greys"):
    """按固定标尺绘制语谱图：vmax 由调用方给定（跨样本统一），低于 vmax − dynamic_range 显示为底色。"""
    top = float(np.nanmax(values_db)) if vmax is None else vmax
    mesh = ax.pcolormesh(times, freqs, values_db, shading="nearest", cmap=cmap,
                         vmin=top - dynamic_range, vmax=top, rasterized=True)
    ax.set_ylim(0, fmax or float(freqs[-1]))
    ax.set_ylabel("频率 (Hz)")
    return mesh


# ---------------- 绘图约定 ----------------

@dataclass
class DbScales:
    """跨样本统一的 dB 显示上限（下限 = 上限 − 动态范围）。None 表示由单图自行确定，仅供调试。"""
    broadband_max_db: float | None = None
    broadband_preemph_max_db: float | None = None
    narrowband_max_db: float | None = None
    mel_max_db: float | None = None


_MPL_READY = False
_FONT_CANDIDATES = ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "WenQuanYi Micro Hei")


def setup_matplotlib():
    """Agg 后端 + 字体回退链：中文字体在前，DejaVu Sans 在后补齐 IPA 字形。

    回退链必须直接写入 font.family（逐字形回退只作用于该列表），并滤掉未安装的字体以免刷屏告警。
    """
    global _MPL_READY
    import matplotlib

    if not _MPL_READY:
        from matplotlib import font_manager

        matplotlib.use("Agg")
        installed = {f.name for f in font_manager.fontManager.ttflist}
        matplotlib.rcParams["font.family"] = [n for n in _FONT_CANDIDATES if n in installed] + ["DejaVu Sans"]
        matplotlib.rcParams["axes.unicode_minus"] = False
        _MPL_READY = True
    import matplotlib.pyplot as plt

    return plt


def save_fig(fig, out_dir: str | Path, name: str) -> Path:
    import matplotlib.pyplot as plt

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / (name if name.endswith(".png") else f"{name}.png")
    fig.savefig(path, dpi=OUT_DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def set_time_axis(ax, aln: Alignment) -> None:
    ax.set_xlim(0.0, aln.duration)
    ax.set_xlabel("时间 (s)")


def draw_boundaries(ax, aln: Alignment, labels: bool = True, color: str = "#333333") -> None:
    """叠加讯飞音素边界（虚线）；labels=True 时在轴内顶部标注音素（讯飞符号 + IPA）。

    标签放在坐标轴内并带半透明底色，避免与面板标题重叠；放大视图中超出横轴范围的标签被裁掉。
    """
    from matplotlib.transforms import blended_transform_factory

    edges = sorted({round(t, 4) for p in aln.phones for t in (p.t0, p.t1)})
    for t in edges:
        ax.axvline(t, color=color, ls="--", lw=0.8, alpha=0.8)
    if labels:
        trans = blended_transform_factory(ax.transData, ax.transAxes)
        for p in aln.phones:
            ax.text((p.t0 + p.t1) / 2, 0.97, display_label(p), transform=trans,
                    ha="center", va="top", fontsize=8, color=color, clip_on=True,
                    bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.75})


def mark_edge_regions(ax, duration: float, window_sec: float) -> None:
    """灰色斜线标出分析窗伸出录音边界的区域（该处没有真实上下文，结果仅供参考）。"""
    half = window_sec / 2
    for a, b in ((0.0, half), (duration - half, duration)):
        ax.axvspan(a, b, facecolor="none", edgecolor="#999999", hatch="//", lw=0, alpha=0.6)


# ---------------- 输出 ----------------

def new_result() -> dict:
    """模块返回值：images/tables 为 {名称: 路径}，params 为实际使用的参数，warnings 为文字说明。"""
    return {"images": {}, "tables": {}, "params": {}, "warnings": []}


def write_csv(rows: list[dict], out_dir: str | Path, name: str) -> Path:
    """写 UTF-8（带 BOM，便于 Excel 打开）CSV；列取所有行键的并集，保持首次出现顺序。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / (name if name.endswith(".csv") else f"{name}.csv")
    fields: list[str] = []
    for r in rows:
        fields += [k for k in r if k not in fields]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return path
