"""拼音文本工具（纯函数，无 app 内依赖）：评测文本音节化、声母/韵母拆分、
主元音提取、语料库音节文件名归一。供内容搜索、评分标定与 Mock Provider 共用。"""
from __future__ import annotations

import re

# 单字呼读音/教学定音覆盖表：修正 pypinyin 在单字脱离词境时的多音字歧义
# 例如：L01「啊」作阴平示范 a1；L10「佛」声母 f 呼读音 fo2（pypinyin 默认 fu2）；
# L11「得」声母 d 呼读音 de2；L14「勒」四声示范 le4（pypinyin 默认 lei1）
_CHAR_PINYIN_OVERRIDES: dict[str, str] = {
    "啊": "a1",
    "噢": "o1",
    "喔": "o1",
    "鹅": "e2",
    "一": "yi1",
    "衣": "yi1",
    "医": "yi1",
    "乌": "wu1",
    "迂": "yu1",
    "鱼": "yu2",
    "五": "wu3",
    "波": "bo1",
    "坡": "po1",
    "摸": "mo1",
    "佛": "fo2",
    "得": "de2",
    "特": "te4",
    "讷": "ne4",
    "勒": "le4",
    "哥": "ge1",
    "科": "ke1",
    "喝": "he1",
    "鸡": "ji1",
    "机": "ji1",
    "七": "qi1",
    "妻": "qi1",
    "西": "xi1",
    "知": "zhi1",
    "吃": "chi1",
    "诗": "shi1",
    "日": "ri4",
    "资": "zi1",
    "次": "ci4",
    "思": "si1",
}

# 单韵母裸符号 → 语料库标准音节文件名词干（一声）
_BARE_VOWEL_TO_SYLLABLE: dict[str, tuple[str, str, int]] = {
    "a": ("啊", "a1", 1),
    "ā": ("啊", "a1", 1),
    "o": ("噢", "o1", 1),
    "ō": ("噢", "o1", 1),
    "e": ("鹅", "e1", 1),
    "ē": ("鹅", "e1", 1),
    "é": ("鹅", "e2", 2),
    "i": ("衣", "yi1", 1),
    "ī": ("衣", "yi1", 1),
    "u": ("乌", "wu1", 1),
    "ū": ("乌", "wu1", 1),
    "ü": ("迂", "yu1", 1),
    "ǖ": ("迂", "yu1", 1),
    "v": ("迂", "yu1", 1),
}


def expected_syllables(text: str) -> list[dict]:
    """评测文本 → 音节序列（文本/带调拼音/无声调拼音/声调/语料库词干）。

    1. 自动剔除括号内注释（如「啊（平稳延长）」→「啊」）；
    2. 含汉字时逐字转拼音（优先查教学定音表 `_CHAR_PINYIN_OVERRIDES`，再退回 pypinyin）；
    3. 不含汉字但为单韵母符号（如听辨题 stimulusText='a'/'ü'）时映射为对应一声标准音节。
    """
    from pypinyin import Style, pinyin

    cleaned = re.sub(r"（[^）]*）|\([^)]*\)", "", text or "").strip()
    out: list[dict] = []
    for ch in cleaned:
        if not ("一" <= ch <= "鿿"):
            continue
        py = _CHAR_PINYIN_OVERRIDES.get(ch)
        if not py:
            py = pinyin(ch, style=Style.TONE3, heteronym=False)[0][0]
        tone = None
        for c in py:
            if c.isdigit():
                tone = int(c)
                break
        if tone is None:
            tone = 1
            py = f"{py}1"
        plain = "".join(c for c in py if not c.isdigit())
        stem = corpus_stem_of(plain, tone)
        out.append({"text": ch, "pinyin": py, "plain": plain, "tone": tone, "stem": stem})

    if not out and cleaned in _BARE_VOWEL_TO_SYLLABLE:
        ch, py, tone = _BARE_VOWEL_TO_SYLLABLE[cleaned]
        plain = "".join(c for c in py if not c.isdigit())
        out.append({
            "text": ch, "pinyin": py, "plain": plain,
            "tone": tone, "stem": corpus_stem_of(plain, tone),
        })
    return out


def corpus_stem_of(plain: str, tone: int | None = 1) -> str:
    """无声调拼音 + 声调号 → 语料库文件名词干（如 'ü'/'yu'→'yu1', 'nü'→'nv3'）。"""
    t = tone if tone in (1, 2, 3, 4) else 1
    p = plain.strip().lower().replace("u:", "v")
    if p in ("i",):
        p = "yi"
    elif p in ("u",):
        p = "wu"
    elif p in ("ü", "v"):
        p = "yu"
    else:
        # n/l 后接 ü 在语料库中记为 nv / lv / nve / lve
        p = p.replace("ü", "v")
    return f"{p}{t}"


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
