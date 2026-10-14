"""四步反馈生成（重构占位骨架）。

意图：根据声学与发音诊断生成「现象 -> 相关环节 -> 提示 -> 练习」四步反馈。
- 每条反馈只输出一套字段（phenomenon/link/hint/practice + type/category/severity），
  前端契约单一化；
- 调性：说明现象与成因，不给空话；检测不可靠时如实降档，不硬给结论。
"""


def build_four_step_feedback(**diagnosis) -> list[dict]:
    """意图：规则引擎（或接 LLM）生成四步反馈列表。

    入参口径待重构定义（声调分、音素诊断、流利度、录音质量告警等）。
    """
    raise NotImplementedError("重构占位：四步反馈生成")


def compute_reliability(**signals) -> tuple[str, str]:
    """意图：结果可靠性分档（reliable / reference_only / not_available）+ 说明。

    依据：录音质量、有效语音占比、识别置信度。
    """
    raise NotImplementedError("重构占位：可靠性判定")
