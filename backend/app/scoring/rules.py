"""规则引擎：现象标签与四步反馈、五度曲线分析、共振峰对比、朗读检错报告
（FR-1004/1005/1006/1007；四步文字来自人工审定模板，同一分析结果输出一致）。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from app.acoustics import analysis
from app.acoustics.analysis import (
    F0Result, detect_onset_span, extract_formants, formant_stats_in_segments,
)
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

# 现象标签 → 发音环节归类：决定追加哪类方言背景提示（FR-1007）
_TAG_FAMILY = {
    "tone_error": "tone", "tone_shape_flat": "tone", "tone_start_high": "tone",
    "tone_start_low": "tone", "tone_rise_insufficient": "tone",
    "tone_fall_insufficient": "tone", "tone_end_unstable": "tone",
    "initial_error": "initial",
    "final_error": "final", "formant_deviation": "final",
}

# 方言区/母语背景 → 常见偏误提示（内容组审定前的种子版；代码集见
# identity.usecases.DIALECT_CODES）。仅在出现对应环节现象时追加一句，
# 不改变现象与分数本身；未登记的背景不追加。
DIALECT_CUES: dict[str, dict[str, str]] = {
    "mandarin_north": {
        "tone": "北方官话区常见：儿化与轻声习惯会让调型走样，按本字调值读满。",
        "final": "北方官话区常见：儿化容易改变韵母，本关先不儿化。",
        "initial": "北方官话区常见：语速快时平翘舌容易滑过，放慢把舌尖位置做足。",
    },
    "mandarin_southwest": {
        "tone": "西南官话区常见：第二声容易读得偏平或下行，保持一路上扬。",
        "final": "西南官话区常见：前后鼻音容易不分（in/ing、en/eng），收尾舌位区分开。",
        "initial": "西南官话区常见：n/l 容易相混，注意舌尖位置与气流走向的差别。",
    },
    "wu": {
        "tone": "吴语区常见：调域整体偏窄、起伏偏小，故意把高低拉开会更像普通话。",
        "final": "吴语区常见：单元音化与鼻化明显，韵母口型保持到位、别提前收鼻。",
        "initial": "吴语区常见：清声母容易带上浊音起头，b/d/g 起音只送气不带音。",
    },
    "yue": {
        "tone": "粤语母语者常见：第三声结尾容易上挑，先把降调读完、尾巴收在低处。",
        "final": "粤语母语者常见：前后鼻音与圆唇度容易弱化，注意韵母收尾口型保持。",
        "initial": "粤语母语者常见：翘舌音 zh/ch/sh 容易发成平舌，舌尖往后卷一点。",
    },
    "min": {
        "tone": "闽语区常见：调值容易整体漂移，盯着目标调型逐字定型。",
        "final": "闽语区常见：撮口呼 ü 容易发成齐齿呼 i，嘴唇拢圆再发音。",
        "initial": "闽语区常见：f/h 与翘舌音容易混，上齿轻碰下唇发 f，舌尖后卷发 zh 组。",
    },
    "xiang": {
        "tone": "湘语区常见：调值整体偏低，试着把起点抬高一点再走调型。",
        "final": "湘语区常见：前后鼻音容易混，前鼻音收尾时舌尖抵住上齿龈。",
        "initial": "湘语区常见：翘舌音容易发平，舌尖卷起对准硬腭前部。",
    },
    "gan": {
        "tone": "赣语区常见：送气调习惯会影响调型走向，先按普通话调型慢慢读。",
        "final": "赣语区常见：鼻化与儿化习惯不同，韵母按标准口型收尾。",
        "initial": "赣语区常见：送气量容易迁移，注意本声母该送多少气。",
    },
    "hakka": {
        "tone": "客家话区常见：入声习惯会让音节收得急，声调后半段容易被截短。",
        "final": "客家话区常见：鼻音韵尾偏重，前后鼻音区分时别把韵尾拖长。",
        "initial": "客家话区常见：送气与不送气对立敏感，注意别把不送气音发成送气。",
    },
    "english": {
        "tone": "英语母语者常见：英语没有固定字调，调型容易自由滑动，按目标调型定型练习。",
        "final": "英语母语者常见：元音容易双元音化（如 a 滑向 ai），口型稳定到音节结束。",
        "initial": "英语母语者常见：送气习惯与汉语不同，注意本声母该不该送气。",
    },
    "japanese": {
        "tone": "日语母语者常见：音高重音容易读成阶梯式，按目标曲线连着滑。",
        "final": "日语母语者常见：元音偏短促，韵母拉长、口型保持住。",
        "initial": "日语母语者常见：r 容易发成闪音，卷舌接近但不要弹一下。",
    },
    "korean": {
        "tone": "韩语母语者常见：声调概念弱，先用夸张的高低起伏找调型，再收自然。",
        "final": "韩语母语者常见：圆唇与展唇的区分要留意，按普通话韵母的唇形来。",
        "initial": "韩语母语者常见：送气与紧音习惯不同，对准本声母的送气强度。",
    },
}


def reading_report(provider: ProviderResult) -> dict:
    """朗读检错信息（漏读/增读/回读/替换/乱读）＋改善建议，
    仅作为结果中的提示随质量信息返回，不拦截评分与可视化（FR-1301）。"""
    r = provider.reading
    reading = {
        "missing": list(r.get("missing", [])),
        "extra": list(r.get("extra", [])),
        "repeated": list(r.get("repeated", [])),
        "replaced": list(r.get("replaced", [])),
        "disordered": bool(r.get("disordered", False)),
    }
    if reading["disordered"]:
        reading["advice"] = "没有听出按提示词的朗读内容，建议对着提示词完整朗读一遍再试"
    elif reading["missing"]:
        reading["advice"] = (f"有漏读（{ '、'.join(reading['missing']) }），"
                             "把提示的内容一个字一个字读完，效果会更好")
    elif reading["extra"] or reading["repeated"]:
        parts = reading["extra"] + reading["repeated"]
        reading["advice"] = (f"有多读或回读（{'、'.join(parts)}），"
                             "只朗读提示的内容会得到更准确的对比")
    else:
        reading["advice"] = None
    return reading


def _not_available_curve(snapshot: dict, note: str) -> dict:
    return {
        "status": "not_available",
        "scale": "degree",
        "algorithmVersion": analysis.ALGORITHM_VERSION,
        "segments": [],
        "rangeSnapshotId": snapshot.get("id"),
        "userRange": {"fLo": snapshot.get("fLo"), "fHi": snapshot.get("fHi")},
        "note": note,
    }


def analyze_user_curve(wav_path: str, provider: ProviderResult,
                       snapshot: dict, standard_curve: dict | None) -> dict:
    """结果主对比曲线：与标准示范同一条 F0 管线（filtered AC + 四步清洗 +
    degree 1-5 五度坐标，docs/f0展示修改测试版1.md），音域按受理时快照冻结
    （FR-1006）。整段录音有任一可绘制音节即返回 ok。"""
    from app.acoustics import f0_pipeline

    f_lo, f_hi = snapshot["fLo"], snapshot["fHi"]
    if standard_curve is None:
        return _not_available_curve(snapshot, "本关暂无标准曲线")
    try:
        track = f0_pipeline.extract_track(wav_path)
    except f0_pipeline.F0PipelineError as e:
        return _not_available_curve(snapshot, str(e))
    bounds = ([(s.t0, s.t1) for s in provider.syllables]
              or [(0.0, track.duration)])
    processed = f0_pipeline.process_syllables(track, bounds, f_lo, f_hi)
    if not any((seg.get("quality") or {}).get("validFrames", 0) >= f0_pipeline.MIN_DRAW_RUN
               for seg in processed):
        return _not_available_curve(snapshot, "录音里没有提取到可用的音高曲线")

    ref_segments = list(standard_curve.get("segments", []))
    _REF_FIELDS = ("frames", "t0", "t1", "analysisStart", "analysisEnd", "duration",
                   "analysisDuration", "comparisonPoints", "chao", "shape",
                   "featurePoints", "quality")
    segments = []
    for i, seg in enumerate(processed):
        syll = provider.syllables[i] if i < len(provider.syllables) else None
        ref_in = ref_segments[i] if i < len(ref_segments) else None
        ref_side = None
        if ref_in is not None:
            if ref_in.get("frames") is not None:
                ref_side = {k: ref_in[k] for k in _REF_FIELDS if k in ref_in}
            elif ref_in.get("points"):     # 历史 0-5 T 值曲线（版本转换见前端）
                ref_side = {"points": ref_in["points"],
                            "t0": ref_in.get("t0"), "t1": ref_in.get("t1")}
        segments.append({
            "syllable": (syll.text if syll else seg.get("syllable")) or "",
            "toneValue": syll.tone_value if syll else None,
            "user": seg,
            "reference": ref_side,
        })
    curve = {
        "status": "ok",
        "scale": "degree",
        "algorithmVersion": analysis.ALGORITHM_VERSION,
        "segments": segments,
        "rangeSnapshotId": snapshot.get("id"),
        "userRange": {"fLo": f_lo, "fHi": f_hi},
    }
    ref_range = standard_curve.get("referenceRange")
    if ref_range:
        curve["referenceRange"] = ref_range
    if standard_curve.get("sampleMediaId"):
        curve["sampleMediaId"] = standard_curve["sampleMediaId"]
    return curve


# T 值 0-5 旧阈值 → degree 1-5 迁移（docs §4.3：D = 1 + 0.8*T；差值 ×0.8）
_D_END_DRIFT = 1.0 * 0.8        # 一声首尾漂移 > 0.8 T 度
_D_START_HIGH = 1 + 0.8 * 3.2   # 二声起点偏高（T>3.2）
_D_START_LOW2 = 1 + 0.8 * 1.0   # 二声起点偏低（T<1.0）
_D_START_LOW4 = 1 + 0.8 * 1.2   # 四声起点偏低（T<1.2）
_D_RISE_MIN = 1.2 * 0.8         # 二声升幅不足（< 0.96 度）
_D_FALL_MIN = 1.2 * 0.8         # 四声降幅不足
_D_SHAPE_FLAT = 0.8 * 0.8       # 曲线整体偏平（起伏 < 0.64 度）


def curve_phenomena(curve: dict) -> list[dict]:
    """从 degree 1-5 五度曲线提取声调形状现象（只陈述本次测得的现象，
    FR-1301/FR-2004；诊断帧只取 measured/corrected，插值帧不参与）。"""
    out: list[dict] = []
    if curve.get("status") != "ok":
        return out
    for i, seg in enumerate(curve.get("segments", [])):
        tone = seg.get("toneValue")
        syl = seg.get("syllable", "")
        user = seg.get("user") or {}
        quality = user.get("quality") or {}
        if not quality.get("canDiagnose"):
            continue                      # 条件不足只显示曲线，不生成现象
        start, end = user.get("analysisStart"), user.get("analysisEnd")
        if start is None or end is None or end <= start:
            continue
        frames = user.get("frames") or []
        pts = [((p["t"] - start) / (end - start), p["degree"])
               for p in frames if p.get("degree") is not None
               and p.get("source") in ("measured", "corrected")]
        if len(pts) < 4 or not tone:
            continue
        us = np.array([u for u, _ in pts])
        vals = np.array([v for _, v in pts])
        if us[-1] <= us[0]:
            continue
        def value_at(u: float) -> float | None:
            """Read a feature inside a continuous measured/corrected run."""
            target = start + u * (end - start)
            for left, right in zip(frames, frames[1:]):
                if not left["t"] <= target <= right["t"]:
                    continue
                if all(p.get("degree") is not None and p.get("source") in
                       ("measured", "corrected") for p in (left, right)):
                    return float(np.interp(target, [left["t"], right["t"]],
                                           [left["degree"], right["degree"]]))
                return None
            return None

        v20, v80 = value_at(0.2), value_at(0.8)
        vr = float(vals.max() - vals.min())
        add = lambda tag, desc: out.append({  # noqa: E731
            "tag": tag, "syllable": syl,
            "position": {"syllableIndex": i, "part": "tone"},
            "description": desc,
        })
        if tone == 1:
            if v20 is not None and v80 is not None and abs(v80 - v20) > _D_END_DRIFT:
                add("tone_end_unstable", f"「{syl}」第一声的尾巴有较明显的滑动，整体不够平稳")
        elif tone == 2:
            if v20 is not None and v20 > _D_START_HIGH:
                add("tone_start_high", f"「{syl}」第二声起点偏高，升上去的空间就小了")
            elif v20 is not None and v20 < _D_START_LOW2:
                add("tone_start_low", f"「{syl}」第二声起点偏低，上升显得吃力")
            if v20 is not None and v80 is not None and (v80 - v20) < _D_RISE_MIN:
                add("tone_rise_insufficient",
                    f"「{syl}」第二声只升了约 {max(0.0, v80 - v20):.1f} 度，标准要升 1.5 度以上")
            if vr < _D_SHAPE_FLAT:
                add("tone_shape_flat", f"「{syl}」的音高曲线整体偏平，起伏不够")
        elif tone == 3:
            if vr < _D_SHAPE_FLAT:
                add("tone_shape_flat", f"「{syl}」第三声整体偏平，先降后升的形状不明显")
        elif tone == 4:
            if v20 is not None and v20 < _D_START_LOW4:
                add("tone_start_low", f"「{syl}」第四声起点偏低，降下来显得不够干脆")
            if v20 is not None and v80 is not None and (v20 - v80) < _D_FALL_MIN:
                add("tone_fall_insufficient",
                    f"「{syl}」第四声只降了约 {max(0.0, v20 - v80):.1f} 度，标准要降 2 度左右")
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


# 声母送气分类（FR-1005 送气对比；哪些关出该视图由 layer 控制，见 detection 管线）
INITIAL_ASPIRATION = {
    "p": "aspirated", "t": "aspirated", "k": "aspirated",
    "c": "aspirated", "ch": "aspirated", "q": "aspirated",
    "b": "unaspirated", "d": "unaspirated", "g": "unaspirated",
    "z": "unaspirated", "zh": "unaspirated", "j": "unaspirated",
    "f": "fricative", "s": "fricative", "sh": "fricative", "x": "fricative", "h": "fricative",
    "m": "voiced", "n": "voiced", "l": "voiced", "r": "voiced", "y": "voiced", "w": "voiced",
}


def analyze_vot(user_wav: str, user_f0: F0Result, reference_wav: str,
                target_sound: str, reference_media_id: str) -> dict:
    """声母关送气段/VOT 对比（FR-1005）：用户录音与本关参考示范双侧检测，
    输出时段与 VOT 供前端波形标注。"""
    user_span = detect_onset_span(Path(user_wav), user_f0)
    ref_span = detect_onset_span(Path(reference_wav))
    if user_span is None or ref_span is None:
        return {"status": "not_available", "targetSound": target_sound,
                "note": "未能定位清晰的清辅音起始或嗓音起始，暂不做送气段对比"}

    def span_dict(span) -> dict:
        return {"onsetSec": span.onset_sec, "voicingOnsetSec": span.voicing_sec,
                "votMs": span.vot_ms}

    return {
        "status": "ok",
        "targetSound": target_sound,
        "aspiration": INITIAL_ASPIRATION.get(target_sound),
        "user": span_dict(user_span),
        "reference": span_dict(ref_span),
        "referenceMediaId": reference_media_id,
    }


def build_phenomena_and_four_steps(
    *,
    provider: ProviderResult,
    curve_phenomena_items: list[dict],
    formant_deviation: float | None,
    level_content: dict,
    fallback_templates: list[dict],
    dialect_background: str | None = None,
) -> tuple[list[dict], list[dict], float | None]:
    """现象（本关允许标签）→ 四步（本关模板优先，全局兜底）→ 分数。

    分数只在 "score" 属于本关 allowedMetrics 时输出。
    dialect_background（FR-1007）：登记过的背景在对应环节现象的 cue 后追加
    一句常见偏误提示，不改现象与分数；未登记背景不追加。
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

    dialect_cues = DIALECT_CUES.get(dialect_background or "", {})

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
        cue = tpl["cue"]
        dialect_hint = dialect_cues.get(_TAG_FAMILY.get(tag, ""))
        if dialect_hint:
            cue = f"{cue}{dialect_hint}"
        steps.append({
            "phenomenon": tpl["phenomenon"],
            "possibleCause": tpl["possibleCause"],
            "cue": cue,
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
