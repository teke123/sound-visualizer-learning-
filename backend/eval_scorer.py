# -*- coding: utf-8 -*-
"""
看得见的声音 - 四步反馈评测打分脚本（雏形）

用途：
    加载 eval_samples.json，对每条样本用「反馈生成器」生成四步反馈，
    再按样本 expected 约束逐项检查，输出通过率报告。

评测维度（对应 eval_samples.json 的 eval_dimensions）：
    1. 四步完整性  —— 每条反馈是否含 现象/环节/提示/练习 四步（自动化）
    2. 准确性      —— 是否引用了输入里的关键诊断事实 must_mention（自动化）
    3. 类别命中    —— 是否生成了 expected 指定的 category + level（自动化）
    4. 安全性      —— 是否避开了 forbidden 禁用词（自动化，覆盖"安全/鼓励"部分）
    5. 自然度      —— 暂无法自动，需人工评审（见报告末尾提示）

生成器可插拔：
    当前 baseline 直接调用 feedback_engine.build_four_step_feedback（规则引擎）。
    待 Z2 的提示词模板 / LLM 接口（/api/llm/chat）就绪后，只需替换
    generate_feedback() 函数体，其余评测逻辑完全复用。

用法：
    cd backend && python eval_scorer.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # 保证可从任意目录 import feedback_engine

SAMPLES_PATH = os.path.join(HERE, "eval_samples.json")

# 四步反馈的标准字段名（对应 RES-05：现象→环节→提示→练习）
FOUR_STEPS = ["phenomenon", "link", "hint", "practice"]


def generate_feedback(diagnosis: dict) -> dict:
    """反馈生成器（可插拔）。

    输入：诊断 JSON（样本的 input 字段）
    输出：{"overview": str, "steps": [{"category","type","severity","phenomenon","link","hint","practice"}]}

    TODO(Z2)：接入 LLM 后，把下面的规则引擎实现替换为：
        1) 组装提示词（用 diagnosis）
        2) 调 Ollama /api/llm/chat
        3) 解析出与下面相同结构的 steps
    """
    from feedback_engine import build_four_step_feedback

    phonemes = diagnosis.get("phonemes", [])
    target = diagnosis.get("target", {})
    quality = diagnosis.get("quality", {})

    # 提取录音质量警告项（warn 级）
    quality_warn = None
    for item in quality.get("items", []):
        if item.get("status") == "warn":
            quality_warn = {"message": item.get("message", "")}
            break

    items = build_four_step_feedback(
        tone_combined=diagnosis.get("tone_score", 0.0),
        f0_mean=diagnosis.get("f0_mean", 0.0),
        f0_std=diagnosis.get("f0_std", 0.0),
        ref_f0=diagnosis.get("ref_f0", 200.0),
        detected_tone=diagnosis.get("detected_tone", 0),
        ref_tone=target.get("tone", 1),
        fluency=diagnosis.get("fluency", 50.0),
        phonemes=phonemes,
        quality_warn=quality_warn,
    )

    steps = [
        {
            "category": it.get("category"),
            "type": it.get("type"),
            "severity": it.get("severity"),
            "phenomenon": it.get("phenomenon", ""),
            "link": it.get("link", ""),
            "hint": it.get("hint", ""),
            "practice": it.get("practice", ""),
        }
        for it in items
    ]
    return {"overview": "基于规则引擎共生成 %d 条四步反馈" % len(steps), "steps": steps}


def _parse_llm_json(text: str) -> dict:
    """从 LLM 回复中提取 JSON 对象（容忍代码块包裹、前后杂文字）"""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"overview": "LLM 未返回有效 JSON", "steps": []}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {"overview": "LLM 返回 JSON 解析失败", "steps": []}


_TYPE_TO_SEVERITY = {"suggestion": 0, "warning": 1, "error": 2}


def _normalize_severity(raw, ftype) -> int:
    """把 severity 归一化为契约要求的整数 0/1/2（兼容 LLM 输出字符串的情况）"""
    if isinstance(raw, int) and raw in (0, 1, 2):
        return raw
    if isinstance(raw, str) and raw.strip().isdigit():
        v = int(raw.strip())
        if v in (0, 1, 2):
            return v
    if isinstance(raw, str) and raw.strip() in _TYPE_TO_SEVERITY:
        return _TYPE_TO_SEVERITY[raw.strip()]
    return _TYPE_TO_SEVERITY.get(str(ftype).strip(), 1)


# ---------------------------------------------------------------------------
# 提示词模板 V2（Z3 · 第 13 周）
# 核心原则：检测结论由规则引擎定死，LLM 只负责把四步话术写得自然。
# 这样保证 category/type/severity 与规则引擎 100% 一致、多次生成稳定。
# ---------------------------------------------------------------------------

TONE_NAMES = {1: "第一声（阴平）", 2: "第二声（阳平）", 3: "第三声（上声）", 4: "第四声（去声）"}

PROMPT_TEMPLATE = """你是普通话发音教练，正在为一名零基础学习者写四步反馈。

【最重要规则 —— 必须遵守】
1. 输出必须是合法 JSON，不要输出任何解释、注释或代码块标记。
2. steps 数组里的每一项，category、type、severity、key_fact 四个字段必须【原样照抄】我给你的"结论清单"，一个字都不能改、不能少、不能多。
3. steps 的数量必须【严格等于结论清单的条数】，一条都不能少。结论清单有 2 条就输出 2 步，有 3 条就输出 3 步。每一条结论都必须对应生成一步，不能遗漏任何一条。
4. 你只能自己写 phenomenon / link / hint / practice 四个文字字段，其余字段照抄。每一步的四个文字字段都必须写满，不能留空字符串。
5. 每一项的 phenomenon 必须包含对应的 key_fact 原文（逐字引用），不得改写、不得说反。
   - 特别注意：若 key_fact 写"第三声"，就是学习者把音发成了第三声；若写"目标第一声"，第一声才是标准。不要说反。
6. 语气温和鼓励，面向零基础孩子和家长，避免医学术语。练习必须安全、可在家完成、不超过1分钟。

【结构化诊断】
{diagnosis_json}

【结论清单】（category/type/severity/key_fact 必须原样照抄到每一步）
{conclusion_list}

【输出格式】
{{"overview":"一句话总评","steps":[
  {{"category":"<照抄>","type":"<照抄>","severity":"<照抄整数>","key_fact":"<照抄>",
    "phenomenon":"①现象，必须含 key_fact 原文","link":"②可能相关的发声环节",
    "hint":"③可感知的改进提示","practice":"④安全的短练习"}}
]}}

只输出 JSON。"""


def _build_key_facts(diagnosis: dict, rule_items: list) -> list:
    """为规则引擎的每条结论生成一条必须逐字引用的关键事实。"""
    target = diagnosis.get("target", {})
    detected = diagnosis.get("detected_tone", 0)
    facts = []
    for it in rule_items:
        cat = it.get("category")
        if cat == "tone":
            ref = target.get("tone", 1)
            facts.append("目标%s，实际识别为%s" % (
                TONE_NAMES.get(ref, "第一声"), TONE_NAMES.get(detected, "其他声调")))
        elif cat == "pronunciation":
            # 优先引用真正的声母/韵母错误，避免把声调事实串到音素步骤
            for ph in diagnosis.get("phonemes", []):
                if ph.get("phoneme") in ("声母", "韵母") and ph.get("score", 100) < 60:
                    facts.append("%s目标「%s」，实际识别为「%s」" % (
                        ph.get("phoneme", "音素"), ph.get("expected", "?"), ph.get("detected", "?")))
                    break
            else:
                facts.append("目标「%s」，识别为「%s」" % (
                    diagnosis.get("unit", "?"), diagnosis.get("recognized_text", "?")))
        elif cat == "fluency":
            facts.append("流利度偏低（%.0f分），存在停顿或拖音" % diagnosis.get("fluency", 0.0))
        elif cat == "quality":
            for q in diagnosis.get("quality", {}).get("items", []):
                if q.get("status") == "warn":
                    facts.append("录音质量提示：%s" % q.get("message", "录音环境需改善"))
                    break
            else:
                facts.append("录音质量提示：建议改善录音环境")
        else:
            facts.append("发音与标准存在偏差")
    return facts


def generate_feedback_llm(diagnosis: dict) -> dict:
    """反馈生成器（LLM 版 · 提示词模板 V2）。

    检测结论由规则引擎定死（category/type/severity/key_fact 照抄），
    LLM 只生成四步文字，保证「话术不改结论」+ 多次生成稳定。
    """
    import llm_service

    # ① 规则引擎先定结论（不调用 LLM，保证结论权威）
    rule_fb = generate_feedback(diagnosis)
    rule_items = rule_fb.get("steps", [])
    key_facts = _build_key_facts(diagnosis, rule_items)

    conclusion_list = json.dumps([
        {
            "category": it.get("category"),
            "type": it.get("type"),
            "severity": _normalize_severity(it.get("severity"), it.get("type")),
            "key_fact": key_facts[i] if i < len(key_facts) else "发音与标准存在偏差",
        }
        for i, it in enumerate(rule_items)
    ], ensure_ascii=False, indent=2)

    prompt = PROMPT_TEMPLATE.format(
        diagnosis_json=json.dumps(diagnosis, ensure_ascii=False),
        conclusion_list=conclusion_list,
    )

    reply = llm_service.chat([{"role": "user", "content": prompt}], temperature=0.2)
    parsed = _parse_llm_json(reply)

    # ② 结论字段强制从规则引擎覆盖（双保险：即使 LLM 抄错也纠正）
    steps = []
    for i, it in enumerate(rule_items):
        gen = parsed.get("steps", [])[i] if i < len(parsed.get("steps", [])) else {}
        fact = key_facts[i] if i < len(key_facts) else "发音与标准存在偏差"
        steps.append({
            "category": it.get("category"),
            "type": it.get("type"),
            "severity": _normalize_severity(it.get("severity"), it.get("type")),
            "phenomenon": str(gen.get("phenomenon", "")).strip() or fact,
            "link": str(gen.get("link", "")).strip() or "可能与发音时的肌肉控制与气息有关。",
            "hint": str(gen.get("hint", "")).strip() or "放慢速度，注意听示范音，再跟着模仿一次。",
            "practice": str(gen.get("practice", "")).strip() or "跟着示范音练 3 遍，每次不超过 1 分钟。",
        })
    return {"overview": parsed.get("overview", "") or "这次发音有几点可以改进，我们一步一步来。", "steps": steps}


def flatten_text(feedback: dict) -> str:
    """把反馈内容拼成一段文本，供关键词/禁用词检查"""
    parts = [str(feedback.get("overview", ""))]
    for s in feedback.get("steps", []):
        parts.append(" ".join(str(s.get(k, "")) for k in FOUR_STEPS))
    return " ".join(parts)


def check_sample(sample: dict, generator=None) -> dict:
    """对单条样本执行评测，返回检查明细"""
    if generator is None:
        generator = generate_feedback
    feedback = generator(sample["input"])
    expected = sample["expected"]
    steps = feedback.get("steps", [])
    text = flatten_text(feedback)

    checks = []

    # 1. 四步完整性
    complete = bool(steps) and all(
        all(str(s.get(k, "")).strip() for k in FOUR_STEPS) for s in steps
    )
    checks.append(("四步完整性", complete, "每步需含现象/环节/提示/练习" if not complete else ""))

    # 2. 类别/级别命中
    cat_level = any(
        s.get("category") == expected.get("category")
        and s.get("type") == expected.get("level")
        for s in steps
    )
    checks.append(("类别/级别命中", cat_level,
                   f"需含 {expected.get('category')}/{expected.get('level')}" if not cat_level else ""))

    # 3. 准确性（关键词命中）
    missing = [m for m in expected.get("must_mention", []) if m not in text]
    checks.append(("关键词命中", not missing, "缺:" + ",".join(missing) if missing else ""))

    # 4. 安全/鼓励（禁用词）
    hit = [f for f in expected.get("forbidden", []) if f in text]
    checks.append(("无禁用词", not hit, "命中:" + ",".join(hit) if hit else ""))

    ok = all(c[1] for c in checks)
    return {
        "id": sample["id"],
        "scene": sample["scene"],
        "ok": ok,
        "checks": checks,
        "steps_count": len(steps),
    }


def main() -> int:
    use_llm = "--llm" in sys.argv
    with open(SAMPLES_PATH, encoding="utf-8") as f:
        data = json.load(f)

    samples = data.get("samples", [])
    generator = generate_feedback_llm if use_llm else generate_feedback
    results = [check_sample(s, generator) for s in samples]
    passed = sum(1 for r in results if r["ok"])

    mode = "LLM（qwen2.5:7b）" if use_llm else "规则引擎（baseline）"
    print("=" * 64)
    print("看得见的声音 · 四步反馈评测报告 [%s]" % mode)
    print("样本总数: %d   通过: %d   通过率: %.1f%%" % (len(results), passed, 100.0 * passed / len(results)))
    print("=" * 64)

    for r in results:
        flag = "PASS" if r["ok"] else "FAIL"
        print("\n[%s] %s  (%s)  -> %d 步反馈" % (flag, r["id"], r["scene"], r["steps_count"]))
        for name, passed_check, detail in r["checks"]:
            mark = "[OK]" if passed_check else "[X ]"
            suffix = ("  " + detail) if detail else ""
            print("      %s %s%s" % (mark, name, suffix))

    print("\n" + "=" * 64)
    print("提示：自然度、鼓励性两个维度无法全自动，请人工抽检 steps 话术是否自然。")
    print("接入 Z2 的 LLM 模板后，替换 generate_feedback() 即可复用本评测框架。")
    print("=" * 64)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
