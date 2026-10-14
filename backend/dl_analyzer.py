# -*- coding: utf-8 -*-
"""发音错误诊断（重构占位骨架）。

意图：误读 / 漏读 / 声调错位定位——
把 Wav2Vec2 当声学打分器，对目标音的候选字集合（闭集）与开集候选做
强制选择比较，再按声母/韵母/声调逐项比对得到结构化诊断。
- 多音字按与目标声韵匹配的读音消歧；
- y/w 半元音、尾滑音的教学宽容口径在此集中定义；
- 目标音来源（关卡表）由内容服务提供，代码内不冻结关卡数据。
"""

VERDICT_LABELS = {
    "correct": "正确",
    "misread_initial": "误读·声母",
    "misread_final": "误读·韵母",
    "misread_syllable": "误读·声韵",
    "tone_error": "声调错位",
    "missed": "漏读/未识别",
    "uncertain": "低置信(待复核)",
}

# 置信度阈值的标定口径（重构后用标准样本集重新标定，过程写入实验日志）：
#   闭集 = 目标音候选字集合；开集 = 模型每帧 top-k 冒出的其它汉字。
PROB_CONFIDENT = 0.30     # 选中字概率 ≥ 此值才给确定结论
PROB_UNCERTAIN = 0.10     # 低于此值判"漏读/未识别"
CLOSED_MISS_PROB = 0.05   # 闭集最优字概率低于此值 → 没读到目标音
OPEN_MARGIN_RATIO = 1.5   # 开集字须至少 1.5× 闭集最优字概率才采信


def diagnose(audio_path: str, target=None) -> dict:
    """意图：诊断入口；目标（声母/韵母/声调 + 候选字集合）由调用方传入。"""
    raise NotImplementedError("重构占位：发音诊断")
