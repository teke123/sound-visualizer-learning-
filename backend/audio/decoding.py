"""使用 soundfile 和 FFmpeg 将音频文件解码为单声道浮点波形。"""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

import numpy as np
import soundfile as sf


@dataclass
class DecodedAudio:
    samples: np.ndarray
    sample_rate: int


def decode_audio(path: str | Path) -> DecodedAudio:
    """读取音频文件，返回单声道波形及采样率。"""
    try:
        samples, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    except Exception:
        samples, sample_rate = _decode_via_ffmpeg(path)
    return DecodedAudio(samples.mean(axis=1), sample_rate)


def _decode_via_ffmpeg(path: str | Path) -> tuple[np.ndarray, int]:
    """将音频转码为 16 kHz 单声道 WAV，并读取波形。"""
    import imageio_ffmpeg

    with TemporaryDirectory(prefix="pronunciation-decode-") as directory:
        output = Path(directory) / "decoded.wav"
        result = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(path),
             "-ar", "16000", "-ac", "1", "-f", "wav", str(output)],
            capture_output=True,
        )
        if result.returncode != 0:
            error = result.stderr.decode("utf-8", errors="replace")[-200:]
            raise RuntimeError(f"ffmpeg 解码失败: {error}")
        return sf.read(output, dtype="float32", always_2d=True)
