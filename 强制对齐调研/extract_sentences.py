# -*- coding: utf-8 -*-
"""提取浓重口音语料库的所有短句，生成候选清单 + 说话人统计"""
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

BASE = "A_CHINESE_STRONG_MANDARIN_ACCENT_CONVERSATIONAL_SPEECH_CORPUS/Mandarin_Heavy_Accent_Conversational_Speech_Corpus"

sentences = []
for f in sorted(os.listdir(BASE)):
    if not f.endswith(".txt"):
        continue
    with open(os.path.join(BASE, f), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            m = re.match(r"\[([\d.]+),([\d.]+)\]", parts[0])
            if not m:
                continue
            start, end = float(m.group(1)), float(m.group(2))
            speaker = parts[1].strip()
            gender = parts[2].strip()
            text = parts[3].strip()
            if speaker in ("0", "none", "") or not text:
                continue
            if text.startswith("[") and text.endswith("]"):
                continue
            dur = end - start
            if dur < 0.8 or dur > 10:
                continue
            sentences.append((f, speaker, gender, start, end, dur, text))

sentences.sort(key=lambda x: (x[0], x[3]))

# 写 UTF-8 清单文件
lines = ["共提取 %d 句（0.8~10 秒）" % len(sentences), "=" * 80]
for f, speaker, gender, start, end, dur, text in sentences:
    lines.append("[%.1fs] %s(%s) %.1f-%.1f  %s" % (dur, speaker, gender, start, end, text))
with open("候选句子清单.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")

# 说话人统计
sp = Counter(s[1] for s in sentences)
gd = {}
for s in sentences:
    gd[s[1]] = s[2]
print("共提取 %d 句" % len(sentences))
print("说话人分布：")
for k, v in sorted(sp.items()):
    print("  %s (%s) : %d 句" % (k, gd[k], v))
