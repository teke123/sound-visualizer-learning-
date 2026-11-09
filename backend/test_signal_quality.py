"""信号维质检针对性测试：频带截断检测（蓝牙 HFP 窄带录音识别）。

背景：蓝牙耳机被网页调用麦克风时会切到 HFP 免提协议（8/16 kHz 窄带采集 +
高强度有损压缩），转码后 8 kHz 以上频谱全空，擦音/送气等高频特征丢失。
合成信号验证 check_signal 的 bandwidth 维度：
  1. 全频带白噪声 → 频带完整（pass）
  2. 7.8 kHz 低通白噪声（模拟 HFP 宽带 16k 采集转码后的空高频）→ 截断（fail）
  3. 元音谐波 + 擦音高频段 → max-hold 保留擦音能量（pass，不被元音平均谱主导）
  4. 纯谐波元音（谐波止于 4 kHz）→ 截断（fail）
  5. to_dict 输出包含 bandwidth 维度键

直接运行：py -3 test_signal_quality.py（离线，无网络）。
"""
from __future__ import annotations

import sys
import tempfile
import wave
from pathlib import Path

import numpy as np
from scipy.signal import firwin, lfilter

sys.path.insert(0, str(Path(__file__).parent))
from app.acoustics import analysis, transcode  # noqa: E402

FS = transcode.SAMPLE_RATE
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"（{detail}）" if detail else ""))


def write_wav(path: Path, samples: np.ndarray) -> None:
    pcm = np.round(np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes(pcm.tobytes())


def run_case(name: str, samples: np.ndarray, expect_pass: bool) -> dict:
    """频带维度仅提示、不进 failures / verdict（FR-1301）：断言带宽字段本身
    的判定与建议文案，并断言 failures 不含 bandwidth。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.wav"
        write_wav(path, samples)
        result = analysis.check_signal(path, purpose="recording")
    bw = result.bandwidth
    detail = f"cutoff={bw.get('cutoffHz')}Hz pass={bw.get('pass')}"
    if expect_pass:
        ok = bw.get("pass") is True and bw.get("cutoffHz", 0) >= analysis.BANDWIDTH_CUTOFF_HZ_MIN
    else:
        ok = bw.get("pass") is False and "蓝牙" in (bw.get("advice") or "")
    ok = ok and "bandwidth" not in result.failures
    check(name, ok, detail)
    return bw


def lowpass(samples: np.ndarray, cutoff_hz: float, numtaps: int = 1023) -> np.ndarray:
    taps = firwin(numtaps, cutoff_hz / (FS / 2), window="hamming")
    return lfilter(taps, 1.0, samples)


def band_noise(rng: np.random.Generator, lo_hz: float, hi_hz: float, seconds: float, amplitude: float) -> np.ndarray:
    """带限白噪声（FFT 域置零带外频点，边界锐利）"""
    n = int(seconds * FS)
    spec = np.fft.rfft(rng.standard_normal(n))
    freqs = np.fft.rfftfreq(n, 1.0 / FS)
    spec[(freqs < lo_hz) | (freqs > hi_hz)] = 0.0
    sig = np.fft.irfft(spec, n)
    peak = float(np.max(np.abs(sig))) or 1.0
    return sig / peak * amplitude


def harmonic_vowel(seconds: float, f0_hz: float = 200.0, n_partials: int = 20) -> np.ndarray:
    """元音式谐波（1/k 幅度包络），谐波能量止于 f0 × n_partials"""
    t = np.arange(int(seconds * FS)) / FS
    sig = np.zeros_like(t)
    for k in range(1, n_partials + 1):
        sig += (0.15 / k) * np.sin(2 * np.pi * f0_hz * k * t + 0.7 * k)
    return sig


def main() -> int:
    rng = np.random.default_rng(2026)

    # 1. 全频带白噪声：正常麦克风录音，高频完整
    run_case("全频带白噪声判为频带完整", rng.standard_normal(int(2.0 * FS)) * 0.05, expect_pass=True)

    # 2. HFP 宽带模式模拟：7.8 kHz 以上无能量（16k 采集转码后高频全空）
    run_case("7.8 kHz 低通噪声判为频带截断", lowpass(rng.standard_normal(int(2.0 * FS)) * 0.05, 7800.0), expect_pass=False)

    # 3. 元音 + 擦音：max-hold 须保留擦音帧的高频能量（平均谱会被元音主导而漏检）
    vowel = harmonic_vowel(0.7)
    sibilant = band_noise(rng, 6000.0, 11000.0, 0.3, 0.03)
    speech_like = np.concatenate([vowel, sibilant, vowel])
    run_case("元音+擦音合成语音判为频带完整", speech_like, expect_pass=True)

    # 4. 纯谐波元音（谐波止于 4 kHz）：频带确实不完整，应判截断
    run_case("纯谐波（4 kHz 止）判为频带截断", harmonic_vowel(1.5), expect_pass=False)

    # 5. to_dict 输出带宽维度键
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.wav"
        write_wav(path, rng.standard_normal(int(1.0 * FS)) * 0.05)
        raw = analysis.check_signal(path, purpose="recording").to_dict()
    check("to_dict 包含 bandwidth 维度", "bandwidth" in raw and "cutoffHz" in raw["bandwidth"],
          f"keys={sorted(raw['bandwidth'])}")

    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    print(f"\n==== {len(RESULTS) - n_fail}/{len(RESULTS)} 项通过 ====")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
