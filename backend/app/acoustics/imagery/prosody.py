"""韵律层基础图：波形、F0 与声调、强度（方案 §5、§7.1、§9 的 F0 部分、§10 B/C）。

分析与输出的统一约定见 common.py。本模块要点：
- F0 用 Praat "To Pitch (filtered ac)"（common.pitch_filtered_ac），无声帧记 NaN，
  不跨无声段插值（方案 §5.3）；另以 50–600 Hz 宽范围复测一遍做倍频/半频检查（方案 §5.1 / §9），
  并按「相邻有声帧半音差切段」检测局部倍频/半频跳变，疑似段不计入声调统计；
- 半音 12·log2(F0/F_ref)：F_ref 优先取 context["f0_ref_hz"]（集成时按发音人统计的语料中位数），
  否则退回本文件 F0 中位数，并在 warnings 中注明；
- 声调：每个音节有效有声区间的 11 点归一化（P0–P10）、dF0/dt 与转折点（方案 §5.2 图 C/D）；
  区间右端用韵母有效终点（common.vowel_interval），起点为音节内第一个有声帧（含浊声母）；
- 强度：Praat To Intensity（相对 dB，未校准）与 25 ms 短时 RMS（dBFS）。
DbScales 只约束频谱类图像的跨样本统一标尺；本模块的强度轴未校准，不参与该标尺，故不使用。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import common

F0_TIME_STEP = 0.005                          # s（方案 §5.1）
F0_WIDE_FLOOR, F0_WIDE_CEILING = 50.0, 600.0  # 倍频/半频检查的宽范围（方案 §5.1）
OCTAVE_MEDIAN_RANGE = (0.6, 1.67)             # 两次 F0 共同有声帧中位数之比的可接受范围
OCTAVE_TOL_ST = 1.0                           # 逐帧比值判为倍频/半频的容差（距 ±12 半音）
OCTAVE_MIN_FRAMES = 3                         # 分歧帧触发告警的最少帧数
OCTAVE_MIN_FRACTION = 0.10                    # 分歧帧触发告警的最低占比
OCTAVE_JUMP_ST = 7.0                          # 相邻有声帧半音差 ≥ 该值处切段（跨缺口也比较）
OCTAVE_BAND_ST = (9.0, 15.0)                  # 段间差落在 12 ± 3 st 判为倍频/半频
OCTAVE_LOCAL_FRAMES = 5                       # 边界局部比较的窗口帧数
NORM_POSITIONS = np.linspace(0.0, 1.0, 11)    # P0–P10（方案 §5.2 图 C）
SMOOTH_WINDOW, SMOOTH_ORDER = 9, 2            # 半音域 Savitzky-Golay 轻度平滑（9 帧 ≈ 45 ms）
SMOOTH_MIN_FRAMES = 5                         # 段长不足 5 帧不平滑、不求导
TURN_PROMINENCE_ST = 0.5                      # 转折点突出度阈值（方案 §5.2 图 D）
INTENSITY_TIME_STEP = 0.005                   # s
INTENSITY_SPAN_DB = 60.0                      # 06 图双纵轴的共同 dB 跨度（下限 = 数据最大值 − 60）
RMS_WIN_SEC, RMS_STEP_SEC = 0.025, 0.005      # 短时 RMS 的窗长与步长
BOUNDARY_HALF_WIN = 0.1                       # 音节交界细节图的时间半径（方案 §5.3）


# ---------------- 数值工具 ----------------

def _fmt(value, nd: int):
    """CSV 单元格：None/NaN/inf 写为空字符串，其余按 nd 位小数。"""
    if value is None:
        return ""
    v = float(value)
    return round(v, nd) if np.isfinite(v) else ""


def _bool_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """布尔序列中连续 True 游程的闭区间下标 [(i0, i1), ...]。"""
    runs = []
    i, n = 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    return runs


def _align_to_grid(t_src: np.ndarray, v_src: np.ndarray, t_dst: np.ndarray,
                   tol: float) -> np.ndarray:
    """把 (t_src, v_src) 的最近帧值对齐到 t_dst 网格；时间差超过 tol 的位置记 NaN。"""
    idx = np.clip(np.searchsorted(t_src, t_dst), 1, len(t_src) - 1)
    idx = np.where(np.abs(t_src[idx - 1] - t_dst) <= np.abs(t_src[idx] - t_dst), idx - 1, idx)
    ok = np.abs(t_src[idx] - t_dst) <= tol
    return np.where(ok, v_src[idx], np.nan)


def _octave_stats(f0: np.ndarray, f0_wide: np.ndarray) -> dict:
    """主趟与宽范围趟在共同有声帧上的倍频/半频统计（方案 §5.1 / §9）。"""
    both = ~np.isnan(f0) & ~np.isnan(f0_wide)
    idx = np.where(both)[0]
    stat = {"n_common": int(idx.size), "median_ratio": None, "n_octave": 0,
            "fraction": 0.0, "sus_frames": idx[:0]}
    if idx.size == 0:
        return stat
    ratio = f0_wide[idx] / f0[idx]
    dist_st = 12.0 * np.log2(ratio)
    sus = np.abs(np.abs(dist_st) - 12.0) <= OCTAVE_TOL_ST   # 比值接近 2 或 0.5
    stat.update(median_ratio=float(np.median(ratio)), n_octave=int(sus.sum()),
                fraction=float(sus.mean()), sus_frames=idx[sus])
    return stat


def _octave_conclusion(stat: dict) -> str:
    """倍频/半频检查的结论文本（供 warnings 与 tone_stats.csv 共用）。"""
    if stat["n_common"] == 0:
        return "无共同有声帧"
    med = stat["median_ratio"]
    if med < OCTAVE_MEDIAN_RANGE[0] or med > OCTAVE_MEDIAN_RANGE[1]:
        return f"中位数之比 {med:.2f} 超出 [{OCTAVE_MEDIAN_RANGE[0]}, {OCTAVE_MEDIAN_RANGE[1]}]"
    if stat["n_octave"] >= OCTAVE_MIN_FRAMES and stat["fraction"] >= OCTAVE_MIN_FRACTION:
        return f"倍频/半频分歧 {stat['n_octave']} 帧（占 {stat['fraction']:.0%}）"
    return "正常"


def _octave_jumps(t: np.ndarray, f0: np.ndarray,
                  f_ref: float) -> tuple[np.ndarray, list[dict]]:
    """按相邻有声帧半音差切段，检测局部倍频/半频跳变（方案 §5.1 / §9）。

    相邻有声帧（跨无声缺口也比较）半音差 ≥ OCTAVE_JUMP_ST 处切段；帧数最多的段为主段，
    从主段向两侧逐段比较：与最近有效段（参照段）的中位半音差 ≥ OCTAVE_JUMP_ST 即判为疑似，
    差值落在 12 ± 3 st 为倍频/半频，否则为非整八度（嘎裂周期加倍等）。疑似段不做 ×2/÷2
    校正，只返回逐帧标志与段信息，由调用方在统计中记 NaN 并在图上标出。
    """
    idx = np.flatnonzero(np.isfinite(f0))
    sus = np.zeros(len(f0), dtype=bool)
    if idx.size < 2:
        return sus, []
    st = _semitone(f0, f_ref)
    jump = np.flatnonzero(np.abs(np.diff(st[idx])) >= OCTAVE_JUMP_ST)
    bounds = np.concatenate(([0], jump + 1, [idx.size]))
    segs = [(int(bounds[i]), int(bounds[i + 1])) for i in range(len(bounds) - 1)]
    med = [float(np.median(st[idx[a:b]])) for a, b in segs]
    main = max(range(len(segs)), key=lambda i: segs[i][1] - segs[i][0])
    seg_info: list[dict] = []

    def mark(seg_i: int, kind: str, delta: float) -> None:
        a, b = segs[seg_i]
        sus[idx[a:b]] = True
        seg_info.append({"type": kind, "t0": float(t[idx[a]]), "t1": float(t[idx[b - 1]]),
                         "n_frames": int(b - a), "delta_st": round(delta, 2)})

    # 边界局部比较：长下降段的中位数可能恰好落在孤岛电平附近（段中位数比较会漏判），
    # 直接比较每个切段边界两侧 OCTAVE_LOCAL_FRAMES 帧的局部中位数，帧数少的一侧判为疑似
    for i in range(len(segs) - 1):
        b = segs[i][1]
        left = st[idx[max(segs[i][0], b - OCTAVE_LOCAL_FRAMES):b]]
        right = st[idx[b:min(segs[i + 1][1], b + OCTAVE_LOCAL_FRAMES)]]
        if left.size and right.size:
            delta = float(np.median(right) - np.median(left))
            if abs(delta) >= OCTAVE_JUMP_ST:
                kind = "疑似倍频/半频" if OCTAVE_BAND_ST[0] <= abs(delta) <= OCTAVE_BAND_ST[1] \
                    else "疑似跳变（非整八度）"
                smaller = i if segs[i][1] - segs[i][0] <= segs[i + 1][1] - segs[i + 1][0] else i + 1
                mark(smaller, kind, delta)

    # 段中位数比较：从主段向两侧游走，捕捉边界差不明显但整体错位的段；
    # 已判疑似的段不更新参照（否则半频段的参照会把正常段错判为跳变）
    for step in (-1, 1):
        ref_med, j = med[main], main
        while 0 <= j + step < len(segs):
            k = j + step
            delta = med[k] - ref_med
            if abs(delta) >= OCTAVE_JUMP_ST:
                if not sus[idx[segs[k][0]:segs[k][1]]].any():
                    kind = ("疑似倍频/半频" if OCTAVE_BAND_ST[0] <= abs(delta) <= OCTAVE_BAND_ST[1]
                            else "疑似跳变（非整八度）")
                    mark(k, kind, delta)
            else:
                ref_med = med[k]   # 有效段成为新的参照
            j = k
    seg_info.sort(key=lambda d: d["t0"])
    return sus, seg_info


def _semitone(f0_hz: np.ndarray, f_ref: float) -> np.ndarray:
    """Hz → 半音（12·log2(F0/F_ref)）；无声帧保持 NaN。"""
    with np.errstate(invalid="ignore", divide="ignore"):
        return 12.0 * np.log2(f0_hz / f_ref)


def _smooth_and_derivative(t: np.ndarray, f0_st: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """连续有声段内：半音域 Savitzky-Golay 轻度平滑后求 dF0/dt（st/s）；段外 NaN。

    平滑窗 SMOOTH_WINDOW 帧（约 45 ms）；段长不足时降为不小于 SMOOTH_MIN_FRAMES 的最大
    奇数窗；段长不足 SMOOTH_MIN_FRAMES 帧时不平滑、不求导。疑似倍频/半频帧已先置 NaN，
    段在跳变处断开，不跨缺口连线或求导。
    """
    from scipy.signal import savgol_filter

    st_sm = np.full_like(f0_st, np.nan)
    d_st = np.full_like(f0_st, np.nan)
    for i0, i1 in _bool_runs(~np.isnan(f0_st)):
        n = i1 - i0 + 1
        seg = f0_st[i0:i1 + 1]
        if n >= SMOOTH_MIN_FRAMES:
            win = min(SMOOTH_WINDOW, n if n % 2 == 1 else n - 1)
            seg = savgol_filter(seg, win, SMOOTH_ORDER)
            d_st[i0:i1 + 1] = np.gradient(seg, t[i0:i1 + 1])
        st_sm[i0:i1 + 1] = seg
    return st_sm, d_st


def _turning_points(t: np.ndarray, f0: np.ndarray, st_sm: np.ndarray) -> list[dict]:
    """平滑半音曲线上的转折点：局部极值且突出度 ≥ TURN_PROMINENCE_ST（方案 §5.2 图 D）。"""
    from scipy.signal import find_peaks

    pts: list[dict] = []
    for i0, i1 in _bool_runs(~np.isnan(st_sm)):
        seg = st_sm[i0:i1 + 1]
        for sign, kind in ((1.0, "max"), (-1.0, "min")):
            peaks, _ = find_peaks(sign * seg, prominence=TURN_PROMINENCE_ST)
            for k in peaks:
                g = i0 + k
                pts.append({"type": kind, "t": float(t[g]),
                            "hz": float(f0[g]), "st": float(st_sm[g])})
    pts.sort(key=lambda p: p["t"])
    return pts


def _missing_regions(t: np.ndarray, f0: np.ndarray, i0: int, i1: int) -> list[list[float]]:
    """[i0, i1] 帧区间内的无声缺口 [[起, 止], ...]（秒，帧中心时间；方案 §5.3 不跨无声段）。"""
    gaps: list[list[float]] = []
    bad = np.isnan(f0[i0:i1 + 1])
    for a, b in _bool_runs(bad):
        gaps.append([round(float(t[i0 + a]), 4), round(float(t[i0 + b]), 4)])
    return gaps


# ---------------- 音节级统计 ----------------

def _syllable_f0(syl: common.SyllableSeg, t: np.ndarray, f0: np.ndarray,
                 f_ref: float, t_end: float) -> dict:
    """音节范围内的有声统计与 11 点归一化（方案 §5.2 图 C）。

    有效有声区间 = [音节内第一个有声帧（含 m/n/l 等浊声母）, t_end（韵母有效终点，
    common.vowel_interval 的 t1）] 内的最后一个有声帧；P0–P10 在该区间内等间隔取点，
    只在相邻两帧都有声时线性插值，否则记 NaN（不跨无声段插值，嘎裂/漏检/疑似倍频帧均为缺失）。
    """
    inside = np.where((t >= syl.t0 - 1e-9) & (t <= t_end + 1e-9))[0]
    info = {"voiced": np.array([], dtype=int), "voiced_ratio": float("nan"),
            "p_t": np.full(11, np.nan), "p_hz": np.full(11, np.nan),
            "p_st": np.full(11, np.nan)}
    if inside.size == 0:
        return info
    voiced = inside[~np.isnan(f0[inside])]
    info["voiced_ratio"] = float(voiced.size / inside.size)
    if voiced.size == 0:
        return info
    info["voiced"] = voiced
    t0v, t1v = float(t[voiced[0]]), float(t[voiced[-1]])
    p_t = t0v + NORM_POSITIONS * (t1v - t0v)
    p_hz = np.interp(p_t, t, f0)   # 任一相邻帧无声 → NaN（np.interp 对 NaN 逐点传播）
    info.update(p_t=p_t, p_hz=p_hz, p_st=_semitone(p_hz, f_ref))
    return info


def _tone_row(syl: common.SyllableSeg, info: dict, t: np.ndarray, f0: np.ndarray,
              f0_st: np.ndarray, f0_wide: np.ndarray, turning: list[dict],
              sus_mask: np.ndarray) -> dict:
    """tone_stats.csv 的一行（方案 §5.2 参数表、§10 C）；f0 为剔除疑似倍频帧后的序列。"""
    row: dict = {"syllable": syl.symbol,
                 "tone": syl.tone if syl.tone is not None else "",
                 "t0": _fmt(syl.t0, 4), "t1": _fmt(syl.t1, 4),
                 "vowel_t1": _fmt(info["final_t1_effective"], 4),
                 "vowel_end_source": info["final_end_source"],
                 "voiced_t0": _fmt(info["p_t"][0], 4), "voiced_t1": _fmt(info["p_t"][10], 4),
                 "voiced_ratio": _fmt(info["voiced_ratio"], 3)}
    for q in range(11):
        row[f"p{q}_t"] = _fmt(info["p_t"][q], 4)
        row[f"p{q}_hz"] = _fmt(info["p_hz"][q], 2)
        row[f"p{q}_st"] = _fmt(info["p_st"][q], 3)
    v = info["voiced"]
    if v.size == 0:
        for key in ("onset", "offset", "mean", "median", "min", "max", "range"):
            row[f"{key}_hz"] = ""
            row[f"{key}_st"] = ""
        row.update(slope_st_per_s="", n_turning_points=0, turning_points="[]",
                   missing_regions="[]", octave_check="音节内无有声帧")
        return row
    hz, stv = f0[v], f0_st[v]
    for key, val_hz, val_st in (
            ("onset", hz[0], stv[0]), ("offset", hz[-1], stv[-1]),
            ("mean", float(np.mean(hz)), float(np.mean(stv))),
            ("median", float(np.median(hz)), float(np.median(stv))),
            ("min", float(np.min(hz)), float(np.min(stv))),
            ("max", float(np.max(hz)), float(np.max(stv)))):
        row[f"{key}_hz"] = _fmt(val_hz, 2)
        row[f"{key}_st"] = _fmt(val_st, 3)
    row["range_hz"] = _fmt(float(np.max(hz) - np.min(hz)), 2)
    row["range_st"] = _fmt(float(np.max(stv) - np.min(stv)), 3)
    # 有声区间的整体斜率：对半音做线性回归（跳过区间内的无声帧）
    span = np.arange(v[0], v[-1] + 1)
    m = ~np.isnan(f0_st[span])
    row["slope_st_per_s"] = (_fmt(float(np.polyfit(t[span][m], f0_st[span][m], 1)[0]), 2)
                             if int(m.sum()) >= 2 else "")
    # 转折点限制在有效有声区间内
    tp = [p for p in turning
          if info["p_t"][0] - 1e-9 <= p["t"] <= info["p_t"][10] + 1e-9]
    row["n_turning_points"] = len(tp)
    row["turning_points"] = json.dumps(
        [{**p, "t": round(p["t"], 4), "hz": round(p["hz"], 2), "st": round(p["st"], 3)}
         for p in tp], ensure_ascii=False)
    row["missing_regions"] = json.dumps(
        _missing_regions(t, f0, int(v[0]), int(v[-1])), ensure_ascii=False)
    n_sus = int(np.count_nonzero(
        sus_mask & (t >= syl.t0 - 1e-9) & (t <= info["final_t1_effective"] + 1e-9)))
    row["octave_check"] = (f"疑似倍频/半频 {n_sus} 帧（未计入统计）" if n_sus
                           else _octave_conclusion(_octave_stats(f0[v], f0_wide[v])))
    return row


# ---------------- 绘图 ----------------

def _plot_waveform(x: np.ndarray, sr: int, aln: common.Alignment, out_dir: Path) -> Path:
    plt = common.setup_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(np.arange(x.size) / sr, x, color="#1f77b4", lw=0.4)
    peak_db = 20.0 * np.log10(float(np.max(np.abs(x))))
    ax.set_ylim(-1.0, 1.0)
    ax.set_ylabel("振幅（左声道）")
    common.set_time_axis(ax, aln)
    common.draw_boundaries(ax, aln)
    ax.set_title(f"{aln.file} 波形（左声道）｜峰值 {peak_db:.1f} dBFS，文件已做峰值归一化")
    fig.tight_layout()
    return common.save_fig(fig, out_dir, "01_waveform.png")


def _legend_outside(fig, ax) -> None:
    """图例移到坐标轴外右侧（constrained layout 会为其留出空间）。"""
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="outside center right", fontsize=9)


def _plot_f0(aln: common.Alignment, t: np.ndarray, f0: np.ndarray, f0_raw: np.ndarray,
             sus_mask: np.ndarray, f0_wide: np.ndarray, oct_stat: dict,
             syll_infos: list[dict], profile: common.SpeakerProfile,
             pitch, out_dir: Path) -> Path:
    plt = common.setup_matplotlib()
    from matplotlib.transforms import blended_transform_factory

    fig, ax = plt.subplots(figsize=(10, 4.2), layout="constrained")
    ax.plot(t, f0, "-", color="#1f77b4", lw=1.4,
            label="F0（filtered ac，无声段留空）")
    if sus_mask.any():
        ax.plot(t[sus_mask], f0_raw[sus_mask], "x", ms=5, color="#8c8c8c",
                label="疑似倍频/半频（未计入统计）")
    sus = oct_stat["sus_frames"]
    if sus.size:
        ax.plot(t[sus], f0_wide[sus], "o", ms=4, mfc="#ffb3a0", mec="#ff7043",
                label="宽范围（50–600 Hz）倍频/半频分歧帧")
    trans = blended_transform_factory(ax.transData, ax.transAxes)
    first, first_ext, first_miss = True, True, True
    for info in syll_infos:
        if info["voiced"].size:
            ax.plot(info["p_t"], info["p_hz"], "o", ms=5, mfc="none", mec="#222222",
                    label="P0–P10（音节有效有声区间）" if first else None)
            first = False
            miss = np.isnan(info["p_hz"])
            if miss.any():
                # 缺失取样位置在横轴底部画空心三角占位（方案 §5.3：嘎裂/漏检不插值）
                ax.plot(info["p_t"][miss], np.full(int(miss.sum()), 0.04), "v", ms=7,
                        mfc="none", mec="#8c8c8c", transform=trans,
                        label="缺失取样点（未插值）" if first_miss else None)
                first_miss = False
        if info["final_end_source"] == "voicing_extended":
            ax.axvline(info["final_t1_effective"], color="#e65100", ls=":", lw=1.4,
                       label="有效终点（有声延伸）" if first_ext else None)
            first_ext = False
    for s in aln.syllables:
        if s.tone is not None:
            ax.text((s.t0 + s.t1) / 2, 0.85, f"声调{s.tone}", transform=trans,
                    ha="center", va="top", fontsize=10, color="#333333")
    common.mark_edge_regions(ax, aln.duration, 3.0 / profile.f0_floor)
    ax.set_ylabel("频率 (Hz)")
    common.set_time_axis(ax, aln)
    common.draw_boundaries(ax, aln)
    ax.set_title(f"{aln.file} F0 轨迹｜filtered ac {profile.f0_floor:.0f}–{profile.f0_ceiling:.0f} Hz，"
                 f"实际步长 {pitch.dx * 1000:.2f} ms，首帧 {pitch.x1 * 1000:.1f} ms，"
                 f"有效分析窗 ≈ 3/floor = {3000.0 / profile.f0_floor:.0f} ms")
    _legend_outside(fig, ax)
    return common.save_fig(fig, out_dir, "05_f0.png")


def _plot_f0_semitone(aln: common.Alignment, t: np.ndarray, f0_st: np.ndarray,
                      f_ref: float, ref_source: str, profile: common.SpeakerProfile,
                      pitch, out_dir: Path) -> Path:
    plt = common.setup_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 4.2), layout="constrained")
    ax.plot(t, f0_st, "-", color="#1f77b4", lw=1.4, label="F0（半音）")
    common.mark_edge_regions(ax, aln.duration, 3.0 / profile.f0_floor)
    ax.set_ylabel("F0 (半音)")
    common.set_time_axis(ax, aln)
    common.draw_boundaries(ax, aln)
    ax.set_title(f"{aln.file} F0 半音轨迹｜F_ref = {f_ref:.1f} Hz（{ref_source}），"
                 f"实际步长 {pitch.dx * 1000:.2f} ms")
    _legend_outside(fig, ax)
    return common.save_fig(fig, out_dir, "05b_f0_semitone.png")


def _missing_p_label(miss_q: list[int]) -> str:
    """缺失取样点序号的紧凑标签：连续游程压缩为「P3–P4」，多段用「、」连接。"""
    runs = []
    for q in miss_q:
        if runs and q == runs[-1][1] + 1:
            runs[-1][1] = q
        else:
            runs.append([q, q])
    return "、".join(f"P{a}" if a == b else f"P{a}–P{b}" for a, b in runs)


def _plot_f0_normalized(aln: common.Alignment, syll_infos: list[dict], f_ref: float,
                        ref_source: str, out_dir: Path) -> Path:
    plt = common.setup_matplotlib()
    from matplotlib.transforms import blended_transform_factory

    fig, (ax_hz, ax_st) = plt.subplots(2, 1, figsize=(8, 6), sharex=True,
                                       layout="constrained")
    xs = NORM_POSITIONS * 100.0
    plotted = [info for info in syll_infos if info["voiced"].size]
    notes = []
    for syl, info in zip(aln.syllables, syll_infos):
        if not info["voiced"].size:
            continue
        # 含 NaN 直接 plot：缺失点处连线自动断开（方案 §5.3，不插值）
        ax_hz.plot(xs, info["p_hz"], "-o", ms=4, label=syl.symbol)
        ax_st.plot(xs, info["p_st"], "-o", ms=4, label=syl.symbol)
        miss_q = [q for q in range(11) if np.isnan(info["p_hz"][q])]
        if miss_q:
            for ax in (ax_hz, ax_st):
                ax.plot(xs[miss_q], np.full(len(miss_q), 0.04), "v", ms=7,
                        mfc="none", mec="#8c8c8c",
                        transform=blended_transform_factory(ax.transData, ax.transAxes))
            name = syl.symbol if len(plotted) >= 2 else ""
            notes.append(f"{name}{_missing_p_label(miss_q)} ".lstrip() +
                         "无有声帧（嘎裂/漏检），未插值")
    if len(plotted) >= 2:
        # 方案 §5.2 图 C：两个及以上音节时，额外绘制拼接的完整连续轨迹（各音节等分 0–100%）
        seg = 100.0 / len(plotted)
        xt = np.concatenate([i * seg + NORM_POSITIONS * seg for i in range(len(plotted))])
        ax_hz.plot(xt, np.concatenate([info["p_hz"] for info in plotted]),
                   "--", color="#7f7f7f", lw=1.0, label="连续轨迹（拼接）")
        ax_st.plot(xt, np.concatenate([info["p_st"] for info in plotted]),
                   "--", color="#7f7f7f", lw=1.0, label="连续轨迹（拼接）")
    extended = any(info["final_end_source"] == "voicing_extended" for info in plotted)
    if extended:
        # 有效终点：延伸音节的取样区间右缘（未延伸的音节与对齐终点重合，不画）
        for ax in (ax_hz, ax_st):
            ax.axvline(100.0, color="#e65100", ls=":", lw=1.2)
        ax_hz.plot([], [], color="#e65100", ls=":", lw=1.2, label="有效终点（有声延伸）")
    if notes:
        ax_hz.text(0.02, 0.98, "；".join(notes), transform=ax_hz.transAxes,
                   ha="left", va="top", fontsize=9, color="#8c8c8c",
                   bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "none", "alpha": 0.75})
    valid = [int(np.sum(~np.isnan(info["p_hz"]))) for info in plotted]
    part = "11 点" if valid and all(v == 11 for v in valid) \
        else "11 点（有效 " + "、".join(f"{v}/11" for v in valid) + "）"
    ax_hz.set_ylabel("F0 (Hz)")
    ax_st.set_ylabel("F0 (半音)")
    ax_st.set_xticks(xs)
    ax_st.set_xlabel("有效有声区间归一化时间 (%)")
    ax_hz.set_title(f"{aln.file} 时间归一化 F0（{part}）｜F_ref = {f_ref:.1f} Hz（{ref_source}）")
    if len(plotted) >= 2:
        _legend_outside(fig, ax_hz)
    return common.save_fig(fig, out_dir, "05c_f0_normalized.png")


def _plot_f0_derivative(aln: common.Alignment, t: np.ndarray, f0_st: np.ndarray,
                        st_sm: np.ndarray, d_st: np.ndarray, turning: list[dict],
                        profile: common.SpeakerProfile, out_dir: Path) -> Path:
    plt = common.setup_matplotlib()
    fig, (ax_up, ax_dn) = plt.subplots(2, 1, figsize=(10, 6), sharex=True,
                                       layout="constrained")
    ax_up.plot(t, f0_st, "-", color="#1f77b4", lw=0.8, alpha=0.45, label="半音（实测）")
    ax_up.plot(t, st_sm, "-", color="#1f77b4", lw=1.4,
               label=f"半音（Savitzky-Golay 窗 {SMOOTH_WINDOW} 帧"
                     f"（{SMOOTH_WINDOW * F0_TIME_STEP * 1000:.0f} ms）阶 {SMOOTH_ORDER}）")
    tp_max = [p for p in turning if p["type"] == "max"]
    tp_min = [p for p in turning if p["type"] == "min"]
    if tp_max:
        ax_up.plot([p["t"] for p in tp_max], [p["st"] for p in tp_max], "^",
                   color="#d62728", ms=9, mfc="none",
                   label=f"局部极大（突出度 ≥ {TURN_PROMINENCE_ST} st）")
    if tp_min:
        ax_up.plot([p["t"] for p in tp_min], [p["st"] for p in tp_min], "v",
                   color="#1a7f37", ms=9, mfc="none",
                   label=f"局部极小（突出度 ≥ {TURN_PROMINENCE_ST} st）")
    common.mark_edge_regions(ax_up, aln.duration, 3.0 / profile.f0_floor)
    ax_up.set_ylabel("F0 (半音)")
    ax_up.set_xlim(0.0, aln.duration)
    common.draw_boundaries(ax_up, aln)
    ax_dn.plot(t, d_st, "-", color="#ff7f0e", lw=1.2)
    ax_dn.axhline(0.0, color="#999999", lw=0.8, ls=":")
    ax_dn.set_ylabel("dF0/dt (st/s)")
    common.set_time_axis(ax_dn, aln)
    common.draw_boundaries(ax_dn, aln, labels=False)
    fig.suptitle(f"{aln.file} F0 导数与转折点｜上：半音曲线（平滑后）及转折点，下：dF0/dt｜"
                 f"先在半音域做 Savitzky-Golay 平滑（窗 {SMOOTH_WINDOW} 帧"
                 f"（{SMOOTH_WINDOW * F0_TIME_STEP * 1000:.0f} ms）阶 {SMOOTH_ORDER}，"
                 f"段长不足不平滑），再对时间求导（仅连续有声段内）")
    _legend_outside(fig, ax_up)
    return common.save_fig(fig, out_dir, "05d_f0_derivative.png")


def _plot_f0_boundary(aln: common.Alignment, t: np.ndarray, f0: np.ndarray,
                      d_st: np.ndarray, out_dir: Path) -> Path:
    """音节交界处 ±100 ms 的 F0 细节与导数（方案 §5.3，需 ≥ 2 个音节）。"""
    plt = common.setup_matplotlib()
    pairs = list(zip(aln.syllables, aln.syllables[1:]))
    fig, axs = plt.subplots(2, len(pairs), figsize=(6.5 * len(pairs), 5), squeeze=False)
    for j, (sa, sb) in enumerate(pairs):
        tb = 0.5 * (sa.t1 + sb.t0)
        lo, hi = max(0.0, tb - BOUNDARY_HALF_WIN), min(aln.duration, tb + BOUNDARY_HALF_WIN)
        m = (t >= lo) & (t <= hi)
        ax = axs[0][j]
        ax.plot(t[m], f0[m], "-o", ms=3, lw=1.2, color="#1f77b4")
        ax.axvline(tb, color="#333333", ls="--", lw=0.8)
        ax.set_xlim(lo, hi)
        ax.set_ylabel("频率 (Hz)")
        ax.set_title(f"{sa.symbol} / {sb.symbol} 交界 ±{BOUNDARY_HALF_WIN * 1000:.0f} ms",
                     fontsize=10)
        ax2 = axs[1][j]
        ax2.plot(t[m], d_st[m], "-o", ms=3, lw=1.2, color="#ff7f0e")
        ax2.axvline(tb, color="#333333", ls="--", lw=0.8)
        ax2.axhline(0.0, color="#999999", lw=0.8, ls=":")
        ax2.set_xlim(lo, hi)
        ax2.set_ylabel("dF0/dt (st/s)")
        ax2.set_xlabel("时间 (s)")
    fig.suptitle(f"{aln.file} 音节交界 F0 细节（方案 §5.3）", y=1.00)
    fig.tight_layout()
    return common.save_fig(fig, out_dir, "05e_f0_boundary.png")


def _plot_intensity(aln: common.Alignment, t_int: np.ndarray, v_int: np.ndarray,
                    t_rms: np.ndarray, v_rms: np.ndarray,
                    profile: common.SpeakerProfile, intensity, out_dir: Path) -> Path:
    plt = common.setup_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 3.5), layout="constrained")
    ln1 = ax.plot(t_int, v_int, color="#1f77b4", lw=1.3,
                  label="Praat To Intensity（相对强度，未校准）")[0]
    ax.set_ylabel("相对强度 dB（未校准）")
    ax_r = ax.twinx()
    ln2 = ax_r.plot(t_rms, v_rms, color="#d62728", lw=1.1, alpha=0.9,
                    label=f"短时 RMS（{RMS_WIN_SEC * 1000:.0f} ms 窗 / "
                          f"{RMS_STEP_SEC * 1000:.0f} ms 步，边缘截短不补零）")[0]
    ax_r.set_ylabel("RMS dBFS")
    # 两根纵轴同为 dB：取相同跨度（数据最大值 − INTENSITY_SPAN_DB），使两条曲线的斜率可直接比较
    ax.set_ylim(float(np.nanmax(v_int)) - INTENSITY_SPAN_DB, float(np.nanmax(v_int)))
    ax_r.set_ylim(float(np.nanmax(v_rms)) - INTENSITY_SPAN_DB, float(np.nanmax(v_rms)))
    common.set_time_axis(ax, aln)
    common.draw_boundaries(ax, aln)
    ax.set_title(f"{aln.file} 强度｜To Intensity：minimum pitch {profile.f0_floor:.0f} Hz，"
                 f"实际步长 {intensity.dx * 1000:.2f} ms，不减均值｜"
                 f"双纵轴同跨度 {INTENSITY_SPAN_DB:.0f} dB")
    fig.legend(handles=[ln1, ln2], loc="outside center right", fontsize=9)
    return common.save_fig(fig, out_dir, "06_intensity.png")


# ---------------- 数据表 ----------------

def _phone_at(aln: common.Alignment, tv: float) -> str:
    """该时刻所在音素的标签；不在任何音素内则为空字符串。"""
    for p in aln.phones:
        if p.t0 - 1e-9 <= tv <= p.t1 + 1e-9:
            return p.label
    return ""


def _timeseries_rows(aln: common.Alignment, t: np.ndarray, f0: np.ndarray,
                     f0_st: np.ndarray, f0_wide: np.ndarray, int_on_t: np.ndarray,
                     rms_on_t: np.ndarray, sus_mask: np.ndarray) -> list[dict]:
    """时间序列行：f0_hz/f0_st 保留原始测量值（含疑似倍频帧），另加 octave_suspect 标志。"""
    rows = []
    for i, tv in enumerate(t):
        rows.append({"time": _fmt(tv, 4),
                     "phone": _phone_at(aln, float(tv)),
                     "f0_hz": _fmt(f0[i], 2),
                     "f0_st": _fmt(f0_st[i], 3),
                     "octave_suspect": int(bool(sus_mask[i])),
                     "f0_wide_hz": _fmt(f0_wide[i], 2),
                     "intensity_db": _fmt(int_on_t[i], 2),
                     "rms_dbfs": _fmt(rms_on_t[i], 2)})
    return rows


def _safe_plot(res: dict, name: str, fn, *args) -> None:
    """单张图失败只记 warning，不中断其余图像的生成。"""
    try:
        res["images"][name] = fn(*args)
    except Exception as exc:
        res["warnings"].append(f"生成 {name} 失败：{exc!r}")


# ---------------- 模块入口 ----------------

def generate(x: np.ndarray, sr: int, aln: common.Alignment, out_dir: str | Path,
             scales: common.DbScales | None = None,
             context: dict | None = None) -> dict:
    """生成波形、F0/声调与强度图像及数值表（接口约定见包 docstring）。"""
    res = common.new_result()
    out_dir = Path(out_dir)
    profile = common.profile_for(aln.speaker)
    snd = common.to_sound(x, sr)

    # ---- F0：主趟（profile 范围）+ 宽范围趟（倍频/半频检查） ----
    pitch = common.pitch_filtered_ac(snd, profile, time_step=F0_TIME_STEP)
    t, f0 = common.pitch_arrays(pitch)
    pitch_wide = common.pitch_filtered_ac(snd, profile, time_step=F0_TIME_STEP,
                                          floor=F0_WIDE_FLOOR, ceiling=F0_WIDE_CEILING)
    t_wide, f0_wide_raw = common.pitch_arrays(pitch_wide)
    tol = max(pitch.dx, pitch_wide.dx) / 2 + 1e-6
    f0_wide = _align_to_grid(t_wide, f0_wide_raw, t, tol)

    oct_stat = _octave_stats(f0, f0_wide)
    if oct_stat["n_common"] == 0:
        if np.any(~np.isnan(f0)):
            res["warnings"].append("F0 倍频/半频检查：宽范围趟（50–600 Hz）与主趟没有共同有声帧，"
                                   "请人工核对两趟结果。")
    else:
        concl = _octave_conclusion(oct_stat)
        if concl != "正常":
            res["warnings"].append(f"F0 倍频/半频检查：{concl}（共同有声帧 "
                                   f"{oct_stat['n_common']} 个）；可疑帧已用浅色点叠画在 05_f0.png。")

    # ---- 半音参考频率：优先说话人语料中位数（context），否则本文件中位数 ----
    f_ref, ref_source = None, None
    if context is not None and context.get("f0_ref_hz"):
        f_ref = float(context["f0_ref_hz"])
        ref_source = f"发音人 {aln.speaker} 语料有声帧中位数"
    if f_ref is None:
        voiced_all = f0[~np.isnan(f0)]
        f_ref = float(np.median(voiced_all)) if voiced_all.size else float("nan")
        ref_source = "本文件 F0 中位数"
        res["warnings"].append(f"context 未提供 f0_ref_hz，半音参考频率退回本文件 F0 中位数"
                               f"（{f_ref:.1f} Hz）；正式比较应使用说话人语料中位数。")
    # ---- 局部倍频/半频跳变（方案 §5.1 / §9）：按相邻有声帧半音差切段检测 ----
    sus_mask, jump_segs = _octave_jumps(t, f0, f_ref)
    for seg in jump_segs:
        res["warnings"].append(f"F0 {seg['type']}段：{seg['t0']:.3f}–{seg['t1']:.3f} s"
                               f"（{seg['n_frames']} 帧，与参照段中位差 {seg['delta_st']:+.1f} st），"
                               f"不做 ×2/÷2 校正，未计入声调统计，图中以灰色 × 标出。")
    f0_stat = np.where(sus_mask, np.nan, f0)   # 声调统计与取样用序列：疑似帧记 NaN
    f0_st = _semitone(f0_stat, f_ref)          # 05b/05c/05d 与统计用的半音序列
    st_sm, d_st = _smooth_and_derivative(t, f0_st)
    turning = _turning_points(t, f0_stat, st_sm)

    # ---- 强度（Praat，未校准）与短时 RMS（dBFS） ----
    from parselmouth.praat import call

    intensity = call(snd, "To Intensity", profile.f0_floor, INTENSITY_TIME_STEP, False)
    t_int = np.asarray(intensity.xs(), dtype=float)
    v_int = np.asarray(intensity.values, dtype=float).reshape(-1)
    t_rms = np.arange(0.0, aln.duration, RMS_STEP_SEC)
    v_rms = np.array([
        20.0 * np.log10(max(float(np.sqrt(np.mean(seg ** 2))), 1e-10))
        for seg, _ in (common.segment_at(x, sr, c, RMS_WIN_SEC) for c in t_rms)])
    int_on_t = np.interp(t, t_int, v_int)
    rms_on_t = np.interp(t, t_rms, v_rms)

    # ---- 音节级统计（取样区间右端用韵母有效终点，common.vowel_interval） ----
    syll_infos = []
    for k, syl in enumerate(aln.syllables):
        vi = common.vowel_interval(aln, k, x, sr, profile)
        info = _syllable_f0(syl, t, f0_stat, f_ref, vi.t1)
        info["final_t1_effective"] = vi.t1
        info["final_end_source"] = vi.end_source
        syll_infos.append(info)
        if vi.end_source == "voicing_extended":
            res["warnings"].append(
                f"音节 {syl.symbol}：讯飞韵母终点 {syl.final.t1:.3f} s 早于实际发声结束 "
                f"{vi.t1:.3f} s，声调取样延伸到 {vi.t1:.3f} s。")
        if info["voiced"].size == 0:
            res["warnings"].append(f"音节 {syl.symbol}（{syl.t0:.2f}–{vi.t1:.2f} s）范围内"
                                   f"没有有声帧，11 点归一化与声调统计记为空。")

    # ---- 图像 ----
    _safe_plot(res, "01_waveform.png", _plot_waveform, x, sr, aln, out_dir)
    _safe_plot(res, "05_f0.png", _plot_f0, aln, t, f0_stat, f0, sus_mask, f0_wide,
               oct_stat, syll_infos, profile, pitch, out_dir)
    _safe_plot(res, "05b_f0_semitone.png", _plot_f0_semitone,
               aln, t, f0_st, f_ref, ref_source, profile, pitch, out_dir)
    _safe_plot(res, "05c_f0_normalized.png", _plot_f0_normalized,
               aln, syll_infos, f_ref, ref_source, out_dir)
    _safe_plot(res, "05d_f0_derivative.png", _plot_f0_derivative,
               aln, t, f0_st, st_sm, d_st, turning, profile, out_dir)
    if len(aln.syllables) >= 2:
        _safe_plot(res, "05e_f0_boundary.png", _plot_f0_boundary,
                   aln, t, f0_stat, d_st, out_dir)
    else:
        res["warnings"].append("录音只包含一个音节，没有音节交界，"
                               "未生成 05e_f0_boundary.png（方案 §5.3 需 ≥ 2 个音节）。")
    _safe_plot(res, "06_intensity.png", _plot_intensity,
               aln, t_int, v_int, t_rms, v_rms, profile, intensity, out_dir)

    # ---- 数据表 ----
    try:
        res["tables"]["prosody_timeseries.csv"] = common.write_csv(
            _timeseries_rows(aln, t, f0, _semitone(f0, f_ref), f0_wide, int_on_t,
                             rms_on_t, sus_mask),
            out_dir / "csv", "prosody_timeseries.csv")
    except Exception as exc:
        res["warnings"].append(f"写 prosody_timeseries.csv 失败：{exc!r}")
    try:
        rows = [_tone_row(s, info, t, f0_stat, f0_st, f0_wide, turning, sus_mask)
                for s, info in zip(aln.syllables, syll_infos)]
        res["tables"]["tone_stats.csv"] = common.write_csv(rows, out_dir / "csv", "tone_stats.csv")
    except Exception as exc:
        res["warnings"].append(f"写 tone_stats.csv 失败：{exc!r}")

    # ---- 实际参数（含 Praat 自行调整后的值） ----
    res["params"] = {
        "f0": {
            "command": "To Pitch (filtered ac)",
            "time_step_s": F0_TIME_STEP,
            "actual_time_step_s": float(pitch.dx),
            "floor_hz": float(profile.f0_floor),
            "ceiling_hz": float(profile.f0_ceiling),
            "analysis_window_s": 3.0 / profile.f0_floor,   # 有效分析窗 ≈ 3/floor（方案 §5.1）
            "first_frame_t": float(pitch.x1),
            "n_frames": int(pitch.nx),
        },
        "f0_wide": {
            "floor_hz": F0_WIDE_FLOOR,
            "ceiling_hz": F0_WIDE_CEILING,
            "actual_time_step_s": float(pitch_wide.dx),
            "analysis_window_s": 3.0 / F0_WIDE_FLOOR,
            "first_frame_t": float(pitch_wide.x1),
            "n_frames": int(pitch_wide.nx),
        },
        "semitone": {"formula": "12*log2(F0/F_ref)", "f_ref_hz": f_ref, "f_ref_source": ref_source},
        "normalization": {
            "positions": "P0–P10 = 0%–100% 等间隔 11 点（有效有声区间）",
            "interpolation": "仅相邻两帧都有声时线性插值，否则 NaN",
            "interval": "[音节内第一个有声帧（含浊声母）, 韵母有效终点]；"
                        "有效终点为 common.vowel_interval 的 t1（有声且非低能量帧的延伸，"
                        "延伸 ≥10 ms 记为 voicing_extended）",
        },
        "derivative": {"unit": "st/s",
                       "smoothing": f"Savitzky-Golay 窗 {SMOOTH_WINDOW} 帧"
                                    f"（{SMOOTH_WINDOW * F0_TIME_STEP * 1000:.0f} ms）"
                                    f"阶 {SMOOTH_ORDER}；段长不足 {SMOOTH_WINDOW} 帧时降为"
                                    f"不小于 {SMOOTH_MIN_FRAMES} 帧的最大奇数窗，"
                                    f"不足 {SMOOTH_MIN_FRAMES} 帧不求导"},
        "turning_point": {"prominence_st": TURN_PROMINENCE_ST},
        "octave_check": {
            "wide_range_hz": [F0_WIDE_FLOOR, F0_WIDE_CEILING],
            "median_ratio_range": list(OCTAVE_MEDIAN_RANGE),
            "frame_tolerance_st": OCTAVE_TOL_ST,
            "n_common": oct_stat["n_common"],
            "median_ratio": oct_stat["median_ratio"],
            "n_octave": oct_stat["n_octave"],
            "octave_fraction": oct_stat["fraction"],
            "conclusion": _octave_conclusion(oct_stat),
        },
        "octave_jump": {
            "cut_st": OCTAVE_JUMP_ST,
            "octave_band_st": list(OCTAVE_BAND_ST),
            "correction": "不做 ×2/÷2 校正，疑似帧在声调统计与 11 点取样中记 NaN",
            "n_suspect_frames": int(np.count_nonzero(sus_mask)),
            "segments": jump_segs,
        },
        "intensity": {
            "command": "To Intensity",
            "minimum_pitch_hz": float(profile.f0_floor),
            "time_step_s": INTENSITY_TIME_STEP,
            "subtract_mean": False,
            "actual_time_step_s": float(intensity.dx),
            "first_frame_t": float(intensity.x1),
            "note": "相对强度 dB，未校准；文件间峰值归一化不同，只能在单个文件内比较",
        },
        "rms": {"window_s": RMS_WIN_SEC, "step_s": RMS_STEP_SEC,
                "edge": "segment_at 截短边缘，不补零", "unit": "dBFS"},
    }
    return res
