# -*- coding: utf-8 -*-
"""批量切片候选句子，生成试听 wav 文件"""
import os
import re
import subprocess
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

BASE = "A_CHINESE_STRONG_MANDARIN_ACCENT_CONVERSATIONAL_SPEECH_CORPUS/Mandarin_Heavy_Accent_Conversational_Speech_Corpus"
FFMPEG = r"D:\Python314\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v9.0.2.exe"
OUT = "试听片段"
os.makedirs(OUT, exist_ok=True)

# 口癖/语气词开头，干扰评测，跳过
SKIP_START = ("哎", "嗯", "啊", "哦", "呃", "对", "对对", "呀", "嗯嗯")

candidates = defaultdict(list)
for f in sorted(os.listdir(BASE)):
    if not f.endswith(".txt"):
        continue
    wav = os.path.join(BASE, f.replace(".txt", ".wav"))
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
            # 筛选条件：2~6 秒，文本 5~20 字，无口癖开头
            if not (2 <= dur <= 6):
                continue
            if not (5 <= len(text) <= 20):
                continue
            if text.startswith(SKIP_START):
                continue
            candidates[speaker].append((wav, speaker, gender, start, end, text))

# 每个说话人挑 8 句
count = 0
for speaker in sorted(candidates):
    for wav, sp, gd, start, end, text in candidates[speaker][:8]:
        count += 1
        safe = re.sub(r"[^\w\u4e00-\u9fff]+", "", text)[:12]
        out = os.path.join(OUT, f"{sp}_{gd}_{count:02d}_{safe}.wav")
        subprocess.run(
            [FFMPEG, "-y", "-ss", str(start), "-to", str(end), "-i", wav,
             "-acodec", "pcm_s16le", out],
            capture_output=True,
        )

print(f"已切出 {count} 个试听片段到「{OUT}」文件夹")
