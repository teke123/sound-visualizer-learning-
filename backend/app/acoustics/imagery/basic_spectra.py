"""基础频谱图像：宽带、窄带、预加重宽带、Log-Mel 与 MFCC（方案 §2.3、§2.4、§8.2、§9）。

- 宽带/窄带用 Praat Spectrogram（Gaussian 窗），实际网格 dx/dy 以对象读数为准并写入 params；
- Mel/MFCC 用 numpy 按 librosa 默认行为实现（周期 Hann 窗、center=True 补零、功率谱、
  Slaney Mel 刻度与面积归一化、DCT-II 正交、Savitzky-Golay 差分），不依赖 librosa；
- dB 参考值固定：语谱图沿用 Praat 绘图参考（common.PRAAT_POWER_REF），Mel 用 1.0
  （方案 §8.2：跨录音比较不能用各录音自身最大值作参考）；
- 显示上限由调用方传入的 DbScales 跨样本统一，下限 = 上限 − 动态范围；
- 02b 的预加重只作用于显示（+6 dB/oct），不改变测量用频谱。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .common import (Alignment, BROADBAND, DbScales, NARROWBAND, db, draw_boundaries,
                     mark_edge_regions, new_result, plot_spectrogram, save_fig, set_time_axis,
                     setup_matplotlib, spectrogram, spectrogram_actual, spectrogram_arrays,
                     to_sound, write_csv)

BROADBAND_FMAX = 12000.0        # 宽带显示与计算频率上限（高采样率录音，方案 §2.3）
NARROWBAND_FMAX = 5000.0        # 窄带显示与计算频率上限
NARROWBAND_WINDOW_SEC = 0.060   # 窄带 30 ms Gaussian 窗的物理长度（2 × 窗长），首尾各半不完整
SPECTROGRAM_RANGE_DB = 50.0     # 宽带/窄带动态范围

N_MELS = 80
MEL_WIN_SEC = 0.025
MEL_HOP_SEC = 0.005
MEL_FMIN = 0.0
MEL_FMAX = 12000.0              # 实际再与奈奎斯特频率取小
MEL_RANGE_DB = 80.0             # Log-Mel 动态范围
MEL_YTICK_HZ = (500.0, 1000.0, 2000.0, 4000.0, 8000.0, 12000.0)   # 纵轴刻度对应的频率

MFCC_HOP_SEC = 0.010
N_MFCC = 13
MFCC_DB_FLOOR = 1e-10           # MFCC 输入 log-mel 的固定下限（amin，取 librosa power_to_db 默认值）
DELTA_WIDTH = 9                 # Δ/ΔΔ 的 Savitzky-Golay 窗宽（帧）

# Slaney Mel 刻度（librosa.filters.mel 默认）：1000 Hz 以下线性（斜率 200/3），
# 以上对数段步长 ln(6.4)/27；1 kHz 处两种定义的衔接点为 15 mel。
_MEL_F_SP = 200.0 / 3.0
_MEL_LOGSTEP = float(np.log(6.4) / 27.0)


def _hz_to_mel(freqs: np.ndarray) -> np.ndarray:
    """Slaney Mel 频率（librosa hz_to_mel 默认，非 HTK）。"""
    f = np.asarray(freqs, dtype=float)
    linear = f / _MEL_F_SP
    return np.where(f >= 1000.0,
                    15.0 + np.log(np.maximum(f, 1000.0) / 1000.0) / _MEL_LOGSTEP,
                    linear)


def _mel_to_hz(mels: np.ndarray) -> np.ndarray:
    m = np.asarray(mels, dtype=float)
    linear = _MEL_F_SP * m
    return np.where(m >= 15.0, 1000.0 * np.exp(_MEL_LOGSTEP * (m - 15.0)), linear)


def _mel_filterbank(sr: int, n_fft: int, fmax: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """80 个 Slaney 三角 Mel 滤波器，返回 (滤波器组, 中心频率 Hz, 中心频率 mel)。

    行为对齐 librosa.filters.mel(sr, n_fft, n_mels=80, fmin=0, fmax, norm="slaney")：
    相邻滤波器重叠 2，每行乘 2/(f_{i+2} − f_i) 做面积归一化。
    """
    fftfreqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    mel_f = _mel_to_hz(np.linspace(float(_hz_to_mel(np.array(MEL_FMIN))),
                                   float(_hz_to_mel(np.array(fmax))), N_MELS + 2))
    fdiff = np.diff(mel_f)
    ramps = np.subtract.outer(mel_f, fftfreqs)
    weights = np.zeros((N_MELS, len(fftfreqs)))
    for i in range(N_MELS):
        lower = -ramps[i] / fdiff[i]
        upper = ramps[i + 2] / fdiff[i + 1]
        weights[i] = np.maximum(0.0, np.minimum(lower, upper))
    weights *= (2.0 / (mel_f[2:] - mel_f[:N_MELS]))[:, None]
    centers = mel_f[1:-1]
    return weights, centers, _hz_to_mel(centers)


def _stft_power(x: np.ndarray, n_fft: int, win_length: int, hop_length: int) -> np.ndarray:
    """与 librosa.stft(center=True) + 功率谱一致的 STFT，形状 (帧, 频率 bin)。

    周期 Hann 窗居中补零到 n_fft；录音首尾各补 n_fft//2 个零，帧中心位于 k·hop；
    录音首尾不足半窗的帧因此含补零样本（调用方负责在图上标出该区域）。
    """
    from scipy.signal import get_window

    window = np.zeros(n_fft)
    left = (n_fft - win_length) // 2
    window[left:left + win_length] = get_window("hann", win_length)   # fftbins=True → 周期 Hann
    padded = np.pad(np.asarray(x, dtype=float), (n_fft // 2, n_fft // 2))
    n_frames = 1 + len(x) // hop_length
    idx = np.arange(n_frames)[:, None] * hop_length + np.arange(n_fft)[None, :]
    frames = padded[idx] * window[None, :]
    return np.abs(np.fft.rfft(frames, axis=1)) ** 2


def _log_mel(x: np.ndarray, sr: int, hop_sec: float, db_floor: float = 1e-20) -> dict:
    """80 维 Log-Mel 频谱（dB，固定参考值 1.0），帧中心位于 k·hop。"""
    win_length = int(round(MEL_WIN_SEC * sr))
    n_fft = 1 << (win_length - 1).bit_length()   # 不小于窗长的 2 的整数次幂
    hop_length = int(round(hop_sec * sr))
    fmax = min(MEL_FMAX, sr / 2)
    power = _stft_power(x, n_fft, win_length, hop_length)
    weights, centers_hz, centers_mel = _mel_filterbank(sr, n_fft, fmax)
    mel_db = db(weights @ power.T, ref=1.0, floor=db_floor)
    return {
        "times": np.arange(mel_db.shape[1]) * hop_length / sr,
        "mel_db": mel_db,               # (N_MELS, 帧)
        "centers_hz": centers_hz,
        "centers_mel": centers_mel,
        "params": {"win_length": win_length, "n_fft": n_fft, "hop_length": hop_length,
                   "hop_sec": hop_length / sr, "n_mels": N_MELS, "fmin": MEL_FMIN,
                   "fmax": float(fmax), "window": "hann（周期）", "power": 2.0, "center": True,
                   "db_ref": 1.0, "db_floor": db_floor, "n_frames": int(mel_db.shape[1]),
                   "edge_affected_sec": MEL_WIN_SEC / 2},
    }


def _mfcc_features(x: np.ndarray, sr: int) -> dict:
    """MFCC 0–12 及其一阶、二阶差分（25 ms 窗 / 10 ms 步长）。

    窗、Mel 滤波器、DCT 与差分对齐 librosa 默认行为；log-mel 输入按方案 §8.2 用
    固定参考值 ref=1.0 与固定下限 amin=1e-10，不做相对本录音最大值的 top_db 裁剪，
    使系数跨录音可比。
    """
    from scipy.fft import dct
    from scipy.signal import savgol_filter

    lm = _log_mel(x, sr, MFCC_HOP_SEC, db_floor=MFCC_DB_FLOOR)
    mfcc = dct(lm["mel_db"], type=2, norm="ortho", axis=0)[:N_MFCC]
    # librosa.feature.delta 默认：Savitzky-Golay，width=9，mode="interp"，polyorder=order
    delta1 = savgol_filter(mfcc, DELTA_WIDTH, 1, deriv=1, axis=-1, mode="interp")
    delta2 = savgol_filter(mfcc, DELTA_WIDTH, 2, deriv=2, axis=-1, mode="interp")
    return {"times": lm["times"], "mfcc": mfcc, "delta1": delta1, "delta2": delta2,
            "mel_params": lm["params"]}


def _preemphasis_db(freqs: np.ndarray) -> np.ndarray:
    """显示用预加重曲线：+6 dB/oct（以 1 kHz 为 0 dB 基准，即 6.0206·log2(f/1000)）；0 Hz 处为 0。"""
    lift = np.zeros_like(freqs, dtype=float)
    pos = freqs > 0
    lift[pos] = 20.0 * np.log10(2.0) * np.log2(freqs[pos] / 1000.0)
    return lift


def db_levels(x: np.ndarray, sr: int) -> dict:
    """该录音四张基础频谱图 dB 值的最大值，计算与出图完全一致，供整批统一显示标尺（DbScales）。"""
    snd = to_sound(x, sr)
    _, freqs_bb, db_bb = spectrogram_arrays(spectrogram(snd, "broadband", BROADBAND_FMAX))
    _, _, db_nb = spectrogram_arrays(spectrogram(snd, "narrowband", NARROWBAND_FMAX))
    db_bb_pre = db_bb + _preemphasis_db(freqs_bb)[:, None]
    mel_db = _log_mel(x, sr, MEL_HOP_SEC)["mel_db"]
    return {
        "broadband_max_db": float(np.max(db_bb)),
        "broadband_preemph_max_db": float(np.max(db_bb_pre)),
        "narrowband_max_db": float(np.max(db_nb)),
        "mel_max_db": float(np.max(mel_db)),
    }


# ---------------- 出图 ----------------

def _fig_spectrogram(times: np.ndarray, freqs: np.ndarray, values_db: np.ndarray,
                     aln: Alignment, out_dir: Path, name: str, title: str, vmax: float,
                     dynamic_range: float, fmax: float, edge_sec: float | None = None,
                     colorbar_label: str = "功率谱级 (dB)") -> Path:
    plt = setup_matplotlib()
    fig, ax = plt.subplots(figsize=(12, 5))
    mesh = plot_spectrogram(ax, times, freqs, values_db, vmax=vmax,
                            dynamic_range=dynamic_range, fmax=fmax)
    if edge_sec is not None:
        mark_edge_regions(ax, aln.duration, edge_sec)
    set_time_axis(ax, aln)
    draw_boundaries(ax, aln)
    ax.set_title(title)   # 两行标题，避免单行过长把 tight 画布撑宽
    fig.colorbar(mesh, ax=ax, label=colorbar_label)
    return save_fig(fig, out_dir, name)


def _fig_mel(lm: dict, aln: Alignment, out_dir: Path, stem: str, vmax: float) -> Path:
    plt = setup_matplotlib()
    fig, ax = plt.subplots(figsize=(12, 5))
    p = lm["params"]
    mesh = plot_spectrogram(ax, lm["times"], np.arange(N_MELS, dtype=float), lm["mel_db"],
                            vmax=vmax, dynamic_range=MEL_RANGE_DB, fmax=N_MELS - 0.5)
    # 纵轴为 Mel 通道，在指定频率对应的通道位置标刻度（在 mel 坐标上线性插值）
    ticks = np.array([f for f in MEL_YTICK_HZ if f <= p["fmax"]])
    pos = np.interp(_hz_to_mel(ticks), lm["centers_mel"], np.arange(N_MELS))
    ax.set_yticks(pos, [f"{f / 1000:g}k" for f in ticks])
    ax.set_ylabel("频率 (Hz，Mel 刻度)")
    mark_edge_regions(ax, aln.duration, MEL_WIN_SEC)
    set_time_axis(ax, aln)
    draw_boundaries(ax, aln)
    ax.set_title(f"{stem} 80 维 Log-Mel 频谱：Hann 窗 {MEL_WIN_SEC * 1000:.0f} ms（{p['win_length']} 点），"
                 f"步长 {p['hop_sec'] * 1000:.2f} ms，FFT {p['n_fft']}，fmax {p['fmax'] / 1000:g} kHz\n"
                 f"dB 参考 1.0，动态范围 {MEL_RANGE_DB:.0f} dB；斜线区=首尾半窗补零")
    fig.colorbar(mesh, ax=ax, label="Mel 功率谱级 (dB)")
    return save_fig(fig, out_dir, "04_mel80.png")


def _fig_mfcc(feats: dict, aln: Alignment, out_dir: Path, stem: str) -> Path:
    plt = setup_matplotlib()
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    times = feats["times"]
    coef_pos = np.arange(N_MFCC, dtype=float)
    p = feats["mel_params"]
    edge_sec = DELTA_WIDTH * p["hop_sec"]   # Savitzky-Golay 边缘多项式拟合影响的时长

    # MFCC 面板：C0 主要反映总能量，数值远大于其他系数；色标只按 C1–C12 对称定标，
    # 否则 C1–C12 会被 C0 压成同色
    v_mfcc = float(np.max(np.abs(feats["mfcc"][1:])))
    mesh = axes[0].pcolormesh(times, coef_pos, feats["mfcc"], shading="nearest",
                              cmap="coolwarm", vmin=-v_mfcc, vmax=v_mfcc)
    axes[0].set_title("MFCC 0–12（DCT-II 正交；色标按 C1–C12 对称定标，C0 只反映总能量、不参与定标）",
                      fontsize=10, loc="left")
    fig.colorbar(mesh, ax=axes[0], label="系数值")

    for ax, data, subtitle, clabel in (
            (axes[1], feats["delta1"], "一阶差分 Δ（Savitzky-Golay，width=9，mode=interp）", "dB/帧"),
            (axes[2], feats["delta2"], "二阶差分 ΔΔ（Savitzky-Golay，width=9，mode=interp）", "dB/帧²")):
        v = float(np.max(np.abs(data)))
        mesh = ax.pcolormesh(times, coef_pos, data, shading="nearest", cmap="coolwarm", vmin=-v, vmax=v)
        # 首尾约 ±45 ms（width/2 帧）是 Savitzky-Golay 的边缘多项式拟合区，数值整块同色
        mark_edge_regions(ax, aln.duration, edge_sec)
        ax.set_title(subtitle + f"；斜线区=边缘拟合区（首尾 ±{edge_sec / 2 * 1000:.0f} ms）",
                     fontsize=10, loc="left")
        fig.colorbar(mesh, ax=ax, label=clabel)

    for ax in axes:
        ax.set_ylabel("MFCC 序号")
        ax.set_xlim(0.0, aln.duration)
        draw_boundaries(ax, aln, labels=ax is axes[0])
    set_time_axis(axes[2], aln)   # 只在最底面板标时间轴，避免压住下一面板的标题
    fig.suptitle(f"{stem} MFCC 压缩特征图：Log-Mel({N_MELS}，{MEL_WIN_SEC * 1000:.0f} ms 窗 / "
                 f"{p['hop_sec'] * 1000:.0f} ms 步长，dB 参考 1.0、无 top_db 裁剪) → "
                 f"DCT-II 取 {N_MFCC} 系数", y=0.995)
    return save_fig(fig, out_dir, "04b_mfcc.png")


def _mfcc_table_rows(feats: dict) -> list[dict]:
    rows: list[dict] = []
    for j, t in enumerate(feats["times"]):
        row: dict = {"time_s": round(float(t), 4)}
        for i in range(N_MFCC):
            row[f"mfcc_{i}"] = round(float(feats["mfcc"][i, j]), 5)
            row[f"delta1_{i}"] = round(float(feats["delta1"][i, j]), 5)
            row[f"delta2_{i}"] = round(float(feats["delta2"][i, j]), 5)
        rows.append(row)
    return rows


# ---------------- 模块入口 ----------------

def generate(x: np.ndarray, sr: int, aln: Alignment, out_dir: str | Path,
             scales: DbScales | None = None, context: dict | None = None) -> dict:
    """生成基础频谱图像 02/02b/03/04/04b 与 MFCC 数值表（context 未使用的键直接忽略）。"""
    result = new_result()
    out_dir = Path(out_dir)
    stem = Path(aln.file).stem
    params = result["params"]
    vmax_bb = vmax_bb_pre = vmax_nb = vmax_mel = None   # 实际使用的显示上限（供 params 记录）

    if scales is None:
        result["warnings"].append(
            "未传入统一 dB 标尺 DbScales，各图色标上限取本录音最大值，仅限调试，跨样本不可比")

    def register(name: str, producer) -> None:
        """单张图失败只记 warning，不影响其余图像。"""
        try:
            path = producer()
        except Exception as e:
            result["warnings"].append(f"{name} 生成失败：{type(e).__name__}: {e}")
        else:
            result["images"][name] = path

    # —— 宽带（02 与 02b 共用同一 Praat Spectrogram）——
    try:
        sg_bb = spectrogram(to_sound(x, sr), "broadband", BROADBAND_FMAX)
        t_bb, f_bb, db_bb = spectrogram_arrays(sg_bb)
        actual_bb = spectrogram_actual(sg_bb)
        params["broadband_settings"] = BROADBAND
        params["broadband_actual"] = actual_bb
        db_bb_pre = db_bb + _preemphasis_db(f_bb)[:, None]
        vmax_bb = scales.broadband_max_db if scales else float(np.max(db_bb))
        vmax_bb_pre = scales.broadband_preemph_max_db if scales else float(np.max(db_bb_pre))
        register("02_broadband.png", lambda: _fig_spectrogram(
            t_bb, f_bb, db_bb, aln, out_dir, "02_broadband.png",
            f"{stem} 宽带语谱图：Gaussian 窗 5 ms，步长 {actual_bb['dx'] * 1000:.1f} ms，"
            f"频率步长 {actual_bb['dy']:.1f} Hz\n"
            f"显示 0–{BROADBAND_FMAX / 1000:g} kHz，动态范围 {SPECTROGRAM_RANGE_DB:.0f} dB",
            vmax_bb, SPECTROGRAM_RANGE_DB, BROADBAND_FMAX))
        register("02b_broadband_preemph.png", lambda: _fig_spectrogram(
            t_bb, f_bb, db_bb_pre, aln, out_dir, "02b_broadband_preemph.png",
            f"{stem} 宽带语谱图（Gaussian 窗 5 ms，显示用预加重 +6 dB/oct）\n"
            f"仅增强可见性，不可用于测量；显示 0–{BROADBAND_FMAX / 1000:g} kHz，"
            f"动态范围 {SPECTROGRAM_RANGE_DB:.0f} dB",
            vmax_bb_pre, SPECTROGRAM_RANGE_DB, BROADBAND_FMAX,
            colorbar_label="预加重后谱级 (dB，仅供显示)"))
    except Exception as e:
        result["warnings"].append(f"02_broadband/02b_broadband_preemph 计算失败：{type(e).__name__}: {e}")

    # —— 窄带 ——
    try:
        sg_nb = spectrogram(to_sound(x, sr), "narrowband", NARROWBAND_FMAX)
        t_nb, f_nb, db_nb = spectrogram_arrays(sg_nb)
        actual_nb = spectrogram_actual(sg_nb)
        params["narrowband_settings"] = NARROWBAND
        params["narrowband_actual"] = actual_nb
        vmax_nb = scales.narrowband_max_db if scales else float(np.max(db_nb))
        register("03_narrowband.png", lambda: _fig_spectrogram(
            t_nb, f_nb, db_nb, aln, out_dir, "03_narrowband.png",
            f"{stem} 窄带语谱图：Gaussian 窗 30 ms，步长 {actual_nb['dx'] * 1000:.1f} ms，"
            f"频率步长 {actual_nb['dy']:.2f} Hz\n"
            f"显示 0–{NARROWBAND_FMAX / 1000:g} kHz，动态范围 {SPECTROGRAM_RANGE_DB:.0f} dB；"
            f"斜线区=首尾 ±{NARROWBAND_WINDOW_SEC / 2 * 1000:.0f} ms（物理窗 60 ms 的一半）分析不完整",
            vmax_nb, SPECTROGRAM_RANGE_DB, NARROWBAND_FMAX, edge_sec=NARROWBAND_WINDOW_SEC))
    except Exception as e:
        result["warnings"].append(f"03_narrowband 计算失败：{type(e).__name__}: {e}")

    # —— Log-Mel ——
    try:
        lm = _log_mel(x, sr, MEL_HOP_SEC)
        params["mel80"] = lm["params"]
        vmax_mel = scales.mel_max_db if scales else float(np.max(lm["mel_db"]))
        result["warnings"].append(
            f"04_mel80：录音首尾各约 {MEL_WIN_SEC / 2 * 1000:.1f} ms（半窗）内的帧伸出录音边界，"
            "已按 center=True 补零（图中斜线区域），该处 Mel 值偏低，仅供参考")
        register("04_mel80.png", lambda: _fig_mel(lm, aln, out_dir, stem, vmax_mel))
    except Exception as e:
        result["warnings"].append(f"04_mel80 计算失败：{type(e).__name__}: {e}")

    # —— MFCC 及差分 ——
    try:
        feats = _mfcc_features(x, sr)
        params["mfcc"] = {**feats["mel_params"], "n_mfcc": N_MFCC,
                          "dct": "DCT-II（norm=ortho）",
                          "top_db": None,   # 不做相对本录音最大值的裁剪（方案 §8.2，跨录音可比）
                          "delta": f"Savitzky-Golay width={DELTA_WIDTH}，polyorder=deriv，mode=interp"}
        register("04b_mfcc.png", lambda: _fig_mfcc(feats, aln, out_dir, stem))
        try:
            result["tables"]["04b_mfcc.csv"] = write_csv(_mfcc_table_rows(feats),
                                                         out_dir / "csv", "04b_mfcc.csv")
        except Exception as e:
            result["warnings"].append(f"04b_mfcc.csv 写入失败：{type(e).__name__}: {e}")
    except Exception as e:
        result["warnings"].append(f"04b_mfcc 计算失败：{type(e).__name__}: {e}")

    params["display_vmax_db"] = {"broadband": vmax_bb, "broadband_preemph": vmax_bb_pre,
                                 "narrowband": vmax_nb, "mel": vmax_mel}
    return result
