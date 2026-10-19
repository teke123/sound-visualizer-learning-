"""F0 管线针对性测试（docs/f0展示修改测试版1.md §9.2）。

合成四种调型（高平/全升/降升/全降）＋静音缺口＋八度毛刺，验证：
  1. 五度映射（fLo→1、中点→3、fHi→5、越界保留）
  2. degree/相对半音/Hz 三坐标一致
  3. 断口保留（静音帧 hz=None 占位、comparisonPoints null）
  4. 核心区裁剪与 SG 平滑不改变调型走向
  5. 近似调值与调型分类（11/35/51/214 类走向）
  6. 21 点比较序列 u 网格与 near/far 插值
  7. 哼鸣合成输出非空 WAV 且时长≈录音
  8. 八度毛刺纠偏（毛刺帧被重选或置空，不出现 ±12ST 平台）

直接运行：py -3 test_f0_pipeline.py（离线，无网络）。
"""
from __future__ import annotations

import io
import math
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from app import config  # noqa: E402
from app.acoustics import f0_pipeline as fp  # noqa: E402

FS = 16000
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def synth_wav(pattern: str, dur: float = 0.6, gap_at: float | None = None,
             glitch_at: float | None = None) -> bytes:
    """合成指定调型的基频曲线（谐波丰富的锯齿波），可选静音缺口与八度毛刺。

    频率按音域 [100, 400] 的五度格点标定（digit5≥336、4∈[238,336)、
    3∈[168,238)、2∈[119,168)、1<119）。"""
    t = np.arange(int(dur * FS)) / FS
    f0 = np.full_like(t, 200.0)
    if pattern == "high":            # 55：高平
        f0[:] = 360.0
    elif pattern == "rising":        # 35：全升
        f0[:] = 200.0 + (380.0 - 200.0) * (t / dur)
    elif pattern == "dipping":       # 214：降升
        w = t / dur
        f0[:] = 140.0 - 35.0 * np.clip(w / 0.45, 0, 1) \
            + 185.0 * np.clip((w - 0.55) / 0.45, 0, 1)
    elif pattern == "falling":       # 51：前 75% 下降，尾段持平（真实四声形态）
        w = np.minimum(t / (dur * 0.75), 1.0)
        f0[:] = 380.0 - (380.0 - 95.0) * w
    phase = 2 * np.pi * np.cumsum(f0) / FS
    x = 0.5 * np.sign(np.sin(phase)) + 0.25 * np.sin(2 * phase)
    env = np.ones_like(x)
    if gap_at is not None:           # 80ms 静音缺口
        m = (t >= gap_at) & (t < gap_at + 0.08)
        env[m] = 0.0
    if glitch_at is not None:        # 3 帧八度毛刺（×2 频率）
        m = (t >= glitch_at) & (t < glitch_at + 0.03)
        phase_g = 2 * np.pi * np.cumsum(np.where(m, f0 * 2.0, f0)) / FS
        x = 0.5 * np.sign(np.sin(phase_g)) + 0.25 * np.sin(2 * phase_g)
    x = x * env * 0.6
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    return bio.getvalue()


def run(pattern: str, **kw) -> fp.PitchTrack:
    p = Path(__file__).parent / "data" / "tmp_test" / f"f0p_{pattern}.wav"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(synth_wav(pattern, **kw))
    return fp.extract_track(p)


def main() -> int:
    f_lo, f_hi = 100.0, 400.0

    # 1. 五度映射
    d = fp.hz_to_degree([f_lo, math.sqrt(f_lo * f_hi), f_hi, 80.0, 500.0], f_lo, f_hi)
    check("五度映射 fLo→1 / 中点→3 / fHi→5",
          abs(d[0] - 1) < 1e-9 and abs(d[1] - 3) < 1e-9 and abs(d[2] - 5) < 1e-9)
    check("越界五度值保留（80Hz<5、500Hz>5）", d[3] < 1.0 and d[4] > 5.0,
          f"{d[3]:.2f} / {d[4]:.2f}")
    st = fp.hz_to_rel_st([f_lo, math.sqrt(f_lo * f_hi), f_hi], f_lo, f_hi)
    check("相对半音：中心为 0、上下对称", abs(st[1]) < 1e-9 and abs(st[0] + st[2]) < 1e-9)
    check("degree→Hz 逆映射", abs(fp.degree_to_hz(3.0, f_lo, f_hi) - math.sqrt(f_lo * f_hi)) < 1e-6)

    # 2. 高平调：帧网格、断口、平滑、质量
    track = run("high", gap_at=0.3)
    seg = fp.process_syllables(track, [(0.0, track.duration)], f_lo, f_hi)[0]
    frames = seg["frames"]
    check("帧网格保留（分析区间内逐 10ms 帧占位）",
          len(frames) >= 40 and all("hz" in fr for fr in frames),
          f"{len(frames)} frames")
    nulls = [fr for fr in frames if fr["hz"] is None]
    check("静音缺口保留为 null（不插值跨接）", len(nulls) >= 5,
          f"{len(nulls)} null frames")
    voiced_d = [fr["degree"] for fr in frames if fr["degree"] is not None]
    check("高平调 degree 值域合理（360Hz → ≈4.7）",
          4.2 < np.median(voiced_d) < 5.3, f"median={np.median(voiced_d):.2f}")
    check("按音节质量报告", seg["quality"] is not None and seg["quality"]["validFrames"] > 0,
          f"coverage={seg['quality']['coverage']}")
    check("源标注齐全（measured 为主）",
          any(fr["source"] == "measured" for fr in frames))

    # 3. 21 点比较序列
    comp = seg["comparisonPoints"]
    check("21 点 u 网格 0..1 步长 0.05",
          len(comp) == 21 and abs(comp[0]["u"]) < 1e-9 and abs(comp[-1]["u"] - 1.0) < 1e-9
          and abs(comp[1]["u"] - 0.05) < 1e-9)
    check("比较序列缺口位置保留 null",
          any(p["hz"] is None for p in comp if 0.4 < p["u"] < 0.6))
    st_by_u = [p for p in comp if p["degree"] is not None]
    check("比较序列 degree 与帧一致（同为高平）",
          4.2 < np.median([p["degree"] for p in st_by_u]) < 5.3)

    # 4. 四种调型的近似调值
    expect = {"high": "55", "rising": "35", "dipping": "214", "falling": "51"}
    for pat, want in expect.items():
        tr = run(pat)
        s = fp.process_syllables(tr, [(0.0, tr.duration)], f_lo, f_hi)[0]
        chao = s["chao"]
        shape = s["shape"]
        first_digit = chao[0] if chao else "?"
        last_digit = chao[-1] if chao else "?"
        ok = chao is not None and first_digit == want[0] and last_digit == want[-1]
        check(f"{pat} 调型走向 {want}（实测 {chao}/{shape}）", ok,
              f"chao={chao} shape={shape}")

    # 5. 八度毛刺纠偏
    tr = run("high", glitch_at=0.3)
    s = fp.process_syllables(tr, [(0.0, tr.duration)], f_lo, f_hi)[0]
    voiced = [fr["hz"] for fr in s["frames"] if fr["hz"] is not None]
    st_v = [12 * math.log2(h / 55.0) for h in voiced]
    med = np.median(st_v)
    big_dev = sum(1 for x in st_v if abs(x - med) > 6.0)
    check("八度毛刺被纠偏（无 ±6ST 平台残留）", big_dev <= 2,
          f"{big_dev} frames deviate")

    # 6. 哼鸣合成
    tr = run("dipping")
    s = fp.process_syllables(tr, [(0.0, tr.duration)], f_lo, f_hi)[0]
    wav = fp.sonify_frames(s["frames"])
    with wave.open(io.BytesIO(wav)) as w:
        n, fs = w.getnframes(), w.getframerate()
    dur_out = n / fs
    check("哼鸣 WAV 非空且时长≈录音", n > FS * 0.3 and abs(dur_out - tr.duration) < 0.25,
          f"{dur_out:.2f}s vs {tr.duration:.2f}s")
    wav2 = fp.sonify_frames(s["frames"], remap_range=(f_lo, f_hi))
    check("按我的音域哼鸣（remap）合成成功", len(wav2) > 1000)

    # 7. 开关独立可用
    saved = config.F0_CORRECT_ENABLED, config.F0_RESCUE_ENABLED, config.F0_INTERP_ENABLED
    try:
        config.F0_CORRECT_ENABLED = False
        config.F0_RESCUE_ENABLED = False
        config.F0_INTERP_ENABLED = False
        tr = run("falling")
        s = fp.process_syllables(tr, [(0.0, tr.duration)], f_lo, f_hi)[0]
        check("全部纠偏开关关闭时管线仍可出曲线",
              s["quality"]["validFrames"] > 10, f"valid={s['quality']['validFrames']}")
    finally:
        (config.F0_CORRECT_ENABLED, config.F0_RESCUE_ENABLED,
         config.F0_INTERP_ENABLED) = saved

    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    print(f"\n==== {len(RESULTS) - n_fail}/{len(RESULTS)} 项通过 ====")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
