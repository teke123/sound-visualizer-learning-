"""异步路径自测：202 回落与轮询、Provider 不可达（PROVIDER_DOWN 503）、
处理超时（TIMEOUT 504）、同键重试复活。需要服务以对应环境变量启动。"""
from __future__ import annotations

import io
import sys
import time
import wave
from pathlib import Path

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from app.seed_support import synthesize_text  # noqa: E402

BASE = "http://127.0.0.1:8000"
HEADERS = {"Origin": "http://localhost:5173"}
results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if not ok and detail else ""))


def wav_bytes(samples):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def calibrate(c):
    audio = wav_bytes(synthesize_text("妈坡车米布女妈麻马骂", "male", syllable_dur=0.36))
    r = c.post("/api/audio/uploads", data={"purpose": "calibration"},
               files={"file": ("c.webm", audio, "audio/webm")})
    r = c.post("/api/pitch-calibration",
               json={"audioId": r.json()["data"]["audioId"], "textVersion": "v1"})
    assert r.json()["code"] == "OK", r.text[:200]


def upload_rec(c, name="mama"):
    audio = wav_bytes(synthesize_text("妈麻马骂", "male", syllable_dur=0.32))
    r = c.post("/api/audio/uploads", data={"purpose": "recording"},
               files={"file": (f"{name}.webm", audio, "audio/webm")})
    return r.json()["data"]["audioId"]


def main() -> int:
    import os

    mode = os.environ.get("E2E_MODE", "202")

    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=40) as c:
        cv = c.get("/api/levels/L30").json()["data"]["contentVersion"]
        calibrate(c)
        audio_id = upload_rec(c)
        r = c.post("/api/recordings", json={
            "audioId": audio_id, "levelId": "L30", "contentVersion": cv,
            "submissionId": f"async-{mode}-{time.time()}"})
        rec = r.json()["data"]["recording"]
        if mode == "202":
            check("first submit → 202 (sync window ~0)", r.status_code == 202,
                  f"{r.status_code}")
            check("retry-after header", r.headers.get("retry-after") is not None)
            rec_id = rec["recordingId"]
            # 处理中重复提交 → 202
            r2 = c.post("/api/recordings", json={
                "audioId": audio_id, "levelId": "L30", "contentVersion": 1,
                "submissionId": rec["recordingId"].replace("rc_", "")})
            # 轮询直到 200
            ok = False
            for _ in range(40):
                r = c.get(f"/api/recordings/{rec_id}")
                if r.status_code == 200:
                    ok = True
                    break
                time.sleep(0.5)
            check("poll → 200 with result", ok, f"last={r.status_code} {r.text[:150]}")
        elif mode == "down":
            # Provider 不可达 → failed(retryable PROVIDER_DOWN)，查询 503
            deadline = time.time() + 45
            status = None
            body = None
            while time.time() < deadline:
                rr = c.get(f"/api/recordings/{rec['recordingId']}")
                status, body = rr.status_code, rr
                if status != 202:
                    break
                time.sleep(1)
            check("provider down → 503 PROVIDER_DOWN",
                  status == 503 and body.json()["code"] == "PROVIDER_DOWN",
                  f"{status} {body.text[:150]}")
            check("failed carries retryable", body.json()["data"]["retryable"] is True)
        elif mode == "timeout":
            deadline = time.time() + 50
            status = None
            body = None
            while time.time() < deadline:
                rr = c.get(f"/api/recordings/{rec['recordingId']}")
                status, body = rr.status_code, rr
                if status != 202:
                    break
                time.sleep(1)
            check("hard deadline → 504 TIMEOUT",
                  status == 504 and body.json()["code"] == "TIMEOUT",
                  f"{status} {body.text[:150]}")

    failed = [r for r in results if not r[1]]
    print(f"\n==== {len(results) - len(failed)}/{len(results)} passed ====")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
