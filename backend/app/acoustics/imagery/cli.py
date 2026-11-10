"""批量生成声学图像。

在 backend 目录下运行：
    py -3 -m app.acoustics.imagery.cli --samples <WAV 根目录> --alignment <对齐 JSON> --out <输出目录>

两遍处理：
1. 统计整批录音的 dB 显示上限（DbScales）与各发音人的 F0 中位数（半音参考），
   使图像标尺跨样本一致（方案 §9 第四项）；
2. 逐条录音运行全部模块：每条录音一个子目录，写 manifest.json；
   各样本的 CSV 合并到 <out>/_汇总/，整批参数与软件版本写入 run_config.json（方案 §10）。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

import numpy as np

from . import MODULES, basic_spectra, generate_all
from .common import (ANALYSIS_CHANNEL, WIDE_F0_RANGE, DbScales, SpeakerProfile, estimate_profile,
                     load_alignment, pitch_arrays, pitch_filtered_ac, profile_for, read_mono,
                     set_speaker_profiles, to_sound)


def _jsonable(v):
    """numpy 标量/数组、Path、NaN 等转为可写入 JSON 的值（NaN/inf → null）。"""
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, np.ndarray):
        return _jsonable(v.tolist())
    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, Path):
        return str(v)
    return v


def _versions() -> dict:
    import matplotlib
    import parselmouth
    import scipy

    return {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
            "matplotlib": matplotlib.__version__, "parselmouth": parselmouth.VERSION,
            "praat": parselmouth.PRAAT_VERSION}


def _batch_stats(items: list) -> tuple[DbScales, dict[str, SpeakerProfile], dict[str, float]]:
    """第一遍：整批 dB 上限取各录音最大值；按方案 §5.1 先用宽范围提取 F0，
    再据实测分布收窄各发音人的 F0 范围；半音参考取该发音人全部有声帧的中位数。"""
    levels: dict[str, list[float]] = defaultdict(list)
    f0_by_speaker: dict[str, list[float]] = defaultdict(list)
    for wav, aln in items:
        x, sr = read_mono(wav)
        for k, v in basic_spectra.db_levels(x, sr).items():
            levels[k].append(float(v))
        pitch = pitch_filtered_ac(to_sound(x, sr), profile_for(aln.speaker),
                                  floor=WIDE_F0_RANGE[0], ceiling=WIDE_F0_RANGE[1])
        _, f0 = pitch_arrays(pitch)
        f0_by_speaker[aln.speaker].extend(f0[np.isfinite(f0)].tolist())
    scales = DbScales(**{k: max(v) for k, v in levels.items()})
    profiles = {spk: estimate_profile(spk, np.asarray(v)) for spk, v in f0_by_speaker.items() if v}
    f0_ref = {spk: float(np.median(v)) for spk, v in f0_by_speaker.items() if v}
    return scales, profiles, f0_ref


def _relative(paths: dict, base: Path) -> dict:
    out = {}
    for name, p in paths.items():
        p = Path(p)
        out[name] = str(p.relative_to(base)) if p.is_relative_to(base) else str(p)
    return out


def _merge_tables(table_files: dict[str, list[tuple[str, Path]]], out_dir: Path) -> list[Path]:
    """把各样本同名 CSV 合并为一张表（首列为样本名）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, entries in sorted(table_files.items()):
        rows: list[dict] = []
        fields = ["sample"]
        for sample, path in entries:
            with path.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    fields += [k for k in row if k not in fields]
                    rows.append({"sample": sample, **row})
        target = out_dir / name
        with target.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        written.append(target)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="按 docs/声学图像提取/方案.md 批量生成声学图像")
    ap.add_argument("--samples", required=True, help="样本 WAV 根目录（递归查找 *.wav）")
    ap.add_argument("--alignment", required=True, help="对齐汇总 JSON（alignment.json 格式）")
    ap.add_argument("--out", required=True, help="输出目录（每条录音一个子目录）")
    ap.add_argument("--only", nargs="*",
                    help="只为文件名包含这些片段的录音出图，例如 ma3_FV1 si1_（第一遍统计仍覆盖全部录音）")
    ap.add_argument("--modules", nargs="*", default=list(MODULES), choices=MODULES, help="只运行指定模块")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    alignments = load_alignment(args.alignment)
    wavs = sorted(Path(args.samples).rglob("*.wav"))
    # 第一遍统计始终覆盖全部已对齐录音，使 --only 子集运行与全量运行的标尺、发音人参数一致
    all_items = [(w, alignments[w.name]) for w in wavs if w.name in alignments]
    items = [(w, aln) for w, aln in all_items if not args.only or any(s in w.name for s in args.only)]
    unaligned = [w.name for w in wavs if w.name not in alignments]
    if unaligned:
        print(f"跳过 {len(unaligned)} 条无对齐结果的录音：{', '.join(unaligned[:10])}")
    if not items:
        print("没有可处理的录音")
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    scales, profiles, f0_ref = _batch_stats(all_items)
    set_speaker_profiles(profiles)
    print(f"第一遍完成：统计 {len(all_items)} 条录音，dB 上限 {asdict(scales)}，F0 参考 {f0_ref}")
    for spk, p in profiles.items():
        print(f"  发音人 {spk}：F0 范围 {p.f0_floor:.0f}–{p.f0_ceiling:.0f} Hz，共振峰上限 {p.formant_ceiling:.0f} Hz")

    module_stats = {m: {"ok": 0, "error": 0, "images": 0, "tables": 0, "seconds": 0.0} for m in args.modules}
    warning_counter: Counter = Counter()
    errors: list[dict] = []
    table_files: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    first_params: dict = {}

    for i, (wav, aln) in enumerate(items, 1):
        x, sr = read_mono(wav)
        sample_dir = out / wav.stem
        context = {"f0_ref_hz": f0_ref.get(aln.speaker),
                   "f0_ref_source": f"发音人 {aln.speaker} 在本批录音中全部有声帧的 F0 中位数"}
        results = generate_all(x, sr, aln, sample_dir, scales=scales, context=context,
                               modules=tuple(args.modules))
        manifest = {"file": wav.name, "speaker": aln.speaker, "durationSec": aln.duration,
                    "sampleRate": sr, "channel": ANALYSIS_CHANNEL,
                    "syllables": [{"text": s.text, "symbol": s.symbol, "t0": s.t0, "t1": s.t1,
                                   "phones": [asdict(p) for p in s.phones]} for s in aln.syllables],
                    "modules": {}}
        n_images = 0
        for name, res in results.items():
            stats = module_stats[name]
            stats["seconds"] += res.get("seconds", 0.0)
            if "error" in res:
                stats["error"] += 1
                errors.append({"sample": wav.stem, "module": name, "error": res["error"],
                               "traceback": res.get("traceback")})
            else:
                stats["ok"] += 1
                first_params.setdefault(name, res.get("params", {}))
            missing = [p for p in res.get("images", {}).values() if not Path(p).is_file()]
            if missing:
                errors.append({"sample": wav.stem, "module": name,
                               "error": f"声明的图片不存在：{[str(p) for p in missing]}"})
            stats["images"] += len(res.get("images", {}))
            stats["tables"] += len(res.get("tables", {}))
            n_images += len(res.get("images", {}))
            for p in res.get("tables", {}).values():
                table_files[Path(p).name].append((wav.stem, Path(p)))
            warning_counter.update(f"[{name}] {w}" for w in res.get("warnings", []))
            manifest["modules"][name] = {
                "images": _relative(res.get("images", {}), sample_dir),
                "tables": _relative(res.get("tables", {}), sample_dir),
                "params": res.get("params", {}), "warnings": res.get("warnings", []),
                "error": res.get("error"), "seconds": res.get("seconds")}
        (sample_dir / "manifest.json").write_text(
            json.dumps(_jsonable(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
        failed = [n for n, r in results.items() if "error" in r]
        print(f"[{i}/{len(items)}] {wav.stem}: 图 {n_images} 张"
              + (f"，失败模块 {failed}" if failed else "")
              + f"，{sum(r.get('seconds', 0) for r in results.values()):.1f} s")

    merged = _merge_tables(table_files, out / "_汇总")
    elapsed = round(time.perf_counter() - started, 1)
    run_config = {"createdAt": time.strftime("%Y-%m-%dT%H:%M:%S"), "versions": _versions(),
                  "samples": len(items), "alignment": args.alignment, "channel": ANALYSIS_CHANNEL,
                  "dbScales": asdict(scales), "f0ReferenceHz": f0_ref,
                  "speakerProfiles": {spk: asdict(p) for spk, p in profiles.items()},
                  "speakerProfileRule": "先以 50–600 Hz 提取 F0，floor = 0.75 × 第 1 百分位，"
                                        "ceiling = 1.25 × 第 99 百分位（取 5 Hz 整数倍）",
                  "moduleParams": first_params,
                  "note": "moduleParams 取每个模块第一条成功录音的参数；逐条录音的实际参数见各自 manifest.json"}
    summary = {"elapsedSec": elapsed, "samples": len(items), "modules": module_stats,
               "mergedTables": [p.name for p in merged], "errors": errors,
               "warnings": [{"count": c, "warning": w} for w, c in warning_counter.most_common()]}
    (out / "run_config.json").write_text(json.dumps(_jsonable(run_config), ensure_ascii=False, indent=2),
                                         encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(_jsonable(summary), ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    print(f"\n完成：{len(items)} 条录音，用时 {elapsed} s，错误 {len(errors)} 个，结果在 {out}")
    for name, s in module_stats.items():
        print(f"  {name:14s} 成功 {s['ok']:3d}  失败 {s['error']:3d}  图 {s['images']:4d}  表 {s['tables']:4d}"
              f"  {s['seconds']:.1f} s")
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
