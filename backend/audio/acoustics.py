"""声学测量（重构占位骨架）。

意图：以 Praat(parselmouth) 为唯一测量引擎，返回独立时间轴上的
F0、F1/F2、能量和 MFCC；librosa 只承担能量/MFCC。
- 各轨迹自带帧中心时间（f0_times / formant_times / ...），禁止按索引跨轨迹对齐；
- 未测得的值以 0 写入，禁止 NaN 进入 JSON；
- 幅度约定：输入为单声道或 (samples, channels)，本模块不改幅度
  （归一化口径由调用方统一定义，避免不同管线幅度语义不一致）。
"""
import numpy as np

from .models import AcousticFeatures

# 测量参数（意图默认值，调用方可经接口覆盖）
FRAME_LENGTH = 2048
HOP_LENGTH = 512
TIME_STEP = 0.01
PITCH_FLOOR = 75.0
PITCH_CEILING = 600.0
MAXIMUM_FORMANT = 5500.0
FORMANT_WINDOW = 0.025


def _waveform(audio_data: np.ndarray, sr: int) -> np.ndarray:
    """意图：校验并规整为单声道一维有限波形，不改变幅度。"""
    raise NotImplementedError("重构占位：波形规整")


def _formant_tracks(sound, time_step: float, maximum_formant: float):
    """意图：Praat Burg 共振峰轨迹（F1/F2 + 时间轴），NaN 归零。"""
    raise NotImplementedError("重构占位：共振峰轨迹")


def analyze_audio(audio_data: np.ndarray, sr: int, *, time_step: float = TIME_STEP,
                  pitch_floor: float = PITCH_FLOOR, pitch_ceiling: float = PITCH_CEILING,
                  maximum_formant: float = MAXIMUM_FORMANT) -> AcousticFeatures:
    """意图：完整声学特征测量（F0/F1/F2/能量/MFCC + 元数据），不做评分。"""
    raise NotImplementedError("重构占位：声学特征分析")
