"""拼音文本工具（纯函数，无 app 内依赖）：评测文本音节化、声母/韵母拆分、
主元音提取。供内容搜索、评分标定、种子合成与 Mock Provider 共用。"""
from __future__ import annotations


def expected_syllables(text: str) -> list[dict]:
    """评测文本 → 音节序列（文本/带调拼音/无声调拼音/声调）。用 pypinyin。"""
    from pypinyin import Style, pinyin

    out = []
    for ch in text:
        if not ("\u4e00" <= ch <= "\u9fff"):
            continue
        py = pinyin(ch, style=Style.TONE3, heteronym=False)[0][0]
        tone = None
        for c in py:
            if c.isdigit():
                tone = int(c)
                break
        plain = "".join(c for c in py if not c.isdigit())
        out.append({"text": ch, "pinyin": py, "plain": plain, "tone": tone})
    return out


def split_pinyin(s: str) -> tuple[str, str]:
    """无声调拼音 → (声母, 韵母)；无声母时声母为空串。"""
    initials = ["zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l",
                "g", "k", "h", "j", "q", "x", "r", "z", "c", "s", "y", "w"]
    for ini in initials:
        if s.startswith(ini) and len(s) > len(ini):
            return ini, s[len(ini):]
    return "", s


def main_vowel(pinyin_plain: str, default: str | None = None) -> str | None:
    """无声调拼音（或韵母）→ 主元音（六个单韵母口径）；无命中返回 default。"""
    v = pinyin_plain.replace("v", "ü")
    for ch in ("a", "o", "e", "i", "u", "ü"):
        if ch in v:
            return ch
    return default
