# -*- coding: utf-8 -*-
"""发音诊断 API(1.0)。

GET  /api/asr/status    模型与推理状态(加载耗时 / 设备 / 是否可对外演示)
POST /api/asr/load      模型加载(懒加载入口;model_id/force 参数供 2.0 CON-08 模型对比)
POST /api/asr/diagnose  音频 + 关卡 → 结构化发音诊断(误读 / 漏读 / 声调错位)
GET  /api/levels        冻结的 L01-L30 关卡清单

每次诊断自动落盘 experiment_log.jsonl + 音频副本,形成可复现实验记录。
"""
from __future__ import annotations

import datetime
import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.asr_analyzer import DEFAULT_MODEL_ID, get_analyzer
from backend.dl_analyzer import diagnose
from backend.levels import FROZEN_SINCE, LEVELS

EXP_DIR = ROOT / "experiments"
EXP_AUDIO_DIR = EXP_DIR / "audio"
EXP_LOG = EXP_DIR / "experiment_log.jsonl"
for d in (EXP_DIR, EXP_AUDIO_DIR):
    d.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="1.0 发音诊断 ASR API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/asr/status")
def asr_status():
    return {"service": "asr", "version": "1.0", **get_analyzer().status()}


@app.post("/api/asr/load")
def asr_load(payload: dict):
    """body: {"model_id": 可选, "force": 可选}。返回加载耗时(汇报用)。"""
    model_id = payload.get("model_id") or DEFAULT_MODEL_ID
    force = bool(payload.get("force", False))
    t0 = time.perf_counter()
    result = get_analyzer().load(model_id=model_id, force=force)
    result["api_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return result


@app.post("/api/asr/diagnose")
def asr_diagnose(file: UploadFile = File(...),
                 level_id: str = Form(""),
                 target_pinyin: str = Form("")):
    """form-data: file=音频, level_id=Lxx(或 target_pinyin=mǎ)。"""
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    name = f"{datetime.datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}{suffix}"
    save_path = EXP_AUDIO_DIR / name
    save_path.write_bytes(file.file.read())
    t0 = time.perf_counter()
    result = diagnose(str(save_path), level_id=level_id or None,
                      target_pinyin=target_pinyin or None)
    result["api_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    record = {
        "ts": datetime.datetime.now().isoformat(timespec="milliseconds"),
        "model_id": get_analyzer().model_id,
        "audio": name, "level_id": result.get("level_id"),
        "target_pinyin": result.get("target_pinyin"),
        "verdict": result["verdict"]["code"],
        "detected": result.get("detected"),
        "api_ms": result["api_ms"],
    }
    with open(EXP_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return result


@app.get("/api/levels")
def levels():
    return {"frozen_since": FROZEN_SINCE, "count": len(LEVELS),
            "levels": [lv.__dict__ for lv in LEVELS]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
