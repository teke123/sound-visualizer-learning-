"""鼻音（含鼻韵尾）、边音、r 与零声母的专项声学图像（方案 §4.4、§4.5、§4.6、§4.2 浊擦音、§7.2）。

覆盖以下类别（由 common.initial_class / common.nasal_coda 判定）：
- 鼻音声母 m/n：鼻音段即讯飞声母区间；鼻腔共振取段内有声帧 Burg F1 的中位数（N1 测法）；
- 鼻韵尾 n/ng：讯飞未给边界，用韵母内 500–3000 Hz 频带能量的下降点做声学估计；
- 边音 l：与前后元音作为一个连续时间序列分析 F1–F3；
- r：按近音分析 F1–F3 轨迹，并按浊擦音要求（方案 §4.2）给出浊音占比、HNR、F0
  与噪声谱（谱重心、谱倾斜）；
- 零声母（伪声母）：精细波形 + 声门脉冲 + 逐周期长度 + 窄带谱，检验喉塞/紧喉起始。

反共振（谱零点）候选由倒谱平滑包络上的谱谷给出：倒谱截断长度随基频自适应
（0.6 × 基音周期，限制 1–4 ms）。共振峰轨迹统一做 5 帧中值滤波的连续性检查，
并屏蔽远低于音节强度峰值的帧。
闪音、颤音、喷音、内爆音、搭嘴音在普通话中不出现，本模块不实现。
共振峰统一用 Praat "To Formant (burg)"。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from parselmouth.praat import call

from . import common
from .common import Alignment, DbScales

# 共振峰分析（方案要求：time step 0.005、max formants 5、ceiling 取 profile、window 0.025、pre-emphasis 50）
FORMANT_TIME_STEP = 0.005
FORMANT_MAX_NUM = 5
FORMANT_WINDOW = 0.025
FORMANT_PRE_EMPHASIS = 50.0

# 鼻音/边音中点频谱与谱谷候选
MID_WINDOW = 0.040            # 中点频谱窗长（秒）
CEP_LIFTER_F0_RATIO = 0.6     # 倒谱截断长度 = 该系数 × 基音周期（秒）
CEP_LIFTER_MIN_S = 0.001      # 截断长度下限（秒）
CEP_LIFTER_MAX_S = 0.004      # 截断长度上限（秒）
VALLEY_MIN_DEPTH_DB = 6.0     # 谱谷候选的最小深度（相对两侧峰，dB）
VALLEY_SEARCH_MAX_HZ = 5000.0

# 鼻韵尾区间估计
CODA_BAND_HZ = (500.0, 3000.0)
CODA_BAND_WINDOW = 0.020
CODA_BAND_HOP = 0.005
CODA_DROP_DB = 8.0
CODA_FALLBACK_TAIL = 0.30     # 找不到下降点时取韵母末尾的比例

# 近音/边音轨迹与 r 的噪声谱
APPROX_TRAJ_FINAL_FRAC = 0.5  # 轨迹画到韵母时长的该比例处
NOISE_WINDOW = 0.020
NOISE_HOP = 0.005
NOISE_COG_BAND_HZ = (500.0, 8000.0)
NOISE_TILT_BANDS_HZ = ((0.0, 1000.0), (1000.0, 4000.0))

# 零声母起始
ZERO_WINDOW = 0.080           # 精细分析的时间窗（秒）
ZERO_N_PERIODS = 5            # 计算周期抖动使用的周期数
ZERO_RMS_WINDOW = 0.010       # 强度差用的短时 RMS 窗长（秒；Praat To Intensity 的窗长
                              # 为 6.4/最低基频，会远长于伪声母段，故直接算短时 RMS）

HNR_TIME_STEP = 0.01
HNR_VOICELESS_DB = -200.0

# 共振峰轨迹清洗（毛刺抑制）：5 帧中值滤波 + 20% 离群判定 + 低能量帧屏蔽
# （common.short_time_level_db / low_level_mask）；换轨征兆（F2/F3 贴合）与
# 阶跃式漂移（跳变加平台）另行补标
FORMANT_MEDIAN_FILTER_FRAMES = 5
FORMANT_OUTLIER_DEVIATION = 0.2
FORMANT_MERGE_GAP_HZ = 100.0    # |F3 − F2| 小于该值视为换轨征兆
FORMANT_STABLE_CONTEXT_FRAMES = 10
FORMANT_STEP_DEV = 0.15         # 阶跃判定：跳变、平台起伏、电平偏差的统一相对阈值
FORMANT_STEP_MIN_FRAMES = 3     # 阶跃式漂移平台的最小帧数
FORMANT_STEP_MAX_FRAMES = 15    # 阶跃式漂移平台的最大帧数（更长的是真实过渡/正常段）
FORMANT_STEP_EDGE_SKIP = 3      # 平台边沿向两侧跳过的帧数（过渡斜坡）
FORMANT_STEP_LOCAL_FRAMES = 5   # 平台两侧局部稳态电平的取样帧数

F1_F2_F3_COLORS = ("#1f77b4", "#ff7f0e", "#2ca02c")


@dataclass
class _NasalSeg:
    """一个被分析的鼻音段（声母或估计出的韵尾）。"""

    t0: float
    t1: float
    kind: str                 # "nasal_initial" | "nasal_coda"
    label: str                # m / n / ng


@dataclass
class _MidSpectrum:
    """区间中点 40 ms 窗的高分辨率频谱分析结果。"""

    freq: np.ndarray          # 频率 Hz
    db: np.ndarray            # 原始功率谱 dB（固定参考，与语谱图一致）
    f0_median_hz: float       # 分析窗内有声帧 F0 中位数（无声帧时为 NaN）
    lifter_s: float | None    # 实际采用的倒谱截断长度（秒）；无有声帧时为 None
    env: np.ndarray | None    # 倒谱平滑包络 dB；无有声帧时为 None
    n_cep_coeffs: int | None  # 倒谱平滑保留的系数个数；无有声帧时为 None
    lpc_env_db: np.ndarray | None   # 同一帧的 Burg(LPC) 包络（幅度对齐到原始谱，dB）
    valleys: list[tuple[float, float]]  # 谱谷候选 (频率 Hz, 深度 dB)


@dataclass
class _Ctx:
    """一次 generate 内共享的对象与结果容器。"""

    x: np.ndarray
    sr: int
    aln: Alignment
    out_dir: Path
    scales: DbScales | None
    result: dict
    snd: object | None = None
    profile: common.SpeakerProfile | None = None
    stem: str = ""
    cache: dict = field(default_factory=dict)

    def narrowband_max_db(self) -> float | None:
        return self.scales.narrowband_max_db if self.scales else None

    def broadband_max_db(self) -> float | None:
        return self.scales.broadband_max_db if self.scales else None

    def formant(self):
        """整条录音的 Burg 共振峰对象（各图共用一份）。"""
        if "formant" not in self.cache:
            fm = call(self.snd, "To Formant (burg)", FORMANT_TIME_STEP, FORMANT_MAX_NUM,
                      self.profile.formant_ceiling, FORMANT_WINDOW, FORMANT_PRE_EMPHASIS)
            self.cache["formant"] = fm
            self.result["params"].setdefault("formant_burg", {}).update({
                "time_step": FORMANT_TIME_STEP, "max_formants": FORMANT_MAX_NUM,
                "ceiling_hz": self.profile.formant_ceiling, "window_length_s": FORMANT_WINDOW,
                "pre_emphasis_hz": FORMANT_PRE_EMPHASIS, "dx_actual": float(fm.dx),
            })
        return self.cache["formant"]

    def formant_tracks(self) -> dict:
        """整条录音的 F1–F3 轨迹清洗结果（B1 原始值附在 F1 条目上），缓存一份。

        清洗规则：① 5 帧中值滤波，偏离中值超过 20% 的帧标为离群点；② 帧强度低于所属
        音节最大强度 30 dB 以上时屏蔽（低能量帧的 Burg 结果不可靠）。离群点与低能量帧
        不画线、不参与派生数值；CSV 保留原始值并附 outlier 标志。
        """
        if "tracks" not in self.cache:
            tracks: dict[int, dict] = {}
            for number in (1, 2, 3):
                ts, raw = _formant_track_raw(self, number)
                # 低能量屏蔽：25 ms 短时 RMS 电平低于所属音节最大电平 30 dB 以上
                level = common.short_time_level_db(self.x, self.sr, ts)
                low = ~np.isfinite(level)
                covered = np.zeros(len(ts), dtype=bool)
                for syllable in self.aln.syllables:
                    inside = (ts >= syllable.t0) & (ts <= syllable.t1)
                    covered |= inside
                    if inside.any():
                        low |= common.low_level_mask(level, ts, syllable.t0, syllable.t1) & inside
                low |= ~covered
                clean = raw.copy()
                clean[low] = np.nan
                half = FORMANT_MEDIAN_FILTER_FRAMES // 2
                outlier = np.zeros(len(ts), dtype=bool)
                for i in range(len(ts)):
                    if np.isnan(clean[i]):
                        continue
                    window = clean[max(0, i - half):i + half + 1]
                    window = window[~np.isnan(window)]
                    if len(window) < 2:
                        continue
                    median = float(np.median(window))
                    if median > 0 and abs(clean[i] - median) > FORMANT_OUTLIER_DEVIATION * median:
                        outlier[i] = True
                clean[outlier] = np.nan
                entry = {"ts": ts, "raw": raw, "clean": clean, "outlier": outlier, "low": low}
                if number == 1:
                    entry["b1_raw"] = np.asarray(
                        [float(call(self.formant(), "Get bandwidth at time", 1, float(t),
                                    "Hertz", "Linear")) for t in ts], dtype=float)
                tracks[number] = entry
            # 换轨征兆：同一时刻 |F3 − F2| 小于 100 Hz 的连续帧段，
            # 段内偏离稳态轨迹（段前后两侧稳态帧合并中位数）的那一条标为离群
            f2_track, f3_track = tracks[2], tracks[3]
            merge = ((~np.isnan(f2_track["clean"])) & (~np.isnan(f3_track["clean"]))
                     & (np.abs(f3_track["clean"] - f2_track["clean"]) < FORMANT_MERGE_GAP_HZ))
            for start, stop in _true_runs(merge):
                ref2 = _stable_combined(f2_track["clean"], start, stop)
                ref3 = _stable_combined(f3_track["clean"], start, stop)
                if np.isnan(ref2) or np.isnan(ref3) or ref2 <= 0 or ref3 <= 0:
                    continue
                mid2 = float(np.nanmedian(f2_track["clean"][start:stop]))
                mid3 = float(np.nanmedian(f3_track["clean"][start:stop]))
                victim = f3_track if abs(mid3 - ref3) / ref3 >= abs(mid2 - ref2) / ref2 else f2_track
                victim["outlier"][start:stop] = True
                victim["clean"][start:stop] = np.nan
            # 阶跃式漂移：原始值上相邻帧跳变 > 15% 界定出平坦平台（3–15 帧、起伏 ≤ 15%），
            # 平台电平相对段前局部稳态电平（跳过 3 帧斜坡后取 5 帧原始值中位数）偏差 > 15%，
            # 且要么其后回到段前电平（矩形凹坑）、要么平台延伸到轨迹末端（收尾阶跃），
            # 才标为离群。逐帧渐进的真实过渡无跳变边沿；被两个异常段夹住的正常段长度
            # 通常远超 15 帧，也不会误标。
            for entry in tracks.values():
                raw_e, clean_e = entry["raw"], entry["clean"]
                edges = [i for i in range(len(raw_e) - 1)
                         if not np.isnan(raw_e[i]) and not np.isnan(raw_e[i + 1])
                         and raw_e[i] > 0
                         and abs(raw_e[i + 1] - raw_e[i]) / raw_e[i] > FORMANT_STEP_DEV]
                if not edges:
                    continue
                bounds = [(edge + 1, nxt) for edge, nxt in zip(edges, edges[1:])]
                bounds.append((edges[-1] + 1, len(raw_e)))
                for start, stop in bounds:
                    plateau = clean_e[start:stop]
                    plateau = plateau[~np.isnan(plateau)]
                    if not FORMANT_STEP_MIN_FRAMES <= len(plateau) <= FORMANT_STEP_MAX_FRAMES:
                        continue
                    level = float(np.median(plateau))
                    if level <= 0 or (float(plateau.max()) - float(plateau.min())) / level > FORMANT_STEP_DEV:
                        continue    # 平台内仍在单调移动，属真实过渡
                    before = _median_defined(
                        raw_e[max(0, start - FORMANT_STEP_EDGE_SKIP - FORMANT_STEP_LOCAL_FRAMES):
                              max(0, start - FORMANT_STEP_EDGE_SKIP)], minimum=3)
                    if np.isnan(before) or before <= 0:
                        continue
                    if abs(level - before) / before <= FORMANT_STEP_DEV:
                        continue
                    after = _median_defined(
                        raw_e[stop + FORMANT_STEP_EDGE_SKIP:
                              stop + FORMANT_STEP_EDGE_SKIP + FORMANT_STEP_LOCAL_FRAMES], minimum=3)
                    returns = (not np.isnan(after)
                               and abs(after - before) / before <= FORMANT_STEP_DEV)
                    reaches_end = not np.any(~np.isnan(raw_e[stop:]))
                    if returns or reaches_end:
                        entry["outlier"][start:stop] = True
                        entry["clean"][start:stop] = np.nan
            self.cache["tracks"] = tracks
            self.result["params"]["formant_track_cleanup"] = {
                "median_filter_frames": FORMANT_MEDIAN_FILTER_FRAMES,
                "outlier_rel_deviation": FORMANT_OUTLIER_DEVIATION,
                "low_energy_mask": f"帧的 {common.LEVEL_WINDOW_SEC * 1000:.0f} ms 短时 RMS 电平低于"
                                   f"所属音节最大电平 {common.LOW_LEVEL_DROP_DB:.0f} dB 以上时"
                                   "不画、不参与派生数值（common.low_level_mask）",
                "merge_gap": f"|F3 − F2| < {FORMANT_MERGE_GAP_HZ:.0f} Hz 的连续帧段视为换轨征兆，"
                             "段内偏离稳态电平（段前后两侧稳态帧合并中位数）的一条标为离群",
                "step_drift": f"原始值相邻帧跳变 > {FORMANT_STEP_DEV * 100:.0f}% 后接平坦平台"
                              f"（{FORMANT_STEP_MIN_FRAMES}–{FORMANT_STEP_MAX_FRAMES} 帧、"
                              f"起伏 ≤ {FORMANT_STEP_DEV * 100:.0f}%），平台电平相对段前局部"
                              f"稳态电平偏差 > {FORMANT_STEP_DEV * 100:.0f}%，且回到段前电平"
                              "或延伸到轨迹末端的标为离群",
                "outlier_flag_note": "CSV 中的 outlier 标志 = 20% 离群、换轨/阶跃补标或低能量屏蔽",
            }
        return self.cache["tracks"]

    def spectrogram(self, kind: str, max_freq: float):
        """语谱图对象（按 (类型, 上限) 缓存），并把 Praat 实际网格写入 params。"""
        key = (kind, max_freq)
        if key not in self.cache:
            sg = common.spectrogram(self.snd, kind, max_freq)
            self.cache[key] = sg
            self.result["params"].setdefault("spectrogram", {})[
                f"{kind}_{int(max_freq)}"] = common.spectrogram_actual(sg)
        return self.cache[key]

    def point_process(self):
        if "pp" not in self.cache:
            pp = call(self.snd, "To PointProcess (periodic, cc)",
                      self.profile.f0_floor, self.profile.f0_ceiling)
            n = int(call(pp, "Get number of points"))
            times = np.asarray([call(pp, "Get time from index", i) for i in range(1, n + 1)],
                               dtype=float)
            self.cache["pp"] = times
            self.result["params"]["pointprocess"] = {
                "command": "To PointProcess (periodic, cc)",
                "f0_floor": self.profile.f0_floor, "f0_ceiling": self.profile.f0_ceiling,
                "n_points": n,
            }
        return self.cache["pp"]

    def pitch(self):
        if "pitch" not in self.cache:
            self.cache["pitch"] = common.pitch_filtered_ac(self.snd, self.profile)
        return self.cache["pitch"]

    def pitch_arrays(self) -> tuple[np.ndarray, np.ndarray]:
        """(帧时间, F0 Hz) 数组；无声帧为 NaN。"""
        if "pitch_arrays" not in self.cache:
            self.cache["pitch_arrays"] = common.pitch_arrays(self.pitch())
        return self.cache["pitch_arrays"]

    def intensity(self):
        """短时 RMS 轨迹（dB，固定参考）：Praat To Intensity 的窗长为 6.4/最低基频，
        对几十毫秒的伪声母段来说过宽，强度差改用直接计算的短时 RMS。"""
        if "intensity" not in self.cache:
            times: list[float] = []
            values: list[float] = []
            t = 0.0
            while t <= self.aln.duration + 1e-9:
                seg, complete = common.segment_at(self.x, self.sr, t, ZERO_RMS_WINDOW)
                if complete and len(seg) >= 2:
                    times.append(t)
                    rms = float(np.sqrt(np.mean(np.square(seg))))
                    values.append(20.0 * np.log10(max(rms, 1e-10)))
                t += CODA_BAND_HOP
            self.cache["intensity"] = (np.asarray(times), np.asarray(values))
            self.result["params"]["zero_intensity"] = {
                "window_s": ZERO_RMS_WINDOW, "hop_s": CODA_BAND_HOP,
                "measure": "伪声母段末端短时 RMS − 音节内短时 RMS 最大值 (dB)",
            }
        return self.cache["intensity"]


def _num(value, digits: int = 1) -> str | float:
    """CSV 用数值：NaN/None 写空串，其余四舍五入。"""
    if value is None:
        return ""
    value = float(value)
    return "" if np.isnan(value) else round(value, digits)


def _json_or_empty(value) -> str:
    """列表/字典转 JSON 字符串（NaN → null）。"""
    return json.dumps(value, ensure_ascii=False)


def _nan_to_none(values) -> list:
    """数值列表 → 保留两位小数、NaN 转为 None（JSON 里写作 null）。"""
    return [None if v is None or np.isnan(float(v)) else round(float(v), 2) for v in values]


# ---------------- 频谱分析 ----------------

def _cepstral_envelope_db(db: np.ndarray, n_keep: int) -> np.ndarray:
    """倒谱平滑包络：对 dB 谱做倒谱（保留前 n_keep 个系数）后还原。

    全极点 LPC 不能表示鼻音的谱零点，这里只用倒谱平滑作为谱谷候选的定位手段。
    第 0 个频点是去直流后的残留（接近 −inf），用相邻频点替代，避免包络在 0 Hz 附近畸变。
    """
    patched = db.copy()
    patched[0] = patched[1]
    two_sided = np.concatenate([patched, patched[-2:0:-1]])
    cep = np.fft.ifft(two_sided).real
    cep[n_keep:] = 0.0
    return np.fft.fft(cep).real[: len(db)]


def _voiced_at(ctx: _Ctx, t: float) -> bool:
    """时刻 t 最近的 F0 帧是否有声（统一用 filtered autocorrelation 的 Pitch 对象）。"""
    pt, pf = ctx.pitch_arrays()
    if not len(pt):
        return False
    return not bool(np.isnan(pf[int(np.argmin(np.abs(pt - t)))]))


def _f0_median_in(ctx: _Ctx, t0: float, t1: float) -> float:
    """[t0, t1] 内有声帧 F0 的中位数（无声帧时为 NaN）。"""
    pt, pf = ctx.pitch_arrays()
    voiced = (pt >= t0) & (pt <= t1) & ~np.isnan(pf)
    return float(np.median(pf[voiced])) if voiced.any() else float("nan")


def _nasal_formant_medians(ctx: _Ctx, t0: float, t1: float) -> tuple[float, float, int]:
    """鼻音段内有声帧 Burg F1/B1 的中位数（N1 测法），返回 (F1, B1, 有声帧数)。

    鼻音声母取讯飞区间，鼻韵尾取声学估计区间；离群帧与低能量帧已排除。
    全极点模型能估计极点（N1），但不能表示鼻音谱零点，零点另由倒谱包络的谱谷候选观察。
    """
    tr1 = ctx.formant_tracks()[1]
    inside = (tr1["ts"] >= t0) & (tr1["ts"] <= t1)
    usable = inside & ~np.isnan(tr1["clean"]) & ~np.isnan(tr1["b1_raw"])
    for i in np.where(inside)[0]:
        if not _voiced_at(ctx, float(tr1["ts"][i])):
            usable[i] = False
    f1s = tr1["clean"][usable]
    b1s = tr1["b1_raw"][usable]
    if not len(f1s):
        return float("nan"), float("nan"), 0
    return float(np.median(f1s)), float(np.median(b1s)), int(len(f1s))


def _find_valleys(freq: np.ndarray, env: np.ndarray, fmax: float,
                  min_depth: float) -> list[tuple[float, float]]:
    """包络上的明显谱谷：相对两侧最近局部峰深度 ≥ min_depth，返回 (频率, 深度)。"""
    band = np.where(freq <= fmax)[0]
    out: list[tuple[float, float]] = []
    for i in band:
        if i == 0 or i >= len(env) - 1:
            continue
        if not (env[i] < env[i - 1] and env[i] <= env[i + 1]):
            continue
        left = i
        while left > 0 and env[left - 1] > env[left]:
            left -= 1
        right = i
        while right < len(env) - 1 and env[right + 1] > env[right]:
            right += 1
        depth = min(env[left], env[right]) - env[i]
        if depth >= min_depth:
            out.append((float(freq[i]), float(depth)))
    return out


def _mid_spectrum(ctx: _Ctx, t0: float, t1: float) -> _MidSpectrum:
    """区间中点 40 ms 窗的高分辨率频谱 + 自适应倒谱包络 + Burg(LPC) 包络 + 谱谷候选。

    倒谱截断长度 = 0.6 × 基音周期（基音周期取分析窗内有声帧 F0 中位数的倒数），
    限制在 1–4 ms；分析窗内没有有声帧时不做倒谱包络与谱谷候选。
    Burg(LPC) 包络与 N1 的测量方法同源（全极点模型，能估极点、不能表示零点），
    幅度按原始谱与包络差的中位数对齐，仅供叠加对照。
    """
    mid = 0.5 * (t0 + t1)
    seg, complete = common.segment_at(ctx.x, ctx.sr, mid, MID_WINDOW)
    if not complete or len(seg) < 2:
        raise ValueError(f"中点 {mid:.3f} s 处 {MID_WINDOW * 1000:.0f} ms 分析窗越过录音边界")
    freq, power = common.power_spectrum(seg, ctx.sr)
    db = common.db(power, ref=common.PRAAT_POWER_REF)
    # Burg(LPC) 包络（重采样到 2 × 共振峰上限，只拟合 0–ceiling 频段）
    lpc_env = None
    try:
        ceiling = ctx.profile.formant_ceiling
        resampled, sr_lpc = common.resample_for_lpc(seg, ctx.sr, ceiling)
        w, h_db = common.lpc_envelope(resampled, sr_lpc, common.lpc_order(ceiling),
                                      n_points=1024)
        band = w <= VALLEY_SEARCH_MAX_HZ
        interp = np.interp(freq, w[band], h_db[band])
        offset = float(np.median(db - interp))
        lpc_env = interp + offset
    except ValueError:
        lpc_env = None
    f0_median = _f0_median_in(ctx, mid - MID_WINDOW / 2.0, mid + MID_WINDOW / 2.0)
    if np.isnan(f0_median):
        return _MidSpectrum(freq=freq, db=db, f0_median_hz=float("nan"), lifter_s=None,
                            env=None, n_cep_coeffs=None, lpc_env_db=lpc_env, valleys=[])
    lifter = float(np.clip(CEP_LIFTER_F0_RATIO / f0_median, CEP_LIFTER_MIN_S, CEP_LIFTER_MAX_S))
    n_keep = int(round(lifter * ctx.sr))
    env = _cepstral_envelope_db(db, n_keep)
    return _MidSpectrum(freq=freq, db=db, f0_median_hz=f0_median, lifter_s=lifter, env=env,
                        n_cep_coeffs=n_keep, lpc_env_db=lpc_env,
                        valleys=_find_valleys(freq, env, VALLEY_SEARCH_MAX_HZ, VALLEY_MIN_DEPTH_DB))


def _average_power_spectrum(ctx: _Ctx, t0: float, t1: float) -> tuple[np.ndarray, np.ndarray]:
    """区间内（窗完全落在区间内的帧）20 ms 窗、5 ms 步长平均功率谱。"""
    freqs: np.ndarray | None = None
    acc: np.ndarray | None = None
    n_frames = 0
    t = t0 + NOISE_WINDOW / 2.0
    while t <= t1 - NOISE_WINDOW / 2.0 + 1e-9:
        seg, complete = common.segment_at(ctx.x, ctx.sr, t, NOISE_WINDOW)
        if complete and len(seg) >= 2:
            f, p = common.power_spectrum(seg, ctx.sr)
            freqs = f if freqs is None else freqs
            acc = p.copy() if acc is None else acc + p
            n_frames += 1
        t += NOISE_HOP
    if n_frames == 0:
        raise ValueError(f"区间 {t0:.3f}–{t1:.3f} s 内放不下一个完整的 {NOISE_WINDOW * 1000:.0f} ms 分析窗")
    return freqs, acc / n_frames


# ---------------- 鼻韵尾区间估计 ----------------

def _estimate_coda_interval(ctx: _Ctx, t_start: float, t_end: float) -> tuple[float, float, str, str]:
    """估计鼻韵尾区间：在 [韵母声学区间起点, 有效终点] 内计算 500–3000 Hz 频带能量，
    找到从区间最大值下降超过 8 dB 且不再回升的起点（只在后半段搜索）。

    返回 (t0, t1, 方式, 说明)；区间终点取有效终点。找不到满足条件的点时取区间末 30%。
    两者均为声学估计，非对齐边界。
    """
    times: list[float] = []
    values: list[float] = []
    t = t_start
    while t <= t_end + 1e-9:
        seg, complete = common.segment_at(ctx.x, ctx.sr, t, CODA_BAND_WINDOW)
        if complete and len(seg) >= 2:
            freq, power = common.power_spectrum(seg, ctx.sr)
            band = (freq >= CODA_BAND_HZ[0]) & (freq <= CODA_BAND_HZ[1])
            times.append(t)
            values.append(float(power[band].sum()))
        t += CODA_BAND_HOP
    span = t_end - t_start
    if not times:
        return (t_end - CODA_FALLBACK_TAIL * span, t_end, "fallback_tail",
                "韵母内没有完整分析帧，鼻韵尾区间取区间末 30%")
    ts = np.asarray(times)
    db = common.db(np.asarray(values))
    threshold = float(db.max()) - CODA_DROP_DB
    above = np.where(db >= threshold)[0]
    last_above = int(above[-1])
    half_index = int(np.searchsorted(ts, t_start + 0.5 * span))
    half_index = min(half_index, len(ts) - 1)
    if last_above >= len(ts) - 1:
        return (t_end - CODA_FALLBACK_TAIL * span, t_end, "fallback_tail",
                f"区间末端能量未低于最大值 −{CODA_DROP_DB:.0f} dB，鼻韵尾区间取区间末 30%")
    start = max(float(ts[last_above + 1]), float(ts[half_index]))
    return start, t_end, "band_energy_drop", (
        f"500–3000 Hz 频带能量于 {start:.3f} s 起低于韵母最大值 −{CODA_DROP_DB:.0f} dB "
        f"（最大值 {ts[int(np.argmax(db))]:.3f} s）")


# ---------------- 共振峰取样 ----------------

def _formant_track_raw(ctx: _Ctx, number: int) -> tuple[np.ndarray, np.ndarray]:
    """整条录音第 number 个共振峰的原始轨迹（帧时刻, Hz；未定义帧为 NaN）。"""
    fm = ctx.formant()
    ts = np.asarray(fm.xs(), dtype=float)
    values = np.asarray([float(call(fm, "Get value at time", number, float(t), "Hertz", "Linear"))
                         for t in ts], dtype=float)
    return ts, values


def _track_frame_at(ctx: _Ctx, number: int, t: float) -> int | None:
    """距 t 最近的轨迹帧下标；超出半帧步长（2.6 ms）时返回 None。"""
    tr = ctx.formant_tracks()[number]
    if not len(tr["ts"]):
        return None
    i = int(np.argmin(np.abs(tr["ts"] - t)))
    return i if abs(float(tr["ts"][i]) - t) <= 0.0026 else None


def _formant_value_and_flag(ctx: _Ctx, number: int, t: float,
                            any_distance: bool = False) -> tuple[float, bool | None]:
    """时刻 t 处第 number 个共振峰的原始值与 outlier 标志（离群或低能量屏蔽）。

    any_distance=True 时取最近帧而不限制距离（用于中点取值）。
    """
    tr = ctx.formant_tracks()[number]
    if not any_distance:
        i = _track_frame_at(ctx, number, t)
    else:
        i = int(np.argmin(np.abs(tr["ts"] - t))) if len(tr["ts"]) else None
    if i is None:
        return float("nan"), None
    return float(tr["raw"][i]), bool(tr["outlier"][i] or tr["low"][i])


def _formant_transition(ctx: _Ctx, time_points: list[float]) -> dict:
    """若干时刻的原始 F1/F2 与 outlier 标志，供 CSV 的 JSON 字段使用。"""
    out: dict = {"times_s": [round(t, 3) for t in time_points]}
    for number, key in ((1, "F1"), (2, "F2")):
        values: list[float] = []
        flags: list[bool | None] = []
        for t in time_points:
            value, flag = _formant_value_and_flag(ctx, number, t)
            values.append(value)
            flags.append(flag)
        out[f"{key}_hz"] = _nan_to_none(values)
        out[f"{key}_outlier"] = flags
    return out


# ---------------- r 的浊音/噪声指标 ----------------

def _rhotic_metrics(ctx: _Ctx, initial) -> dict:
    """r 区间的浊音占比、平均 HNR、F0 均值与噪声谱指标（方案 §4.2 浊擦音）。"""
    t0, t1 = initial.t0, initial.t1
    # F0（统一用 filtered autocorrelation）
    pt, pf = common.pitch_arrays(ctx.pitch())
    in_interval = (pt >= t0) & (pt <= t1)
    f0_frames = pf[in_interval]
    voiced = f0_frames[~np.isnan(f0_frames)]
    voiced_fraction = float(len(voiced)) / len(f0_frames) if len(f0_frames) else float("nan")
    f0_mean = float(np.mean(voiced)) if len(voiced) else float("nan")
    # HNR（−200 dB 视为无声帧并排除）
    harm = call(ctx.snd, "To Harmonicity (cc)", HNR_TIME_STEP, ctx.profile.f0_floor, 0.1, 4.5)
    ht = np.asarray(harm.xs(), dtype=float)
    hv = np.asarray(harm.values, dtype=float).ravel()
    h_in = hv[(ht >= t0) & (ht <= t1)]
    h_valid = h_in[h_in > HNR_VOICELESS_DB]
    hnr_mean = float(np.mean(h_valid)) if len(h_valid) else float("nan")
    if np.isnan(hnr_mean):
        ctx.result["warnings"].append(
            f"{ctx.stem}：r 区间内没有有效 HNR 帧（全部为 {HNR_VOICELESS_DB:.0f} dB 无声），"
            "平均 HNR 记为空值")
    ctx.result["params"]["harmonicity_cc"] = {
        "time_step": HNR_TIME_STEP, "minimum_pitch": ctx.profile.f0_floor,
        "silence_threshold": 0.1, "periods_per_window": 4.5,
        "voiceless_excluded_db": HNR_VOICELESS_DB, "frames_used": int(len(h_valid)),
    }
    # 噪声谱（区间平均功率谱，未分离谐波与噪声成分）
    freq, power = _average_power_spectrum(ctx, t0, t1)
    cog_band = (freq >= NOISE_COG_BAND_HZ[0]) & (freq <= NOISE_COG_BAND_HZ[1])
    cog = float(np.sum(freq[cog_band] * power[cog_band]) / np.sum(power[cog_band]))
    db = common.db(power, ref=common.PRAAT_POWER_REF)
    (lo0, lo1), (hi0, hi1) = NOISE_TILT_BANDS_HZ
    tilt = float(db[(freq >= lo0) & (freq < lo1)].mean() - db[(freq >= hi0) & (freq <= hi1)].mean())
    ctx.result["params"]["r_noise_spectrum"] = {
        "frame_window_s": NOISE_WINDOW, "frame_hop_s": NOISE_HOP,
        "note": "r 区间平均功率谱，未分离谐波与噪声成分",
        "cog_band_hz": list(NOISE_COG_BAND_HZ),
        "tilt_bands_hz": [list(b) for b in NOISE_TILT_BANDS_HZ],
    }
    return {"voiced_fraction": voiced_fraction, "hnr_db": hnr_mean, "f0_mean_hz": f0_mean,
            "cog_hz": cog, "tilt_db": tilt, "freq": freq, "power_db": db}


# ---------------- 零声母测量 ----------------

def _zero_metrics(ctx: _Ctx, initial, syllable) -> dict:
    """第一个声门脉冲时间、前 5 个周期的周期抖动、伪声母末端相对音节最大强度的 dB 差。

    周期抖动 = 前 5 个周期相邻周期差绝对值的均值 / 周期均值（局部抖动定义）。
    """
    pulses = ctx.point_process()
    first_pulse = float(pulses[0]) if len(pulses) else float("nan")
    if len(pulses) >= ZERO_N_PERIODS + 1:
        periods = np.diff(pulses[: ZERO_N_PERIODS + 1])
        jitter = float(np.mean(np.abs(np.diff(periods))) / np.mean(periods))
    else:
        jitter = float("nan")
        ctx.result["warnings"].append(
            f"{ctx.stem}：声门脉冲不足 {ZERO_N_PERIODS + 1} 个，周期抖动记为空值")
    it, iv = ctx.intensity()
    in_syll = (it >= syllable.t0) & (it <= syllable.t1)
    peak_db = float(iv[in_syll].max()) if in_syll.any() else float("nan")
    end_db = float(np.interp(initial.t1, it, iv)) if len(it) else float("nan")
    return {"first_pulse_s": first_pulse, "jitter": jitter,
            "intensity_rel_db": end_db - peak_db
            if not (np.isnan(peak_db) or np.isnan(end_db)) else float("nan")}


# ---------------- 绘图 ----------------

def _shade_nasal(ax, segs: list[_NasalSeg], label_y_hz: float | None = None) -> None:
    """阴影标出鼻音段；声学估计的韵尾起点另用点划线标出。

    标签加白色半透明底色；label_y_hz 给定时把标签放到该频率处（数据坐标），
    避开低频能量带，否则放在轴底部。
    """
    for seg in segs:
        color = "#4c72b0" if seg.kind == "nasal_initial" else "#dd8452"
        ax.axvspan(seg.t0, seg.t1, color=color, alpha=0.15, lw=0)
        text = f"{seg.label} 鼻音段" if seg.kind == "nasal_initial" else f"{seg.label} 韵尾（估计）"
        mid = 0.5 * (seg.t0 + seg.t1)
        bbox = {"boxstyle": "round,pad=0.15", "facecolor": "white",
                "edgecolor": "none", "alpha": 0.75}
        if label_y_hz is None:
            ax.text(mid, 0.04, text, transform=ax.get_xaxis_transform(),
                    ha="center", va="bottom", fontsize=8, color=color, bbox=bbox)
        else:
            ax.text(mid, label_y_hz, text, ha="center", va="center", fontsize=8,
                    color=color, bbox=bbox)
        if seg.kind == "nasal_coda":
            ax.axvline(seg.t0, color=color, ls="-.", lw=1.0)


def _plot_formant_track(ctx: _Ctx, ax, number: int, t0: float | None, t1: float | None,
                        lw: float, label: str | None = None) -> None:
    """在 ax 上画清洗后的共振峰轨迹；离群点画成灰色空心点（低能量帧不画）。"""
    tr = ctx.formant_tracks()[number]
    ts, clean, raw = tr["ts"], tr["clean"], tr["raw"]
    keep = np.ones(len(ts), dtype=bool)
    if t0 is not None:
        keep &= ts >= t0
    if t1 is not None:
        keep &= ts <= t1
    outlier = tr["outlier"] & ~tr["low"] & keep
    ax.plot(ts[keep], clean[keep], color=F1_F2_F3_COLORS[number - 1], lw=lw, label=label)
    if outlier.any():
        ax.plot(ts[outlier], raw[outlier], "o", ls="none", ms=4,
                mfc="none", mec="0.45", mew=1.0)


def _fig_nasal_lowfreq(ctx: _Ctx, segs: list[_NasalSeg]) -> Path:
    """12a：0–2000 Hz 窄带语谱图，观察鼻音低频共振与谐波结构。"""
    plt = common.setup_matplotlib()
    sg = ctx.spectrogram("narrowband", 2000.0)
    t, f, v = common.spectrogram_arrays(sg)
    fig, ax = plt.subplots(figsize=(9, 4))
    common.plot_spectrogram(ax, t, f, v, vmax=ctx.narrowband_max_db(), fmax=2000.0)
    _shade_nasal(ax, segs)
    common.draw_boundaries(ax, ctx.aln)
    common.set_time_axis(ax, ctx.aln)
    ax.set_title(f"{ctx.stem} 鼻音低频窄带谱（0–2000 Hz，窗长 30 ms，dy={sg.dy:.2f} Hz）")
    fig.tight_layout()
    return common.save_fig(fig, ctx.out_dir, "12a_nasal_lowfreq")


def _fig_nasal_broadband(ctx: _Ctx, segs: list[_NasalSeg]) -> Path:
    """12b：0–8000 Hz 宽带语谱图叠加 F1–F2，观察鼻音与元音之间的过渡。"""
    plt = common.setup_matplotlib()
    sg = ctx.spectrogram("broadband", 8000.0)
    t, f, v = common.spectrogram_arrays(sg)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    common.plot_spectrogram(ax, t, f, v, vmax=ctx.broadband_max_db(), fmax=8000.0)
    for number in (1, 2):
        _plot_formant_track(ctx, ax, number, None, None, lw=1.4, label=f"F{number}")
    ax.plot([], [], "o", ls="none", ms=4, mfc="none", mec="0.45", mew=1.0, label="离群点")
    _shade_nasal(ax, segs, label_y_hz=4600.0)   # 标签放在中高频，避开低频能量带
    common.draw_boundaries(ax, ctx.aln)
    common.set_time_axis(ax, ctx.aln)
    ax.legend(loc="upper right", fontsize=8, ncols=3)
    ax.set_title(f"{ctx.stem} 鼻音宽带谱与 F1–F2 过渡（Burg：窗 25 ms，上限 "
                 f"{ctx.profile.formant_ceiling:.0f} Hz）")
    fig.tight_layout()
    return common.save_fig(fig, ctx.out_dir, "12b_nasal_broadband")


def _plot_spectrum_with_candidates(ax, analysis: _MidSpectrum, seg_label: str,
                                   comparison: _MidSpectrum | None, comp_label: str | None,
                                   n1_hz: float | None = None, b1_hz: float | None = None) -> None:
    """在 ax 上画出中点频谱、倒谱包络、Burg(LPC) 包络、对照频谱、N1 参考线与谱谷标注。"""
    ax.plot(analysis.freq, analysis.db, color="0.70", lw=0.8, label=f"{seg_label} 中点频谱（40 ms 窗）")
    if analysis.lpc_env_db is not None:
        ax.plot(analysis.freq, analysis.lpc_env_db, color="#55a868", lw=1.2, ls="-.",
                label="中点帧 Burg(LPC) 包络（幅度对齐）")
    if analysis.env is not None:
        ax.plot(analysis.freq, analysis.env, color="#4c72b0", lw=1.8,
                label=f"倒谱平滑包络（保留前 {analysis.n_cep_coeffs} 个倒谱系数）")
    if comparison is not None:
        ax.plot(comparison.freq, comparison.db, color="#c44e52", lw=0.9, ls="--",
                label=f"对照：{comp_label} 中点频谱")
    if n1_hz is not None and not np.isnan(n1_hz):
        bw_text = f"，B1≈{b1_hz:.0f} Hz" if b1_hz is not None and not np.isnan(b1_hz) else ""
        ax.axvline(n1_hz, color="#8c8c8c", ls=":", lw=1.4,
                   label=f"鼻腔共振 N1≈{n1_hz:.0f} Hz{bw_text}（鼻音段多帧 Burg F1 中位数）")
    for freq_hz, depth_db in analysis.valleys:
        index = int(np.argmin(np.abs(analysis.freq - freq_hz)))
        if analysis.env is not None:
            ax.plot(freq_hz, analysis.env[index], "^", color="#8172b3", ms=7)
        ax.annotate(f"{freq_hz:.0f} Hz\n−{depth_db:.1f} dB",
                    xy=(freq_hz, analysis.env[index]), xytext=(-14, -22),
                    textcoords="offset points", fontsize=7, color="#8172b3")
    if not analysis.valleys:
        ax.text(0.02, 0.97, f"未检出深度 ≥ {VALLEY_MIN_DEPTH_DB:.0f} dB 的谱谷候选",
                transform=ax.transAxes, ha="left", va="top", fontsize=8, color="#8172b3",
                bbox={"boxstyle": "round,pad=0.2", "facecolor": "white",
                      "edgecolor": "none", "alpha": 0.75})
    ax.set_xlim(0, VALLEY_SEARCH_MAX_HZ)
    ax.set_xlabel("频率 (Hz)")
    ax.set_ylabel("功率谱 (dB)")
    # 图例放右下：避开中高频处的对照谱峰（如 4 kHz 附近）
    ax.legend(loc="lower right", fontsize=8)


def _fig_nasal_spectrum(ctx: _Ctx, items: list[tuple]) -> Path:
    """12c：鼻音段中点高分辨率频谱 + 倒谱包络 + N1 参考线与谱谷候选，附元音对照。"""
    plt = common.setup_matplotlib()
    fig, ax = plt.subplots(figsize=(9, 5))
    for seg, analysis, n1, b1, comparison, comp_label in items:
        _plot_spectrum_with_candidates(ax, analysis, seg.label, comparison, comp_label,
                                       n1_hz=n1, b1_hz=b1)
    ax.set_title(f"{ctx.stem} 鼻音段中点频谱（40 ms 窗，0–5000 Hz）")
    has_coda = any(seg.kind == "nasal_coda" for seg, *_rest in items)
    coda_note = "韵尾区间为声学估计，非对齐边界。" if has_coda else ""
    fig.text(0.5, 0.005,
             "注：N1 取鼻音段多帧 Burg F1 的中位数，不一定与中点帧的谱峰重合；Burg(LPC) 包络"
             "幅度对齐到原始谱。谱谷为倒谱平滑包络上的反共振候选；全极点 LPC 不能表示零点，"
             f"本实现未做 pole-zero/ARMA 建模。{coda_note}",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return common.save_fig(fig, ctx.out_dir, "12c_nasal_spectrum")


def _fig_approximant_formants(ctx: _Ctx, initial, final, noise: dict | None) -> Path:
    """13a：宽带谱叠加声母起点到韵母 50% 处的 F1–F3 连续轨迹；r 另加噪声谱面板。"""
    plt = common.setup_matplotlib()
    sg = ctx.spectrogram("broadband", 5000.0)
    t, f, v = common.spectrogram_arrays(sg)
    if noise:
        fig, (ax, ax_n) = plt.subplots(2, 1, figsize=(9, 6.4),
                                       gridspec_kw={"height_ratios": (2, 1)})
    else:
        fig, ax = plt.subplots(figsize=(9, 4.2))
    common.plot_spectrogram(ax, t, f, v, vmax=ctx.broadband_max_db(), fmax=5000.0)
    t_end = final.t0 + APPROX_TRAJ_FINAL_FRAC * final.duration
    for number in (1, 2, 3):
        is_r_f3 = noise is not None and number == 3
        _plot_formant_track(ctx, ax, number, initial.t0, t_end,
                            lw=3.0 if is_r_f3 else 1.4,
                            label=f"F{number}" + ("（观察 F3 走向）" if is_r_f3 else ""))
    ax.plot([], [], "o", ls="none", ms=4, mfc="none", mec="0.45", mew=1.0, label="离群点")
    common.draw_boundaries(ax, ctx.aln, labels=False)
    ax.axvspan(initial.t0, initial.t1, color="#55a868", alpha=0.15, lw=0)
    ax.legend(loc="upper right", fontsize=8, ncols=3)
    common.set_time_axis(ax, ctx.aln)
    ipa = common.PHONE_IPA.get(initial.label, initial.label)
    title = (f"{ctx.stem} {initial.label} [{ipa}] F1–F3 连续轨迹"
             f"（声母起点至韵母 {APPROX_TRAJ_FINAL_FRAC * 100:.0f}%，宽带谱 0–5000 Hz）")
    ax.set_title(title)
    if noise:
        fig.text(0.5, 0.005,
                 "注：不能把英语 /ɹ/ 的 F3 降低现象直接套用到普通话 r 上；下方为 r 区间噪声谱"
                 "（平均功率谱，未分离谐波与噪声成分）。",
                 ha="center", fontsize=8)
        ax_n.plot(noise["freq"], noise["power_db"], color="#4c72b0", lw=1.2)
        ax_n.set_xlim(0, 8000)
        ax_n.set_xlabel("频率 (Hz)")
        ax_n.set_ylabel("功率谱 (dB)")
        ax_n.set_title(f"r 区间噪声谱：谱重心 {noise['cog_hz']:.0f} Hz（500–8000 Hz），"
                       f"谱倾斜 {noise['tilt_db']:.1f} dB（0–1 kHz 均值 − 1–4 kHz 均值）")
        fig.tight_layout(rect=(0, 0.03, 1, 1))
    else:
        fig.text(0.5, 0.005, "注：边音与前后元音按连续时间序列分析（方案 §4.5），不止看辅音中点。",
                 ha="center", fontsize=8)
        fig.tight_layout(rect=(0, 0.03, 1, 1))
    return common.save_fig(fig, ctx.out_dir, "13a_approximant_formants")


def _fig_lateral_spectrum(ctx: _Ctx, initial, final, analysis: _MidSpectrum,
                          comparison: _MidSpectrum | None) -> Path:
    """13b：l 区间中点 40 ms 频谱 + 倒谱包络 + 谱谷候选（反共振候选），与韵母中点对照。"""
    plt = common.setup_matplotlib()
    fig, ax = plt.subplots(figsize=(9, 5))
    _plot_spectrum_with_candidates(ax, analysis, "l", comparison, final.label)
    ax.set_title(f"{ctx.stem} l [l] 中点频谱（40 ms 窗，0–5000 Hz）")
    fig.text(0.5, 0.005,
             "注：谱谷为倒谱平滑包络上的反共振候选；全极点 LPC 不能表示零点，本实现未做 "
             "pole-zero/ARMA 建模。",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return common.save_fig(fig, ctx.out_dir, "13b_lateral_spectrum")


def _fig_zero_onset(ctx: _Ctx, initial) -> Path:
    """13c：录音开头 0–80 ms 的精细波形 + 声门脉冲、逐周期长度与窄带谱。"""
    plt = common.setup_matplotlib()
    pulses = ctx.point_process()
    n_samples = int(round(ZERO_WINDOW * ctx.sr))
    wf = ctx.x[:n_samples]
    wt = np.arange(len(wf)) / ctx.sr
    sg = ctx.spectrogram("narrowband", 5000.0)
    t, f, v = common.spectrogram_arrays(sg)

    end_in_view = initial.t1 <= ZERO_WINDOW    # 伪声母段末端是否落在视图内
    span_end = min(initial.t1, ZERO_WINDOW)
    fig, axes = plt.subplots(3, 1, figsize=(9, 7.5), sharex=True,
                             gridspec_kw={"height_ratios": (2, 1, 1.6)})
    # 上面板：精细波形 + 声门脉冲（图例放坐标轴外，避免压住波形）
    ax = axes[0]
    ax.axvspan(initial.t0, span_end, color="#999999", alpha=0.18, lw=0)
    ax.plot(wt, wf, color="#4c72b0", lw=0.7, label="精细波形")
    for p in pulses[pulses <= ZERO_WINDOW]:
        ax.axvline(p, color="#c44e52", lw=0.8, alpha=0.9)
    ax.plot([], [], color="#c44e52", lw=0.8, label="声门脉冲")
    if end_in_view:
        ax.axvline(initial.t1, color="#999999", ls="--", lw=0.8)
        ax.text(initial.t1, 0.86, "伪声母段末端", transform=ax.get_xaxis_transform(),
                ha="left", va="top", fontsize=8, color="#666666")
    ax.set_ylabel("振幅")
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), ncols=2, frameon=False,
              borderaxespad=0.0, fontsize=8)
    # 中面板：逐周期长度
    ax = axes[1]
    ax.axvspan(initial.t0, span_end, color="#999999", alpha=0.18, lw=0)
    starts = pulses[:-1]
    lengths = np.diff(pulses) * 1000.0
    keep = starts <= ZERO_WINDOW
    ax.plot(starts[keep], lengths[keep], color="#55a868", lw=1.2, marker="o", ms=3)
    ax.set_ylabel("周期长度 (ms)")
    # 下面板：窄带谱（伪声母段灰底画在谱图之上，避免被谱图盖住）；
    # 首帧之前没有完整分析窗，用斜线标出
    ax = axes[2]
    common.plot_spectrogram(ax, t, f, v, vmax=ctx.narrowband_max_db(), fmax=5000.0)
    # 谱图网格不透明：伪声母段画在其上，浅灰底加反向斜线，保证在谱图上可辨识
    ax.axvspan(initial.t0, span_end, facecolor="#999999", alpha=0.30,
               edgecolor="#888888", hatch="\\\\", lw=0, zorder=3)
    no_data_end = float(sg.x1) - float(sg.dx) / 2.0
    ax.axvspan(0.0, no_data_end, facecolor="none", edgecolor="#999999", hatch="//", lw=0,
               zorder=4)
    ax.text(0.5 * no_data_end, 0.5, "分析窗不完整，无数据", transform=ax.get_xaxis_transform(),
            ha="center", va="center", fontsize=8, color="#666666", zorder=5,
            bbox={"boxstyle": "round,pad=0.15", "facecolor": "white",
                  "edgecolor": "none", "alpha": 0.75})
    ax.set_ylabel("频率 (Hz)")
    ax.set_xlabel("时间 (s)")
    for ax in axes:
        ax.set_xlim(0, ZERO_WINDOW)
    fig.suptitle(f"{ctx.stem} 零声母起始精细分析（0–{ZERO_WINDOW * 1000:.0f} ms，伪声母 ∅）",
                 fontsize=11)
    end_note = "" if end_in_view else (
        f"伪声母段末端 {initial.t1:.3f} s 超出视图，未标出；视图内均属伪声母段。")
    fig.text(0.5, 0.005,
             "注：灰色区间为讯飞插入的零声母占位伪声母段（∅），非真实独立音段；"
             f"横轴为放大视图，不采用完整时间轴。{end_note}",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    return common.save_fig(fig, ctx.out_dir, "13c_zero_onset")


# ---------------- 逐类分析 ----------------

def _true_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """布尔数组中连续 True 段的 [起, 止) 下标列表。"""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, value in enumerate(mask):
        if value and start is None:
            start = i
        elif not value and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs


def _median_defined(values: np.ndarray, minimum: int = 1) -> float:
    """已定义帧（非 NaN）的中位数，少于 minimum 个则 NaN。"""
    defined = values[~np.isnan(values)]
    return float(np.median(defined)) if len(defined) >= minimum else float("nan")


def _stable_combined(clean: np.ndarray, start: int, stop: int) -> float:
    """段前后两侧稳态帧合起来的中位数（两侧电平接近时即稳态电平）。"""
    side = np.concatenate([clean[max(0, start - FORMANT_STABLE_CONTEXT_FRAMES):start],
                           clean[stop:stop + FORMANT_STABLE_CONTEXT_FRAMES]])
    return _median_defined(side)


def _nasal_row_measurements(ctx: _Ctx, row: dict, label: str,
                            t0: float, t1: float) -> tuple[_MidSpectrum | None, float, float]:
    """鼻音段的公共测量：N1/B1 中位数（Burg F1/B1 中位）、中点频谱与谱谷候选。

    返回 (中点频谱分析, N1, B1)；中点分析窗越界时频谱为 None。
    """
    n1, b1, n_frames = _nasal_formant_medians(ctx, t0, t1)
    row["nasal_resonance_f1_median_hz"] = _num(n1)
    row["nasal_resonance_b1_median_hz"] = _num(b1)
    row["nasal_resonance_frames"] = n_frames
    if np.isnan(n1):
        ctx.result["warnings"].append(
            f"{ctx.stem}：{label} 段内没有可用的有声帧，鼻腔共振（F1/B1 中位）记为空值")
    try:
        analysis = _mid_spectrum(ctx, t0, t1)
    except ValueError as e:
        ctx.result["warnings"].append(f"{ctx.stem}：{label} 中点频谱未生成（{e}）")
        return None, n1, b1
    row["valley_candidates"] = _json_or_empty(
        [{"freq_hz": round(f, 1), "depth_db": round(d, 1)} for f, d in analysis.valleys])
    if analysis.lifter_s is not None:
        row["cepstral_lifter_ms"] = _num(analysis.lifter_s * 1000.0, 2)
    else:
        row["cepstral_lifter_ms"] = ""
    ctx.result["params"]["mid_spectrum"]["cepstral_lifter_s"][f"{ctx.stem}:{label}"] = (
        round(analysis.lifter_s, 4) if analysis.lifter_s is not None else None)
    if analysis.env is None:
        ctx.result["warnings"].append(f"{ctx.stem}：{label} 中点分析窗内没有有声帧，谱谷候选跳过")
    elif not analysis.valleys:
        ctx.result["warnings"].append(
            f"{ctx.stem}：{label} 中点倒谱包络上未检出深度 ≥ "
            f"{VALLEY_MIN_DEPTH_DB:.0f} dB 的谱谷候选")
    return analysis, n1, b1


def _analyze_nasal_initial(ctx: _Ctx, initial, final, rows: list[dict],
                           segs: list[_NasalSeg]) -> None:
    """鼻音声母 m/n：测量 + 三张图（图在收集完全部鼻音段后统一画）。"""
    segs.append(_NasalSeg(initial.t0, initial.t1, "nasal_initial", initial.label))
    row = {
        "type": "nasal_initial", "label": initial.label,
        "t0": round(initial.t0, 3), "t1": round(initial.t1, 3),
        "interval_source": "alignment",
        "duration_ms": round(initial.duration * 1000.0, 1),
        "formant_transition": _json_or_empty(
            _formant_transition(ctx, [initial.t1, initial.t1 + 0.020, initial.t1 + 0.040])),
    }
    analysis, n1, b1 = _nasal_row_measurements(ctx, row, initial.label, initial.t0, initial.t1)
    if analysis is not None:
        ctx.cache.setdefault("nasal_items", []).append(
            (segs[-1], analysis, n1, b1, _vowel_comparison(ctx, final, None), final.label))
    rows.append(row)


def _analyze_nasal_coda(ctx: _Ctx, syll_index: int, final, rows: list[dict],
                        segs: list[_NasalSeg]) -> None:
    """鼻韵尾：先取韵母声学区间（common.vowel_interval），再在其后半段声学估计韵尾区间。"""
    vi = common.vowel_interval(ctx.aln, syll_index, ctx.x, ctx.sr, ctx.profile)
    coda_t0, coda_t1, method, detail = _estimate_coda_interval(ctx, vi.t0, vi.t1)
    segs.append(_NasalSeg(coda_t0, coda_t1, "nasal_coda", common.nasal_coda(final.label)))
    ctx.result["warnings"].append(
        f"{ctx.stem}：鼻韵尾区间为声学估计，非对齐边界（韵母声学区间 {vi.t0:.3f}–{vi.t1:.3f} s，"
        f"起点来源 {vi.start_source}、终点来源 {vi.end_source}；{detail}）")
    ctx.result["params"].setdefault("nasal_coda", {}).setdefault("method_by_final", {})[
        f"{ctx.stem}:{final.label}"] = method
    ctx.result["params"]["nasal_coda"].setdefault("vowel_interval_by_final", {})[
        f"{ctx.stem}:{final.label}"] = {
        "t0": round(vi.t0, 3), "t1": round(vi.t1, 3),
        "start_source": vi.start_source, "end_source": vi.end_source}
    row = {
        "type": "nasal_coda", "label": common.nasal_coda(final.label),
        "t0": round(coda_t0, 3), "t1": round(coda_t1, 3),
        "interval_source": "acoustic_estimate" if method == "band_energy_drop" else "fallback_tail",
        "interval_end_source": vi.end_source,
        "duration_ms": round((coda_t1 - coda_t0) * 1000.0, 1),
        "formant_transition": _json_or_empty(
            _formant_transition(ctx, [coda_t0 - 0.040, coda_t0 - 0.020, coda_t0])),
    }
    analysis, n1, b1 = _nasal_row_measurements(ctx, row, final.label, coda_t0, coda_t1)
    if analysis is not None:
        ctx.cache.setdefault("nasal_items", []).append(
            (segs[-1], analysis, n1, b1, _vowel_comparison(ctx, final, coda_t0),
             f"{final.label[:-len(common.nasal_coda(final.label))]}（韵尾前）"))
    rows.append(row)


def _vowel_comparison(ctx: _Ctx, final, before_t: float | None) -> _MidSpectrum | None:
    """对照元音频谱：鼻音声母取韵母中点；鼻韵尾取韵尾起点前的元音部分中点。"""
    t0, t1 = final.t0, (final.t1 if before_t is None else before_t)
    try:
        return _mid_spectrum(ctx, t0, t1)
    except ValueError as e:
        ctx.result["warnings"].append(f"{ctx.stem}：对照元音频谱未生成（{e}）")
        return None


def _analyze_lateral_or_r(ctx: _Ctx, initial, final, rows: list[dict]) -> None:
    """边音 l 与 r：13a 轨迹图；l 另有 13b 中点频谱；r 另有噪声谱面板与浊音指标。"""
    cls = common.initial_class(initial.label)
    noise: dict | None = None
    if cls == "approximant":
        try:
            noise = _rhotic_metrics(ctx, initial)
        except ValueError as e:
            ctx.result["warnings"].append(f"{ctx.stem}：r 的噪声谱未生成（{e}）")
    ctx.cache.setdefault("approx_items", []).append((initial, final, noise))
    mid = 0.5 * (initial.t0 + initial.t1)
    mid_formants: dict = {"times_s": [round(mid, 3)]}
    for number, key in ((1, "F1"), (2, "F2"), (3, "F3")):
        value, flag = _formant_value_and_flag(ctx, number, mid, any_distance=True)
        mid_formants[f"{key}_hz"] = _nan_to_none([value])
        mid_formants[f"{key}_outlier"] = [flag]
    row = {
        "type": "lateral" if cls == "lateral" else "rhotic", "label": initial.label,
        "t0": round(initial.t0, 3), "t1": round(initial.t1, 3), "interval_source": "alignment",
        "duration_ms": round(initial.duration * 1000.0, 1),
        "mid_formants": _json_or_empty(mid_formants),
    }
    if noise:
        row["voiced_fraction"] = _num(noise["voiced_fraction"], 3)
        row["hnr_db"] = _num(noise["hnr_db"])
        row["f0_mean_hz"] = _num(noise["f0_mean_hz"])
        row["noise_cog_hz"] = _num(noise["cog_hz"])
        row["noise_tilt_db"] = _num(noise["tilt_db"])
        if np.isnan(noise["voiced_fraction"]):
            ctx.result["warnings"].append(f"{ctx.stem}：r 区间内没有 F0 帧，浊音占比记为空值")
    if cls == "lateral":
        try:
            analysis = _mid_spectrum(ctx, initial.t0, initial.t1)
        except ValueError as e:
            ctx.result["warnings"].append(f"{ctx.stem}：l 中点频谱未生成（{e}）")
            analysis = None
        if analysis is not None:
            row["valley_candidates"] = _json_or_empty(
                [{"freq_hz": round(f, 1), "depth_db": round(d, 1)} for f, d in analysis.valleys])
            if analysis.lifter_s is not None:
                row["cepstral_lifter_ms"] = _num(analysis.lifter_s * 1000.0, 2)
            else:
                row["cepstral_lifter_ms"] = ""
            ctx.result["params"]["mid_spectrum"]["cepstral_lifter_s"][
                f"{ctx.stem}:{initial.label}"] = (round(analysis.lifter_s, 4)
                                                  if analysis.lifter_s is not None else None)
            if analysis.env is None:
                ctx.result["warnings"].append(
                    f"{ctx.stem}：l 中点分析窗内没有有声帧，谱谷候选跳过")
            elif not analysis.valleys:
                ctx.result["warnings"].append(
                    f"{ctx.stem}：l 中点倒谱包络上未检出深度 ≥ {VALLEY_MIN_DEPTH_DB:.0f} dB "
                    f"的谱谷候选")
            ctx.cache.setdefault("lateral_spectrum", []).append(
                (initial, final, analysis, _vowel_comparison(ctx, final, None)))
    rows.append(row)


def _analyze_zero(ctx: _Ctx, initial, syllable, rows: list[dict]) -> None:
    """零声母：13c 精细起始图与测量。"""
    ctx.cache.setdefault("zero_items", []).append(initial)
    metrics = _zero_metrics(ctx, initial, syllable)
    rows.append({
        "type": "zero", "label": initial.label,
        "t0": round(initial.t0, 3), "t1": round(initial.t1, 3), "interval_source": "alignment",
        "duration_ms": round(initial.duration * 1000.0, 1),
        "zero_first_pulse_s": _num(metrics["first_pulse_s"], 4),
        "zero_period_jitter": _num(metrics["jitter"], 4),
        "zero_intensity_rel_db": _num(metrics["intensity_rel_db"]),
    })


# ---------------- 入口 ----------------

def generate(x, sr: int, aln: Alignment, out_dir: str | Path, scales: DbScales | None = None,
             context: dict | None = None) -> dict:
    """对一条录音生成鼻音/边音/r/零声母的专项图像与参数表（接口见模块 docstring 与 common.new_result）。"""
    result = common.new_result()
    ctx = _Ctx(x=np.asarray(x, dtype=float), sr=int(sr), aln=aln, out_dir=Path(out_dir),
               scales=scales, result=result)
    ctx.snd = common.to_sound(x, sr)
    ctx.profile = common.profile_for(aln.speaker)
    ctx.stem = Path(aln.file).stem
    result["params"]["speaker_profile"] = {
        "speaker": aln.speaker, "name": ctx.profile.name, "f0_floor": ctx.profile.f0_floor,
        "f0_ceiling": ctx.profile.f0_ceiling, "formant_ceiling": ctx.profile.formant_ceiling,
    }
    result["params"]["nasal_resonance"] = {
        "method": "鼻音段（声母=讯飞区间，韵尾=声学估计区间）内有声帧 Burg F1 的中位数（N1），"
                  "带宽为 B1 的中位数；离群帧与低能量帧已排除",
        "note": "全极点模型能估计极点（N1），不能表示鼻音谱零点；零点由倒谱包络的谱谷候选观察",
    }
    result["params"]["mid_spectrum"] = {
        "window_s": MID_WINDOW, "db_ref": "PRAAT_POWER_REF（与语谱图一致）",
        "cepstral_lifter_rule": f"截断长度 = {CEP_LIFTER_F0_RATIO} × 基音周期"
                                f"（分析窗内有声帧 F0 中位数的倒数），限制在 "
                                f"{CEP_LIFTER_MIN_S * 1000:.0f}–{CEP_LIFTER_MAX_S * 1000:.0f} ms",
        "cepstral_lifter_s": {},
        "valley_min_depth_db": VALLEY_MIN_DEPTH_DB, "valley_search_max_hz": VALLEY_SEARCH_MAX_HZ,
    }
    result["params"]["nasal_coda_search"] = {
        "band_hz": list(CODA_BAND_HZ), "frame_window_s": CODA_BAND_WINDOW,
        "frame_hop_s": CODA_BAND_HOP, "drop_threshold_db": CODA_DROP_DB,
        "fallback_tail_fraction": CODA_FALLBACK_TAIL,
        "interval": "common.vowel_interval 的韵母声学区间，搜索其后半段，区间终点取 t1"
                    "（来源见 vowel_interval_by_final）",
    }

    rows: list[dict] = []
    nasal_segs: list[_NasalSeg] = []
    for syll_index, syllable in enumerate(aln.syllables):
        initial, final = syllable.initial, syllable.final
        if initial is not None and common.initial_class(initial.label) == "nasal":
            _analyze_nasal_initial(ctx, initial, final, rows, nasal_segs)
        if final is not None and common.nasal_coda(final.label):
            _analyze_nasal_coda(ctx, syll_index, final, rows, nasal_segs)
        if initial is not None and common.initial_class(initial.label) in ("lateral", "approximant"):
            _analyze_lateral_or_r(ctx, initial, final, rows)
        if initial is not None and common.initial_class(initial.label) == "zero":
            _analyze_zero(ctx, initial, syllable, rows)

    # 出图（单图失败只记 warning，不中断）
    figures: list[tuple[str, object]] = []
    if nasal_segs:
        figures += [
            ("12a_nasal_lowfreq.png", lambda: _fig_nasal_lowfreq(ctx, nasal_segs)),
            ("12b_nasal_broadband.png", lambda: _fig_nasal_broadband(ctx, nasal_segs)),
        ]
    nasal_items = ctx.cache.get("nasal_items", [])
    if nasal_items:
        figures.append(("12c_nasal_spectrum.png",
                        lambda: _fig_nasal_spectrum(ctx, nasal_items)))
    for initial, final, noise in ctx.cache.get("approx_items", []):
        figures.append(("13a_approximant_formants.png",
                        lambda i=initial, f=final, n=noise: _fig_approximant_formants(ctx, i, f, n)))
    for initial, final, analysis, comparison in ctx.cache.get("lateral_spectrum", []):
        figures.append(("13b_lateral_spectrum.png",
                        lambda i=initial, f=final, a=analysis, c=comparison:
                        _fig_lateral_spectrum(ctx, i, f, a, c)))
    for initial in ctx.cache.get("zero_items", []):
        figures.append(("13c_zero_onset.png", lambda i=initial: _fig_zero_onset(ctx, i)))
    for name, builder in figures:
        try:
            result["images"][name] = builder()
        except Exception as e:  # noqa: BLE001 —— 单图失败不应中断整批
            result["warnings"].append(f"{ctx.stem}：生成 {name} 失败（{type(e).__name__}: {e}）")

    if not result["images"]:
        result["warnings"].append("录音中没有鼻音、鼻韵尾、边音、r 或零声母，本模块未生成图像")

    if rows:
        result["tables"]["sonorant_params.csv"] = common.write_csv(
            rows, Path(out_dir) / "csv", "sonorant_params.csv")
    return result
