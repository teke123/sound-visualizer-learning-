# -*- coding: utf-8 -*-
"""
话术输出质量评测脚本（第 11 周 · 起步）

整合三重评测维度，一键输出评测报告：
1. 契约合规  —— 结构 / 必填字段 / 枚举值（validate_contract.validate）
2. 话术质量  —— 四步完整性 / 准确性 / 类别命中 / 禁用词（eval_scorer.check_sample）
3. 结论一致性 —— LLM 话术的 category/type 与规则引擎结论是否一致

用法：
    cd backend && python eval_feedback.py        # 规则引擎 baseline（自检）
    cd backend && python eval_feedback.py --llm  # 评测 LLM 话术（需 Ollama 运行）
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from eval_scorer import generate_feedback, generate_feedback_llm, check_sample
from validate_contract import validate

SAMPLES_PATH = os.path.join(HERE, "eval_samples.json")


def rule_conclusion(feedback: dict) -> set:
    """提取反馈的结论集合：{(category, type), ...}"""
    return {(s.get("category"), s.get("type")) for s in feedback.get("steps", [])}


def check_consistency(rule_fb: dict, llm_fb: dict) -> dict:
    """校验 LLM 话术结论与规则引擎结论是否一致。

    一致性 = LLM 话术的 category/type 集合必须覆盖规则引擎的 category/type 集合
    （话术只能解释诊断，不能改变检测结论）。
    """
    rule = rule_conclusion(rule_fb)
    llm = rule_conclusion(llm_fb)
    missing = rule - llm
    extra = llm - rule
    return {
        "consistent": len(missing) == 0,
        "missing": sorted(list(missing)),
        "extra": sorted(list(extra)),
    }


def main() -> int:
    use_llm = "--llm" in sys.argv
    with open(SAMPLES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    samples = data.get("samples", [])

    mode = "LLM（qwen2.5:7b）" if use_llm else "规则引擎（baseline）"
    print("=" * 64)
    print("话术输出质量评测报告 [%s]" % mode)
    print("=" * 64)

    contract_ok = quality_ok = consist_ok = 0
    total = len(samples)

    for s in samples:
        rule_fb = generate_feedback(s["input"])
        fb = generate_feedback_llm(s["input"]) if use_llm else rule_fb

        # 1. 契约合规
        issues = validate(fb)
        c_ok = not issues
        contract_ok += 1 if c_ok else 0

        # 2. 话术质量（4 项检查）
        q = check_sample(s, generate_feedback_llm if use_llm else generate_feedback)
        q_ok = q["ok"]
        quality_ok += 1 if q_ok else 0

        # 3. 结论一致性（仅 LLM 模式有意义）
        cons = check_consistency(rule_fb, fb)
        if cons["consistent"]:
            consist_ok += 1

        overall = c_ok and q_ok and (cons["consistent"] if use_llm else True)
        print("\n[%s] %s  (%s)" % ("PASS" if overall else "FAIL", s["id"], s["scene"]))
        print("      契约合规: %s" % ("OK" if c_ok else "FAIL " + ";".join(issues[:2])))
        if q_ok:
            print("      话术质量: OK")
        else:
            bad = [c[0] for c in q["checks"] if not c[1]]
            print("      话术质量: FAIL (" + ",".join(bad) + ")")
        if use_llm:
            print("      结论一致: %s" % ("OK" if cons["consistent"] else "FAIL 缺:" + str(cons["missing"])))

    print("\n" + "=" * 64)
    print("契约合规: %d/%d (%.1f%%)" % (contract_ok, total, 100.0 * contract_ok / total))
    print("话术质量: %d/%d (%.1f%%)" % (quality_ok, total, 100.0 * quality_ok / total))
    if use_llm:
        print("结论一致: %d/%d (%.1f%%)" % (consist_ok, total, 100.0 * consist_ok / total))
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
