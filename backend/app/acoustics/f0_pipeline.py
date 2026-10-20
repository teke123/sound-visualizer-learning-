"""F0 提取、四步清洗、五度标音与哼鸣合成管线（docs/f0展示修改测试版1.md）。

同源同轨：用户录音与标准示范录音都走 extract_track → process_syllables，
差别只在各自音域 [f_lo, f_hi]（用户＝受理时冻结的个人音域快照，
示范＝参考发音人固定音域）。前端实时轨（MPM）与后端 Praat 轨共用
五度映射口径与 10ms 时间单位。

提取：Praat "To Pitch (filtered ac)"（自相关前高斯低通，抑制高次谐波与
F1 干扰）。Praat 不暴露逐帧候选路径，本管线用「主趟（voicing 0.50）＋
救援趟（voicing 0.25，弱周期帧的真实实测候选）＋八度格点」构成重选
候选集——Step 3 纠偏的主要目标（倍频/半频错误）由此覆盖。

四步清洗（均在音节粗边界内，docs §3）：
  Step 1  孤立伪有声点剔除（<2 帧游程置 NaN；静音/清音断口保留 null）
  Step 2  嘎裂/弱周期恢复（内部缺口≤120ms、尾部≤100ms；候选强度≥0.30，
          帧能量 ≥ max(底噪+6dB, 峰值−22dB)，并与锚点连续）
  Step 3  Sundberg 速率＋八度比跳变检测（tone_py._detect_token_artefacts）
          ＋ 待检查区间的候选路径动态规划纠偏（两侧/单侧锚点＋参考线惩罚）
  Step 4  有声核心区裁剪（首 ≥3 帧游程／末 ≥2 帧游程）＋ ≤2 帧毛刺半音域
          插值 ＋ 分段 Savitzky-Golay 平滑（半音域，窗 5 阶 2）

输出（docs §7.1）：原生 10ms 网格绘图帧（t/hz/degree/confidence/source/
intensityDb，无效帧 hz/degree 为 null 但占位）＋ 21 点等距比较序列
（tone_py near/far 规则，半音域插值，置信度取参与帧较小值）＋ 单音节
近似调值（Chao 数字，端点窗中位数＋内部 0.5 度转折判定）＋ 按音节质量。

各纠偏开关见 config（SVS_F0_RESCUE / SVS_F0_CORRECT / SVS_F0_INTERP），
便于在同一批录音上分别评测定参。
"""
from __future__ import annotations

import io
import logging
import math
import wave
from dataclasses import dataclass

import numpy as np

from app import config
from app.acoustics.tone_py.chao import classify_contour
from app.acoustics.tone_py.inspect import _detect_token_artefacts
from app.acoustics.tone_py.sonify import sonify_f0

logger = logging.getLogger("svs.acoustics.f0")

# ---------------- 集中配置（回归录音调参入口，docs §2.1 / §3）----------------
HOP_SEC = 0.010                 # 帧移（Praat 与前端实时轨一致）
PITCH_FLOOR_HZ = 50.0
PITCH_TOP_HZ = 800.0
MAX_CANDIDATES = 15
ATTENUATION_AT_TOP = 0.03
SILENCE_THRESHOLD = 0.09
VOICING_THRESHOLD = 0.50
RESCUE_VOICING_THRESHOLD = 0.25  # 救援趟：更低门限暴露弱周期帧的实测候选
OCTAVE_COST = 0.055
OCTAVE_JUMP_COST = 0.35
VOICED_UNVOICED_COST = 0.14
INTENSITY_MIN_PITCH = 50.0       # To Intensity 的最低频率参数（docs §2.1.3）

ST_REF_HZ = 55.0                # 半音参考频率（docs §3 Step3：12·log2(f/55)）
RISING_RATE_ST = 1.263          # ST / 10ms
FALLING_RATE_ST = 1.714
OCTAVE_RATIO_BOUNDS = (0.51, 1.95)
CARRYOVER_MULT = 1.5

RESCUE_MIN_STRENGTH = 0.30
RESCUE_INTERNAL_MAX_FRAMES = 12   # 120ms
RESCUE_TAIL_MAX_FRAMES = 10       # 100ms
RESCUE_FLOOR_MARGIN_DB = 6.0
RESCUE_PEAK_DROP_DB = 22.0
RESCUE_CONTINUITY_ST = 3.0      # 恢复帧与锚点连线/外推的半音距离上限

OCTAVE_LATTICE = (0, -1, 1, -2, 2)
LATTICE_STRENGTH_DECAY = 0.97   # 格点候选强度的逐八度衰减

DP_REF_WEIGHT = 1.0             # 参考线偏离惩罚权重
DP_REF_BAND_ST = 2.5            # 偏离参考超过该半音数才开始计罚
DP_TRANS_WEIGHT = 1.0           # 相邻候选半音差（连接代价）权重
ANCHOR_MIN_STRENGTH = 0.50

INTERP_MAX_FRAMES = 2           # 仅修补 Step 3 删除的 ≤2 帧内部毛刺
INTERP_ANCHOR_MAX_ST = 2.0      # 两侧锚点半音差上限
INTERP_CONF_SCALE = 0.5         # 插值帧置信度 = 0.5 × min(两侧)
SG_WINDOW = 5
SG_POLYORDER = 2

COMPARISON_POINTS = 21          # 比较序列点数（步长 0.05）
SOLID_CONFIDENCE = 0.50         # 前端实线/点线分界（docs §6.2）
MIN_DRAW_RUN = 2                # 连续有效段 ≥2 帧即可绘制
DIAG_MIN_FRAMES = 8
DIAG_MIN_COVERAGE = 0.60
DIAG_MAX_JUMP_DENSITY = 0.20
CHAO_TURN_THRESHOLD = 0.5       # 度（转折相对端点的最小突出量）
MAX_SYLL_FRAMES = 1200          # 单音节绘图帧上限（60s 上限的防御性裁剪）

# 帧来源编码
SRC_NONE, SRC_MEASURED, SRC_CORRECTED, SRC_INTERPOLATED = 0, 1, 2, 3
_SRC_NAMES = {SRC_MEASURED: "measured", SRC_CORRECTED: "corrected",
              SRC_INTERPOLATED: "interpolated"}


class F0PipelineError(Exception):
    """提取前置条件不满足（录音过短等），调用方降级为曲线不可用。"""


# ---------------- 提取 ----------------

@dataclass
class PitchTrack:
    times: np.ndarray            # (n,) 秒，Praat 10ms 网格
    f0: np.ndarray               # 主轨 Hz，NaN＝无声
    strength: np.ndarray         # 主轨选中候选强度（无声 0）
    rescue_f0: np.ndarray        # 救援轨 Hz，NaN＝无声
    rescue_strength: np.ndarray
    intensity_db: np.ndarray     # Praat Intensity 线性插值对齐到 times
    background_db: float         # 背景能量（前置静音中位数或全段低分位）
    duration: float

    def candidates_at(self, i: int) -> list[tuple[float, float]]:
        """帧 i 的重选候选：主/救援轨实测频率的八度格点（去重、限幅）。"""
        out: list[tuple[float, float]] = []
        for f, s in ((self.f0[i], self.strength[i]),
                     (self.rescue_f0[i], self.rescue_strength[i])):
            if np.isfinite(f) and f > 0 and s > 0:
                for k in OCTAVE_LATTICE:
                    cand = f * 2.0 ** k
                    if PITCH_FLOOR_HZ <= cand <= PITCH_TOP_HZ:
                        out.append((cand, s * LATTICE_STRENGTH_DECAY ** abs(k)))
        seen: set[float] = set()
        dedup: list[tuple[float, float]] = []
        for f, s in out:
            key = round(f, 3)
            if key not in seen:
                seen.add(key)
                dedup.append((f, s))
        return dedup


def _filtered_ac(snd, voicing_threshold: float):
    from parselmouth.praat import call

    return call(
        snd, "To Pitch (filtered ac)",
        HOP_SEC, PITCH_FLOOR_HZ, PITCH_TOP_HZ, MAX_CANDIDATES, False,
        ATTENUATION_AT_TOP, SILENCE_THRESHOLD, voicing_threshold,
        OCTAVE_COST, OCTAVE_JUMP_COST, VOICED_UNVOICED_COST,
    )


def extract_track(wav_path) -> PitchTrack:
    """filtered AC 主趟＋救援趟＋Intensity 对齐（docs §2.1）。"""
    import parselmouth
    from parselmouth.praat import call

    snd = parselmouth.Sound(str(wav_path))
    if snd.duration < 0.08:
        raise F0PipelineError("录音太短，无法提取音高")

    main = _filtered_ac(snd, VOICING_THRESHOLD)
    times = np.asarray(main.xs(), dtype=float)
    sel = main.selected_array
    f0 = np.asarray(sel["frequency"], dtype=float)
    f0 = np.where((f0 >= PITCH_FLOOR_HZ) & (f0 <= PITCH_TOP_HZ), f0, np.nan)
    strength = np.where(np.isfinite(f0), np.asarray(sel["strength"], dtype=float), 0.0)

    if config.F0_RESCUE_ENABLED:
        rescue = _filtered_ac(snd, RESCUE_VOICING_THRESHOLD)
        r_sel = rescue.selected_array
        r_f0 = np.asarray(r_sel["frequency"], dtype=float)
        r_f0 = np.where((r_f0 >= PITCH_FLOOR_HZ) & (r_f0 <= PITCH_TOP_HZ), r_f0, np.nan)
        r_strength = np.where(np.isfinite(r_f0), np.asarray(r_sel["strength"], dtype=float), 0.0)
        # 救援趟网格与主趟一致（同参数，仅门限不同）
        if len(r_f0) != len(f0):  # 防御：帧数不一致时按时间对齐
            r_t = np.asarray(rescue.xs(), dtype=float)
            r_f0 = np.interp(times, r_t, np.nan_to_num(r_f0, nan=0.0),
                             left=0.0, right=0.0)
            r_f0 = np.where(r_f0 > 0, r_f0, np.nan)
            r_strength = np.interp(times, r_t, r_strength, left=0.0, right=0.0)
            r_strength = np.where(np.isfinite(r_f0), r_strength, 0.0)
    else:
        r_f0 = np.full_like(f0, np.nan)
        r_strength = np.zeros_like(strength)

    intensity = call(snd, "To Intensity", INTENSITY_MIN_PITCH, HOP_SEC, "yes")
    i_times = np.asarray(intensity.xs(), dtype=float)
    i_vals = np.asarray(intensity.values, dtype=float).reshape(-1)
    intensity_db = np.interp(times, i_times, i_vals,
                             left=float(i_vals[0]) if len(i_vals) else -100.0,
                             right=float(i_vals[-1]) if len(i_vals) else -100.0)

    unvoiced_db = intensity_db[~np.isfinite(f0)]
    if unvoiced_db.size >= 5:
        background_db = float(np.median(unvoiced_db))
    else:
        background_db = float(np.percentile(intensity_db, 10))
    return PitchTrack(times=times, f0=f0, strength=strength,
                      rescue_f0=r_f0, rescue_strength=r_strength,
                      intensity_db=intensity_db, background_db=background_db,
                      duration=float(snd.duration))


# ---------------- 五度与半音映射（docs §4.2）----------------

def hz_to_degree(hz, f_lo: float, f_hi: float):
    """连续五度值：fLo→1、对数中点→3、fHi→5；不截断，越界值保留。"""
    hz = np.asarray(hz, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        d = 1.0 + 4.0 * (np.log(hz) - math.log(f_lo)) / (math.log(f_hi) - math.log(f_lo))
    return np.where(np.isfinite(d), d, np.nan)


def degree_to_hz(degree: float, f_lo: float, f_hi: float) -> float:
    """五度值 → Hz（「按我的音域听标准」的目标频率，docs §5.2）。"""
    return math.exp(math.log(f_lo) + (degree - 1.0) / 4.0
                    * (math.log(f_hi) - math.log(f_lo)))


def hz_to_rel_st(hz, f_lo: float, f_hi: float):
    """个人中心归一化半音：以音域对数中心为 0 ST。"""
    center = math.sqrt(f_lo * f_hi)
    hz = np.asarray(hz, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return 12.0 * np.log2(hz / center)


# ---------------- 通用工具 ----------------

def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """连续 True 游程列表 [start, end]（含端点）。"""
    out: list[tuple[int, int]] = []
    n = len(mask)
    i = 0
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def _st(hz: float) -> float:
    return 12.0 * math.log2(hz / ST_REF_HZ)


def _slope_st(times: np.ndarray, hz: np.ndarray, end_idx: int) -> float:
    """取 end_idx 前最多 5 个有效帧做一次线性拟合，返回 ST/秒 斜率。"""
    lo = max(0, end_idx - 4)
    seg_t, seg_st = [], []
    for k in range(lo, end_idx + 1):
        if np.isfinite(hz[k]):
            seg_t.append(float(times[k]))
            seg_st.append(_st(float(hz[k])))
    if len(seg_t) < 2:
        return 0.0
    dt = seg_t[-1] - seg_t[0]
    return 0.0 if dt <= 0 else (seg_st[-1] - seg_st[0]) / dt


def _slope_st_after(times: np.ndarray, hz: np.ndarray, start_idx: int) -> float:
    """取 start_idx 后最多 5 个有效帧拟合 ST/秒 斜率（右侧锚点用）。"""
    hi = min(len(hz) - 1, start_idx + 4)
    seg_t, seg_st = [], []
    for k in range(start_idx, hi + 1):
        if np.isfinite(hz[k]):
            seg_t.append(float(times[k]))
            seg_st.append(_st(float(hz[k])))
    if len(seg_t) < 2:
        return 0.0
    dt = seg_t[-1] - seg_t[0]
    return 0.0 if dt <= 0 else (seg_st[-1] - seg_st[0]) / dt


# ---------------- Step 3：区间候选路径动态规划 ----------------

def _correct_interval(times: np.ndarray, hz: np.ndarray, strength: np.ndarray,
                      sources: np.ndarray, removed: np.ndarray,
                      track: PitchTrack, base: int,
                      i0: int, i1: int,
                      anchor_lo: tuple[int, float] | None,
                      anchor_hi: tuple[int, float] | None) -> None:
    """待检查区间 [i0, i1] 的候选路径重选（原地更新切片数组）。

    锚点为（区间外可靠帧索引, 半音值）；观测代价＝候选强度负对数＋
    参考线偏离惩罚；连接代价＝相邻候选半音差；只有总代价低于原路径
    才替换（docs §3 Step3.2）。
    """
    m = i1 - i0 + 1
    if m <= 0:
        return
    cands: list[list[tuple[float, float]]] = [track.candidates_at(base + k)
                                              for k in range(i0, i1 + 1)]
    if not anchor_lo and not anchor_hi:
        return

    # 参考线：两侧锚点线性连线；单侧用锚点外侧稳定趋势外推（docs §3）
    t0, t1 = float(times[i0]), float(times[i1])
    if anchor_lo and anchor_hi:
        (ta, sa), (tb, sb) = anchor_lo, anchor_hi
        anchor_time = float(times[ta])
        span = max(float(times[tb]) - anchor_time, 1e-6)

        def ref_st(i: int) -> float:
            w = min(max((float(times[i]) - anchor_time) / span, -2.0), 3.0)
            return sa + (sb - sa) * w
    elif anchor_lo:
        (ta, sa) = anchor_lo
        slope = _slope_st(times, hz, ta)
        anchor_time = float(times[ta])

        def ref_st(i: int) -> float:  # noqa: F811
            return sa + slope * (float(times[i]) - anchor_time)
    else:
        (ta, sa) = anchor_hi
        slope = _slope_st_after(times, hz, ta)
        anchor_time = float(times[ta])

        def ref_st(i: int) -> float:  # noqa: F811
            return sa + slope * (float(times[i]) - anchor_time)

    def obs_cost(i: int, f: float, s: float) -> float:
        band = max(0.0, abs(_st(f) - ref_st(i)) - DP_REF_BAND_ST)
        return -math.log(max(s, 1e-4)) + DP_REF_WEIGHT * band

    def trans_cost(fa: float, fb: float) -> float:
        return DP_TRANS_WEIGHT * abs(_st(fa) - _st(fb))

    # 原路径总代价（含锚点连接）
    def path_cost(freqs: list[float | None], stren: list[float]) -> float | None:
        if any(f is None for f in freqs):
            return None
        total = 0.0
        for k, (f, s) in enumerate(zip(freqs, stren)):
            total += obs_cost(i0 + k, f, s)
            if k > 0:
                total += trans_cost(freqs[k - 1], f)
        if anchor_lo:
            total += trans_cost(float(freqs[0]), 2.0 ** ((anchor_lo[1]) / 12.0) * ST_REF_HZ)
        if anchor_hi:
            total += trans_cost(float(freqs[-1]), 2.0 ** ((anchor_hi[1]) / 12.0) * ST_REF_HZ)
        return total

    old_freqs = [float(hz[i]) if np.isfinite(hz[i]) else None for i in range(i0, i1 + 1)]
    old_stren = [float(strength[i]) for i in range(i0, i1 + 1)]
    old_cost = path_cost(old_freqs, old_stren)

    # Viterbi
    neg_inf = float("inf")
    width = max(1, max(len(row) for row in cands))
    dp = np.full((m, width), neg_inf)
    back = np.full((m, width), -1, dtype=int)
    for k, cands_k in enumerate(cands):
        for ci, (f, s) in enumerate(cands_k):
            c = obs_cost(i0 + k, f, s)
            if k == 0:
                if anchor_lo:
                    c += trans_cost(f, 2.0 ** (anchor_lo[1] / 12.0) * ST_REF_HZ)
                dp[k][ci] = c
            else:
                for pj, (pf, _ps) in enumerate(cands[k - 1]):
                    if dp[k - 1][pj] == neg_inf:
                        continue
                    v = dp[k - 1][pj] + trans_cost(pf, f)
                    if v < dp[k][ci]:
                        dp[k][ci] = v
                        back[k][ci] = pj
        # 帧无候选：强制 NaN（交 Step 4 处理）
    last = m - 1
    best_ci = int(np.argmin(dp[last])) if dp[last].size else -1
    if best_ci < 0 or dp[last][best_ci] == neg_inf:
        for i in range(i0, i1 + 1):
            hz[i] = np.nan
            strength[i] = 0.0
            sources[i] = SRC_NONE
            removed[i] = True
        return
    if anchor_hi:
        hi_hz = 2.0 ** (anchor_hi[1] / 12.0) * ST_REF_HZ
        dp[last, :len(cands[last])] += [trans_cost(f, hi_hz) for f, _s in cands[last]]
        best_ci = int(np.argmin(dp[last]))
    new_cost = float(dp[last][best_ci])

    # 回溯
    path_ci = [0] * m
    ci = best_ci
    for k in range(m - 1, -1, -1):
        path_ci[k] = ci
        ci = int(back[k][ci])
    if old_cost is not None and new_cost >= old_cost:
        return  # 新路径不更优：保留原路径
    for k in range(m):
        if not cands[k]:
            hz[i0 + k] = np.nan
            strength[i0 + k] = 0.0
            sources[i0 + k] = SRC_NONE
            removed[i0 + k] = True
            continue
        f, s = cands[k][path_ci[k]]
        if np.isfinite(hz[i0 + k]) and abs(_st(f) - _st(float(hz[i0 + k]))) > 0.05:
            sources[i0 + k] = SRC_CORRECTED
        hz[i0 + k] = f
        strength[i0 + k] = s


# ---------------- 单音节四步清洗 ----------------

def _process_one(track: PitchTrack, t0: float, t1: float,
                 f_lo: float, f_hi: float) -> dict:
    lo = int(np.searchsorted(track.times, t0 - 1e-9))
    hi = int(np.searchsorted(track.times, t1 + 1e-9))
    empty = {
        "t0": round(float(t0), 3), "t1": round(float(t1), 3),
        "analysisStart": None, "analysisEnd": None,
        "duration": round(float(max(t1 - t0, 0.0)), 3), "analysisDuration": 0.0,
        "frames": [], "comparisonPoints": [],
        "chao": None, "shape": None, "featurePoints": None, "quality": None,
    }
    if hi <= lo:
        return empty
    times = track.times[lo:hi][:MAX_SYLL_FRAMES].copy()
    n = len(times)
    hz = track.f0[lo:lo + n].copy()
    strength = track.strength[lo:lo + n].copy()
    rescue_hz = track.rescue_f0[lo:lo + n]
    rescue_strength = track.rescue_strength[lo:lo + n]
    intensity = track.intensity_db[lo:lo + n]
    sources = np.where(np.isfinite(hz), SRC_MEASURED, SRC_NONE).astype(int)
    removed = np.zeros(n, dtype=bool)

    # Step 1：孤立伪有声点剔除（<2 帧游程）
    for a, b in _runs(np.isfinite(hz)):
        if b - a + 1 < 2:
            hz[a:b + 1] = np.nan
            strength[a:b + 1] = 0.0
            sources[a:b + 1] = SRC_NONE

    # Step 2：嘎裂/弱周期恢复（Creaky Rescue Pass）
    if config.F0_RESCUE_ENABLED:
        finite_int = intensity[np.isfinite(intensity)]
        peak_db = float(finite_int.max()) if finite_int.size else track.background_db
        energy_thr = max(track.background_db + RESCUE_FLOOR_MARGIN_DB,
                         peak_db - RESCUE_PEAK_DROP_DB)
        voiced_runs = _runs(np.isfinite(hz))

        def try_rescue(a: int, b: int, anchor_st: float, anchor_slope: float,
                       anchor_t: float) -> None:
            for i in range(a, b + 1):
                rf, rs = float(rescue_hz[i]), float(rescue_strength[i])
                if not (np.isfinite(rf) and rs >= RESCUE_MIN_STRENGTH):
                    continue
                if not (np.isfinite(intensity[i]) and intensity[i] >= energy_thr):
                    continue
                expect = anchor_st + anchor_slope * (float(times[i]) - anchor_t)
                if abs(_st(rf) - expect) > RESCUE_CONTINUITY_ST:
                    continue
                hz[i], strength[i], sources[i] = rf, rs, SRC_CORRECTED

        for (a0, a1), (b0, _b1) in zip(voiced_runs, voiced_runs[1:]):
            gap_a, gap_b = a1 + 1, b0 - 1  # noqa: E741  内部缺口（两侧锚点）
            if 0 < gap_b - gap_a + 1 <= RESCUE_INTERNAL_MAX_FRAMES:
                st_a = _st(float(hz[a1]))
                st_b = _st(float(hz[b0]))
                span = max(float(times[b0] - times[a1]), 1e-6)
                slope = (st_b - st_a) / span
                mid_st = st_a + slope * (float(times[gap_a]) - float(times[a1]))
                try_rescue(gap_a, gap_b, mid_st, slope, float(times[gap_a]))
        if voiced_runs:  # 尾部缺口（前侧锚点外推）
            a1 = voiced_runs[-1][1]
            gap_a, gap_b = a1 + 1, n - 1
            if 0 < gap_b - gap_a + 1 <= RESCUE_TAIL_MAX_FRAMES:
                slope = _slope_st(times, hz, a1)
                try_rescue(gap_a, gap_b, _st(float(hz[a1])), slope, float(times[a1]))

    # Step 3：跳变检测＋区间候选路径纠偏
    if config.F0_CORRECT_ENABLED:
        for a, b in _runs(np.isfinite(hz)):
            r_hz, r_t = hz[a:b + 1], times[a:b + 1]
            flags, _notes = _detect_token_artefacts(
                r_hz, r_t, "s", RISING_RATE_ST, FALLING_RATE_ST,
                OCTAVE_RATIO_BOUNDS, CARRYOVER_MULT)
            if not flags.any():
                continue
            for f0i, f1i in _runs(flags):
                i0, i1 = a + f0i, a + f1i
                anchor_lo = None
                for k in range(i0 - 1, a - 1, -1):
                    if not flags[k - a] and np.isfinite(hz[k]) and strength[k] >= ANCHOR_MIN_STRENGTH:
                        anchor_lo = (k, _st(float(hz[k])))
                        break
                anchor_hi = None
                for k in range(i1 + 1, b + 1):
                    if not flags[k - a] and np.isfinite(hz[k]) and strength[k] >= ANCHOR_MIN_STRENGTH:
                        anchor_hi = (k, _st(float(hz[k])))
                        break
                _correct_interval(times, hz, strength, sources, removed,
                                  track, lo, i0, i1, anchor_lo, anchor_hi)

    # Step 4a：有声核心区裁剪（起点首个 ≥3 帧游程，终点末个 ≥2 帧游程）
    valid_runs = _runs(np.isfinite(hz))
    if not valid_runs:
        return empty
    start_runs = [r for r in valid_runs if r[1] - r[0] + 1 >= 3]
    end_runs = [r for r in valid_runs if r[1] - r[0] + 1 >= 2]
    if start_runs and end_runs:
        ia = start_runs[0][0]
        ib = max(ia, end_runs[-1][1])
    elif len(valid_runs) == 1 and valid_runs[0][1] - valid_runs[0][0] + 1 >= MIN_DRAW_RUN:
        ia, ib = valid_runs[0]
    else:
        return empty

    # Step 4b：≤2 帧毛刺缺口修补（仅 Step 3 删除的片段）
    if config.F0_INTERP_ENABLED:
        v = np.isfinite(hz[ia:ib + 1])
        for a, b in _runs(~v):
            if b - a + 1 > INTERP_MAX_FRAMES or not (0 < ia + a - 1 and ia + b + 1 <= ib):
                continue
            if not removed[ia + a:ia + b + 1].any():
                continue  # 只修补纠偏删除的片段，自然缺口保留断口
            lft, rgt = ia + a - 1, ia + b + 1
            if not (np.isfinite(hz[lft]) and np.isfinite(hz[rgt])):
                continue
            if strength[lft] < ANCHOR_MIN_STRENGTH or strength[rgt] < ANCHOR_MIN_STRENGTH:
                continue
            st_l, st_r = _st(float(hz[lft])), _st(float(hz[rgt]))
            if abs(st_r - st_l) >= INTERP_ANCHOR_MAX_ST:
                continue
            conf = INTERP_CONF_SCALE * min(float(strength[lft]), float(strength[rgt]))
            for k in range(a, b + 1):
                w = (k - a + 1) / (b - a + 2)
                hz[ia + k] = 2.0 ** ((st_l + (st_r - st_l) * w) / 12.0) * ST_REF_HZ
                strength[ia + k] = conf
                sources[ia + k] = SRC_INTERPOLATED

    # Step 4c：分段 Savitzky-Golay 平滑（半音域，≥5 帧的连续有效游程）
    from scipy.signal import savgol_filter

    for a, b in _runs(np.isfinite(hz[ia:ib + 1])):
        if b - a + 1 < SG_WINDOW:
            continue
        seg = hz[ia + a:ia + b + 1]
        st_seg = savgol_filter(np.array([_st(float(f)) for f in seg]),
                               SG_WINDOW, SG_POLYORDER)
        hz[ia + a:ia + b + 1] = 2.0 ** (st_seg / 12.0) * ST_REF_HZ

    # 质量统计（覆盖率分母＝分析区间原生网格帧数）
    valid = np.isfinite(hz[ia:ib + 1])
    n_valid = int(valid.sum())
    jump_flags = 0
    for a, b in _runs(valid):
        flags, _ = _detect_token_artefacts(
            hz[ia + a:ia + b + 1], times[ia + a:ia + b + 1], "s",
            RISING_RATE_ST, FALLING_RATE_ST, OCTAVE_RATIO_BOUNDS, 0.0)
        jump_flags += int(flags.sum())
    grid_n = ib - ia + 1
    coverage = n_valid / max(grid_n, 1)
    jump_density = jump_flags / max(n_valid, 1)
    quality = {
        "validFrames": n_valid,
        "coverage": round(float(coverage), 3),
        "jumpDensity": round(float(jump_density), 3),
        "canDiagnose": bool(n_valid >= DIAG_MIN_FRAMES and coverage >= DIAG_MIN_COVERAGE
                            and jump_density <= DIAG_MAX_JUMP_DENSITY),
    }

    # 绘图帧（原生网格，无效帧 null 占位）
    frames: list[dict] = []
    for k in range(ia, ib + 1):
        f_hz = float(hz[k]) if np.isfinite(hz[k]) else None
        frames.append({
            "t": round(float(times[k]), 3),
            "hz": round(f_hz, 1) if f_hz else None,
            "degree": round(float(hz_to_degree(hz[k], f_lo, f_hi)), 2)
                      if f_hz else None,
            "confidence": round(float(strength[k]), 2) if f_hz else 0.0,
            "source": _SRC_NAMES.get(int(sources[k])) if f_hz else None,
            "intensityDb": round(float(intensity[k]), 1)
                           if np.isfinite(intensity[k]) else None,
        })

    comparison = _comparison_points(times, hz, strength, sources, ia, ib, f_lo, f_hi)
    chao, shape, feature_points = _chao_from_comparison(comparison)
    analysis_duration = float(times[ib] - times[ia])
    return {
        "t0": round(float(t0), 3), "t1": round(float(t1), 3),
        "analysisStart": round(float(times[ia]), 3),
        "analysisEnd": round(float(times[ib]), 3),
        "duration": round(float(max(t1 - t0, 0.0)), 3),
        "analysisDuration": round(analysis_duration, 3),
        "frames": frames,
        "comparisonPoints": comparison,
        "chao": chao, "shape": shape, "featurePoints": feature_points,
        "quality": quality,
    }


def process_syllables(track: PitchTrack, syll_bounds: list[tuple[float, float]],
                      f_lo: float, f_hi: float) -> list[dict]:
    """逐音节四步清洗（docs §3）；无有效音节时间戳时由调用方传整段区间。"""
    return [_process_one(track, t0, t1, f_lo, f_hi) for t0, t1 in syll_bounds]


def calibration_frequencies(track: PitchTrack,
                            syll_bounds: list[tuple[float, float]]) -> np.ndarray:
    """标定统计复用四步清洗后的可靠 Hz，不纳入插值及低置信度帧。

    清洗不依赖待求音域；传入搜索上下界只生成未使用的 degree 字段。
    长区间分块处理，覆盖整段标定录音；共享音节端点按原始时间去重。
    """
    max_duration = (MAX_SYLL_FRAMES - 1) * HOP_SEC
    bounds = []
    for start, end in syll_bounds:
        while end - start > max_duration:
            bounds.append((start, start + max_duration))
            start += max_duration
        bounds.append((start, end))
    frames_by_time = {}
    for side in process_syllables(track, bounds, PITCH_FLOOR_HZ, PITCH_TOP_HZ):
        for frame in side["frames"]:
            if (frame.get("hz") is not None
                    and frame.get("source") in ("measured", "corrected")
                    and frame.get("confidence", 0) >= ANCHOR_MIN_STRENGTH):
                frames_by_time[frame["t"]] = frame["hz"]
    return np.asarray(list(frames_by_time.values()), dtype=float)


# ---------------- 21 点比较序列（tone_py near/far 规则）----------------

def _comparison_points(times: np.ndarray, hz: np.ndarray, strength: np.ndarray,
                       sources: np.ndarray, ia: int, ib: int,
                       f_lo: float, f_hi: float) -> list[dict]:
    ts = times[ia:ib + 1]
    st = np.array([_st(float(f)) if np.isfinite(f) else np.nan
                   for f in hz[ia:ib + 1]])
    idx = np.arange(len(ts), dtype=float)
    t_start, t_end = float(ts[0]), float(ts[-1])
    out: list[dict] = []
    for p in range(COMPARISON_POINTS):
        u = p / (COMPARISON_POINTS - 1)
        x = t_start + u * (t_end - t_start)
        pos = float(np.interp(x, ts, idx)) if t_end > t_start else 0.0
        left = int(math.floor(pos))
        phase = pos - left
        near_i = left if phase < 0.5 else min(left + 1, len(ts) - 1)
        far_i = left + 1 if phase < 0.5 else left
        on_native = abs(pos - round(pos)) < 1e-6 and 0 <= round(pos) < len(ts)
        near_ok = near_i < len(ts) and np.isfinite(st[near_i])
        if not near_ok:
            out.append({"u": round(u, 3), "hz": None, "degree": None,
                        "confidence": 0.0, "source": None})
            continue
        far_ok = far_i < len(ts) and np.isfinite(st[far_i]) and far_i != near_i
        if far_ok and not on_native:
            # near→far 的插值权重：near 在左前进 phase，near 在右后退 1-phase
            w = phase if phase < 0.5 else 1.0 - phase
            st_v = st[near_i] + w * (st[far_i] - st[near_i])
            conf = min(float(strength[ia + near_i]), float(strength[ia + far_i]))
            source = "interpolated"
        else:
            st_v = st[near_i]
            conf = float(strength[ia + near_i])
            source = _SRC_NAMES.get(int(sources[ia + near_i]))
        f_hz = 2.0 ** (st_v / 12.0) * ST_REF_HZ
        out.append({
            "u": round(u, 3),
            "hz": round(float(f_hz), 1),
            "degree": round(float(hz_to_degree(f_hz, f_lo, f_hi)), 2),
            "confidence": round(conf, 2),
            "source": source,
        })
    return out


# ---------------- 近似调值（Chao 数字，docs §4.2.2）----------------

def _chao_from_comparison(comp: list[dict]):
    pts = [(p["u"], p["degree"]) for p in comp if p["degree"] is not None]
    if len(pts) < 4:
        return None, None, None
    us = np.array([u for u, _ in pts])
    ds = np.array([d for _, d in pts])

    def window_median(lo: float, hi_: float) -> tuple[float, float] | None:
        m = (us >= lo) & (us <= hi_)
        if not m.any():
            return None
        return float(np.median(us[m])), float(np.median(ds[m]))

    start = window_median(0.0, 0.10)
    end = window_median(0.90, 1.0)
    if start is None or end is None:
        return None, None, None
    inner = (us >= 0.15) & (us <= 0.85)

    d_start, d_end = start[1], end[1]
    feature = {"start": {"u": round(start[0], 3), "degree": round(d_start, 2)},
               "end": {"u": round(end[0], 3), "degree": round(d_end, 2)},
               "turning": None}
    digits = [d_start, d_end]
    # 内部有保留缺口 → 只输出两位端点调值（docs §4.2.2）
    has_inner_gap = any(p["degree"] is None for p in comp if 0.15 < p["u"] < 0.85)
    if inner.any() and not has_inner_gap:
        ius, ids = us[inner], ds[inner]
        k_max, k_min = int(np.argmax(ids)), int(np.argmin(ids))
        d_max, d_min = float(ids[k_max]), float(ids[k_min])
        dip_prom = min(d_start, d_end) - d_min
        peak_prom = d_max - max(d_start, d_end)
        take_dip = dip_prom >= CHAO_TURN_THRESHOLD and \
            (peak_prom < CHAO_TURN_THRESHOLD or dip_prom >= peak_prom)
        take_peak = peak_prom >= CHAO_TURN_THRESHOLD and not take_dip
        if take_dip:
            digits = [d_start, d_min, d_end]
            feature["turning"] = {"kind": "min", "u": round(float(ius[k_min]), 3),
                                  "degree": round(d_min, 2)}
        elif take_peak:
            digits = [d_start, d_max, d_end]
            feature["turning"] = {"kind": "max", "u": round(float(ius[k_max]), 3),
                                  "degree": round(d_max, 2)}
    chao = "".join(str(min(5, max(1, int(math.floor(d + 0.5))))) for d in digits)
    return chao, classify_contour(chao), feature


# ---------------- 哼鸣合成（docs §5.2，接入 tone_py.sonify）----------------

def sonify_frames(frames: list[dict], *, remap_range: tuple[float, float] | None = None,
                  duration: float | None = None, fs: int = 16000) -> bytes:
    """绘图帧 → WAV 音高哼鸣。

    连续有效段分别用 sonify_f0（三共振峰级联合成器，中性元音 /a/）合成，
    按原始时间放入输出；缺口填静音，段边缘短淡入淡出由 sonify 自带 fade
    实现。remap_range 给定时忽略原 Hz，按五度值映射到该音域
    （「按我的音域听标准」）。
    """
    if not any(fr.get("hz") is not None for fr in frames):
        raise F0PipelineError("没有可合成的有效音高段")
    f_lo, f_hi = remap_range or (0.0, 0.0)
    end_time = duration if duration is not None else frames[-1]["t"] + HOP_SEC
    total = int(round(end_time * fs))
    buf = np.zeros(total, dtype=np.float64)
    valid = np.array([fr.get("hz") is not None and
                      (remap_range is None or fr.get("degree") is not None)
                      for fr in frames])
    i = 0
    while i < len(frames):
        if not valid[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(frames) and valid[j + 1] \
                and abs(frames[j + 1]["t"] - frames[j]["t"] - HOP_SEC) < 0.001:
            j += 1
        seg = frames[i:j + 1]
        if remap_range:
            hz_seg = np.array([degree_to_hz(fr["degree"], f_lo, f_hi) for fr in seg])
        else:
            hz_seg = np.array([fr["hz"] for fr in seg], dtype=float)
        dur = seg[-1]["t"] - seg[0]["t"] + HOP_SEC
        inten = np.array([fr.get("intensityDb") if fr.get("intensityDb") is not None
                          else 60.0 for fr in seg], dtype=float)
        if len(seg) == 1:
            hz_seg, inten = np.repeat(hz_seg, 2), np.repeat(inten, 2)
        audio = sonify_f0(hz_seg, fs=fs, dur=dur, source="vowel", vowel="a",
                          intensity=inten)
        start = int(round(seg[0]["t"] * fs))
        end = min(start + len(audio), total)
        if end > start:
            buf[start:end] += audio[:end - start]
        i = j + 1
    return wav_bytes(np.clip(buf, -1.0, 1.0), fs)


def wav_bytes(pcm: np.ndarray, fs: int) -> bytes:
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes((pcm * 32767.0).astype("<i2").tobytes())
    return bio.getvalue()
