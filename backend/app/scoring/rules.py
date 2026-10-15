"""规则引擎：朗读维判定、现象标签与四步反馈、T 值曲线分析、共振峰对比
（FR-1004/1005/1006/1007；四步文字来自人工审定模板，同一分析结果输出一致）。
"""
from __future__ import annotations

import numpy as np

from app import config
from app.acoustics.analysis import F0Result, extract_formants, formant_stats_in_segments, to_t_values
from app.scoring.provider import ProviderResult

# 现象标签全集（与内容组约定，模板按 tag 匹配）
TAGS = [
    "low_overall_score", "initial_error", "final_error", "tone_error",
    "missing_syllable", "extra_syllable",
    "tone_shape_flat", "tone_start_high", "tone_start_low",
    "tone_rise_insufficient", "tone_fall_insufficient", "tone_end_unstable",
    "formant_deviation",
]

_PART_LABEL = {"initial": "声母", "final": "韵母", "tone": "声调", "overall": "整体"}


def judge_reading(provider: ProviderResult) -> tuple[bool, dict]:
    """朗读维闸门（FR-1301 维度二）：不合格丢弃 Provider 分数。"""
    r = provider.reading
    reading = {
        "missing": list(r.get("missing", [])),
        "extra": list(r.get("extra", [])),
        "repeated": list(r.get("repeated", [])),
        "replaced": list(r.get("replaced", [])),
        "disordered": bool(r.get("disordered", False)),
    }
    if reading["disordered"]:
        reading["advice"] = "没有听出按提示词的朗读内容，请对着提示词完整朗读一遍再提交"
        return False, reading
    if reading["missing"]:
        reading["advice"] = (f"有漏读（{ '、'.join(reading['missing']) }），"
                             "请把提示的内容一个字一个字读完再提交")
        return False, reading
    if reading["extra"] or reading["repeated"]:
        parts = reading["extra"] + reading["repeated"]
        reading["advice"] = (f"有多读或回读（{'、'.join(parts)}），"
                             "请只朗读提示的内容，读错了请停下重录")
        return False, reading
    reading["advice"] = None
    return True, reading


def _t_curve_in_segment(f0: F0Result, seg: tuple[float, float],
                        f_lo: float, f_hi: float) -> list[dict]:
    ts = np.array([fr["t"] for fr in f0.frames], dtype=float)
    hz = np.array([fr.get("hz", np.nan) for fr in f0.frames], dtype=float)
    mask = (ts >= seg[0]) & (ts <= seg[1]) & np.isfinite(hz)
    t_sel, hz_sel = ts[mask], hz[mask]
    if t_sel.size < 3:
        return []
    span = t_sel[-1] - t_sel[0]
    if span <= 0:
        return []
    tv = to_t_values(hz_sel, f_lo, f_hi)
    return [
        {"t": round(float((ti - t_sel[0]) / span), 4), "v": round(float(v), 3)}
        for ti, v in zip(t_sel, tv) if np.isfinite(v)
    ]


def analyze_user_curve(f0: F0Result, provider: ProviderResult,
                       snapshot: dict, standard_curve: dict | None) -> dict:
    """结果主对比曲线：按音节分段，T 值换算按受理时音域快照冻结（FR-1006）。"""
    f_lo, f_hi = snapshot["fLo"], snapshot["fHi"]
    if standard_curve is None or not f0.reliable:
        return {
            "status": "not_available",
            "scale": "T",
            "segments": [],
            "rangeSnapshotId": snapshot.get("id"),
            "note": f0.note or "本关暂无标准曲线",
        }
    ref_by_index = list(standard_curve.get("segments", []))
    segments = []
    for i, syl in enumerate(provider.syllables):
        user = _t_curve_in_segment(f0, (syl.t0, syl.t1), f_lo, f_hi)
        ref = ref_by_index[i]["points"] if i < len(ref_by_index) else []
        segments.append({
            "syllable": syl.text,
            "toneValue": syl.tone_value,
            "user": user,
            "reference": ref,
        })
    return {
        "status": "ok",
        "scale": "T",
        "segments": segments,
        "rangeSnapshotId": snapshot.get("id"),
    }


def curve_phenomena(curve: dict) -> list[dict]:
    """从 T 值曲线提取声调形状现象（只陈述本次测得的现象，FR-1004）。"""
    out: list[dict] = []
    if curve.get("status") != "ok":
        return out
    for i, seg in enumerate(curve.get("segments", [])):
        tone = seg.get("toneValue")
        pts = [(p["t"], p["v"]) for p in seg.get("user", [])]
        if len(pts) < 4 or not tone:
            continue
        vals = np.array([v for _, v in pts])
        t_arr = np.array([t for t, _ in pts])
        v20 = float(np.interp(0.2, t_arr, vals))
        v80 = float(np.interp(0.8, t_arr, vals))
        vr = float(vals.max() - vals.min())
        syl = seg.get("syllable", "")
        add = lambda tag, desc: out.append({  # noqa: E731
            "tag": tag, "syllable": syl,
            "position": {"syllableIndex": i, "part": "tone"},
            "description": desc,
        })
        if tone == 1:
            if abs(v80 - v20) > 1.2:
                add("tone_end_unstable", f"「{syl}」第一声的尾巴有较明显的滑动，整体不够平稳")
        elif tone == 2:
            if v20 > 3.2:
                add("tone_start_high", f"「{syl}」第二声起点偏高，升上去的空间就小了")
            elif v20 < 1.0:
                add("tone_start_low", f"「{syl}」第二声起点偏低，上升显得吃力")
            if (v80 - v20) < 1.2:
                add("tone_rise_insufficient",
                    f"「{syl}」第二声只升了约 {max(0.0, v80 - v20):.1f} 度，标准约 2 度")
            if vr < 0.8:
                add("tone_shape_flat", f"「{syl}」的音高曲线整体偏平，起伏不够")
        elif tone == 3:
            if vr < 0.8:
                add("tone_shape_flat", f"「{syl}」第三声整体偏平，先降后升的形状不明显")
        elif tone == 4:
            if v20 < 1.2:
                add("tone_start_low", f"「{syl}」第四声起点偏低，降下来显得不够干脆")
            if (v20 - v80) < 1.2:
                add("tone_fall_insufficient",
                    f"「{syl}」第四声只降了约 {max(0.0, v20 - v80):.1f} 度，标准约 2–3 度")
    return out


def analyze_formants(wav_path: str, provider: ProviderResult, snapshot: dict,
                     reference_region: dict | None) -> dict:
    """单韵母关共振峰对比：按本人元音空间归一化（FR-1005）。"""
    space = snapshot.get("vowelSpace") or {}
    overall = space.get("overall") if isinstance(space, dict) else None
    if not overall or not reference_region:
        return {"status": "not_available", "reason": "尚未标定元音空间，暂不能对比共振峰"}

    formants = extract_formants(wav_path)
    stats = formant_stats_in_segments(formants, [(s.t0, s.t1) for s in provider.syllables])
    if not stats:
        return {"status": "not_available", "reason": "未能提取有效共振峰"}

    def normalize(f1: float, f2: float) -> list[float]:
        s1, s2 = max(overall["f1Std"], 1.0), max(overall["f2Std"], 1.0)
        return [round((f1 - overall["f1Mean"]) / s1, 3), round((f2 - overall["f2Mean"]) / s2, 3)]

    user = normalize(stats["f1Mean"], stats["f2Mean"])
    ref = reference_region.get("center") or [0.0, 0.0]
    dev = float(np.linalg.norm(np.array(user) - np.array(ref)))
    return {
        "status": "ok",
        "space": "normalized",
        "user": {"f1": user[0], "f2": user[1], "raw": {"f1Mean": stats["f1Mean"], "f2Mean": stats["f2Mean"]}},
        "referenceRegion": {
            "center": ref,
            "radius": reference_region.get("radius", 1.5),
            "vowel": reference_region.get("vowel"),
        },
        "deviation": round(dev, 3),
    }


def build_phenomena_and_four_steps(
    *,
    provider: ProviderResult,
    curve_phenomena_items: list[dict],
    formant_deviation: float | None,
    level_content: dict,
    fallback_templates: list[dict],
) -> tuple[list[dict], list[dict], float | None]:
    """现象（本关允许标签）→ 四步（本关模板优先，全局兜底）→ 分数。

    分数只在 "score" 属于本关 allowedMetrics 时输出。
    """
    allowed = set(level_content.get("detection", {}).get("allowedMetrics", ["score"]))
    templates: dict[str, dict] = {}
    for tpl in level_content.get("detection", {}).get("fourStepTemplates", []):
        templates[tpl["tag"]] = tpl
    for tpl in fallback_templates:
        templates.setdefault(tpl["tag"], tpl)

    phenomena: list[dict] = []
    steps: list[dict] = []
    used_tags: set[str] = set()

    def emit(tag: str, phenomenon_obj: dict) -> None:
        if tag in used_tags or tag not in templates:
            return
        used_tags.add(tag)
        phenomena.append(phenomenon_obj)
        tpl = templates[tag]
        step_ref = tpl.get("practiceStepId")
        if not step_ref:
            practice = level_content.get("practice") or []
            step_ref = practice[0]["id"] if practice else None
        steps.append({
            "phenomenon": tpl["phenomenon"],
            "possibleCause": tpl["possibleCause"],
            "cue": tpl["cue"],
            "practice": {"levelId": level_content.get("id"), "stepRef": step_ref},
            "wordingSource": "rule_template",
        })

    r = provider.reading
    if r.get("missing"):
        emit("missing_syllable", {
            "tag": "missing_syllable", "syllable": None,
            "position": {"syllableIndex": None, "part": "overall"},
            "description": f"有漏读：{'、'.join(r['missing'])}",
        })
    if r.get("extra") or r.get("repeated") or r.get("replaced"):
        emit("extra_syllable", {
            "tag": "extra_syllable", "syllable": None,
            "position": {"syllableIndex": None, "part": "overall"},
            "description": "有多读或回读",
        })
    for i, syl in enumerate(provider.syllables):
        if "initial" in allowed and not syl.initial_ok:
            emit("initial_error", {
                "tag": "initial_error", "syllable": syl.text,
                "position": {"syllableIndex": i, "part": "initial"},
                "description": f"「{syl.text}」的声母（{ (syl.pinyin or '?')[0] }）没有读准",
            })
        if "final" in allowed and not syl.final_ok:
            emit("final_error", {
                "tag": "final_error", "syllable": syl.text,
                "position": {"syllableIndex": i, "part": "final"},
                "description": f"「{syl.text}」的韵母口型不到位",
            })
        if "tone" in allowed and not syl.tone_ok:
            emit("tone_error", {
                "tag": "tone_error", "syllable": syl.text,
                "position": {"syllableIndex": i, "part": "tone"},
                "description": f"「{syl.text}」的声调走向和标准不一致",
            })
    for ph in curve_phenomena_items:
        emit(ph["tag"], ph)
    if formant_deviation is not None and formant_deviation > 1.5 and "formants" in allowed:
        emit("formant_deviation", {
            "tag": "formant_deviation", "syllable": None,
            "position": {"syllableIndex": None, "part": "final"},
            "description": "元音的位置离标准参考区较远（舌位/开口度差别）",
        })
    score = provider.overall_score if "score" in allowed else None
    if score is not None and score < 60:
        emit("low_overall_score", {
            "tag": "low_overall_score", "syllable": None,
            "position": {"syllableIndex": None, "part": "overall"},
            "description": "本次整体得分偏低，建议先回本关把示范多听几遍",
        })
    return phenomena, steps, score
