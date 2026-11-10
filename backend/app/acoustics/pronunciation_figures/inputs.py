"""产品评分结果转换为音素对齐；时间单位仅在边界处转换。"""
from pathlib import Path

from app.acoustics.imagery.common import Alignment, PhoneSeg, SyllableSeg


def alignment_from_provider(provider, wav_path, duration: float) -> Alignment:
    syllables = []
    for s in provider.syllables:
        phones = []
        if s.detail.get("dpMessage", 0) != 0:
            raise ValueError("音节对齐包含漏读、增读或替换")
        for p in s.detail.get("phones", []):
            if p.get("dpMessage", 0) != 0:
                raise ValueError("音素对齐包含朗读检错")
            if p.get("begPos") is None or p.get("endPos") is None:
                raise ValueError("评分结果缺少音素时间戳")
            if p.get("part") in {"initial", "final"} and p["endPos"] > p["begPos"]:
                phones.append(PhoneSeg(p["content"], p["part"], p["begPos"] / 100.0, p["endPos"] / 100.0))
        symbol = s.pinyin or ""
        if s.tone_value is not None:
            symbol = symbol.rstrip("0123456789") + str(s.tone_value)
        syllables.append(SyllableSeg(s.text, symbol, s.t0, s.t1, phones))
    return Alignment(Path(wav_path).name, "learner", duration, syllables)
