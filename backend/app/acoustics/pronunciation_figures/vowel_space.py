"""从同一发音人的边缘元音录音建立个人元音空间。

两种输入口径共用同一套上限扫描与汇总：

- 对齐语料（每元音一条 Recording，稳态区取韵母 30%–70%）：离线验证与 CLI 用；
- 独立元音录音（无对齐，稳态区取最长连续有声段的 30%–70%）：个人标定会话用。

跨录音等权：每条录音先取稳态区 F1/F2/F3 中位数，锚点输出跨录音的均值与标准差。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import parselmouth

from app.acoustics import f0_pipeline, transcode
from .measure import Recording, SR

ANCHORS = ("i", "u", "a", "ü")
CEILINGS = range(4500, 6301, 100)

STEADY_LO, STEADY_HI = 0.30, 0.70   # 稳态区：发音段的 30%–70%
MIN_STEADY_FRAMES = 5               # 参与计算的最少有效帧
MIN_VOICED_SEC = 0.25               # 独立录音最小可用发音时长


def _formant_track(x: np.ndarray, sr: int, ceiling: float) -> parselmouth.Formant:
    snd = parselmouth.Sound(np.asarray(x, dtype=float), sampling_frequency=sr)
    return snd.to_formant_burg(time_step=.005, max_number_of_formants=5,
                               maximum_formant=ceiling, window_length=.025, pre_emphasis_from=50)


def _sample_window(fm: parselmouth.Formant, start: float, end: float) -> np.ndarray:
    times = np.arange(start + STEADY_LO * (end - start),
                      start + STEADY_HI * (end - start), .005)
    return np.asarray([[fm.get_value_at_time(k, t) for k in (1, 2, 3)] for t in times])


def _clean(values: np.ndarray) -> np.ndarray:
    return values[np.isfinite(values).all(axis=1)] if len(values) else values


def _default_ceiling(track: f0_pipeline.PitchTrack) -> float:
    """未获得个人上限前的测量上限：按 F0 中位数选择（与 extract_formants 同规则）。"""
    med = float(np.nanmedian(track.f0)) if np.isfinite(track.f0).any() else 0.0
    return 5000.0 if med and med < 165 else 5500.0


def voiced_steady_interval(track: f0_pipeline.PitchTrack) -> tuple[float, float] | None:
    """独立元音录音的稳态区：最长连续有声段的 30%–70%。太短返回 None。"""
    runs = f0_pipeline._runs(np.isfinite(track.f0))
    if not runs:
        return None
    a, b = max(runs, key=lambda r: track.times[r[1]] - track.times[r[0]])
    start, end = float(track.times[a]), float(track.times[b])
    if end - start < MIN_VOICED_SEC:
        return None
    return start + STEADY_LO * (end - start), start + STEADY_HI * (end - start)


def measure_vowel_take(wav_path: str | Path) -> dict:
    """独立元音单条录音的验收测量（无对齐）：稳态区 F1/F2/F3 中位数、
    帧间波动与可用帧数；稳态区供最终计算按候选上限复测。"""
    track = f0_pipeline.extract_track(wav_path)
    runs = f0_pipeline._runs(np.isfinite(track.f0))
    voiced_sec = 0.0
    steady = None
    if runs:
        a, b = max(runs, key=lambda r: track.times[r[1]] - track.times[r[0]])
        voiced_sec = float(track.times[b] - track.times[a])
        steady = voiced_steady_interval(track)
    if steady is None:
        return {"ok": False,
                "reason": "没有检测到足够的持续发音，请自然、平稳地延长元音后重录",
                "voicedSec": round(voiced_sec, 2)}

    x = transcode.read_pcm_samples(Path(wav_path))
    sr = transcode.SAMPLE_RATE
    ceiling = _default_ceiling(track)
    values = _clean(_sample_window(_formant_track(x, sr, ceiling), steady[0], steady[1]))
    if len(values) < MIN_STEADY_FRAMES:
        return {"ok": False,
                "reason": "元音共振峰不可测，请用正常说话的音量重录",
                "voicedSec": round(voiced_sec, 2)}
    med = np.median(values, axis=0)
    std = np.std(values, axis=0)
    return {"ok": True,
            "voicedSec": round(voiced_sec, 2),
            "steady": [round(steady[0], 3), round(steady[1], 3)],
            "ceiling": ceiling,
            "f1": round(float(med[0]), 1), "f2": round(float(med[1]), 1), "f3": round(float(med[2]), 1),
            "f1Std": round(float(std[0]), 1), "f2Std": round(float(std[1]), 1),
            "f3Std": round(float(std[2]), 1),
            "nFrames": int(len(values))}


def calibrate_personal_vowel_space(takes: dict[str, list[dict]]) -> dict:
    """个人标定：独立元音录音建立元音空间。

    takes：元音 → 参与计算的录音列表，每条 {"x", "sr", "steady"}；
    steady 为 measure_vowel_take 给出的稳态区（秒）。
    每条录音跨候选上限复测共振峰，逐上限按拓扑约束与轨迹平稳度选优；
    锚点输出跨录音的 F1/F2/F3 均值与标准差。
    """
    missing = [v for v in ANCHORS if not takes.get(v)]
    if missing:
        raise ValueError(f"请提供边缘元音录音：{', '.join(missing)}")
    best = None
    for ceiling in CEILINGS:
        traces: dict[str, list[np.ndarray]] = {}
        ok = True
        for vowel in ANCHORS:
            samples = [_clean(_sample_window(_formant_track(t["x"], t["sr"], ceiling),
                                             t["steady"][0], t["steady"][1]))
                       for t in takes[vowel]]
            if any(len(s) < MIN_STEADY_FRAMES for s in samples):
                ok = False
                break
            traces[vowel] = samples
        if not ok:
            continue
        centers = {v: np.mean([np.median(s, axis=0) for s in lst], axis=0)
                   for v, lst in traces.items()}
        i, u, a, y = (centers[v] for v in ANCHORS)
        topology = min(a[0] - i[0], a[0] - u[0], i[1] - u[1], y[1] - u[1])
        if topology <= 0:
            continue
        smoothness = np.mean([np.mean(np.diff(s[:, :2], axis=0) ** 2)
                              for lst in traces.values() for s in lst])
        score = float(smoothness) / max(topology, 1.0) ** 2
        if best is None or score < best[0]:
            best = (score, ceiling, traces)
    if best is None:
        raise ValueError("边缘元音的共振峰轨迹需要重新标定")
    _, ceiling, traces = best
    anchors: dict = {}
    for vowel, samples in traces.items():
        medians = np.asarray([np.median(s, axis=0) for s in samples])   # (条数, 3)
        stats: dict = {}
        for k in (1, 2, 3):
            stats[f"f{k}Mean"] = round(float(medians[:, k - 1].mean()), 1)
            stats[f"f{k}Std"] = round(float(medians[:, k - 1].std()), 1)
        anchors[vowel] = stats
    centers = np.asarray([[anchors[v]["f1Mean"], anchors[v]["f2Mean"]] for v in ANCHORS])
    anchors["overall"] = {"f1Mean": round(float(centers[:, 0].mean()), 1),
                          "f2Mean": round(float(centers[:, 1].mean()), 1),
                          "f1Std": round(float(centers[:, 0].std()), 1) or 1.0,
                          "f2Std": round(float(centers[:, 1].std()), 1) or 1.0}
    anchors["speaker_max_formant"] = ceiling
    return anchors


def _aligned_steady(rec: Recording) -> tuple[float, float]:
    syll = rec.aln.syllables[0]
    return (syll.final.t0 + STEADY_LO * (syll.final.t1 - syll.final.t0),
            syll.final.t0 + STEADY_HI * (syll.final.t1 - syll.final.t0))


def calibrate_vowel_space(recordings: dict[str, Recording | list[Recording]]) -> dict:
    """对齐语料入口：每元音一条或多条 Recording（稳态区取韵母 30%–70%）。"""
    takes: dict[str, list[dict]] = {}
    for vowel, recs in recordings.items():
        items = recs if isinstance(recs, list) else [recs]
        takes[vowel] = [{"x": r.x, "sr": SR, "steady": _aligned_steady(r)} for r in items]
    return calibrate_personal_vowel_space(takes)
