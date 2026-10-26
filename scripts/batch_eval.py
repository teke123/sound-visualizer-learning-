# -*- coding: utf-8 -*-
"""批量评测 → 可复现实验报告(直接对应汇报口径:加载耗时/成功率/失败样本/演示可用性)。

用法:
  python scripts/batch_eval.py                            # 评测 audio/tts_raw 与 audio/tts_err
  python scripts/batch_eval.py --dir audio/tts_raw        # 只评某个目录
输出: experiments/batch_<时间戳>/samples.csv + summary.md
"""
import argparse
import csv
import datetime
import re
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.asr_analyzer import get_analyzer
from backend.dl_analyzer import diagnose
from backend.levels import FROZEN_SINCE

# 演示可用性判据(用真实录音集标定后可调整)
DEMO_OK_RATE = 0.9      # 成功率 ≥ 90%
DEMO_MAX_AVG_MS = 3000  # 平均推理 < 3s/条


def level_id_of(name: str) -> str | None:
    m = re.search(r"(L\d{2})", name)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", action="append", default=[])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    dirs = [Path(d) for d in args.dir] or [ROOT / "audio" / "tts_raw", ROOT / "audio" / "tts_err"]
    files = set()
    for d in dirs:
        if d.is_dir():
            # Windows 文件系统大小写不敏感,glob 两种后缀会重复 → 用 set 去重
            files.update(d.glob("*.wav"))
            files.update(d.glob("*.WAV"))
            files.update(d.glob("*.m4a"))
            files.update(d.glob("*.mp3"))
    files = sorted(files)
    if not files:
        print("未找到音频。请先运行 scripts/make_tts_samples.py 生成标准样本。")
        return

    analyzer = get_analyzer()
    t0 = datetime.datetime.now()
    load = analyzer.load()

    out_dir = Path(args.out) if args.out else ROOT / "experiments" / f"batch_{t0:%Y%m%d_%H%M%S}"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for f in files:
        lid = level_id_of(f.name)
        try:
            r = diagnose(str(f), level_id=lid)
        except Exception as e:
            r = {"ok": False, "error": f"{type(e).__name__}: {e}", "audio": {}}
        det = r.get("detected") or {}
        rows.append({
            "file": f.name, "dir": f.parent.name,
            "level_id": r.get("level_id") or lid or "",
            "target_pinyin": r.get("target_pinyin", ""),
            "verdict": (r.get("verdict") or {}).get("code", "error"),
            "label": (r.get("verdict") or {}).get("label", ""),
            "detected_char": det.get("char", ""),
            "detected_pinyin": det.get("pinyin", ""),
            "prob": det.get("prob", ""),
            "recognized_text": r.get("recognized_text", ""),
            "infer_ms": (r.get("audio") or {}).get("forward_ms", ""),
        })

    fields = list(rows[0].keys())
    csv_path = out_dir / "samples.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    cnt = Counter(r["verdict"] for r in rows)
    n = len(rows)
    ok_n = cnt["correct"]
    fails = [r for r in rows if r["verdict"] != "correct"]
    infers = [r for r in rows if r["infer_ms"] not in ("", None)]
    avg_ms = sum(float(r["infer_ms"]) for r in infers) / len(infers) if infers else 0.0

    # 分目录统计: tts_raw = 正确读音成功率(汇报主指标);tts_err = 错误样本命中率(判定为"非正确"即命中)
    def group_stat(dir_names: tuple[str, ...]) -> tuple[int, int]:
        g = [r for r in rows if r["dir"] in dir_names]
        g_ok = sum(1 for r in g if r["verdict"] == "correct")
        return len(g), g_ok

    n_raw, ok_raw = group_stat(("tts_raw", "raw"))
    n_err, ok_err = group_stat(("tts_err", "err"))
    demo_ok = n_raw >= 30 and ok_raw / n_raw >= DEMO_OK_RATE and avg_ms < DEMO_MAX_AVG_MS

    md = [
        f"# 批量评测报告({t0:%Y-%m-%d %H:%M:%S})", "",
        f"- 关卡冻结: {FROZEN_SINCE}(L01-L30,levels.py 单一声源)",
        f"- 模型: {analyzer.model_id}", f"- 设备: {analyzer.device}",
        f"- 模型加载耗时: {load.get('load_ms')} ms(cached={load.get('cached')})",
        f"- 样本总数: {n}",
        f"- **正确读音成功率(tts_raw): {ok_raw}/{n_raw} = {ok_raw / n_raw * 100:.1f}%**" if n_raw else "- tts_raw 目录无样本",
        f"- **错误样本命中率(tts_err): {n_err - ok_err}/{n_err} = {(n_err - ok_err) / n_err * 100:.1f}%**(判定为'非正确'即命中)" if n_err else "- tts_err 目录无样本",
        "", "## 分类统计", "",
    ]
    for code, label in [("correct", "正确"), ("misread_initial", "误读·声母"),
                        ("misread_final", "误读·韵母"), ("misread_syllable", "误读·声韵"),
                        ("tone_error", "声调错位"), ("missed", "漏读/未识别"),
                        ("uncertain", "低置信")]:
        if cnt.get(code):
            md.append(f"- {label}({code}): {cnt[code]}")
    md += ["", "## 失败样本(需复核)", ""]
    if fails:
        for r in fails:
            md.append(f"- `{r['file']}` 目标 `{r['target_pinyin']}` → {r['label']},"
                      f"测到 `{r['detected_char']}`({r['detected_pinyin']}, prob={r['prob']})")
    else:
        md.append("- 无")
    md += ["", "## 演示可用性", "",
           f"- 平均推理耗时: {avg_ms:.0f} ms/条",
           f"- 是否可用于对外演示(判据:正确读音成功率≥{DEMO_OK_RATE * 100:.0f}% 且 平均<{DEMO_MAX_AVG_MS / 1000:.0f}s): "
           f"**{'是' if demo_ok else '否(见失败样本/耗时)'}**",
           "", f"- 明细: {csv_path.name}(Excel 可直接打开)"]
    md_path = out_dir / "summary.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    print(f"完成: {n} 条,正确率 {ok_n / n * 100:.1f}% → {out_dir}")


if __name__ == "__main__":
    main()
