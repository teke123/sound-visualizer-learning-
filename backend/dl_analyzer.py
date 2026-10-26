# -*- coding: utf-8 -*-
"""发音错误诊断(声母/韵母/声调闭环):误读 / 漏读 / 声调错位定位。

1.0 不新训模型:把 audio_analyzer 里的 Wav2Vec2 当声学打分器,对目标音的
候选字集合做 CTC 强制选择(帧级 logsumexp 打分),再用 pypinyin 反查的
声韵调与关卡目标逐项比对 → 结构化诊断。与通用识别(analyze_with_deep_learning)
解耦,故从 audio_analyzer 拆出本模块(符合分工 PDF"必要时再拆出 dl_analyzer.py")。
"""
from __future__ import annotations

from .asr_analyzer import get_analyzer, softmax
from .levels import LEVELS_BY_ID, candidate_chars
from .pinyin_utils import (char_pinyin, char_pinyin_matching, chars_for_base,
                           chars_for_pinyin, parse_pinyin, strip_semivowel)

VERDICT_LABELS = {
    "correct": "正确",
    "misread_initial": "误读·声母",
    "misread_final": "误读·韵母",
    "misread_syllable": "误读·声韵",
    "tone_error": "声调错位",
    "missed": "漏读/未识别",
    "uncertain": "低置信(待复核)",
}

# 置信度阈值(2026-10-11 用标准样本集标定,标定过程见 experiments/batch_*/summary.md):
#   闭集 = 目标音候选字集合;开集 = 模型每帧 top-3 冒出的其它汉字。
PROB_CONFIDENT = 0.30     # 选中字概率 ≥ 此值才给确定结论
PROB_UNCERTAIN = 0.10     # 低于此值判"漏读/未识别"(低置信)
CLOSED_MISS_PROB = 0.05   # 闭集最优字概率低于此值 → 没读到目标音(漏读)
OPEN_MARGIN_RATIO = 1.5   # 开集字须至少 1.5× 闭集最优字概率才采信(防误读假阳性)


def _compare(expected: dict, ch: str) -> tuple[str, str]:
    """按声母/韵母/声调逐项比对 → (诊断结论码, 备注)。

    多音字按与目标声韵匹配的读音比对(char_pinyin_matching),避免"勒/阿/司"
    等字的默认读音把对的答案误判成错。尾滑音(ō→ōu、ē→ēi)记正确并备注。
    """
    py = char_pinyin_matching(ch, expected["initial"], expected["final"],
                              prefer_tone=expected["tone"] if expected["tone_strict"] else None)
    i, f, t = parse_pinyin(py)
    if expected["initial"] == "":
        i = strip_semivowel(i, f)
    init_ok = i == expected["initial"]
    final_ok = f == expected["final"]
    tone_ok = True
    if expected["tone_strict"] and expected["tone"] is not None:
        tone_ok = t == expected["tone"]
    if init_ok and final_ok and tone_ok:
        return "correct", ""
    if init_ok and final_ok:
        return "tone_error", ""           # 声调错位(声韵对、调错)
    if init_ok and f in (expected["final"] + "u", expected["final"] + "i"):
        return "correct", "glide_tolerated"  # 尾滑音宽容(教学口径,不计误读)
    if final_ok:
        return "misread_initial", ""      # 韵母对、声母错
    if init_ok:
        return "misread_final", ""        # 声母对、韵母错
    return "misread_syllable", ""         # 声韵都错


def diagnose(audio_path: str, level_id: str | None = None,
             target_pinyin: str | None = None) -> dict:
    """诊断入口。level_id 优先;也可直接给 target_pinyin(如 'mǎ' 校验 L30 单一声调)。"""
    analyzer = get_analyzer()
    analyzer.ensure_loaded()

    # ---- 目标解析 ----
    level = LEVELS_BY_ID.get(level_id) if level_id else None
    if level is not None:
        chars, tone_strict = candidate_chars(level)
        expected = {"initial": level.initial, "final": level.final,
                    "tone": level.tone, "tone_strict": tone_strict}
        disp = {"level_id": level.level_id, "target_name": level.target_name,
                "target_pinyin": level.target_pinyin, "category": level.category}
    elif target_pinyin:
        ti, tf, tt = parse_pinyin(target_pinyin)
        exact = chars_for_pinyin(target_pinyin)
        tone_strict = bool(exact) and tt != 0
        chars = exact or chars_for_base(ti, tf)
        expected = {"initial": strip_semivowel(ti, tf), "final": tf,
                    "tone": tt if tt else None, "tone_strict": tone_strict}
        disp = {"level_id": None, "target_name": None, "target_pinyin": target_pinyin,
                "category": "自定义"}
    else:
        raise ValueError("需要 level_id 或 target_pinyin")

    # ---- 推理 + 强制选择 ----
    logits, stats = analyzer._forward(audio_path)
    if logits is None:
        return _result(analyzer, disp, expected, stats, "missed",
                       reason="silent_or_too_short", candidates=[], text="", closed_n=len(chars))

    open_chars = analyzer.open_candidates(logits)
    pool = list(dict.fromkeys(list(chars) + open_chars))     # 闭集 ∪ 开集,去重保序
    scores = analyzer.token_scores(logits, pool)
    probs = softmax(scores)
    ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    greedy_text = analyzer.ctc_greedy_text(logits)

    cands = [{"char": c, "pinyin": char_pinyin(c), "prob": round(p, 4),
              "score": round(scores[c], 3)} for c, p in ranked[:8]]

    # ---- 结论(闭集优先;开集须显著越权才采信) ----
    char_set = set(chars)
    closed = [(c, p) for c, p in ranked if c in char_set]
    open_ = [(c, p) for c, p in ranked if c not in char_set]
    bc_char, bc_prob = closed[0] if closed else ("", 0.0)
    bo_char, bo_prob = open_[0] if open_ else ("", 0.0)
    hanzi_text = "".join(ch for ch in greedy_text if "一" <= ch <= "鿿")

    if len(hanzi_text) >= 2:
        # 贪心解码出 ≥2 个汉字 → 多读了音节
        verdict, reason = "misread_syllable", "multiple_syllables"
        best_char, best_prob = ranked[0] if ranked else ("", 0.0)
    else:
        chosen = (bo_char, bo_prob) if (bo_char and bo_prob >= bc_prob * OPEN_MARGIN_RATIO) \
            else (bc_char, bc_prob)
        best_char, best_prob = chosen
        if best_prob < PROB_UNCERTAIN:
            verdict, reason = "missed", "low_confidence"
        elif best_prob < PROB_CONFIDENT:
            # 闭集无质量 + 选中字也不够强 → 没读到目标音;闭集有质量 → 低置信待复核
            verdict, reason = ("missed", "no_target_match") if bc_prob < CLOSED_MISS_PROB \
                else ("uncertain", "below_confident_threshold")
        else:
            verdict, reason = _compare(expected, best_char)

    return _result(analyzer, disp, expected, stats, verdict, reason=reason,
                   candidates=cands, text=greedy_text, closed_n=len(chars),
                   best_char=best_char, best_prob=best_prob)


def _result(analyzer, disp, expected, stats, verdict, reason="",
            candidates=None, text="", closed_n=0, best_char=None, best_prob=None) -> dict:
    detected = None
    if best_char:
        # 与结论一致的口径:多音字取与目标声韵匹配的读音(如 勒→lè、阿→ē)
        py = char_pinyin_matching(best_char, expected["initial"], expected["final"],
                                  prefer_tone=expected["tone"] if expected["tone_strict"] else None)
        i, f, t = parse_pinyin(py)
        detected = {"char": best_char, "pinyin": py,
                    "initial": i, "final": f, "tone": t, "prob": round(best_prob, 4)}
    return {
        "ok": True,
        "service": "1.0 通用模型诊断(Wav2Vec2 CTC 强制选择 + 声韵调比对)",
        "model_id": analyzer.model_id, "device": analyzer.device,
        **disp, "expected": expected,
        "verdict": {"code": verdict, "label": VERDICT_LABELS[verdict]},
        "detected": detected, "recognized_text": text,
        "candidates": candidates or [], "closed_set_size": closed_n,
        "audio": stats, "note": reason or None,
    }
