"""MockProvider：确定性测试替身（docs/architecture/03 第 9 节「Provider 测试替身」）。

行为契约：
- 输入规范化 WAV 与评测文本，输出 SyllableEval + 朗读维检错；
- 结论由（PCM 内容 + 文本）完全决定：同音频同文本永远同结果（FR-1003）；
- 音节时间戳来自本地有声检测；声调对错由音节内 F0 走向与期望声调比对得出，
  使现象与曲线分析对真实输入敏感；
- 环境变量 SVS_MOCK_PROVIDER 可强制故障路径：
  fail（不可达）/ disordered（乱读）/ missing（漏读）——供测试与演练。
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np

from app.acoustics import analysis
from app.pinyin_utils import expected_syllables
from app.scoring.provider import ProviderError, ProviderResult, ScoringProvider, SyllableEval


def _syllable_direction_ok(f0: np.ndarray, t: np.ndarray, seg: tuple[float, float],
                           tone: int | None) -> bool:
    """音节段内 F0 走向 vs 期望声调（宽容判定，仅供替身使用）。"""
    mask = (t >= seg[0]) & (t <= seg[1]) & np.isfinite(f0)
    f = f0[mask]
    if f.size < 4:
        return True  # 帧太少，不下结论
    n = f.size
    head = float(np.median(f[: max(2, n // 3)]))
    tail = float(np.median(f[-max(2, n // 3):]))
    semitones = float(12 * np.log2(max(tail, 1e-3) / max(head, 1e-3)))
    if tone == 1:
        return abs(semitones) < 3.0
    if tone == 2:
        return semitones > -0.8
    if tone == 3:
        return semitones > -3.0   # 降升整体近似低平，宽容
    if tone == 4:
        return semitones < 0.8
    return True


class MockProvider(ScoringProvider):
    name = "mock"
    version = "mock-1.0.0"

    def evaluate(self, wav_path: str, evaluation_text: str) -> ProviderResult:
        import time

        mode = os.environ.get("SVS_MOCK_PROVIDER", "")
        if mode == "fail":
            raise ProviderError("down", "mock provider 模拟不可达")
        if mode == "slow":
            time.sleep(float(os.environ.get("SVS_MOCK_SLOW_SEC", "3")))

        path = Path(wav_path)
        pcm_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        seed = int(pcm_hash[:12], 16)

        expected = expected_syllables(evaluation_text)
        result = ProviderResult(provider_version=self.version)

        f0res = analysis.extract_f0(path)
        voiced = [(a, b) for a, b in f0res.voiced_ranges]

        # 音节时间戳：把全部有声时长按序分配给期望音节（等比切分）
        segments = self._assign_segments(voiced, len(expected))
        if not voiced and expected:
            result.reading["disordered"] = True
            result.syllables = [SyllableEval(text=e["text"], pinyin=e.get("pinyin"),
                                             tone_value=e.get("tone"),
                                             t0=0.0, t1=0.0,
                                             initial_ok=False, final_ok=False, tone_ok=False)
                                for e in expected]
            result.overall_score = 0.0
            return result

        if mode == "missing" and expected:
            result.reading["missing"] = [expected[-1]["text"]]
            expected = expected[:-1]
        if mode == "disordered":
            result.reading["disordered"] = True

        # F0 帧序列（走向判定用）
        frames = f0res.frames
        t = np.array([fr["t"] for fr in frames], dtype=float)
        f = np.array([fr.get("hz", np.nan) for fr in frames], dtype=float)

        n_bad = 0
        for i, e in enumerate(expected):
            seg = segments[i] if i < len(segments) else (0.0, 0.0)
            # 确定性伪声母/韵母判定：几乎总是正确（替身默认口径），微小抖动来自哈希
            bad_phone = ((seed >> (i * 3)) & 0xFF) == 0x07
            tone_ok = _syllable_direction_ok(f, t, seg, e.get("tone"))
            if bad_phone:
                n_bad += 1
            if not tone_ok:
                n_bad += 1
            result.syllables.append(SyllableEval(
                text=e["text"], pinyin=e.get("pinyin"), t0=round(seg[0], 3),
                t1=round(seg[1], 3),
                initial_ok=not bad_phone, final_ok=not bad_phone,
                tone_ok=tone_ok, tone_value=e.get("tone"),
            ))

        if not expected:
            result.reading["extra"] = ["?"]

        base = 96.0 - 6.0 * n_bad
        jitter = (seed % 7) - 3
        result.overall_score = round(max(0.0, min(100.0, base + jitter)), 1)
        if any(not s.initial_ok for s in result.syllables):
            result.initial_score = round(max(60.0, result.overall_score - 5), 1)
        if any(not s.final_ok for s in result.syllables):
            result.final_score = round(max(60.0, result.overall_score - 5), 1)
        if any(not s.tone_ok for s in result.syllables):
            result.tone_score = round(max(60.0, result.overall_score - 8), 1)
        return result

    @staticmethod
    def _assign_segments(voiced: list[tuple[float, float]], n: int) -> list[tuple[float, float]]:
        """把拼接后的有声时长按 n 等分切成音节时间戳。"""
        if n <= 0:
            return []
        total = sum(b - a for a, b in voiced)
        if total <= 0:
            return [(0.0, 0.0)] * n
        timeline = []   # (拼接轴起点, 音频内 a, 音频内 b)
        acc = 0.0
        for a, b in voiced:
            timeline.append((acc, a, b))
            acc += b - a

        def global_to_audio(g: float) -> float:
            for gs, a, b in timeline:
                if g <= gs + (b - a) + 1e-9:
                    return a + (g - gs)
            return timeline[-1][2]

        per = total / n
        return [
            (round(global_to_audio(k * per), 3), round(global_to_audio((k + 1) * per), 3))
            for k in range(n)
        ]
