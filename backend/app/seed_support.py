"""种子音频合成器：为示范/听辨刺激/参考发音人生成 16 kHz 单声道 WAV。

合成目标不是拟真语音，而是「可提取 F0 与共振峰的声道模型示意音频」：
- 声源：谐波丰富的脉冲串（1/n 幅度至 ~4 kHz）+ 声调轮廓；
- 声道：三个并联谐振器（F1/F2/F3，按元音设定）；
- 声母：塞音（静默+爆破）、塞擦音（爆破+摩擦）、擦音（摩擦噪声带）、
  鼻音/边音（低共振浊音段）。
正式示范音频由内容方通过后台上传替换。
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from app.pinyin_utils import expected_syllables, main_vowel, split_pinyin

SR = 16000

VOWEL_FORMANTS = {
    "a": (820, 1200, 2600),
    "o": (500, 850, 2600),
    "e": (550, 1650, 2500),
    "i": (290, 2250, 3000),
    "u": (320, 800, 2400),
    "ü": (310, 1700, 2300),
}
VOICE_BASE_F0 = {"male": 130.0, "female": 215.0}


def _resonator(f: float, bw: float = 90.0) -> tuple[float, float]:
    r = np.exp(-np.pi * bw / SR)
    theta = 2 * np.pi * f / SR
    return 2 * r * np.cos(theta), -(r * r)


def _apply_resonators(x: np.ndarray, formants: tuple[float, float, float],
                      gain: float = 1.0) -> np.ndarray:
    """三并联谐振器（b0=1 的二阶 IIR，scipy 实现）。"""
    from scipy.signal import lfilter

    out = np.zeros_like(x)
    for f in formants:
        a1, a2 = _resonator(f)
        out += lfilter([1.0], [1.0, -a1, -a2], x)
    return out * gain


def _tone_envelope(n: int, tone: int | None) -> np.ndarray:
    """声调 → F0 倍率轮廓。"""
    t = np.linspace(0, 1, n)
    if tone == 2:
        return 0.86 + 0.30 * t
    if tone == 3:
        return 1.08 - 0.30 * np.minimum(t / 0.45, 1.0) + 0.26 * np.maximum((t - 0.5) / 0.5, 0.0)
    if tone == 4:
        return 1.22 - 0.42 * t
    return 1.0 - 0.04 * t   # 一声近似平，微降


def _voiced(dur: float, f0_hz: np.ndarray) -> np.ndarray:
    """谐波脉冲串（1/n 至 4 kHz）。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    phase = 2 * np.pi * np.cumsum(f0_hz) / SR
    x = np.zeros(n)
    k = 1
    while k * float(np.median(f0_hz)) < 4000 and k <= 40:
        x += np.sin(k * phase) / k
        k += 1
    return x


def _noise(dur: float, center: float | None, bw: float = 1500.0) -> np.ndarray:
    n = int(dur * SR)
    rng = np.random.default_rng(12345)
    x = rng.standard_normal(n)
    if center is not None:
        from scipy.signal import lfilter

        a1, a2 = _resonator(center, bw=bw)
        x = lfilter([1.0], [1.0, -a1, -a2], x)
    return x


CONSONANT_KINDS = {
    # 声母 → (类型, 参数)
    "b": ("stop", 0), "d": ("stop", 0), "g": ("stop", 0),
    "p": ("stop", 1), "t": ("stop", 1), "k": ("stop", 1),
    "z": ("affricate", 4500), "c": ("affricate", 4500),
    "zh": ("affricate", 3000), "ch": ("affricate", 3000),
    "j": ("affricate", 3800), "q": ("affricate", 3800),
    "f": ("fricative", 1500), "s": ("fricative", 5500), "x": ("fricative", 4200),
    "sh": ("fricative", 3200), "h": ("fricative", 1800), "r": ("fricative", 1800),
    "m": ("nasal", 0), "n": ("nasal", 0), "l": ("lateral", 0),
    "y": ("glide", 0), "w": ("glide", 0),
}


def synthesize_text(text: str, voice: str = "male", *, syllable_dur: float = 0.32,
                    pause: float = 0.10) -> np.ndarray:
    """汉字串 → 声道模型合成音频（16k float [-1,1]）。"""
    base = VOICE_BASE_F0.get(voice, 150.0)
    chunks: list[np.ndarray] = []
    silence = np.zeros(int(pause * SR))
    for e in expected_syllables(text):
        plain, tone = e["plain"], e["tone"]
        initial, final = split_pinyin(plain)
        vowel = main_vowel(final, "a")
        formants = VOWEL_FORMANTS.get(vowel, VOWEL_FORMANTS["a"])

        # 声母段
        pre: np.ndarray | None = None
        kind = CONSONANT_KINDS.get(initial)
        if kind:
            ktype, param = kind
            if ktype == "stop":
                burst = _noise(0.012, 2000, bw=2500) * (0.7 if param else 0.45)
                pre = np.concatenate([np.zeros(int(0.06 * SR)), burst])
                if param:   # 送气
                    pre = np.concatenate([pre, _noise(0.05, 1200, bw=2000) * 0.35])
            elif ktype in ("affricate",):
                pre = np.concatenate([_noise(0.012, param, bw=1800) * 0.55,
                                      _noise(0.06, param, bw=1400) * 0.4])
            elif ktype == "fricative":
                pre = _noise(0.08, param, bw=1600) * (0.28 if initial == "r" else 0.35)
            elif ktype in ("nasal", "lateral"):
                n = int(0.09 * SR)
                f0 = np.full(n, base * 0.92)
                murmur = _apply_resonators(_voiced(0.09, f0), (280, 1000, 2200)) * 0.5
                pre = murmur
            elif ktype == "glide":
                n = int(0.05 * SR)
                pre = _apply_resonators(
                    _voiced(0.05, np.linspace(base * 1.1, base, n)), formants) * 0.4

        # 韵母段（声调轮廓作用于 F0）
        n = int(syllable_dur * SR)
        f0 = base * _tone_envelope(n, tone)
        vowel_x = _voiced(syllable_dur, f0)
        shaped = _apply_resonators(vowel_x, formants)
        # 边界淡入淡出
        edge = int(0.02 * SR)
        if len(shaped) > 2 * edge:
            shaped[:edge] *= np.linspace(0, 1, edge)
            shaped[-edge:] *= np.linspace(1, 0, edge)
        syllable = shaped * 0.8
        if pre is not None:
            pre = pre * 0.8
            syllable = np.concatenate([pre, syllable])
        chunks.append(syllable)
        chunks.append(silence)
    if not chunks:
        return np.zeros(SR, dtype=np.float32)
    out = np.concatenate(chunks)
    # 轻微底噪，避免「无限 SNR」的不真实样本
    out = out + np.random.default_rng(7).standard_normal(len(out)) * 2e-4
    peak = np.max(np.abs(out)) or 1.0
    out = out / peak * 0.25   # 约 -12 dBFS
    return out.astype(np.float32)


def write_wav(path: Path, samples: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
