"""发声态与谐波—噪声分析（方案 §6、§7.2 末两行、§10 D）。

测量对象是每个音节韵母中的有声帧（F0 有值即为有声），全部指标输出时间轨迹
（方案 L563：在同一元音的多个时刻测量，而不是只取平均数）：

- 谐波振幅 H1/H2/H4/A1/A2/A3/H2k/H5k 与 Iseli & Alwan (2004) 共振峰修正（仿 VoiceSauce），
  分析窗为 3 个基音周期长的 Hann 窗；
- 谱倾斜派生指标 H1*–H2*、H1*–A1*、H1*–A2*、H1*–A3*、H2*–H4*、H4*–H2k*、H2k*–H5k；
- HNR：Praat Harmonicity (cc) 全频带轨迹 + 0–500/1500/2500/3500 Hz 分频带均值；
- CPP/CPPS：Praat PowerCepstrogram 的逐帧表（To Table (cepstral peak prominences)，
  CPPS 先用 Smooth 平滑），另存整段 Get CPPS 参考值；
- SHR：简化谱法（仿 Sun 2002 定义思想，非原算法），SHR 单独用 6 基音周期 Hann 窗
  并补零到 8 倍窗长，谐波与次谐波位置按 ±0.05·F0 对称取峰，避免主瓣泄漏抬高基线；
- 声带周期、Jitter、Shimmer（方案 §6.5：不作为核心指标，同时报告有效周期数）。

本模块各图无 common.spectrogram 语谱图背景；谐波振幅的 dB 参考与 common.db 一致
（ref=1），派生指标为同帧差值，不受 dB 参考影响。
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from . import common
from .formants import VowelFormants, vowel_formants

FRAME_STEP = 0.005              # 分析帧移（秒）
WINDOW_PERIODS = 3.0            # 分析窗长度 = 3 个基音周期（VoiceSauce 做法，方案 L556）
FFT_WINDOW_RATIO = 4.0          # FFT 长度不小于 4 倍窗长
HARMONIC_TOL = 0.1              # 谐波峰值搜索范围 ±0.1·F0
FORMANT_AMPLITUDE_TOL = 0.10    # A_i 在 F_i ± 10% 范围内取最强谐波
H2K_FREQ = 2000.0               # H2k 参考频率 ±F0/2
H5K_FREQ = 5000.0               # H5k 参考频率 ±F0/2（不修正）
BANDWIDTH_RANGE = (30.0, 600.0) # 共振峰带宽的取值限制（Hz）
HNR_BANDS = (500.0, 1500.0, 2500.0, 3500.0)   # 分频带上限（Hz），下限一律 0
BAND_SMOOTHING = 100.0          # Filter (pass Hann band) 的平滑宽度（Hz）
CPP_TIME_STEP = 0.005
CPP_MAX_FREQUENCY = 5000.0
CPP_PRE_EMPHASIS = 50.0
CPP_TREND_QUEFRENCY_MIN = 0.001 # To Table 的趋势线 quefrency 下限，上限 0 表示矩阵上限
CPP_TOLERANCE = 0.001
CPPS_TIME_SMOOTH = 0.01         # CPPS 时间方向平滑窗（秒）；逐帧轨迹与整段 Get CPPS 共用，
CPPS_QUEFRENCY_SMOOTH = 0.001   # quefrency 方向平滑窗（秒）；取值与 AVQI 脚本的 CPPS 设置一致
SHR_WINDOW_PERIODS = 6.0        # SHR 专用窗长：6 个基音周期，主瓣半宽约 0.33·F0，
                                # 次谐波位置 (k−0.5)·F0 落在主瓣之外，避免泄漏抬高基线
SHR_FFT_RATIO = 8.0             # SHR 谱的补零倍数（FFT ≥ 8 倍窗长）
SHR_TOL = 0.05                  # SHR 谐波/次谐波位置对称的峰值搜索范围 ±0.05·F0
SHR_HARMONIC_LIMIT = 4000.0     # SH/H 求和的谐波数上限（k·F0 < 4000 Hz）
PERIOD_FLOOR = 0.0001           # Jitter/Shimmer 的最短周期（秒，Praat 默认）
PERIOD_CEILING = 0.02           # 最长周期（秒，Praat 默认）
MAX_PERIOD_FACTOR = 1.3
MAX_AMPLITUDE_FACTOR = 1.6
MIN_PERIODS_FOR_COMPARISON = 20 # 有效周期数低于此值时 Jitter/Shimmer 不宜与参考值比较
CEPSTROGRAM_WINDOW_FACTOR = 3.0 # PowerCepstrogram 的有效分析窗长约 3/pitchFloor，用于标注边缘区域

# 时间序列表的列（顺序即输出顺序）；带 * 的为共振峰修正值
TS_COLUMNS = ("time", "phone", "F0", "F1", "F2", "F3", "B1", "B2", "B3",
              "H1", "H2", "H4", "A1", "A2", "A3", "H2k", "H5k",
              "H1*", "H2*", "H4*", "A1*", "A2*", "A3*", "H2k*",
              "H1*-H2*", "H1*-A1*", "H1*-A2*", "H1*-A3*", "H2*-H4*",
              "H4*-H2k*", "H2k*-H5k",
              "HNR", "CPP", "CPPS", "SHR")

# 图 15 / 图 16 中的指标与配色顺序
HARMONIC_METRICS = (("H1*", "H1"), ("H2*", "H2"), ("H4*", "H4"),
                    ("A1*", "A1"), ("A2*", "A2"), ("A3*", "A3"))
TILT_METRICS = ("H1*-H2*", "H1*-A1*", "H1*-A2*", "H1*-A3*",
                "H2*-H4*", "H4*-H2k*", "H2k*-H5k")
# 依赖共振峰、在不可靠帧上记 NaN 的量；H1/H2/H4/H2k/H5k 未修正值不依赖共振峰，保留
FORMANT_DEPENDENT_KEYS = ("A1", "A2", "A3", "H1*", "H2*", "H4*", "A1*", "A2*", "A3*",
                          "H2k*", *TILT_METRICS)
# 图 16 的三个面板：谐波间差值 / 与共振峰谐波差值 / 谱倾斜
TILT_PANELS = (("H1*-H2*", "H2*-H4*"),
               ("H1*-A1*", "H1*-A2*", "H1*-A3*"),
               ("H4*-H2k*", "H2k*-H5k"))
EFFECTIVE_END_COLOR = "#e65100"   # 有效终点点线颜色（与 prosody 一致）


def _draw_effective_end(ax, finals_info: list[tuple[int, common.PhoneSeg, VowelFormants]]
                        ) -> None:
    """橙色点线标出发生有声延伸的韵母有效终点（同 prosody 样式；未延伸时不画）。"""
    labeled = False
    for _, _final, vf in finals_info:
        if vf.end_source == "voicing_extended":
            ax.axvline(vf.t1, color=EFFECTIVE_END_COLOR, ls=":", lw=1.4,
                       label=None if labeled else "有效终点（有声延伸）")
            labeled = True


def _effective_end_note(finals_info: list[tuple[int, common.PhoneSeg, VowelFormants]]
                        ) -> str:
    """发生有声延伸时的图注文字（讯飞韵母右界与曲线画到的位置不同）；无延伸返回空串。"""
    parts = [f"韵母 {final.label} 有效终点 {vf.t1:.3f} s"
             f"（有声延伸 +{(vf.t1 - final.t1) * 1000:.0f} ms），"
             f"曲线延伸至此（讯飞韵母右界 {final.t1:.3f} s）"
             for _, final, vf in finals_info if vf.end_source == "voicing_extended"]
    return "；".join(parts)


# ---------------- 通用小工具 ----------------

def _nearest_value(grid_t: np.ndarray, values: np.ndarray, t: float, tol: float) -> float:
    """取网格上离 t 最近一帧的值；距离超过 tol 或该帧为 NaN 时返回 NaN。"""
    if len(grid_t) == 0:
        return math.nan
    i = int(np.argmin(np.abs(grid_t - t)))
    if abs(grid_t[i] - t) > tol or not np.isfinite(values[i]):
        return math.nan
    return float(values[i])


def _band_peak(freqs: np.ndarray, values: np.ndarray, lo: float, hi: float) -> tuple[float, float]:
    """[lo, hi] 频率范围内的最大谱值与其所在频率；范围为空或含 NaN 时返回 (NaN, NaN)。"""
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return math.nan, math.nan
    mask = (freqs >= lo) & (freqs <= hi)
    if not np.any(mask):
        return math.nan, math.nan
    vv = values[mask]
    j = int(np.argmax(vv))
    return float(vv[j]), float(freqs[mask][j])


def _formant_amplitude_correction(f: float, formant: float, bandwidth: float,
                                  sampling_rate: float) -> float:
    """Iseli & Alwan (2004) 共振峰修正量（dB）：单个共振峰 (F, B) 在频率 f 处的补偿。"""
    r = math.exp(-math.pi * bandwidth / sampling_rate)
    omega_x = 2.0 * math.pi * formant / sampling_rate
    omega = 2.0 * math.pi * f / sampling_rate
    a = r * r + 1.0 - 2.0 * r * math.cos(omega_x + omega)
    b = r * r + 1.0 - 2.0 * r * math.cos(omega_x - omega)
    return (-10.0 * (math.log10(a) + math.log10(b))
            + 20.0 * math.log10(r * r + 1.0 - 2.0 * r * math.cos(omega_x)))


def _finite_median(values: list[float]) -> float:
    """有限值的中位数；无有限值时返回 NaN。"""
    v = np.asarray([w for w in values if np.isfinite(w)], dtype=float)
    return float(np.median(v)) if v.size else math.nan


def _csv_value(v):
    """CSV 单元格：NaN/Inf 写成空字符串，其余原样。"""
    if isinstance(v, float) and not math.isfinite(v):
        return ""
    return v


# ---------------- 逐帧谐波测量 ----------------

def _measure_final(x: np.ndarray, sr: int, final: common.PhoneSeg, vf: VowelFormants,
                   t_f0: np.ndarray, f0_arr: np.ndarray, f0_tol: float,
                   shr_best: dict) -> list[dict]:
    """韵母元音区间 [vf.t0, vf.t1] 内所有有声帧的谐波测量。

    谐波测量只在有 F0 的帧上做；帧网格为 FRAME_STEP 的整数倍时刻。共振峰与带宽取
    formants.vowel_formants 的同一份结果（最近帧取值，与 07 图口径一致），带宽限制在
    BANDWIDTH_RANGE 内；vf.valid 为 False 的帧，依赖共振峰的量（FORMANT_DEPENDENT_KEYS）
    记为 NaN（valid 已含低能量与离群判定，本模块不重复计算）。
    """
    rows: list[dict] = []
    vf_step = (float(np.median(np.diff(vf.times))) if len(vf.times) > 1 else FRAME_STEP)
    k0 = math.ceil(vf.t0 / FRAME_STEP - 1e-9)
    k1 = math.floor(vf.t1 / FRAME_STEP + 1e-9)
    for k in range(k0, k1 + 1):
        t = k * FRAME_STEP
        f0 = _nearest_value(t_f0, f0_arr, t, f0_tol)
        if not math.isfinite(f0):
            continue
        j = int(np.argmin(np.abs(vf.times - t))) if len(vf.times) else -1
        if j < 0 or abs(vf.times[j] - t) > vf_step:
            f_fmt = [math.nan] * 3
            b_used = [math.nan] * 3
            formant_valid = False
        else:
            f_fmt = [float(vf.freqs[i, j]) for i in range(3)]
            b_used = [float(np.clip(vf.bands[i, j], *BANDWIDTH_RANGE)) for i in range(3)]
            formant_valid = bool(vf.valid[j])

        win_sec = WINDOW_PERIODS / f0
        seg, complete = common.segment_at(x, sr, t, win_sec)
        n_fft = 1 << math.ceil(math.log2(FFT_WINDOW_RATIO * win_sec * sr))
        freqs, power = common.power_spectrum(seg, sr, n_fft)
        spec_db = common.db(power)

        h1, _ = _band_peak(freqs, spec_db, f0 - HARMONIC_TOL * f0, f0 + HARMONIC_TOL * f0)
        h2, _ = _band_peak(freqs, spec_db, 2 * f0 - HARMONIC_TOL * f0, 2 * f0 + HARMONIC_TOL * f0)
        h4, _ = _band_peak(freqs, spec_db, 4 * f0 - HARMONIC_TOL * f0, 4 * f0 + HARMONIC_TOL * f0)
        a1, _ = _band_peak(freqs, spec_db, f_fmt[0] * (1 - FORMANT_AMPLITUDE_TOL),
                           f_fmt[0] * (1 + FORMANT_AMPLITUDE_TOL))
        a2, _ = _band_peak(freqs, spec_db, f_fmt[1] * (1 - FORMANT_AMPLITUDE_TOL),
                           f_fmt[1] * (1 + FORMANT_AMPLITUDE_TOL))
        a3, _ = _band_peak(freqs, spec_db, f_fmt[2] * (1 - FORMANT_AMPLITUDE_TOL),
                           f_fmt[2] * (1 + FORMANT_AMPLITUDE_TOL))
        h2k, f_h2k = _band_peak(freqs, spec_db, H2K_FREQ - f0 / 2, H2K_FREQ + f0 / 2)
        h5k, _ = _band_peak(freqs, spec_db, H5K_FREQ - f0 / 2, H5K_FREQ + f0 / 2)

        def corr12(f: float) -> float:
            return (_formant_amplitude_correction(f, f_fmt[0], b_used[0], sr)
                    + _formant_amplitude_correction(f, f_fmt[1], b_used[1], sr))

        def corr3(f: float) -> float:
            return corr12(f) + _formant_amplitude_correction(f, f_fmt[2], b_used[2], sr)

        h1s = h1 - corr12(f0)
        h2s = h2 - corr12(2.0 * f0)
        h4s = h4 - corr12(4.0 * f0)
        a1s = a1 - corr12(f_fmt[0])
        a2s = a2 - corr12(f_fmt[1])
        a3s = a3 - corr3(f_fmt[2])
        h2ks = h2k - corr3(f_h2k)

        # SHR：简化谱法，SH/H 均为线性幅度之和。单独用 6 周期 Hann 窗并补零到 8 倍窗长，
        # 使次谐波位置 (k−0.5)·F0 落在主瓣之外，谐波与次谐波位置按 ±0.05·F0 对称取峰
        shr_win = SHR_WINDOW_PERIODS / f0
        seg_shr, _ = common.segment_at(x, sr, t, shr_win)
        n_fft_shr = 1 << math.ceil(math.log2(SHR_FFT_RATIO * shr_win * sr))
        freqs_shr, power_shr = common.power_spectrum(seg_shr, sr, n_fft_shr)
        amplitude_shr = np.sqrt(power_shr)
        n_harm = max(1, int(math.floor((SHR_HARMONIC_LIMIT - f0 * 0.01) / f0)))
        h_sum = 0.0
        sh_sum = 0.0
        for m in range(1, n_harm + 1):
            lo, hi = m * f0 - SHR_TOL * f0, m * f0 + SHR_TOL * f0
            v, _ = _band_peak(freqs_shr, amplitude_shr, lo, hi)
            h_sum += v if math.isfinite(v) else 0.0
            lo, hi = (m - 0.5) * f0 - SHR_TOL * f0, (m - 0.5) * f0 + SHR_TOL * f0
            v, _ = _band_peak(freqs_shr, amplitude_shr, lo, hi)
            sh_sum += v if math.isfinite(v) else 0.0
        shr = sh_sum / h_sum if h_sum > 0 else math.nan

        if math.isfinite(shr) and shr > shr_best.get("shr", -np.inf):
            shr_best.clear()
            shr_best.update(shr=shr, t=t, f0=f0, freqs=freqs_shr.copy(),
                            spec_db=common.db(power_shr).copy(),
                            n_harm=n_harm)

        row = {
            "time": t, "phone": final.label, "F0": f0,
            "F1": f_fmt[0], "F2": f_fmt[1], "F3": f_fmt[2],
            "B1": b_used[0], "B2": b_used[1], "B3": b_used[2],
            "H1": h1, "H2": h2, "H4": h4, "A1": a1, "A2": a2, "A3": a3,
            "H2k": h2k, "H5k": h5k,
            "H1*": h1s, "H2*": h2s, "H4*": h4s, "A1*": a1s, "A2*": a2s, "A3*": a3s,
            "H2k*": h2ks,
            "H1*-H2*": h1s - h2s, "H1*-A1*": h1s - a1s, "H1*-A2*": h1s - a2s,
            "H1*-A3*": h1s - a3s, "H2*-H4*": h2s - h4s, "H4*-H2k*": h4s - h2ks,
            "H2k*-H5k": h2ks - h5k,
            "SHR": shr,
            "_complete": complete,
            "_formant_invalid": not formant_valid,
        }
        if not formant_valid:
            for key in FORMANT_DEPENDENT_KEYS:
                row[key] = math.nan
        rows.append(row)
    return rows


# ---------------- CPP / CPPS ----------------

def _cpp_table(power_cepstrogram, profile: common.SpeakerProfile) -> np.ndarray:
    """Praat "To Table (cepstral peak prominences)" 的逐帧 CPP 数组（dB）。

    计算参数与整段 Get CPPS 一致：峰值搜索按 profile 的 F0 范围、趋势线 quefrency
    0.001 s 至矩阵上限、Exponential decay 趋势、Robust 拟合；表本身不做任何平滑，
    CPPS 的平滑由调用方先用 "Smooth" 完成。
    """
    from parselmouth.praat import call

    table = call(power_cepstrogram, "To Table (cepstral peak prominences)",
                 "no", "no", 6, 6, "no", 6,
                 profile.f0_floor, profile.f0_ceiling, CPP_TOLERANCE, "parabolic",
                 CPP_TREND_QUEFRENCY_MIN, 0.0, "Exponential decay", "Robust")
    n_rows = int(call(table, "Get number of rows"))
    return np.asarray([call(table, "Get value", r, "CPP(dB)")
                       for r in range(1, n_rows + 1)], dtype=float)


# ---------------- 主入口 ----------------

def generate(x, sr, aln: common.Alignment, out_dir, scales: common.DbScales | None = None,
             context: dict | None = None) -> dict:
    """对一条录音做发声态与谐波—噪声分析，输出 6 张图与 2 个 CSV（见模块 docstring）。"""
    from parselmouth.praat import call

    result = common.new_result()
    snd = common.to_sound(x, sr)
    profile = common.profile_for(aln.speaker)

    # F0（谐波帧的有声判定）；共振峰与元音区间统一取自 formants.vowel_formants
    pitch = common.pitch_filtered_ac(snd, profile)
    t_f0, f0_arr = common.pitch_arrays(pitch)

    # 各韵母的共振峰与元音区间（与 formants 模块同一份计算；ceiling 逐韵母自动选择）
    finals_info: list[tuple[int, common.PhoneSeg, VowelFormants]] = []
    for si, syll in enumerate(aln.syllables):
        if syll.final is not None:
            finals_info.append((si, syll.final, vowel_formants(x, sr, aln, si, profile)))
    if not finals_info:
        result["warnings"].append("录音中没有韵母段，无法做发声态分析")
        return result

    # 逐韵母逐帧：谐波振幅、修正、SHR（valid 为 False 的帧屏蔽依赖共振峰的量）
    shr_best: dict = {}
    finals_rows: list[tuple[common.PhoneSeg, list[dict]]] = []
    invalid_stats: dict[str, int] = {}
    for si, final, vf in finals_info:
        rows = _measure_final(x, sr, final, vf, t_f0, f0_arr, float(pitch.dx), shr_best)
        finals_rows.append((final, rows))
        invalid_stats[final.label] = sum(1 for r in rows if r["_formant_invalid"])
        if not rows:
            result["warnings"].append(
                f"韵母 {final.label}（{vf.t0:.3f}–{vf.t1:.3f} s）内没有有声帧（F0 无值），"
                "谐波类指标为空")
            continue
        n_trunc = sum(1 for r in rows if not r["_complete"])
        if n_trunc:
            result["warnings"].append(
                f"韵母 {final.label} 有 {n_trunc} 帧的分析窗越过录音边界被截短，该处谐波振幅仅供参考")

    # HNR：全频带轨迹 + 分频带
    hnr = snd.to_harmonicity_cc(time_step=0.005, minimum_pitch=profile.f0_floor)
    hnr_t = np.asarray(hnr.xs(), dtype=float)
    hnr_v = np.asarray(hnr.values[0], dtype=float).copy()
    hnr_v[hnr_v <= -199.0] = np.nan      # Praat 用 -200 dB 表示无声段
    band_curves: dict[float, tuple[float, np.ndarray, float]] = {}
    for hi in HNR_BANDS:
        band = call(snd, "Filter (pass Hann band)", 0.0, hi, BAND_SMOOTHING)
        hb = band.to_harmonicity_cc(time_step=0.005, minimum_pitch=profile.f0_floor)
        bv = np.asarray(hb.values[0], dtype=float).copy()
        bv[bv <= -199.0] = np.nan
        band_curves[hi] = (float(hb.dx), np.asarray(hb.xs(), dtype=float), bv)

    def band_mean(hi: float, rows: list[dict]) -> float:
        dx, bt, bv = band_curves[hi]
        vals = [v for r in rows
                if math.isfinite(v := _nearest_value(bt, bv, r["time"], dx))]
        return float(np.mean(vals)) if vals else math.nan

    # CPP / CPPS：PowerCepstrogram 全录音；轨迹用 Praat 逐帧表（与 Get CPPS 同一套计算参数），
    # CPPS 的平滑用 Praat "Smooth" 完成，不自行拟合趋势线
    pg = call(snd, "To PowerCepstrogram", profile.f0_floor, CPP_TIME_STEP,
              CPP_MAX_FREQUENCY, CPP_PRE_EMPHASIS)
    mat = call(pg, "To Matrix")
    cep_t = np.asarray(mat.xs(), dtype=float)
    cep_q = np.asarray(mat.ys(), dtype=float)
    cep_db = common.db(np.asarray(mat.values, dtype=float))
    cpp = _cpp_table(pg, profile)
    pg_smooth = call(pg, "Smooth", CPPS_TIME_SMOOTH, CPPS_QUEFRENCY_SMOOTH)
    cpps_track = _cpp_table(pg_smooth, profile)
    cpps_praat = float(call(pg, "Get CPPS", "no", CPPS_TIME_SMOOTH, CPPS_QUEFRENCY_SMOOTH,
                            profile.f0_floor, profile.f0_ceiling, 0.05, "parabolic",
                            0.001, 0, "Exponential decay", "Robust"))

    # 把 HNR / CPP / CPPS 按最近帧填入分析帧
    for final, rows in finals_rows:
        for r in rows:
            r["HNR"] = _nearest_value(hnr_t, hnr_v, r["time"], float(hnr.dx))
            r["CPP"] = _nearest_value(cep_t, cpp, r["time"], float(mat.dx))
            r["CPPS"] = _nearest_value(cep_t, cpps_track, r["time"], float(mat.dx))
        n_missing = sum(1 for r in rows if not math.isfinite(r["CPP"]))
        if n_missing:
            result["warnings"].append(
                f"韵母 {final.label} 有 {n_missing} 个分析帧没有 CPP/CPPS 值"
                f"（PowerCepstrogram 首帧在 {cep_t[0]:.3f} s，"
                f"有效分析窗约 {CEPSTROGRAM_WINDOW_FACTOR / profile.f0_floor * 1000:.0f} ms）")

    # 声带周期、Jitter、Shimmer（逐韵母，区间同为 vowel_interval）
    pp = call(snd, "To PointProcess (periodic, cc)", profile.f0_floor, profile.f0_ceiling)
    n_pts = int(call(pp, "Get number of points"))
    pts = (np.asarray([call(pp, "Get time from index", i) for i in range(1, n_pts + 1)],
                      dtype=float) if n_pts else np.array([]))
    all_periods: list[tuple[float, float, float]] = []   # (周期中点, 周期秒, 峰值振幅)
    period_stats: dict[str, dict] = {}
    for _si, final, vf in finals_info:
        inside = pts[(pts >= vf.t0) & (pts <= vf.t1)] if n_pts else np.array([])
        t_mid, periods, amplitudes = [], [], []
        for a, b in zip(inside[:-1], inside[1:]):
            period = float(b - a)
            # 与 Praat Jitter 的周期有效性标准一致：跨越无声间隙的脉冲对不是声带周期
            if not PERIOD_FLOOR <= period <= PERIOD_CEILING:
                continue
            i0, i1 = round(a * sr), round(b * sr)
            if i1 <= i0:
                continue
            t_mid.append((a + b) / 2.0)
            periods.append(period)
            amplitudes.append(float(np.max(np.abs(x[i0:i1]))))
        all_periods += list(zip(t_mid, periods, amplitudes))
        n_periods = int(call(pp, "Get number of periods", vf.t0, vf.t1,
                             PERIOD_FLOOR, PERIOD_CEILING, MAX_PERIOD_FACTOR))
        try:
            jitter = float(call(pp, "Get jitter (local)", vf.t0, vf.t1,
                                PERIOD_FLOOR, PERIOD_CEILING, MAX_PERIOD_FACTOR))
        except Exception as exc:
            jitter = math.nan
            result["warnings"].append(f"韵母 {final.label} 的 Jitter 计算失败：{exc}")
        try:
            shimmer = float(call([snd, pp], "Get shimmer (local)", vf.t0, vf.t1,
                                 PERIOD_FLOOR, PERIOD_CEILING, MAX_PERIOD_FACTOR,
                                 MAX_AMPLITUDE_FACTOR))
        except Exception as exc:
            shimmer = math.nan
            result["warnings"].append(f"韵母 {final.label} 的 Shimmer 计算失败：{exc}")
        if n_periods < MIN_PERIODS_FOR_COMPARISON:
            result["warnings"].append(
                f"韵母 {final.label} 有效周期数 {n_periods}，短样本，"
                "Jitter/Shimmer 仅供参考，不宜与持续元音参考值比较")
        period_stats[final.label] = {"n_periods": n_periods, "jitter": jitter, "shimmer": shimmer}

    # 统计表（每韵母一行）
    stat_rows = []
    for (_, final, vf), (_, rows) in zip(finals_info, finals_rows):
        ps = period_stats[final.label]
        row: dict = {"final": final.label, "t0": round(final.t0, 4), "t1": round(final.t1, 4),
                     "ceiling_hz": vf.ceiling_hz,
                     "vowel_t0": round(vf.t0, 4), "vowel_start_source": vf.start_source,
                     "vowel_t1": round(vf.t1, 4), "vowel_end_source": vf.end_source,
                     "voiced_frames": len(rows),
                     "formant_invalid_frames": invalid_stats[final.label]}
        for key in ("F0", "H1", "H2", "H4", "A1", "A2", "A3", "H2k", "H5k",
                    "H1*", "H2*", "H4*", "A1*", "A2*", "A3*", "H2k*", *TILT_METRICS,
                    "HNR", "CPP", "CPPS", "SHR"):
            row[f"median_{key}"] = round(_finite_median([r[key] for r in rows]), 3)
        shr_vals = [r["SHR"] for r in rows if math.isfinite(r["SHR"])]
        row["max_SHR"] = round(float(np.max(shr_vals)), 4) if shr_vals else math.nan
        for hi in HNR_BANDS:
            row[f"HNR_below_{int(hi)}Hz"] = round(band_mean(hi, rows), 3)
        row["CPPS_praat_whole_recording"] = round(cpps_praat, 3)
        row["n_periods"] = ps["n_periods"]
        row["jitter_local"] = _csv_value(round(ps["jitter"], 5))
        row["shimmer_local"] = _csv_value(round(ps["shimmer"], 5))
        stat_rows.append(row)

    # 参数记录（Praat 实际网格以对象为准）
    result["params"].update({
        "frameStep_s": FRAME_STEP,
        "finalInterval": "各韵母的元音区间与共振峰均取自 formants.vowel_formants（内部用"
                         "common.vowel_interval）：起点为韵母内首个「有 F0 且非低能量」的帧"
                         "（跳过讯飞划入韵母的送气段，偏移 ≥ 10 ms 时生效），终点沿连续有效帧"
                         "延伸越过讯飞终点（允许 1 帧缺口、延伸 ≥ 10 ms）；两端来源记入 stats 表",
        "formants": {"source": "formants.vowel_formants（Burg，与 07 图同一份计算）",
                     "ceiling_hz": {final.label: vf.ceiling_hz for _, final, vf in finals_info}},
        "formantReliability": {
            "valid": "formants.vowel_formants 的 valid（非低能量且 F1–F3 非离群，"
                     "与 07 图的有效帧同一规则），本模块不重复计算",
            "masked": "valid 为 False 的帧，A1–A3、带 * 的共振峰修正值与 7 个派生差值记 NaN；"
                      "未修正 H1/H2/H4/H2k/H5k 不依赖共振峰，保留",
        },
        "analysisWindow": "以帧时刻为中心、3 个基音周期长的 Hann 窗（录音边界处截短，不补零）",
        "fftLengthRule": "不小于 4 倍窗长的 2 的整数次幂",
        "harmonicPeakSearch": "k·F0 ± 0.1·F0（k = 1, 2, 4）",
        "formantAmplitudeSearch": "F_i ± 10%·F_i",
        "H2kSearch": "2000 Hz ± F0/2", "H5kSearch": "5000 Hz ± F0/2",
        "bandwidth": "Burg 实测带宽，限制在 [30, 600] Hz；VoiceSauce 默认用公式带宽，此处实现不同",
        "correction": "Iseli & Alwan (2004)，采样率即录音采样率；H1*/H2*/H4*、A1*/A2* 用 F1、F2 修正，"
                      "A3*、H2k* 用 F1–F3 修正（H2k* 的修正频率取实际峰值频率），H5k 不修正",
        "hnr": {"command": "To Harmonicity (cc)", "timeStep": 0.005,
                "minimumPitch": profile.f0_floor, "actualDx": float(hnr.dx),
                "firstFrame_s": float(hnr_t[0])},
        "hnrBands_Hz": list(HNR_BANDS),
        "hnrBandFilter": "Filter (pass Hann band)，smoothing 100 Hz，分别求韵母有声帧均值",
        "cepstrogram": {"command": "To PowerCepstrogram", "pitchFloor": profile.f0_floor,
                        "timeStep": CPP_TIME_STEP, "maximumFrequency": CPP_MAX_FREQUENCY,
                        "preEmphasis": CPP_PRE_EMPHASIS,
                        "actualDx": float(mat.dx), "actualDy": float(mat.dy),
                        "firstFrame_s": float(mat.x1), "nx": int(mat.nx), "ny": int(mat.ny)},
        "cppTrack": {"command": "To Table (cepstral peak prominences)",
                     "peakSearchPitchRange_Hz": [profile.f0_floor, profile.f0_ceiling],
                     "tolerance": CPP_TOLERANCE, "interpolation": "parabolic",
                     "trendLineQuefrencyRange_s": [CPP_TREND_QUEFRENCY_MIN, 0.0],
                     "trendType": "Exponential decay", "fitMethod": "Robust",
                     "note": "逐帧 CPP，未经平滑；计算参数与整段 Get CPPS 一致"},
        "cppsTrack": {"smoothCommand": "Smooth", "timeWindow_s": CPPS_TIME_SMOOTH,
                      "quefrencyWindow_s": CPPS_QUEFRENCY_SMOOTH,
                      "note": "先对 PowerCepstrogram 平滑，再用同一命令逐帧取值"},
        "cppsPraatWholeRecording": {"value": round(cpps_praat, 3),
                                    "args": 'Get CPPS "no", 0.01, 0.001, f0_floor, f0_ceiling, '
                                            '0.05, "parabolic", 0.001, 0, "Exponential decay", "Robust"',
                                    "note": "整段录音的值，不只是韵母；与逐帧 CPPS 中位数口径不同"},
        "shrMethod": "简化谱法：SH=Σ幅度((k−0.5)·F0)、H=Σ幅度(k·F0)，k·F0<4000 Hz；"
                     "SHR 专用 6 基音周期 Hann 窗（主瓣半宽约 0.33·F0，次谐波位置在主瓣外）、"
                     f"FFT 补零至 {SHR_FFT_RATIO:.0f} 倍窗长、谐波与次谐波位置按 ±{SHR_TOL:.2f}·F0 "
                     "对称取峰；仿照 Sun (2002) 的定义思想，非原算法",
        "jitterShimmer": {"command": ["To PointProcess (periodic, cc)", "Get jitter (local)",
                                      "Get shimmer (local)"],
                          "shortestPeriod": PERIOD_FLOOR, "longestPeriod": PERIOD_CEILING,
                          "maximumPeriodFactor": MAX_PERIOD_FACTOR,
                          "maximumAmplitudeFactor": MAX_AMPLITUDE_FACTOR},
    })

    # 各图：单张失败只记 warning
    band_means_all = {hi: band_mean(hi, [r for _, rows in finals_rows for r in rows])
                      for hi in HNR_BANDS}
    plots = (
        ("15_harmonic_amplitudes.png",
         lambda: _plot_harmonic_amplitudes(aln, finals_rows, finals_info, out_dir, profile)),
        ("16_spectral_tilt.png",
         lambda: _plot_spectral_tilt(aln, finals_rows, finals_info, out_dir)),
        ("17_hnr.png", lambda: _plot_hnr(aln, out_dir, hnr_t, hnr_v, band_means_all, profile,
                                         finals_info, result["warnings"])),
        ("18_cepstrogram.png",
         lambda: _plot_cepstrogram(aln, out_dir, cep_t, cep_q, cep_db, cpp, cpps_track, profile)),
        ("19_shr.png",
         lambda: _plot_shr(aln, out_dir, finals_rows, finals_info, shr_best, x, sr)),
        ("20_periods.png",
         lambda: _plot_periods(aln, out_dir, all_periods, period_stats, finals_info)),
    )
    for name, make in plots:
        try:
            result["images"][name] = make()
        except Exception as exc:
            result["warnings"].append(f"图 {name} 生成失败：{exc}")

    # 输出表
    try:
        csv_dir = Path(out_dir) / "csv"
        ts_rows = [{k: _csv_value(r[k]) for k in TS_COLUMNS}
                   for _, rows in finals_rows for r in rows]
        result["tables"]["phonation_timeseries.csv"] = common.write_csv(
            ts_rows, csv_dir, "phonation_timeseries.csv")
        result["tables"]["phonation_stats.csv"] = common.write_csv(
            stat_rows, csv_dir, "phonation_stats.csv")
    except Exception as exc:
        result["warnings"].append(f"CSV 输出失败：{exc}")

    return result


# ---------------- 绘图 ----------------

def _series(finals_rows: list[tuple[common.PhoneSeg, list[dict]]], key: str
            ) -> tuple[np.ndarray, np.ndarray]:
    """所有韵母帧的时间与某指标的数组（按时间顺序；无声间隙处插入 NaN 使曲线断开）。"""
    t = np.asarray([r["time"] for _, rows in finals_rows for r in rows], dtype=float)
    v = np.asarray([r[key] for _, rows in finals_rows for r in rows], dtype=float)
    if len(t) > 1:
        idx = np.flatnonzero(np.diff(t) > 1.5 * FRAME_STEP)
        if idx.size:
            t = np.insert(t, idx + 1, t[idx + 1] - 1e-6)
            v = np.insert(v, idx + 1, np.nan)
    return t, v


def _plot_harmonic_amplitudes(aln: common.Alignment,
                              finals_rows: list[tuple[common.PhoneSeg, list[dict]]],
                              finals_info: list[tuple[int, common.PhoneSeg, VowelFormants]],
                              out_dir, profile: common.SpeakerProfile) -> Path:
    """图 15：修正前后的谐波振幅轨迹（H 系列实线，A 系列带圆点，未修正值同色浅虚线）。"""
    from matplotlib.lines import Line2D

    plt = common.setup_matplotlib()
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for i, ((star, raw), color) in enumerate(zip(HARMONIC_METRICS, colors)):
        t, v_star = _series(finals_rows, star)
        _, v_raw = _series(finals_rows, raw)
        if i >= 3:   # A 系列：空心圆标记，避免与数值相近的 H 系列实线混在一起
            style = dict(marker="o", ms=3.2, markerfacecolor="white",
                         markeredgecolor=color, markevery=3)
        else:        # H 系列：实心方标记，错开取样帧
            style = dict(marker="s", ms=2.6, markerfacecolor=color, markevery=(1, 3))
        ax.plot(t, v_star, color=color, lw=1.5, label=star, **style)
        ax.plot(t, v_raw, color=color, lw=1.0, ls="--", alpha=0.45)
    _draw_effective_end(ax, finals_info)
    handles, labels = ax.get_legend_handles_labels()
    handles.append(Line2D([], [], color="#666666", ls="--", lw=1.0, label="虚线 = 未修正值"))
    ax.legend(handles=handles, fontsize=8, loc="center left", bbox_to_anchor=(1.01, 0.5))
    ax.set_ylabel("振幅 (dB)")
    fig.suptitle(f"{aln.file}　谐波振幅（Hann 窗 3 基音周期，帧移 5 ms，Iseli & Alwan 修正）",
                 y=0.98)
    common.set_time_axis(ax, aln)
    common.draw_boundaries(ax, aln)
    notes = ["实线（A 系列带圆点）：共振峰修正值；同色虚线：未修正值。只画韵母内有声帧"
             "（至有效终点），共振峰不可靠帧留空。"]
    if (end_note := _effective_end_note(finals_info)):
        notes.append(end_note + "；尾段弱能量帧的修正值仅供参考")
    fig.text(0.5, 0.005, "\n".join(notes), ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    return common.save_fig(fig, out_dir, "15_harmonic_amplitudes")


def _plot_spectral_tilt(aln: common.Alignment,
                        finals_rows: list[tuple[common.PhoneSeg, list[dict]]],
                        finals_info: list[tuple[int, common.PhoneSeg, VowelFormants]],
                        out_dir) -> Path:
    """图 16：七个谱倾斜派生指标，按谐波间差值 / 共振峰幅度差 / 谱倾斜分三个面板。

    图例集中在坐标区外右侧，避免尖峰顶到面板内的图例盒。
    """
    plt = common.setup_matplotlib()
    fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    panel_titles = ("谐波间差值", "第一谐波与共振峰附近谐波的差值", "谱倾斜")
    legend_handles = []
    for ax, keys, title in zip(axes, TILT_PANELS, panel_titles):
        for key, color in zip(keys, colors):
            t, v = _series(finals_rows, key)
            ax.plot(t, v, color=color, lw=1.3, label=key)
        ax.axhline(0.0, color="#999999", lw=0.6)
        ax.set_ylabel("幅度差 (dB)")
        ax.set_title(title, fontsize=10, loc="left")
        _draw_effective_end(ax, finals_info)
        legend_handles += ax.get_legend_handles_labels()[0]
        common.draw_boundaries(ax, aln, labels=False)
    common.set_time_axis(axes[-1], aln)
    common.draw_boundaries(axes[-1], aln)
    fig.legend(handles=legend_handles, fontsize=8, loc="center right",
               bbox_to_anchor=(0.995, 0.5))
    fig.suptitle(f"{aln.file}　谱倾斜派生指标", y=0.99)
    notes = ["只画韵母内有声帧（至有效终点），共振峰不可靠帧留空。注意：H1*–H2* 不是"
             "声门开放程度的直接测量，不能脱离其他指标独立下结论（方案 §6.1）。"]
    if (end_note := _effective_end_note(finals_info)):
        notes.append(end_note + "；尾段弱能量帧的修正值仅供参考")
    fig.text(0.5, 0.005, "\n".join(notes), ha="center", fontsize=9)
    fig.tight_layout(rect=(0.02, 0.03, 0.86, 0.97))
    return common.save_fig(fig, out_dir, "16_spectral_tilt")


def _plot_hnr(aln: common.Alignment, out_dir, hnr_t: np.ndarray, hnr_v: np.ndarray,
              band_means: dict[float, float], profile: common.SpeakerProfile,
              finals_info: list[tuple[int, common.PhoneSeg, VowelFormants]],
              warnings: list[str]) -> Path:
    """图 17：左侧全频带 HNR 轨迹（橙色点线为发生延伸的韵母有效终点），右侧分频带柱状图。"""
    plt = common.setup_matplotlib()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5),
                                   gridspec_kw={"width_ratios": [2.2, 1]})
    ax1.plot(hnr_t, hnr_v, color="#1f77b4", lw=1.3)
    ax1.set_ylabel("HNR (dB)")
    ax1.set_title("全频带 HNR 轨迹（Harmonicity cc）", pad=18)
    common.set_time_axis(ax1, aln)
    common.draw_boundaries(ax1, aln)
    common.mark_edge_regions(ax1, aln.duration,
                             CEPSTROGRAM_WINDOW_FACTOR / profile.f0_floor)
    _draw_effective_end(ax1, finals_info)
    tail_notes = []
    for _, final, vf in finals_info:
        inside = (hnr_t >= vf.t0) & (hnr_t <= vf.t1)
        finite_t = hnr_t[inside & np.isfinite(hnr_v)]
        if finite_t.size and vf.t1 - finite_t[-1] > 0.015:
            tail_notes.append(
                f"韵母 {final.label}：HNR 到 {finite_t[-1]:.3f} s 为止，"
                f"有效终点 {vf.t1:.3f} s 之前的弱尾段被 Praat Harmonicity 的静音阈值判为无声（无值）")
    for note in tail_notes:
        warnings.append(note)
    if (end_note := _effective_end_note(finals_info)):
        tail_notes.append(end_note)

    means = [band_means[hi] for hi in HNR_BANDS]
    ax2.bar(range(len(HNR_BANDS)), [m if math.isfinite(m) else 0.0 for m in means],
            color="#1f77b4", width=0.6)
    for i, m in enumerate(means):
        if math.isfinite(m):
            ax2.text(i, m, f"{m:.1f}", ha="center", va="bottom", fontsize=8)
    ax2.set_xticks(range(len(HNR_BANDS)), [f"0–{int(hi)}" for hi in HNR_BANDS])
    ax2.set_xlabel("频带 (Hz)")
    ax2.set_ylabel("韵母有声帧 HNR 均值 (dB)")
    ax2.set_title("分频带 HNR")
    fig.suptitle(f"{aln.file}　HNR（minimum pitch {profile.f0_floor:.0f} Hz，分频带平滑 100 Hz，"
                 "橙色点线 = 有效终点（有声延伸））", y=0.98)
    if tail_notes:
        fig.text(0.5, 0.005, "；".join(tail_notes), ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.02 if tail_notes else 0, 1, 0.96))
    return common.save_fig(fig, out_dir, "17_hnr")


def _plot_cepstrogram(aln: common.Alignment, out_dir, cep_t: np.ndarray, cep_q: np.ndarray,
                      cep_db: np.ndarray, cpp: np.ndarray, cpps_track: np.ndarray,
                      profile: common.SpeakerProfile) -> Path:
    """图 18：上为功率倒谱热力图（quefrency 0–20 ms），下为 CPP/CPPS 轨迹。

    两面板共用色标轴（等宽对齐）；色标范围按 quefrency ≥ 1 ms 的部分确定，
    避免 0 倒频条带占满色标。
    """
    plt = common.setup_matplotlib()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True, layout="constrained",
                                   gridspec_kw={"height_ratios": [1.8, 1]})
    vmax = float(np.nanmax(cep_db[cep_q >= 0.001, :]))
    mesh = ax1.pcolormesh(cep_t, cep_q * 1000.0, cep_db, shading="nearest", cmap="Greys",
                          vmin=vmax - 50.0, vmax=vmax, rasterized=True)
    fig.colorbar(mesh, ax=[ax1, ax2], label="功率倒谱 (dB)", pad=0.01)
    ax1.set_ylim(0.0, 20.0)
    ax1.set_ylabel("倒频 (ms)")
    common.mark_edge_regions(ax1, aln.duration,
                             CEPSTROGRAM_WINDOW_FACTOR / profile.f0_floor)
    common.draw_boundaries(ax1, aln, labels=False)

    ax2.plot(cep_t, cpp, color="#1f77b4", lw=1.2, label="CPP")
    ax2.plot(cep_t, cpps_track, color="#d62728", lw=1.2, label="CPPS")
    ax2.set_ylabel("CPP / CPPS (dB)")
    ax2.legend(fontsize=8, loc="best")
    common.set_time_axis(ax2, aln)
    common.draw_boundaries(ax2, aln)
    fig.suptitle(f"{aln.file}　倒谱图与 CPP/CPPS（pitch floor {profile.f0_floor:.0f} Hz，"
                 f"预加重 {CPP_PRE_EMPHASIS:.0f} Hz）")
    return common.save_fig(fig, out_dir, "18_cepstrogram")


def _plot_shr(aln: common.Alignment, out_dir,
              finals_rows: list[tuple[common.PhoneSeg, list[dict]]],
              finals_info: list[tuple[int, common.PhoneSeg, VowelFormants]], shr_best: dict,
              x: np.ndarray, sr: int) -> Path:
    """图 19：SHR 轨迹、最大帧频谱切片（标谐波与次谐波位置）、局部波形放大。"""
    if not shr_best:
        raise ValueError("没有可用的 SHR 帧（韵母内无有声帧）")
    plt = common.setup_matplotlib()
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(9, 9),
                                        gridspec_kw={"height_ratios": [1, 1.3, 1]})
    t, shr = _series(finals_rows, "SHR")
    ax1.plot(t, shr, color="#1f77b4", lw=1.4, marker="o", ms=2.5)
    ax1.set_ylabel("SHR（SH/H，线性比）")
    ax1.set_title("SHR 轨迹（韵母有声帧）", pad=18)
    common.set_time_axis(ax1, aln)
    common.draw_boundaries(ax1, aln)
    _draw_effective_end(ax1, finals_info)

    t_best, f0_best = shr_best["t"], shr_best["f0"]
    n_harm = shr_best["n_harm"]
    ax2.plot(shr_best["freqs"], shr_best["spec_db"], color="#333333", lw=0.8)
    for m in range(1, n_harm + 1):
        ax2.axvline(m * f0_best, color="#1f77b4", lw=0.8)
        ax2.axvline((m - 0.5) * f0_best, color="#d62728", ls="--", lw=0.7)
    ax2.set_xlim(0.0, SHR_HARMONIC_LIMIT)
    spec_top = float(np.nanmax(shr_best["spec_db"]))
    ax2.set_ylim(spec_top - 60.0, spec_top + 6.0)   # 按数据收紧，只显示峰附近 60 dB
    ax2.set_xlabel("频率 (Hz)")
    ax2.set_ylabel("振幅 (dB)")
    ax2.set_title(f"SHR 最大帧的频谱（t = {t_best:.3f} s，F0 = {f0_best:.1f} Hz，"
                  f"SHR = {shr_best['shr']:.3f}）")
    from matplotlib.lines import Line2D
    ax2.legend(handles=[Line2D([], [], color="#1f77b4", label="谐波 k·F0"),
                        Line2D([], [], color="#d62728", ls="--", label="次谐波 (k−0.5)·F0")],
               fontsize=8, loc="upper right")

    period = 1.0 / f0_best
    i0 = max(round((t_best - 3.0 * period) * sr), 0)
    i1 = min(round((t_best + 3.0 * period) * sr), len(x))
    ax3.plot(np.arange(i0, i1) / sr, x[i0:i1], color="#333333", lw=0.9)
    ax3.axvline(t_best, color="#999999", ls=":", lw=0.9)
    ax3.set_xlabel("时间 (s)")
    ax3.set_ylabel("振幅")
    ax3.set_title(f"最大 SHR 时刻前后各 3 个周期的波形（{t_best - 3 * period:.3f}–"
                  f"{t_best + 3 * period:.3f} s）")
    fig.suptitle(f"{aln.file}　次谐波—谐波比 SHR", y=0.995)
    notes = ["SHR 为简化谱法，仿照 Sun (2002) 的定义思想，非原算法；SH/H 为线性幅度之比。"]
    if (end_note := _effective_end_note(finals_info)):
        notes.append(end_note)
    fig.text(0.5, 0.005, "\n".join(notes), ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.025, 1, 0.97))
    return common.save_fig(fig, out_dir, "19_shr")


def _plot_periods(aln: common.Alignment, out_dir,
                  all_periods: list[tuple[float, float, float]],
                  period_stats: dict[str, dict],
                  finals_info: list[tuple[int, common.PhoneSeg, VowelFormants]]) -> Path:
    """图 20：上为逐周期长度，下为逐周期峰值振幅；文本框给出 Jitter/Shimmer/周期数。"""
    if not all_periods:
        raise ValueError("韵母内没有可用的声带周期")
    plt = common.setup_matplotlib()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    t_mid = np.asarray([p[0] for p in all_periods])
    periods_ms = np.asarray([p[1] for p in all_periods]) * 1000.0
    amplitudes = np.asarray([p[2] for p in all_periods])
    ax1.plot(t_mid, periods_ms, color="#1f77b4", lw=1.0, marker="o", ms=3)
    ax1.set_ylabel("周期长度 (ms)")
    _draw_effective_end(ax1, finals_info)
    ax2.plot(t_mid, amplitudes, color="#d62728", lw=1.0, marker="o", ms=3)
    ax2.set_ylabel("周期峰值振幅")
    lines = []
    for label, ps in period_stats.items():
        jitter = f"{ps['jitter'] * 100:.2f}%" if math.isfinite(ps["jitter"]) else "—"
        shimmer = f"{ps['shimmer'] * 100:.2f}%" if math.isfinite(ps["shimmer"]) else "—"
        lines.append(f"韵母 {label}：有效周期 {ps['n_periods']}，jitter {jitter}，shimmer {shimmer}")
    ax1.text(0.98, 0.95, "\n".join(lines), transform=ax1.transAxes, ha="right", va="top",
             fontsize=8, bbox=dict(facecolor="white", edgecolor="#999999", alpha=0.8, pad=3))
    common.set_time_axis(ax2, aln)
    common.draw_boundaries(ax1, aln, labels=False)
    common.draw_boundaries(ax2, aln)
    fig.suptitle(f"{aln.file}　声带周期、Jitter 与 Shimmer（逐周期测量，仅韵母有效区间内）",
                 y=0.995)
    if (end_note := _effective_end_note(finals_info)):
        fig.text(0.5, 0.005, end_note, ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.02 if end_note else 0, 1, 0.97))
    return common.save_fig(fig, out_dir, "20_periods")
