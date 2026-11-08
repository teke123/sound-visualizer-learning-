# -*- coding: utf-8 -*-
"""
讯飞语音评测（ISE）API 调用脚本 —— 强制对齐调研（甲任务）

用途：把音频（16k 16bit 单声道 wav）送入讯飞语音评测，解析音素级起止时间与发音错误信息。
返回结果中的 <phone> 节点 beg_pos/end_pos 即音素起止时间（每帧 10ms）。

用法：
    python xfyun_ise.py <wav路径> <标准文本> [category]
    category 默认 read_sentence（可选 read_word / read_syllable）
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import wave
from datetime import datetime
from urllib.parse import urlencode

import websocket

APP_ID = "32bb20c7"
API_KEY = "58a621b2ed7abc3359bd73e75d814bc7"
API_SECRET = "YWQzNjc3MGE1MTE1OTQ3YjcxNTY4Mjc3"

HOST = "ise-api.xfyun.cn"
PATH = "/v2/open-ise"
URL = "wss://" + HOST + PATH


def build_auth_url() -> str:
    """HMAC-SHA256 签名，构造带鉴权的 WebSocket URL"""
    date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    signature_origin = f"host: {HOST}\ndate: {date}\nGET {PATH} HTTP/1.1"
    signature_sha = hmac.new(
        API_SECRET.encode(), signature_origin.encode(), digestmod=hashlib.sha256
    ).digest()
    signature = base64.b64encode(signature_sha).decode()
    authorization_origin = (
        f'api_key="{API_KEY}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode()).decode()
    params = {"authorization": authorization, "date": date, "host": HOST}
    return URL + "?" + urlencode(params)


def read_pcm(wav_path: str) -> bytes:
    """读取 wav，返回 16k 16bit 单声道 PCM bytes"""
    with wave.open(wav_path, "rb") as w:
        assert w.getnchannels() == 1, "需要单声道 wav"
        assert w.getsampwidth() == 2, "需要 16bit 采样"
        assert w.getframerate() == 16000, f"需要 16000 采样率，当前 {w.getframerate()}"
        return w.readframes(w.getnframes())


def parse_phones(xml: str) -> list:
    """从评测返回的 XML 中提取音素级起止时间"""
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml)
    phones = []
    for p in root.iter("phone"):
        rec_type = p.get("rec_node_type", "")
        if rec_type in ("fil", "sil"):
            continue  # 跳过噪音/静音
        phones.append({
            "content": p.get("content", ""),
            "start_ms": int(p.get("beg_pos", 0)) * 10,
            "end_ms": int(p.get("end_pos", 0)) * 10,
            "perr_msg": p.get("perr_msg", ""),
            "dp_message": p.get("dp_message", ""),
        })
    return phones


def evaluate(wav_path: str, text: str, category: str = "read_sentence") -> dict:
    """送音频到讯飞评测，返回结构化结果"""
    ws = websocket.create_connection(build_auth_url(), timeout=30)

    # 第一帧：参数（cmd=ssb）
    business = {
        "sub": "ise",
        "ent": "cn_vip",
        "category": category,
        "cmd": "ssb",
        "text": "\uFEFF" + text,
        "tte": "utf-8",
        "ttp_skip": True,
        "aue": "raw",
        "auf": "audio/L16;rate=16000",
    }
    ws.send(json.dumps({
        "common": {"app_id": APP_ID},
        "business": business,
        "data": {"status": 0},
    }))

    # 音频帧（cmd=auw，每帧 1280 字节 = 40ms）
    pcm = read_pcm(wav_path)
    chunk = 1280
    for i in range(0, len(pcm), chunk):
        part = pcm[i:i + chunk]
        # business.aus: 1 首音频帧 / 2 中间帧 / 4 最后帧
        aus = 1 if i == 0 else (4 if i + chunk >= len(pcm) else 2)
        # data.status: 1 中间帧 / 2 最后帧（首帧参数已用 0）
        data_status = 2 if (i + chunk >= len(pcm)) else 1
        ws.send(json.dumps({
            "business": {
                "cmd": "auw", "aus": aus, "aue": "raw",
                "auf": "audio/L16;rate=16000",
            },
            "data": {"status": data_status, "data": base64.b64encode(part).decode()},
        }))

    # 收结果
    raws = []
    final = None
    while True:
        try:
            msg = ws.recv()
        except Exception:
            break
        if not msg:
            break
        resp = json.loads(msg)
        raws.append(resp)
        d = resp.get("data", {})
        if d.get("status") == 2:
            final = resp
            break

    ws.close()

    result = {"raw": raws}
    if final:
        b64 = final.get("data", {}).get("data")
        if b64:
            raw = base64.b64decode(b64)
            try:
                xml = raw.decode("utf-8")
            except UnicodeDecodeError:
                xml = raw.decode("gbk", errors="replace")
            result["xml"] = xml
            result["phones"] = parse_phones(xml)
    return result


def main() -> int:
    if len(sys.argv) < 3:
        print("用法: python xfyun_ise.py <wav路径> <标准文本> [category]")
        return 1
    wav_path = sys.argv[1]
    text = sys.argv[2]
    category = sys.argv[3] if len(sys.argv) > 3 else "read_sentence"

    result = evaluate(wav_path, text, category)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 保存响应到文件（交付物）
    out_name = os.path.splitext(os.path.basename(wav_path))[0] + "_xfyun.json"
    with open(out_name, "w", encoding="utf-8") as f:
        json.dump({"wav": wav_path, "text": text, "category": category, "result": result},
                  f, ensure_ascii=False, indent=2)
    print("\n[已保存] %s" % out_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
