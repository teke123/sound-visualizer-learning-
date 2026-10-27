"""异步路径自测：202 回落与轮询、Provider 不可达（PROVIDER_DOWN 503）、
处理超时（TIMEOUT 504）、同键重试复活。三种模式各自要求服务按对应
环境变量启动（backend 目录下）：

- E2E_MODE=202（默认）：SVS_PROVIDER=mock SVS_SYNC_WINDOW=0 py -3 main.py。
  首提应立即回落 202、轮询最终 200。评分缓存键含用户，新注册用户
  必为冷缓存，无需清库。
- E2E_MODE=down：SVS_PROVIDER=mock SVS_MOCK_PROVIDER=fail py -3 main.py
  （mock 模拟不可达；标定不依赖 provider 结果，不受影响）。
- E2E_MODE=timeout：SVS_PROVIDER=mock SVS_MOCK_PROVIDER=slow
  SVS_MOCK_SLOW_SEC=40 py -3 main.py（slow 须大于 SVS_HARD_DEADLINE 默认 30，
  触发 504 TIMEOUT；标定路由等待上限已解耦为 SVS_CALIBRATION_TIMEOUT
  默认 45，slow 40 时标定可在窗口内完成）。全程约 100 秒；另断言迟到的
  管线收尾不会把已判 TIMEOUT 的录音复活成 completed。
  注：Provider 默认已是讯飞，跑本测试必须显式 SVS_PROVIDER=mock，
  否则故障注入变量无效且会消耗真实 API 配额。
"""
from __future__ import annotations

import io
import sys
import time
import wave
from pathlib import Path

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from app import config  # noqa: E402
from app.acoustics import transcode  # noqa: E402

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


def login(c):
    username = f"async用户_{int(time.time()*1000)}"
    r = c.post("/api/auth/register", json={"username": username, "password": "password123"})
    assert r.status_code == 200, r.text[:200]
    r = c.post("/api/auth/login", json={"username": username, "password": "password123"})
    assert r.status_code == 200, r.text[:200]


def upload_rec(c, name="mama"):
    corpus = config.CORPUS_DIR
    if corpus is None or not corpus.is_dir():
        raise RuntimeError("请先在 .env 或环境变量配置 CORPUS_DIR")
    stem = "ma1"
    src = corpus / "MV1" / f"{stem}_MV1.wav"
    tmp = config.DATA_DIR / "tmp_async.wav"
    transcode.normalize_to_wav(src, tmp)
    audio = wav_bytes(transcode.read_pcm_samples(tmp))
    tmp.unlink(missing_ok=True)
    r = c.post("/api/audio/uploads", data={"purpose": "recording"},
               files={"file": (f"{name}.webm", audio, "audio/webm")})
    return r.json()["data"]["audioId"]


def main() -> int:
    import os

    mode = os.environ.get("E2E_MODE", "202")

    # 60s：timeout 模式下标定本身要走完 slow 40s + 分析，40s 客户端超时会先到
    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=60) as c:
        login(c)
        audio_id = upload_rec(c)
        r = c.post("/api/recordings", json={
            "audioId": audio_id, "levelId": "L30",
            "submissionId": f"async-{mode}-{time.time()}"})
        rec = r.json()["data"]["recording"]
        if mode == "202":
            check("first submit → 202 (sync window ~0)", r.status_code == 202,
                  f"{r.status_code}")
            check("retry-after header", r.headers.get("retry-after") is not None)
            rec_id = rec["recordingId"]
            # 处理中重复提交（不同 submissionId）→ 202
            r2 = c.post("/api/recordings", json={
                "audioId": audio_id, "levelId": "L30",
                "submissionId": f"async-dup-{mode}-{time.time()}"})
            check("duplicate submit while processing → 202",
                  r2.status_code == 202, f"{r2.status_code} {r2.text[:150]}")
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
            # 管线睡过截止仍会醒来收尾（slow 40s + 分析约 2s）：多等一会
            # 再查，迟到的完成不得复活已判死的录音
            time.sleep(15)
            rr = c.get(f"/api/recordings/{rec['recordingId']}")
            check("late pipeline cannot resurrect TIMEOUT",
                  rr.status_code == 504 and rr.json()["code"] == "TIMEOUT",
                  f"{rr.status_code} {rr.text[:150]}")

    failed = [r for r in results if not r[1]]
    print(f"\n==== {len(results) - len(failed)}/{len(results)} passed ====")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
