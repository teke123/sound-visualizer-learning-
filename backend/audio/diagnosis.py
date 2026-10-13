"""上传诊断流程：保存实验音频、调用诊断并记录 JSONL 结果。"""
from datetime import datetime
import json
from pathlib import Path
import time
from uuid import uuid4

from ..dl_analyzer import diagnose

EXPERIMENT_DIR = Path(__file__).resolve().parents[2] / "experiments"


def diagnose_upload(
    content: bytes,
    filename: str | None,
    level_id: str | None,
    target_pinyin: str | None,
) -> dict:
    """保存上传音频，返回诊断结果并追加实验记录。"""
    audio_dir = EXPERIMENT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename or "audio.wav").suffix or ".wav"
    name = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}{suffix}"
    audio_path = audio_dir / name
    audio_path.write_bytes(content)

    started_at = time.perf_counter()
    result = diagnose(str(audio_path), level_id=level_id, target_pinyin=target_pinyin)
    result["api_ms"] = round((time.perf_counter() - started_at) * 1000, 1)

    record = {
        "ts": datetime.now().isoformat(timespec="milliseconds"),
        "model_id": result["model_id"],
        "audio": name,
        "level_id": result.get("level_id"),
        "target_pinyin": result.get("target_pinyin"),
        "verdict": result["verdict"]["code"],
        "detected": result.get("detected"),
        "api_ms": result["api_ms"],
    }
    with (EXPERIMENT_DIR / "experiment_log.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(record, ensure_ascii=False) + "\n")
    return result
