"""上传诊断流程（重构占位骨架）。

意图：保存上传音频到实验目录、调用发音诊断、把结果追加到 JSONL 实验日志
（模型/耗时/结论可追溯，供评测与阈值标定）。
"""


def diagnose_upload(content: bytes, filename: str | None,
                    level_id: str | None, target_pinyin: str | None) -> dict:
    """意图：保存音频 -> 诊断 -> 记录实验日志 -> 返回诊断结果。"""
    raise NotImplementedError("重构占位：上传诊断")
