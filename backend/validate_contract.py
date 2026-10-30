# -*- coding: utf-8 -*-
"""
「结构化诊断 → 自然话术」接口契约校验脚本

用途：
    校验生成的四步话术 JSON 是否符合接口契约（结构、必填字段、枚举合法性、四步非空）。
    与 eval_scorer.py 分工：
        - eval_scorer.py       评「话术质量」（四步完整性 / 准确性 / 类别命中 / 禁用词）
        - validate_contract.py 评「契约合规」（JSON 结构 / 必填字段 / 枚举值）

用法：
    cd backend && python validate_contract.py        # 校验规则引擎输出
    cd backend && python validate_contract.py --llm  # 校验 LLM 输出
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SAMPLES_PATH = os.path.join(HERE, "eval_samples.json")

CATEGORIES = {"tone", "pronunciation", "fluency", "quality"}
LEVELS = {"error", "warning", "suggestion"}
SEVERITIES = {0, 1, 2}  # 0 提示 / 1 警告 / 2 错误（与 type 对应）
STEP_FIELDS = ["category", "type", "severity", "phenomenon", "link", "hint", "practice"]


def validate(feedback: dict) -> list:
    """校验单条输出是否符合契约，返回问题列表（空列表 = 合规）"""
    if not isinstance(feedback, dict):
        return ["输出不是 JSON 对象"]

    issues = []
    if not str(feedback.get("overview", "")).strip():
        issues.append("overview 缺失或为空")

    steps = feedback.get("steps")
    if not isinstance(steps, list) or not steps:
        issues.append("steps 缺失或为空数组")
        return issues

    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            issues.append("steps[%d] 不是对象" % i)
            continue
        for f in STEP_FIELDS:
            if not str(s.get(f, "")).strip():
                issues.append("steps[%d].%s 缺失或为空" % (i, f))
        if s.get("category") not in CATEGORIES:
            issues.append("steps[%d].category 非法: %r" % (i, s.get("category")))
        if s.get("type") not in LEVELS:
            issues.append("steps[%d].type 非法: %r" % (i, s.get("type")))
        if s.get("severity") not in SEVERITIES:
            issues.append("steps[%d].severity 非法: %r" % (i, s.get("severity")))
    return issues


def main() -> int:
    from eval_scorer import generate_feedback, generate_feedback_llm

    use_llm = "--llm" in sys.argv
    generator = generate_feedback_llm if use_llm else generate_feedback

    with open(SAMPLES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    samples = data.get("samples", [])

    total = len(samples)
    passed = 0
    mode = "LLM（qwen2.5:7b）" if use_llm else "规则引擎（baseline）"
    print("=" * 64)
    print("「结构化诊断 → 自然话术」接口契约校验 [%s]" % mode)
    print("=" * 64)

    for s in samples:
        feedback = generator(s["input"])
        issues = validate(feedback)
        ok = not issues
        passed += 1 if ok else 0
        print("\n[%s] %s  (%s)" % ("PASS" if ok else "FAIL", s["id"], s["scene"]))
        for it in issues:
            print("      - " + it)

    rate = 100.0 * passed / total if total else 0.0
    print("\n" + "=" * 64)
    print("契约合规: %d/%d (%.1f%%)" % (passed, total, rate))
    print("=" * 64)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
