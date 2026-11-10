"""python -m app.acoustics.pronunciation_figures --help"""
import argparse
import json
from pathlib import Path

from app.acoustics.imagery.common import load_alignment
from . import analyze, build_bundle, export_bundle, load_recording


def main():
    p = argparse.ArgumentParser(description="生成 44.1 kHz 发音建议图像与结构化数值")
    p.add_argument("--audio", required=True, type=Path)
    p.add_argument("--alignment", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--pitch-range", nargs=2, type=float, metavar=("LOW", "HIGH"))
    p.add_argument("--reference", type=Path)
    p.add_argument("--reference-alignment", type=Path)
    p.add_argument("--reference-pitch-range", nargs=2, type=float)
    p.add_argument("--context", type=Path, help="目标、母语背景、评分检错等 JSON")
    p.add_argument("--vowel-space", type=Path, help="个人元音空间 JSON")
    p.add_argument("--goal", default="general", choices=["general", "tone", "vowel", "initial", "nasal"])
    p.add_argument("--all-figures", action="store_true")
    args = p.parse_args()
    vowel_space = json.loads(args.vowel_space.read_text(encoding="utf-8")) if args.vowel_space else None
    if bool(args.reference) != bool(args.reference_alignment):
        p.error("--reference 与 --reference-alignment 必须同时提供")
    def read(audio, alignment, pitch, source):
        alignments = load_alignment(alignment)
        if audio.name not in alignments:
            p.error(f"请在对齐文件中提供 {audio.name} 的时间戳")
        return analyze(load_recording(audio, alignments[audio.name], f0_range=tuple(pitch) if pitch else None,
                                      f0_range_source=source if pitch else None,
                                      vowel_norm=vowel_space if source == "personal_calibration" else None,
                                      formant_ceiling_hz=vowel_space.get("speaker_max_formant") if vowel_space and source == "personal_calibration" else None))
    learner = read(args.audio, args.alignment, args.pitch_range, "personal_calibration")
    reference = read(args.reference, args.reference_alignment, args.reference_pitch_range, "reference_calibration") if args.reference else None
    context = json.loads(args.context.read_text(encoding="utf-8")) if args.context else {}
    bundle = build_bundle(learner, reference, goal=args.goal, context=context, all_figures=args.all_figures)
    print(export_bundle(bundle, args.output))


if __name__ == "__main__":
    main()
