"""根据声学与发音诊断生成现象、相关环节、提示和练习四步反馈。"""
from __future__ import annotations

from typing import Optional


def _item(
    ftype: str,
    category: str,
    phenomenon: str,
    link: str,
    hint: str,
    practice: str,
    severity: int = 1,
) -> dict:
    """构造一条四步反馈项（severity: 0 提示 / 1 警告 / 2 错误）"""
    return {
        "type": ftype,          # suggestion / warning / error
        "category": category,   # tone / pronunciation / fluency / quality / rhythm
        "phenomenon": phenomenon,
        "link": link,
        "hint": hint,
        "practice": practice,
        "severity": severity,

        "message": phenomenon,
        "detail": link,
        "improvement": f"{hint}；然后：{practice}",
    }


def build_four_step_feedback(
    *,
    tone_combined: float,
    f0_mean: float,
    f0_std: float,
    ref_f0: float,
    detected_tone: int,
    ref_tone: int,
    fluency: float,
    phonemes: list[dict],
    quality_warn: Optional[dict],
) -> list[dict]:
    """根据检测特征生成四步反馈列表（规则引擎，模板可配置）"""
    items: list[dict] = []

    # ---- 规则 1：声调偏差（基于基频均值/稳定性/声调识别） ----
    tone_name = {1: "阴平", 2: "阳平", 3: "上声", 4: "去声"}.get(ref_tone, "本声调")
    has_f0 = f0_mean > 0 or f0_std > 0
    if tone_combined < 60:
        if not has_f0:
            items.append(_item(
                "error", "tone", severity=2,
                phenomenon="未能检测到有效基频（语音过弱、过短或噪声过大），无法评估声调",
                link="录音音量与距离——麦克风距离 10-20cm，环境安静，声音清晰响亮",
                hint="靠近麦克风、放慢语速、提高音量重新录音，确保环境无背景噪声",
                practice="先朗读 3 遍示范音节找到合适音量，再开始录音练习",
            ))
        elif detected_tone and detected_tone != ref_tone:
            det_name = {1: "阴平", 2: "阳平", 3: "上声", 4: "去声"}.get(detected_tone, "其他声调")
            items.append(_item(
                "error", "tone", severity=2,
                phenomenon=f"声调识别为「{det_name}」，与目标「{tone_name}」不符（平均基频{f0_mean:.0f}Hz vs 标准{ref_f0:.0f}Hz）",
                link="声带张力调节——声调高低由声带松紧程度控制，紧张度改变音高走向",
                hint="发目标声调前先心里默念它的走向（如去声想象'下楼梯'），再开口发声",
                practice="用「妈麻马骂」四声慢速连读，每字约1秒，共5遍；每遍注意音高起点与落点是否一致",
            ))
        else:
            items.append(_item(
                "error", "tone", severity=2,
                phenomenon=f"声调曲线形状与标准{tone_name}偏差较大（平均基频{f0_mean:.0f}Hz vs 标准{ref_f0:.0f}Hz）",
                link="声带张力调节——声调高低由声带松紧程度控制，曲线不稳定可能与气息支持不足有关",
                hint="用一只手在面前画声调的走向轨迹（平/升/降升/降），边画边发音",
                practice="单字慢速重复8次，每次间隔2秒；第3次起逐步加快到正常语速，注意曲线形状不变",
            ))
    elif tone_combined < 85:
        items.append(_item(
            "warning", "tone", severity=1,
            phenomenon=f"声调基本正确，但曲线与标准{tone_name}存在轻微偏差（基频波动σ={f0_std:.0f}Hz）" if has_f0
                      else "声调评分受语音识别置信度限制，建议在安静环境重新录音以获得更精确反馈",
            link="声调起止位置——音高起点偏高或偏低会导致听感偏差",
            hint="注意声调的起始音高：阴平起高、阳平起中、上声先低、去声起高急落",
            practice="对照示范连续跟读5次，录音对比第1次与第5次的曲线差异",
        ))
    else:
        items.append(_item(
            "suggestion", "tone", severity=0,
            phenomenon="声调曲线与标准走向高度一致，表现优秀",
            link="（无需调整）",
            hint="继续保持当前声带张力控制方式",
            practice="可尝试把该声调套用到其他音节（如 ba、ta），检验迁移能力",
        ))

    # ---- 规则 2：音素级偏差（声母/韵母与目标不符，来自 Wav2Vec2） ----
    for ph in (phonemes or [])[:3]:
        if ph.get("score", 100) >= 80:
            continue
        ph_name = ph.get("phoneme", "")
        expected = ph.get("expected", "")
        detected = ph.get("detected", "")
        if ph_name == "声母":
            link = "发音部位与成阻方式——声母的差别主要在舌位/唇形/送气"
            hint = f"对照口腔动画：目标声母「{expected}」的舌位与唇形，先摆好姿态再发音"
            practice = f"发「{expected}」与「{detected}」各3遍交替，体会成阻部位差异；每遍后用手感受气流"
        elif ph_name == "韵母":
            link = "共鸣腔调节——韵母的差别在舌位高低前后与唇形圆展"
            hint = f"对照镜面观察口型：目标韵母「{expected}」的开口度与唇形"
            practice = f"「{expected}」与「{detected}」交替慢发5遍，观察下巴高度与唇形变化"
        else:
            link = "声调走向——四声的差别在音高曲线形状"
            hint = f"目标「{expected}」，检测到「{detected}」，先听示范再跟读"
            practice = "用「妈麻马骂」四声连读3轮，每轮对比曲线形状"
        items.append(_item(
            "error" if ph.get("score", 0) < 50 else "warning", "pronunciation",
            severity=2 if ph.get("score", 0) < 50 else 1,
            phenomenon=f"{ph_name}识别为「{detected}」，与目标「{expected}」不符（{ph.get('score', 0):.0f}分）",
            link=link,
            hint=hint,
            practice=practice,
        ))

    # ---- 规则 3：流利度（VAD 停顿/语速） ----
    if fluency < 60:
        items.append(_item(
            "warning", "fluency", severity=1,
            phenomenon=f"发音流畅度偏低（{fluency:.0f}分），存在明显停顿或拖音",
            link="气息控制与节奏——停顿过多通常与换气点选择不当有关",
            hint="先想好整个音节再开口，把气流均匀分配到每个音段",
            practice="慢速分解练习：先发声母、再发韵母、最后连贯；每个环节重复5次后合起来",
        ))

    # ---- 规则 4：录音质量警示（质量未达最优但不致命） ----
    if quality_warn:
        items.append(_item(
            "warning", "quality", severity=1,
            phenomenon=f"录音环境提示：{quality_warn['message']}",
            link="录音环境——噪声/距离/音量影响特征提取精度",
            hint="靠近麦克风约一拳距离，保持环境安静，避免爆音",
            practice="调整后重录一次，与本条结果对比曲线差异",
        ))

    return items


# 结果可靠性判定
def compute_reliability(
    *,
    quality_passed: bool,
    voiced_ratio: float,
    recognized: bool,
    phoneme_hits: int,
    total_targets: int,
) -> tuple[str, str]:
    """返回 (可靠性档位, 说明)
    reliable 可靠 / reference_only 仅供参考 / not_available 暂不评价
    """
    if not quality_passed:
        return "not_available", "录音质量不达标，无法可靠评价，请重录"
    if voiced_ratio < 0.3:
        return "not_available", "有效语音过少，无法可靠评价，请靠近麦克风重录"
    if not recognized or phoneme_hits < max(1, total_targets):
        return "reference_only", "声学特征有效，但语音识别置信度有限，结果仅供参考"
    return "reliable", "声学特征与识别结果一致，结果可靠"
