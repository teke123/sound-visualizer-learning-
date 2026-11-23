# -*- coding: utf-8 -*-
"""
CON-07 演示验收脚本（第 13 周 · Z3）

固定演示样本，一键跑出完整证据链：
    结构化诊断 → 规则结论（字段固定）→ LLM 四步话术 → 三重校验 → 多次生成稳定性

对应排期第 13 周「A + Z 组：同一检测结果链路稳定；结论字段固定、话术可生成 / 改写」，
以及第 14 周 CON-07「同一检测结果演示：结论字段不变、四步话术可生成 / 改写、人工审核位」。

用法：
    cd backend && python demo_verify.py              # 默认演示样本 samp_tone_002
    cd backend && python demo_verify.py samp_pron_001  # 指定样本 ID
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from eval_scorer import generate_feedback, generate_feedback_llm
from validate_contract import validate
from eval_feedback import rule_conclusion, check_consistency

SAMPLES_PATH = os.path.join(HERE, "eval_samples.json")
DEFAULT_SAMPLE = "samp_tone_002"
REPEAT = 3  # 多次生成，检验稳定性


def find_sample(samples: list, sid: str) -> dict:
    for s in samples:
        if s["id"] == sid:
            return s
    return None


def main() -> int:
    sid = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SAMPLE
    with open(SAMPLES_PATH, encoding="utf-8") as f:
        samples = json.load(f).get("samples", [])

    sample = find_sample(samples, sid)
    if not sample:
        print("找不到样本: %s" % sid)
        return 1

    diag = sample["input"]
    expected = sample["expected"]

    print("=" * 68)
    print("CON-07 演示验收报告   样本: %s (%s)" % (sid, sample["scene"]))
    print("=" * 68)

    # ① 结构化诊断（关键字段）
    print("\n【1】结构化诊断（输入，字段固定）")
    print("  目标音: %s   目标声调: %s" % (
        diag.get("unit", "-"), diag.get("target", {}).get("tone", "-")))
    print("  识别文本: %s   识别声调: %s   声调得分: %s" % (
        diag.get("recognized_text", "-"), diag.get("detected_tone", "-"),
        diag.get("tone_score", "-")))
    print("  流利度: %s   音素数: %d" % (
        diag.get("fluency", "-"), len(diag.get("phonemes", []))))

    # ② 规则结论（字段固定的基线）
    rule_fb = generate_feedback(diag)
    rule_concl = rule_conclusion(rule_fb)
    print("\n【2】规则引擎结论（检测结论，不变）")
    for cat, typ in sorted(rule_concl):
        print("  - category=%s  type=%s" % (cat, typ))
    print("  期望类别/级别: %s / %s" % (
        expected.get("category"), expected.get("level")))

    # ③ LLM 四步话术
    print("\n【3】LLM 生成的四步话术（qwen2.5:7b）")
    llm_fb = generate_feedback_llm(diag)
    print("  总评: %s" % llm_fb.get("overview", "-"))
    for i, s in enumerate(llm_fb.get("steps", []), 1):
        print("  --- 第 %d 步 [%s/%s] ---" % (i, s.get("category"), s.get("type")))
        print("      ①现象: %s" % s.get("phenomenon", ""))
        print("      ②环节: %s" % s.get("link", ""))
        print("      ③提示: %s" % s.get("hint", ""))
        print("      ④练习: %s" % s.get("practice", ""))

    # ④ 三重校验
    print("\n【4】三重校验")
    issues = validate(llm_fb)
    c_ok = not issues
    cons = check_consistency(rule_fb, llm_fb)
    from eval_scorer import flatten_text
    text = flatten_text(llm_fb)
    missing_kw = [m for m in expected.get("must_mention", []) if m not in text]
    forbidden_hit = [f for f in expected.get("forbidden", []) if f in text]
    print("  契约合规: %s" % ("PASS" if c_ok else "FAIL " + ";".join(issues[:2])))
    print("  结论一致: %s" % ("PASS" if cons["consistent"] else "FAIL 缺:" + str(cons["missing"])))
    print("  关键词命中: %s" % ("PASS" if not missing_kw else "FAIL 缺:" + ",".join(missing_kw)))
    print("  无禁用词: %s" % ("PASS" if not forbidden_hit else "FAIL 命中:" + ",".join(forbidden_hit)))

    # ⑤ 多次生成稳定性（同一诊断，生成 N 次，看话术是否一致）
    print("\n【5】多次生成稳定性（同一诊断生成 %d 次）" % REPEAT)
    outputs = []
    for i in range(REPEAT):
        fb = generate_feedback_llm(diag)
        concl = rule_conclusion(fb)
        outputs.append({"conclusion": concl, "text": flatten_text(fb)})
        print("  第 %d 次: category/type = %s" % (i + 1, sorted(concl)))

    stable_concl = all(o["conclusion"] == outputs[0]["conclusion"] for o in outputs)
    print("  结论字段稳定: %s" % ("PASS" if stable_concl else "FAIL（多次结论不一致）"))
    print("  注：话术措辞允许自然语言差异，但 category/type 结论字段必须一致")

    # 总判定
    overall = c_ok and cons["consistent"] and not missing_kw and not forbidden_hit and stable_concl
    print("\n" + "=" * 68)
    print("演示验收总判定: %s" % ("PASS — 可用于 CON-07 演示" if overall else "FAIL — 需 optimizer 提示词"))
    print("=" * 68)
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
