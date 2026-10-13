"""使用 pYIN、LPC 和 MFCC 提取声学特征。"""
import numpy as np
import librosa
from .models import AcousticFeatures

FRAME_LENGTH = 2048
HOP_LENGTH = 512

def lpc_yule_walker(x: np.ndarray, order: int = 14) -> np.ndarray:
    """Yule-Walker 方程求解 LPC 系数"""
    try:
        from scipy.linalg import toeplitz
    except ImportError:
        return np.zeros(order + 1)
    x = x - np.mean(x)
    n = len(x)
    if n <= order + 1:
        return np.zeros(order + 1)
    r = np.correlate(x, x, "full")[n - 1: n + order]
    try:
        R = toeplitz(r[:-1])
        a = -np.linalg.solve(R, r[1:])
    except (np.linalg.LinAlgError, ValueError):
        return np.zeros(order + 1)
    return np.concatenate(([1.0], a))


def estimate_formants(y: np.ndarray, sr: int) -> tuple[list[float], list[float]]:
    """通过 LPC 系数估计每帧的两个共振峰候选。"""
    frames = librosa.util.frame(y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)
    f1_list: list[float] = []
    f2_list: list[float] = []
    for i in range(frames.shape[1]):
        frame = frames[:, i].copy()
        # 预加重
        frame = np.append(frame[0], frame[1:] - 0.97 * frame[:-1])
        # 加窗
        frame = frame * np.hanning(len(frame))
        # 静音帧跳过
        if np.sqrt(np.mean(frame ** 2)) < 1e-6:
            f1_list.append(0.0)
            f2_list.append(0.0)
            continue
        a = lpc_yule_walker(frame)
        if np.all(a == 0):
            f1_list.append(0.0)
            f2_list.append(0.0)
            continue
        roots = np.roots(a)
        roots = [r for r in roots if np.imag(r) > 0 and 0.5 < np.abs(r) < 1.0]
        if not roots:
            f1_list.append(0.0)
            f2_list.append(0.0)
            continue
        # 计算频率与带宽，按带宽排序选取稳定共振峰
        freqs_bw = []
        for r in roots:
            freq = np.abs(np.angle(r)) * sr / (2 * np.pi)
            if freq < 100 or freq > sr / 2 - 200:
                continue
            bw = -np.log(np.abs(r)) * sr / np.pi
            freqs_bw.append((freq, bw))
        freqs_bw.sort(key=lambda x: x[1])
        formants = [f for f, _ in freqs_bw[:2]]
        while len(formants) < 2:
            formants.append(0.0)
        f1_list.append(float(formants[0]))
        f2_list.append(float(formants[1]))
    return f1_list, f2_list


def analyze_audio(audio_data: np.ndarray, sr: int) -> AcousticFeatures:
    """接收波形与采样率，返回 F0、F1/F2、能量和 MFCC。"""

    y_orig = np.asarray(audio_data, dtype=np.float32)
    if y_orig.ndim > 1:
        # 只适用于 (n_samples, n_channels) 排列。
        y_orig = np.mean(y_orig, axis=-1)


    if y_orig.size == 0:
        return AcousticFeatures(
            f0=[],
            f1=[],
            f2=[],
            energy=[],
            duration=0.0,
            sample_rate=sr,
            mfcc=[],
        )

    # 在预加重前计算能量。
    energy = librosa.feature.rms(y=y_orig)[0].tolist()

    # 去除直流偏移。
    y = y_orig - float(np.mean(y_orig))

    # 预加重系数为 0.97。
    alpha = 0.97
    y_pre = np.empty_like(y)
    y_pre[0] = y[0]
    if y_pre.size > 1:
        y_pre[1:] = y[1:] - alpha * y[:-1]

    # 基频F0的提取
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y_pre, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'), sr=sr
    )
    f0 = np.nan_to_num(f0, nan=0.0).tolist()


    mfcc = librosa.feature.mfcc(y=y_pre, sr=sr, n_mfcc=13)
    mfcc_list = mfcc.tolist()


    f1, f2 = estimate_formants(y_pre, sr)

    duration = len(y_orig) / sr

    return AcousticFeatures(
        f0=f0,
        f1=f1,
        f2=f2,
        energy=energy,
        duration=duration,
        sample_rate=sr,
        mfcc=mfcc_list,
        voiced_flag=voiced_flag,
        voiced_probs=voiced_probs,
    )

