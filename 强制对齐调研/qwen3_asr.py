# -*- coding: utf-8 -*-
"""
Qwen3-ASR 调用脚本 —— 强制对齐调研（甲任务）

通过 HuggingFace 空间 Qwen/Qwen3-ASR 的 /transcribe 接口，
返回转写文本 + 时间戳 JSON，用于与讯飞评测对比。

用法：
    python qwen3_asr.py <音频路径> [语言]
    语言默认 Chinese（可选 Auto / Chinese / Cantonese / ...）
"""
import json
import sys

from gradio_client import Client


def transcribe(audio_path: str, lang: str = "Chinese", return_ts: bool = True) -> dict:
    c = Client("Qwen/Qwen3-ASR")
    result = c.predict(audio_path, lang, return_ts, api_name="/transcribe")
    return {
        "detected_language": result[0],
        "transcription_result": result[1],
        "timestamps_json": result[2],
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python qwen3_asr.py <音频路径> [语言]")
        return 1
    audio = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else "Chinese"

    r = transcribe(audio, lang)
    print(json.dumps(r, ensure_ascii=False, indent=2))

    out = audio.rsplit(".", 1)[0] + "_qwen.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    print("\n[已保存] " + out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
