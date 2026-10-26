# -*- coding: utf-8 -*-
"""拼音工具:声母/韵母/声调拆分 + 字→拼音反向索引(诊断候选字集合)+ 多音字消歧。

反向索引用途: 1.0 不新训模型,把 Wav2Vec2 当声学打分器,对"目标音的候选字
集合"做 CTC 强制选择(见 dl_analyzer.py),候选字由本模块从 pypinyin 字表反查。
"""

INITIALS = (
    "zh", "ch", "sh",
    "b", "p", "m", "f", "d", "t", "n", "l",
    "g", "k", "h", "j", "q", "x",
    "r", "z", "c", "s", "y", "w",
)

_UNMARK = {
    "ā": "a", "á": "a", "ǎ": "a", "à": "a",
    "ē": "e", "é": "e", "ě": "e", "è": "e",
    "ī": "i", "í": "i", "ǐ": "i", "ì": "i",
    "ō": "o", "ó": "o", "ǒ": "o", "ò": "o",
    "ū": "u", "ú": "u", "ǔ": "u", "ù": "u",
    "ǖ": "ü", "ǘ": "ü", "ǚ": "ü", "ǜ": "ü",
}
_TONE = {
    "ā": 1, "á": 2, "ǎ": 3, "à": 4,
    "ē": 1, "é": 2, "ě": 3, "è": 4,
    "ī": 1, "í": 2, "ǐ": 3, "ì": 4,
    "ō": 1, "ó": 2, "ǒ": 3, "ò": 4,
    "ū": 1, "ú": 2, "ǔ": 3, "ù": 4,
    "ǖ": 1, "ǘ": 2, "ǚ": 3, "ǜ": 4,
}


def parse_pinyin(py: str) -> tuple[str, str, int]:
    """解析拼音为 (声母, 韵母, 声调)。声调 1-4,0 表示轻声。

    'mā' → ('m', 'a', 1);  'yū' → ('y', 'ü', 1)
    'ma3' → ('m', 'a', 3); 'ne'  → ('n', 'e', 0)
    """
    py = (py or "").strip().lower().replace("v", "ü")
    if not py:
        return "", "", 0
    tone = 0
    if py[-1] in "0123456789":
        t = int(py[-1])
        tone = t if t in (1, 2, 3, 4) else 0
        py = py[:-1]
    else:
        for ch in py:
            if ch in _TONE:
                tone = _TONE[ch]
                py = py.replace(ch, _UNMARK[ch])
                break
    for init in INITIALS:
        if py.startswith(init):
            final = py[len(init):]
            # 拼音书写规则: y/j/q/x 后的 u 实为 ü(yū=ü、jū=j+ü)
            if init in ("y", "j", "q", "x") and final == "u":
                final = "ü"
            return init, final, tone
    return "", py, tone


def strip_semivowel(initial: str, final: str) -> str:
    """y/w 在 i/u/ü 前只是拼写形式:零声母音节的声母记作 ''。

    'yī' 实际声母为空 → ('', 'i');但关卡 L28(y 的呼读音)目标声母就是 y,不调用本函数。
    """
    if initial in ("y", "w") and final in ("i", "u", "ü"):
        return ""
    return initial


def char_pinyin(ch: str) -> str:
    """单字 → 拼音(带调);多音字取默认读音。非汉字返回 ''。"""
    if not ch or not ("一" <= ch <= "鿿"):
        return ""
    from pypinyin import Style, pinyin
    try:
        r = pinyin(ch, style=Style.TONE, heteronym=False)
        return r[0][0] if r and r[0] else ""
    except Exception:
        return ""


def char_pinyin_matching(ch: str, init: str, final: str,
                         prefer_tone: int | None = None) -> str:
    """多音字读音消歧:取 ch 与目标(声母, 韵母)匹配的那条读音。

    闭集候选字可能靠任一同声韵读音入选(如 勒 lè/lēi、阿 ā/ē、司 sī/cí),
    直接用默认读音会把对的答案误判成错。匹配规则:
      1) 优先与 prefer_tone 同调的读音(严格声调关用);
      2) 未限定声调时取字典首个匹配读音(多为常用音;轻声如实报告);
      3) 无匹配读音时退默认读音。
    """
    if not ch or len(ch) != 1 or not ("一" <= ch <= "鿿"):
        return ""
    from pypinyin.pinyin_dict import pinyin_dict
    pys = pinyin_dict.get(ord(ch), "")
    matches: list[str] = []
    for py in (pys.split(",") if isinstance(pys, str) else pys):
        py = py.strip()
        if not py:
            continue
        i, f, t = parse_pinyin(py)
        si = strip_semivowel(i, f) if init == "" else i
        if (si, f) != (init, final):
            continue
        matches.append(py)
        if prefer_tone is not None and t == prefer_tone:
            return py
    # 未限定声调时取字典首个匹配读音(多为常用音;轻声如实报告,不猜声调)
    return matches[0] if matches else char_pinyin(ch)


# ---------------------------------------------------------------------------
# 反向索引: 拼音(带调) → 汉字集合; (声母, 韵母) → 汉字集合
# ---------------------------------------------------------------------------
_reverse_exact: dict[str, set[str]] | None = None
_reverse_base: dict[tuple[str, str], set[str]] | None = None


def _build_indexes() -> None:
    global _reverse_exact, _reverse_base
    from pypinyin.pinyin_dict import pinyin_dict
    exact: dict[str, set[str]] = {}
    base: dict[tuple[str, str], set[str]] = {}
    for cp, pys in pinyin_dict.items():
        # pypinyin>=0.5x 的字典键是 Unicode 码点整数,不是字符,必须转回字符
        ch = chr(cp) if isinstance(cp, int) else cp
        for py in pys.split(","):
            py = py.strip().lower()
            if not py:
                continue
            exact.setdefault(py, set()).add(ch)
            i, f, _t = parse_pinyin(py)
            base.setdefault((i, f), set()).add(ch)
    _reverse_exact, _reverse_base = exact, base


def chars_for_pinyin(py: str) -> list[str]:
    """同拼音同声调的全部汉字(如 'mǎ' → 马等)。"""
    if _reverse_exact is None:
        _build_indexes()
    return sorted(_reverse_exact.get(py.lower().strip(), set()))


def chars_for_base(initial: str, final: str) -> list[str]:
    """同声母+韵母、任意声调的全部汉字(如 ('m','a') → 妈麻马骂嘛…)。"""
    if _reverse_base is None:
        _build_indexes()
    return sorted(_reverse_base.get((initial, final), set()))
