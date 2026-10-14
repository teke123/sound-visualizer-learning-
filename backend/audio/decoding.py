"""音频解码（重构占位骨架）。

意图：把任意上传格式（WAV/WebM/Opus…）解码为单声道浮点波形。
- 首选 soundfile 直读；失败回落 FFmpeg 转码（浏览器 webm 录音必需）；
- 输出幅度语义必须全链路统一（原始 [-1,1] 还是归一化，只允许一种口径）。
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class DecodedAudio:
    samples: np.ndarray
    sample_rate: int


def decode_audio(path) -> DecodedAudio:
    """意图：读音频文件，返回单声道波形及采样率。"""
    raise NotImplementedError("重构占位：音频解码")
