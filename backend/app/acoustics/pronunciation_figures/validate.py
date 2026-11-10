"""基于对齐语料的算法离线验证入口。"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import time

import numpy as np

from app.acoustics.imagery.common import load_alignment
from . import analyze, load_recording
from .measure import to_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", action="append", required=True, type=Path,
                        help="包含 样本/ 和 对齐结果/alignment.json 的目录，可重复")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows, failures, elapsed = [], [], []
    for corpus in args.corpus:
        alignments = load_alignment(corpus / "对齐结果" / "alignment.json")
        paths = {p.name: p for p in (corpus / "样本").rglob("*.wav")}
        for name, aln in alignments.items():
            start = time.perf_counter()
            try:
                data = to_json(analyze(load_recording(paths[name], aln)))
                rows.append({"file": name, "speaker": aln.speaker, **data})
                elapsed.append(time.perf_counter()-start)
            except Exception as exc:
                failures.append({"file": name, "error": str(exc)})
    vot, rises, spectral, nasals = defaultdict(list), defaultdict(list), defaultdict(dict), []
    prevoiced = []
    for row in rows:
        for s in row["syllables"]:
            c = s["consonant"] or {}
            if c.get("vot_ms") is not None:
                vot["aspirated" if s["initial"]["aspirated_target"] else "unaspirated"].append(c["vot_ms"])
            if c.get("prevoiced"): prevoiced.append(row["file"])
            if c.get("noise_rise_ms") is not None: rises[s["initial_class"]].append(c["noise_rise_ms"])
            if c.get("spectrum"):
                spectral[row["speaker"]][s["initial"]["label"]] = c["spectrum"]["cog_hz"]
            if s["nasal_coda"]:
                nasals.append({"file": row["file"], **s["nasal_coda"]})
    def stats(values):
        return {"count": len(values), "min": min(values), "median": float(np.median(values)), "max": max(values)} if values else {}
    summary = {"count": len(rows), "failures": failures,
               "analysis_seconds": stats(elapsed), "vot_ms": {k: stats(v) for k, v in vot.items()},
               "prevoiced": prevoiced, "noise_rise_ms": {k: stats(v) for k, v in rises.items()},
               "spectral_centroid_hz_by_speaker": dict(spectral), "nasal_codas": nasals}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "recordings": rows}, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in {"nasal_codas", "spectral_centroid_hz_by_speaker"}}, ensure_ascii=False))
    if failures: raise SystemExit(1)


if __name__ == "__main__":
    main()
