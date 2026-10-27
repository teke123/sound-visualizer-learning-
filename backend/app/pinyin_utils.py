"""拼音文本工具（纯函数，无 app 内依赖）：带调拼音标注解析、声母/韵母拆分、
主元音提取。供评分（期望声调/试题构造）、标定（元音归属）与内容搜索共用。

评测文本的读音与声调一律以关卡内容携带的拼音标注为准（讯飞试题用同一标注
构造 interphonic 格式，期望声调回填同源），不做文本侧推断。
"""
from __future__ import annotations

import re

# 带调拼音标注项：无声调拼音（ü 可写作 v/u:）+ 1 位调号（讯飞口径 0-9，
# 其中 0/5-9 均代表轻声），如 na4、nv3、zhi1
_ANNOTATED_PINYIN = re.compile(r"[a-zv:ü]+[0-9]", re.IGNORECASE)

_PINYIN_SEPARATORS = re.compile(r"[|，,\s]+")


def annotated_syllables(text: str, pinyin: str) -> list[dict]:
    """评测文本 + 带调拼音标注 → 音节序列（文本/带调拼音/无声调拼音/声调）。

    拼音以竖线、逗号或空白分隔，个数必须与文本汉字个数一致，每项必须带
    1 位调号，否则抛 ValueError（调用方用于内容校验，不静默兜底）。
    """
    chars = [ch for ch in (text or "") if "\u4e00" <= ch <= "\u9fff"]
    if not chars:
        raise ValueError("评测文本不含汉字")
    pys = [p for p in _PINYIN_SEPARATORS.split((pinyin or "").strip()) if p]
    if len(pys) != len(chars):
        raise ValueError(f"拼音标注数（{len(pys)}）与汉字数（{len(chars)}）不一致")
    out: list[dict] = []
    for ch, py in zip(chars, pys):
        if not _ANNOTATED_PINYIN.fullmatch(py):
            raise ValueError(f"拼音标注格式非法：{py!r}（应为无声调拼音+1位调号，如 na4）")
        py = py.lower()
        tone = int(py[-1])
        out.append({"text": ch, "pinyin": py, "plain": py[:-1], "tone": tone})
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
    p = pinyin_plain.strip().lower().replace("u:", "ü").replace("v", "ü")
    # yu / yue / yuan / yun 在汉语拼音中省略了 ü 的两点，主元音实为 ü（韵母 ü 关与标定用）
    if p in ("yu", "yue", "yuan", "yun", "ju", "jue", "juan", "jun",
             "qu", "que", "quan", "qun", "xu", "xue", "xuan", "xun"):
        return "ü"
    for ch in ("a", "o", "e", "i", "u", "ü"):
        if ch in p:
            return ch
    return default
