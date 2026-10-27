"""端到端闭环自测（直接运行：python e2e_test.py）。

覆盖：健康 / 关卡与搜索 / 注册登录主流程（未标定直接检测→标定后再检测）/
幂等与冲突 / 档案 / 录音派生进度 / 删除与清空 / 注销 /
admin（开放切换 / 内容保存即生效 / 反馈处理）。

所有请求带 Origin 头（CSRF 校验）；媒体语义直接断言 HTTP 状态与头。
"""
from __future__ import annotations

import io
import re
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
ORIGIN = "http://localhost:5173"
HEADERS = {"Origin": ORIGIN}

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not ok else ""))


def wav_bytes(samples: np.ndarray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def silence_bytes(seconds: float = 2.0) -> bytes:
    n = int(16000 * seconds)
    return wav_bytes(np.zeros(n, dtype=np.float32) + np.random.default_rng(1).standard_normal(n) * 1e-4)


def corpus_wav_bytes(pinyin: str, speaker: str = "MV1") -> bytes:
    """按带调拼音标注逐项定位语料库录音并拼接为 16kHz 单声道 WAV 字节。"""
    corpus = config.CORPUS_DIR
    if corpus is None or not corpus.is_dir():
        raise RuntimeError("请先在 .env 或环境变量配置 CORPUS_DIR")
    stems = [s for s in re.split(r"[|，,\s]+", pinyin.strip()) if s]
    chunks: list[np.ndarray] = []
    gap = np.zeros(int(0.08 * 16000), dtype=np.float32)
    tmp_dir = config.DATA_DIR / "tmp_e2e"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for idx, stem in enumerate(stems):
        src = corpus / speaker / f"{stem}_{speaker}.wav"
        dst = tmp_dir / f"{speaker}_{stem}_{idx}.wav"
        transcode.normalize_to_wav(src, dst)
        chunks.append(transcode.read_pcm_samples(dst))
        dst.unlink(missing_ok=True)
        if idx + 1 < len(stems):
            chunks.append(gap)
    return wav_bytes(np.concatenate(chunks) if chunks else np.zeros(16000, dtype=np.float32))


def main() -> int:
    rec_audio = corpus_wav_bytes("ma1", "MV1")
    r2_audio = corpus_wav_bytes("ma1", "FV1")
    cal_audio = corpus_wav_bytes("ma1|po1|che1|mi3|bu4|nv3|ma1|ma2|ma3|ma4", "MV1")

    # 1 健康与内容（公开）
    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=40) as c:
        r = c.get("/api/health")
        check("health", r.status_code == 200 and r.json()["status"] == "ok")

        r = c.get("/api/levels")
        d = r.json()["data"]
        check("levels all open", len(d["levels"]) >= 30, f"got {len(d['levels'])}")
        check("confusablePairs non-empty", len(d["confusablePairs"]) >= 5)
        l30 = next(l for l in d["levels"] if l["id"] == "L30")
        check("L30 availability open", l30["availability"] == "open")

        r = c.get("/api/levels/L30")
        d30 = r.json()["data"]
        check("L30 detail quizzes>=1", len(d30["quizzes"]) >= 1)
        check("L30 nav prev L29", d30["nav"]["prev"] == "L29")
        check("L30 detection promptText", bool(d30["detection"]["promptText"]))

        r = c.get("/api/search", params={"q": "妈"})
        check("search 妈 → L30 first", r.json()["data"]["results"][0]["id"] == "L30")
        r = c.get("/api/search", params={"q": "翘舌"})
        ids = [x["id"] for x in r.json()["data"]["results"]]
        check("search 翘舌 → zh/ch/sh", any(i in ids for i in ("L21", "L22", "L23")), str(ids))

        # 媒体：公开示范可读 + ETag/304
        demo_media = l30["demoMediaId"]
        r = c.get(f"/api/media/{demo_media}")
        check("public media 200 wav", r.status_code == 200 and "audio" in r.headers.get("content-type", ""))
        etag = r.headers.get("ETag")
        r2 = c.get(f"/api/media/{demo_media}", headers={"If-None-Match": etag})
        check("media 304", r2.status_code == 304)
        r3 = c.get(f"/api/media/{demo_media}", headers={"Range": "bytes=0-99"})
        check("media range 206", r3.status_code == 206 and len(r3.content) == 100)

        # 2 未登录：检测/档案接口 401
        r = c.get("/api/me/context")
        ctx = r.json()["data"]
        check("guest context unauthenticated", ctx["authenticated"] is False)
        check("guest nextLevelId L01", ctx["nextLevelId"] == "L01")
        r = c.post("/api/audio/uploads", data={"purpose": "recording"},
                   files={"file": ("g.webm", rec_audio, "audio/webm")})
        check("upload without login → 401", r.status_code == 401)
        r = c.post("/api/recordings", json={
            "audioId": "au_x", "levelId": "L30", "submissionId": "g-1"})
        check("submit without login → 401", r.status_code == 401)
        r = c.get("/api/me/recordings")
        check("me/recordings without login → 401", r.status_code == 401)

    # 3 注册登录主流程
    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=60) as c:
        username = f"e2e用户_{int(time.time())}"
        r = c.post("/api/auth/register", json={"username": username, "password": "password123"})
        check("register", r.status_code == 200, r.text[:150])
        r = c.post("/api/auth/login", json={"username": username, "password": "password123"})
        check("login", r.status_code == 200 and r.json()["data"]["context"]["authenticated"])
        r = c.get("/api/me/context")
        ctx = r.json()["data"]
        check("context authenticated, calibration none",
              ctx["authenticated"] and ctx["calibration"]["status"] == "none")

        # 4 未标定直接提交（D-20：正常受理，不 409）
        r = c.post("/api/audio/uploads", data={"purpose": "recording"},
                   files={"file": ("rec.webm", rec_audio, "audio/webm")})
        check("upload recording audio", r.status_code == 200, r.text[:200])
        audio_id = r.json()["data"]["audioId"]
        r = c.post("/api/recordings", json={
            "audioId": audio_id, "levelId": "L30", "submissionId": "e2e-sub-1"})
        body = r.json()
        check("submit without calibration → 200 with result",
              r.status_code == 200 and body["data"].get("result"),
              f"{r.status_code} {r.text[:300]}")
        result = body["data"]["result"]
        check("result curve ok >=1 segments",
              result["curve"]["status"] == "ok" and len(result["curve"]["segments"]) >= 1,
              str(result["curve"])[:200])
        check("result fourSteps wordingSource",
              all(s["wordingSource"] == "rule_template" for s in result.get("fourSteps", [])))
        rec_id = body["data"]["recording"]["recordingId"]

        # 幂等重放：同 submissionId 同负载
        r = c.post("/api/recordings", json={
            "audioId": audio_id, "levelId": "L30", "submissionId": "e2e-sub-1"})
        check("idempotent replay same recordingId",
              r.status_code == 200 and r.json()["data"]["recording"]["recordingId"] == rec_id)
        # 幂等冲突：同 submissionId 不同负载
        r2up = c.post("/api/audio/uploads", data={"purpose": "recording"},
                      files={"file": ("r2.webm", r2_audio, "audio/webm")})
        other_audio = r2up.json()["data"]["audioId"]
        r = c.post("/api/recordings", json={
            "audioId": other_audio, "levelId": "L30", "submissionId": "e2e-sub-1"})
        check("same submissionId different payload → 409 IDEMPOTENCY_CONFLICT",
              r.status_code == 409 and r.json()["code"] == "IDEMPOTENCY_CONFLICT")

        # 查询录音
        r = c.get(f"/api/recordings/{rec_id}")
        check("GET recording 200", r.status_code == 200 and r.json()["data"]["result"])

        # 本人 F0/共振峰/图片
        r = c.get(f"/api/audio/{audio_id}/f0")
        check("audio f0 frames", r.status_code == 200 and len(r.json()["data"]["frames"]) > 20)
        r = c.get(f"/api/audio/{audio_id}/formants")
        check("audio formants", r.status_code == 200 and r.json()["data"]["frames"])
        r = c.get(f"/api/audio/{audio_id}/formants.png")
        check("audio formants png", r.status_code == 200 and r.headers.get("content-type") == "image/png")
        r = c.get(f"/api/audio/{audio_id}/spectrogram.png")
        check("audio spectrogram png", r.status_code == 200 and r.headers.get("content-type") == "image/png")
        r = c.get(f"/api/audio/{audio_id}/file", headers={"Range": "bytes=0-49"})
        check("audio file range 206", r.status_code == 206 and len(r.content) == 50)

        # 5 标定（FR-1006）
        r = c.post("/api/audio/uploads", data={"purpose": "calibration"},
                   files={"file": ("cal.webm", cal_audio, "audio/webm")})
        cal_audio_id = r.json()["data"]["audioId"]
        r = c.post("/api/pitch-calibration", json={"audioId": cal_audio_id})
        body = r.json()
        check("calibration ok (personal)",
              r.status_code == 200 and body["code"] == "OK" and body["data"]["status"] == "personal",
              r.text[:200])
        f_lo = body["data"]["pitchRange"]["fLo"]
        check("pitch range plausible male", 70 <= f_lo <= 180, str(f_lo))

        # 标定失败路径：静音
        r = c.post("/api/audio/uploads", data={"purpose": "calibration"},
                   files={"file": ("silence.webm", silence_bytes(3), "audio/webm")})
        sid_audio = r.json()["data"]["audioId"]
        r = c.post("/api/pitch-calibration", json={"audioId": sid_audio})
        check("calibration silence → 200 CALIBRATION_FAIL",
              r.status_code == 200 and r.json()["code"] == "CALIBRATION_FAIL")

        # 6 质量提示只作提示：静音录音仍评分并展示曲线/质量建议（FR-1301）
        sil_rec = c.post("/api/audio/uploads", data={"purpose": "recording"},
                         files={"file": ("s.webm", silence_bytes(3), "audio/webm")})
        sil_id = sil_rec.json()["data"]["audioId"]
        r = c.post("/api/recordings", json={
            "audioId": sil_id, "levelId": "L30", "submissionId": "e2e-sil-1"})
        body = r.json()
        check("silence recording → 200 with result",
              r.status_code == 200 and body["data"].get("result") is not None,
              f"{r.status_code} {r.text[:200]}")
        sil_result = body["data"]["result"]
        check("quality hints present, no gate",
              bool(sil_result["quality"]["signal"]) and bool(sil_result["quality"].get("advice")))
        check("score still returned", sil_result.get("score") is not None)

        # 7 标定后再次提交
        r = c.post("/api/audio/uploads", data={"purpose": "recording"},
                   files={"file": ("r3.webm", r2_audio, "audio/webm")})
        a3 = r.json()["data"]["audioId"]
        r = c.post("/api/recordings", json={
            "audioId": a3, "levelId": "L30", "submissionId": "e2e-sub-2"})
        if r.status_code == 202:  # 同步窗口未完成 → 轮询
            pending = r.json()["data"]["recording"]["recordingId"]
            for _ in range(40):
                r = c.get(f"/api/recordings/{pending}")
                if r.status_code == 200:
                    break
                time.sleep(0.3)
        check("post-calibration submit 200", r.status_code == 200 and r.json()["data"].get("result"),
              f"{r.status_code} {r.text[:200]}")
        rec2_id = r.json()["data"]["recording"]["recordingId"]

        # 8 档案
        r = c.get("/api/me/recordings", params={"levelId": "L30"})
        items = r.json()["data"]["recordings"]
        check("me/recordings list >=3", len(items) >= 3, str(len(items)))

        # 9 进度（新口径 D-24：完成 = 该关至少一条未删除检测录音，
        #   前文已给 L30 提交过 e2e-sub-1 / e2e-sil-1 / e2e-sub-2 多条录音）
        r = c.get("/api/me/progress")
        prog = r.json()["data"]
        l30p = next(x for x in prog["levels"] if x["levelId"] == "L30")
        check("L30 completed (derived from recordings)", l30p["completed"] is True, str(l30p))
        check("nextLevelId != L30", prog["nextLevelId"] != "L30")

        # 10 删除单条与清空档案
        r = c.delete(f"/api/recordings/{rec2_id}")
        check("delete single recording", r.status_code == 200 and r.json()["data"]["deleted"])
        r = c.delete("/api/me/recordings")
        check("clear archive", r.status_code == 200 and r.json()["data"]["deleted"] >= 2,
              r.text[:150])
        r = c.get("/api/me/recordings")
        check("archive empty after clear", len(r.json()["data"]["recordings"]) == 0)
        # 该关全部录音删除后 completed 应回落 false，nextLevelId 回到首个开放关
        r = c.get("/api/me/progress")
        prog = r.json()["data"]
        l30p = next(x for x in prog["levels"] if x["levelId"] == "L30")
        check("L30 completed=false after archive cleared", l30p["completed"] is False, str(l30p))
        check("nextLevelId back to L01", prog["nextLevelId"] == "L01", str(prog["nextLevelId"]))

        # 11 反馈（登录后）
        r = c.post("/api/feedback", json={"sourcePage": "P05", "type": "clarity",
                                          "content": "这里没看懂", "levelId": "L30"})
        check("feedback accepted", r.status_code == 200)
        r = c.post("/api/wishes", json={"content": "希望增加 ai 复韵母", "searchQuery": "ai"})
        check("wish accepted", r.status_code == 200)

        # 12 注销
        r = c.request("DELETE", "/api/me/account", json={"password": "password123"})
        check("delete account", r.status_code == 200)
        r = c.post("/api/auth/login", json={"username": username, "password": "password123"})
        check("deleted account cannot login", r.status_code == 401)

    # 13 权限：他人资源 404（新账号读旧 audioId）
    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=60) as c:
        username2 = f"e2e用户2_{int(time.time())}"
        r = c.post("/api/auth/register", json={"username": username2, "password": "password123"})
        check("register second user", r.status_code == 200, r.text[:150])
        r = c.post("/api/auth/login", json={"username": username2, "password": "password123"})
        check("login second user", r.status_code == 200)
        r = c.get(f"/api/audio/{audio_id}/file")
        check("other user reads private audio → 404", r.status_code == 404)
        r = c.get(f"/api/recordings/{rec_id}")
        check("other user reads recording → 404", r.status_code == 404)

    # 14 CSRF：无 Origin 写请求 → 403
    with httpx.Client(base_url=BASE, timeout=30) as c3:
        r = c3.post("/api/auth/register", json={"username": "csrfuser", "password": "password123"})
        check("CSRF missing origin → 403", r.status_code == 403)

    # 15 admin
    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=60) as a:
        r = a.post("/api/admin/login", json={"username": "admin", "password": "admin12345"})
        check("admin login", r.status_code == 200, r.text[:150])
        r = a.get("/api/admin/overview")
        check("admin overview", r.status_code == 200 and r.json()["data"]["levels"]["published"] == 30)

        # 关闭 L30 → 大众端不可见
        r = a.put("/api/admin/levels/L30/published", json={"published": False})
        check("close L30", r.status_code == 200 and r.json()["data"]["published"] is False)
        r = a.get("/api/levels/L30")
        check("L30 detail 404 after closed", r.status_code == 404)
        r = a.get("/api/search", params={"q": "妈"})
        check("search no L30 after closed",
              all(x["id"] != "L30" for x in r.json()["data"]["results"]))

        # 重新开放 → 立即可见
        r = a.put("/api/admin/levels/L30/published", json={"published": True})
        check("reopen L30", r.status_code == 200 and r.json()["data"]["published"] is True)
        r = a.get("/api/levels/L30")
        check("L30 detail back", r.status_code == 200)

        # 内容保存即生效：改专业与声学说明
        d30 = a.get("/api/admin/levels/L30").json()["data"]
        content = d30["content"]
        old_desc = (content.get("professional") or {}).get("description")
        content.setdefault("professional", {})["description"] = "e2e 修改过的专业说明"
        r = a.put("/api/admin/levels/L30", json={"content": content})
        check("save level content", r.status_code == 200, r.text[:150])
        r = a.get("/api/levels/L30")
        check("content change live immediately",
              r.status_code == 200
              and r.json()["data"]["professional"]["description"] == "e2e 修改过的专业说明")
        # 恢复
        content["professional"]["description"] = old_desc
        a.put("/api/admin/levels/L30", json={"content": content})

        # 反馈处理
        r = a.get("/api/admin/feedback", params={"status": "pending"})
        fb = r.json()["data"]["feedback"]
        check("admin sees pending feedback", len(fb) >= 1)
        if fb:
            r = a.put(f"/api/admin/feedback/{fb[0]['id']}", json={"status": "adopted"})
            check("handle feedback adopted", r.status_code == 200)

    failed = [r for r in results if not r[1]]
    print(f"\n==== {len(results) - len(failed)}/{len(results)} passed ====")
    for name, _, detail in failed:
        print(f"FAILED: {name} — {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
