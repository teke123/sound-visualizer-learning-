"""音频解码与转码规范化：任意浏览器录音格式（webm/opus、mp4/aac、ogg、wav、mp3）
统一转 16 kHz 单声道 16-bit PCM WAV；内容哈希基于规范化 PCM（决策图 #11）。

ffmpeg 二进制来自 imageio-ffmpeg（随依赖分发）；进程外调用，不在数据库事务内。
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.platform.envelope import ApiError

SAMPLE_RATE = 16000

_FFMPEG_CANDIDATES: list[str] = []


def _ffmpeg_exe() -> str:
    if _FFMPEG_CANDIDATES:
        return _FFMPEG_CANDIDATES[0]
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        exe = "ffmpeg"
    _FFMPEG_CANDIDATES.append(exe)
    return exe


@dataclass
class NormalizedAudio:
    wav_path: Path
    duration_sec: float
    pcm_sha256: str


def probe_duration(path: Path) -> float:
    """转码后从 WAV 头读时长；失败时 0。"""
    import wave

    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / float(w.getframerate() or SAMPLE_RATE)
    except Exception:
        return 0.0


def normalize_to_wav(input_path: Path, output_path: Path) -> NormalizedAudio:
    """解码并转码为评测规范格式；无法解码抛 DECODE_FAILED（400）。"""
    cmd = [
        _ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(input_path),
        "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-sample_fmt", "s16",
        "-f", "wav", str(output_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired as e:
        raise ApiError(500, "INTERNAL_ERROR", "音频转码超时，请重试") from e
    if proc.returncode != 0 or not output_path.exists():
        detail = proc.stderr.decode("utf-8", "replace")[-300:]
        raise ApiError(400, "DECODE_FAILED",
                       "音频无法解码，请用浏览器录音后直接提交" + (f"（{detail}）" if detail else ""))
    duration = probe_duration(output_path)
    if duration <= 0:
        raise ApiError(400, "DECODE_FAILED", "音频为空，请检查麦克风后重录")
    sha = hashlib.sha256()
    with open(output_path, "rb") as f:
        # WAV 头之后即 PCM 数据；头长可变，用 data chunk 定位
        f.seek(0)
        buf = f.read()
        idx = buf.find(b"data")
        if idx >= 0:
            sha.update(buf[idx + 8: idx + 8 + int.from_bytes(buf[idx + 4:idx + 8], "little")])
        else:
            sha.update(buf)
    return NormalizedAudio(wav_path=output_path, duration_sec=round(duration, 3),
                           pcm_sha256=sha.hexdigest())


def read_pcm_samples(wav_path: Path):
    """读 16k 单声道 s16 WAV 为 numpy float32 [-1, 1]。"""
    import numpy as np
    import wave

    with wave.open(str(wav_path), "rb") as w:
        n = w.getnframes()
        raw = w.readframes(n)
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return samples


def with_tempfile(suffix: str):
    """临时文件上下文（Windows 下改名前须关闭句柄）。"""
    import contextlib

    @contextlib.contextmanager
    def _tmp():
        fd, name = tempfile.mkstemp(suffix=suffix)
        import os

        os.close(fd)
        try:
            yield Path(name)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(name)

    return _tmp()
