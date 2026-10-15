"""端到端闭环自测（直接运行：python e2e_test.py）。

覆盖：健康 / 关卡与搜索 / 访客标定+检测闭环（含曲线与四步） /
质量失败 / 标定前置 409 / 幂等与版本冲突 / 账号（注册-登录-同意-转存-
档案-比较-学习事件-进度-撤回）/ 会话临时记录与重置 / admin（发布-下架-
熔断-审计-预览）。

所有请求带 Origin 头（CSRF 校验）；媒体语义直接断言 HTTP 状态与头。
"""
from __future__ import annotations

import io
import sys
import wave
from pathlib import Path

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from app.seed_support import synthesize_text, write_wav  # noqa: E402

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


def main() -> int:
    # 1 健康与内容
    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=40) as c:
        r = c.get("/api/health")
        check("health", r.status_code == 200 and r.json()["status"] == "ok")

        r = c.get("/api/levels")
        d = r.json()["data"]
        check("levels 30 published", len(d["levels"]) == 30, f"got {len(d['levels'])}")
        check("confusablePairs non-empty", len(d["confusablePairs"]) >= 5)
        l30 = next(l for l in d["levels"] if l["id"] == "L30")
        check("L30 availability open", l30["availability"] == "open")

        r = c.get("/api/levels/L30")
        d30 = r.json()["data"]
        check("L30 detail quizzes>=3", len(d30["quizzes"]) >= 3)
        check("L30 nav prev L29", d30["nav"]["prev"] == "L29")
        check("L30 detection promptText", bool(d30["detection"]["promptText"]))

        r = c.get("/api/search", params={"q": "妈"})
        check("search 妈 → L30 first", r.json()["data"]["results"][0]["id"] == "L30")
        r = c.get("/api/search", params={"q": "翘舌"})
        ids = [x["id"] for x in r.json()["data"]["results"]]
        check("search 翘舌 → zh/ch/sh", any(i in ids for i in ("L21", "L22", "L23")), str(ids))

        r = c.get("/api/articles")
        check("articles >=6", len(r.json()["data"]["articles"]) >= 6)

        # 媒体：公开示范可读 + ETag/304
        demo_media = l30["demoMediaId"]
        r = c.get(f"/api/media/{demo_media}")
        check("public media 200 wav", r.status_code == 200 and "audio" in r.headers.get("content-type", ""))
        etag = r.headers.get("ETag")
        r2 = c.get(f"/api/media/{demo_media}", headers={"If-None-Match": etag})
        check("media 304", r2.status_code == 304)
        r3 = c.get(f"/api/media/{demo_media}", headers={"Range": "bytes=0-99"})
        check("media range 206", r3.status_code == 206 and len(r3.content) == 100)

        # 2 访客：context
        r = c.get("/api/me/context")
        ctx = r.json()["data"]
        check("guest context calibration none", ctx["calibration"]["status"] == "none")
        check("guest nextLevelId L01", ctx["nextLevelId"] == "L01")

        # 3 未标定提交 → 409 CALIBRATION_REQUIRED（先传录音再提交）
        # admin 段发布/回退会让 L30 版本逐轮 +1：全程动态取版本号，保证连跑幂等
        cv = c.get("/api/levels/L30").json()["data"]["contentVersion"]
        rec_audio = wav_bytes(synthesize_text("妈麻马骂", "male", syllable_dur=0.32))
        r = c.post("/api/audio/uploads", data={"purpose": "recording"},
                   files={"file": ("rec.webm", rec_audio, "audio/webm")})
        check("upload recording audio", r.status_code == 200, r.text[:200])
        audio_id = r.json()["data"]["audioId"]
        r = c.post("/api/recordings", json={
            "audioId": audio_id, "levelId": "L30", "contentVersion": cv,
            "submissionId": "e2e-nocal-1"})
        check("submit without calibration → 409 CALIBRATION_REQUIRED",
              r.status_code == 409 and r.json()["code"] == "CALIBRATION_REQUIRED",
              f"{r.status_code} {r.text[:120]}")

        # 4 标定
        cal_audio = wav_bytes(synthesize_text("妈坡车米布女妈麻马骂", "male", syllable_dur=0.36))
        r = c.post("/api/audio/uploads", data={"purpose": "calibration"},
                   files={"file": ("cal.webm", cal_audio, "audio/webm")})
        cal_audio_id = r.json()["data"]["audioId"]
        r = c.post("/api/pitch-calibration", json={"audioId": cal_audio_id, "textVersion": "v1"})
        body = r.json()
        check("calibration ok (session)",
              r.status_code == 200 and body["code"] == "OK" and body["data"]["status"] == "session",
              r.text[:200])
        f_lo = body["data"]["pitchRange"]["fLo"]
        check("pitch range plausible male", 70 <= f_lo <= 180, str(f_lo))

        # 标定失败路径：静音
        r = c.post("/api/audio/uploads", data={"purpose": "calibration"},
                   files={"file": ("silence.webm", silence_bytes(3), "audio/webm")})
        sid_audio = r.json()["data"]["audioId"]
        r = c.post("/api/pitch-calibration", json={"audioId": sid_audio, "textVersion": "v1"})
        check("calibration silence → 200 CALIBRATION_FAIL",
              r.status_code == 200 and r.json()["code"] == "CALIBRATION_FAIL")

        # 5 检测提交（正常）
        r = c.post("/api/recordings", json={
            "audioId": audio_id, "levelId": "L30", "contentVersion": cv,
            "submissionId": "e2e-sub-1"})
        body = r.json()
        check("submit → 200 with result",
              r.status_code == 200 and body["data"].get("result"),
              f"{r.status_code} {r.text[:300]}")
        result = body["data"]["result"]
        check("result quality pass", result["quality"]["verdict"] == "pass")
        check("result curve ok 4 segments",
              result["curve"]["status"] == "ok" and len(result["curve"]["segments"]) == 4,
              str(result["curve"])[:200])
        check("result fourSteps wordingSource",
              all(s["wordingSource"] == "rule_template" for s in result.get("fourSteps", [])))
        check("boundaryNote fixed",
              result["boundaryNote"] == "学习参考，不作为普通话等级认定或医学诊断。")
        rec_id = body["data"]["recording"]["recordingId"]

        # 幂等重放：同 submissionId 同负载
        r = c.post("/api/recordings", json={
            "audioId": audio_id, "levelId": "L30", "contentVersion": cv,
            "submissionId": "e2e-sub-1"})
        check("idempotent replay same recordingId",
              r.status_code == 200 and r.json()["data"]["recording"]["recordingId"] == rec_id)
        # 幂等冲突：同 submissionId 不同负载
        r = c.post("/api/recordings", json={
            "audioId": audio_id, "levelId": "L30", "contentVersion": cv,
            "submissionId": "e2e-sub-1x", })
        r2_audio = wav_bytes(synthesize_text("妈麻马骂", "female", syllable_dur=0.3))
        r2up = c.post("/api/audio/uploads", data={"purpose": "recording"},
                      files={"file": ("r2.webm", r2_audio, "audio/webm")})
        other_audio = r2up.json()["data"]["audioId"]
        r = c.post("/api/recordings", json={
            "audioId": other_audio, "levelId": "L30", "contentVersion": cv,
            "submissionId": "e2e-sub-1"})
        check("same submissionId different payload → 409 IDEMPOTENCY_CONFLICT",
              r.status_code == 409 and r.json()["code"] == "IDEMPOTENCY_CONFLICT")

        # 版本冲突
        r = c.post("/api/recordings", json={
            "audioId": other_audio, "levelId": "L30", "contentVersion": 99,
            "submissionId": "e2e-ver-1"})
        check("stale contentVersion → 409 CONTENT_VERSION_CHANGED",
              r.status_code == 409 and r.json()["code"] == "CONTENT_VERSION_CHANGED")

        # 查询录音
        r = c.get(f"/api/recordings/{rec_id}")
        check("GET recording 200", r.status_code == 200 and r.json()["data"]["result"])

        # 本人 F0/共振峰/图片
        r = c.get(f"/api/audio/{audio_id}/f0")
        check("audio f0 frames", r.status_code == 200 and len(r.json()["data"]["frames"]) > 50)
        r = c.get(f"/api/audio/{audio_id}/formants")
        check("audio formants", r.status_code == 200 and r.json()["data"]["frames"])
        r = c.get(f"/api/audio/{audio_id}/formants.png")
        check("audio formants png", r.status_code == 200 and r.headers.get("content-type") == "image/png")
        r = c.get(f"/api/audio/{audio_id}/spectrogram.png")
        check("audio spectrogram png", r.status_code == 200 and r.headers.get("content-type") == "image/png")
        r = c.get(f"/api/audio/{audio_id}/file", headers={"Range": "bytes=0-49"})
        check("audio file range 206", r.status_code == 206 and len(r.content) == 50)

        # 质量失败：静音录音 → QUALITY_FAIL（200）
        sil_rec = c.post("/api/audio/uploads", data={"purpose": "recording"},
                         files={"file": ("s.webm", silence_bytes(3), "audio/webm")})
        sil_id = sil_rec.json()["data"]["audioId"]
        r = c.post("/api/recordings", json={
            "audioId": sil_id, "levelId": "L30", "contentVersion": cv,
            "submissionId": "e2e-sil-1"})
        body = r.json()
        check("silence recording → 200 QUALITY_FAIL",
              r.status_code == 200 and body["data"]["result"]["quality"]["verdict"] == "fail",
              f"{r.status_code} {r.text[:200]}")
        check("QUALITY_FAIL no score",
              body["data"]["result"].get("score") is None)
        check("QUALITY_FAIL retakeAdvice",
              bool(body["data"]["result"]["quality"].get("retakeAdvice")))

        # 6 会话临时记录
        r = c.get("/api/session/recordings")
        sess = r.json()["data"]
        check("session recordings >=2 completed", len(sess["recordings"]) >= 2,
              str(len(sess.get("recordings", []))))
        check("transferableCount >=1", sess["transferableCount"] >= 1)

        # 7 账号闭环
        import time as _time

        username = f"e2e用户_{int(_time.time())}"
        r = c.post("/api/auth/register", json={"username": username, "password": "password123"})
        check("register", r.status_code == 200, r.text[:150])
        r = c.post("/api/auth/login", json={"username": username, "password": "password123"})
        check("login binds sid", r.status_code == 200 and r.json()["data"]["context"]["authenticated"])
        r = c.get("/api/me/context")
        ctx = r.json()["data"]
        check("context authenticated + pendingTransfer",
              ctx["authenticated"] and ctx.get("pendingTransfer", 0) >= 1,
              str(ctx.get("pendingTransfer")))

        # 同意前：档案接口 403
        r = c.get("/api/me/recordings")
        check("me/recordings before consent → 403", r.status_code == 403)

        # 同意 → 转存
        r = c.post("/api/me/consent", json={"decision": "granted", "consentTextVersion": "v1"})
        tr = r.json()["data"]["transfer"]
        check("consent transfer count>=1",
              tr["transferredCount"] >= 1 and tr["status"] == "completed", str(tr))

        # 再来一次提交（应自动 archived）
        r = c.post("/api/audio/uploads", data={"purpose": "recording"},
                   files={"file": ("r3.webm", r2_audio, "audio/webm")})
        a3 = r.json()["data"]["audioId"]
        r = c.post("/api/recordings", json={
            "audioId": a3, "levelId": "L30", "contentVersion": cv, "submissionId": "e2e-sub-2"})
        check("post-consent submit auto-archived",
              r.status_code == 200 and r.json()["data"]["recording"]["storage"] == "archived",
              r.text[:200])
        rec2_id = r.json()["data"]["recording"]["recordingId"]

        # 档案与比较
        r = c.get("/api/me/recordings", params={"levelId": "L30"})
        items = r.json()["data"]["recordings"]
        check("me/recordings archived list >=2", len(items) >= 2, str(len(items)))
        a, b = sorted([rec_id, rec2_id])
        r = c.get("/api/me/recordings/compare", params={"a": rec_id, "b": rec2_id})
        cmp_ = r.json()["data"]
        check("compare same level ok",
              r.status_code == 200 and cmp_["comparable"]["score"] is True, r.text[:200])

        # 学习事件与进度（D-24）
        d30 = c.get("/api/levels/L30").json()["data"]
        quiz_ids = [q["id"] for q in d30["quizzes"]]
        step_ids = [p["id"] for p in d30["practice"]]
        events = [{"eventId": f"ev-{qid}", "levelId": "L30", "contentVersion": cv,
                   "kind": "listen_quiz",
                   "detail": {"questionId": qid,
                              "choiceIndex": next(q["answerIndex"] for q in d30["quizzes"]
                                                  if q["id"] == qid)}}
                  for qid in quiz_ids]
        events += [{"eventId": f"ev-{sid}", "levelId": "L30", "contentVersion": cv,
                    "kind": "practice_done", "detail": {"stepId": sid}} for sid in step_ids]
        r = c.post("/api/learning-events", json={"events": events})
        acc = r.json()["data"]
        check("learning-events accepted all", acc["accepted"] == len(events), str(acc))
        r = c.post("/api/learning-events", json={"events": events[:1]})
        check("learning-events dedupe", r.json()["data"]["duplicates"] == 1)
        r = c.get("/api/me/progress")
        prog = r.json()["data"]
        l30p = next(x for x in prog["levels"] if x["levelId"] == "L30")
        check("L30 completed (D-24)", l30p["completed"] is True, str(l30p))
        check("nextLevelId != L30", prog["nextLevelId"] != "L30")

        # 撤回同意（删除全部）
        r = c.delete("/api/me/consent")
        check("revoke consent", r.status_code == 200)
        r = c.get("/api/me/recordings")
        check("archive gone after revoke → 403", r.status_code == 403)

        # 注销
        r = c.request("DELETE", "/api/me/account", json={"password": "password123"})
        check("delete account", r.status_code == 200)
        r = c.post("/api/auth/login", json={"username": username, "password": "password123"})
        check("deleted account cannot login", r.status_code == 401)

        # 8 权限：他人资源 404（新会话读旧 audioId）
        c2 = httpx.Client(base_url=BASE, headers=HEADERS, timeout=30)
        r = c2.get(f"/api/audio/{audio_id}/file")
        check("other sid reads private audio → 404", r.status_code == 404)
        r = c2.get(f"/api/recordings/{rec_id}")
        check("other sid reads recording → 404", r.status_code == 404)

        # 9 CSRF：无 Origin 写请求 → 403
        r = c2.post("/api/feedback", json={"type": "clarity", "content": "x"})
        ok = r.status_code == 403
        c3 = httpx.Client(base_url=BASE, timeout=30)
        r = c3.post("/api/feedback", json={"type": "clarity", "content": "x"})
        check("CSRF missing origin → 403", r.status_code == 403)
        c3.close()

        # 10 反馈
        r = c2.post("/api/feedback", json={"sourcePage": "P05", "type": "clarity",
                                           "content": "这里没看懂", "levelId": "L30"})
        check("feedback accepted", r.status_code == 200)
        r = c2.post("/api/wishes", json={"content": "希望增加 ai 复韵母", "searchQuery": "ai"})
        check("wish accepted", r.status_code == 200)

        # 11 会话重置（访客轮换 sid）
        r = c2.post("/api/session/reset")
        check("session reset", r.status_code == 200 and r.json()["data"]["reset"] is True)
        r = c2.get("/api/session/recordings")
        check("session recordings empty after reset", len(r.json()["data"]["recordings"]) == 0)
        c2.close()

    # 12 admin
    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=60) as a:
        r = a.post("/api/admin/login", json={"username": "admin", "password": "admin12345"})
        check("admin login", r.status_code == 200, r.text[:150])
        r = a.get("/api/admin/overview")
        check("admin overview", r.status_code == 200 and r.json()["data"]["levels"]["published"] == 30)

        # 下架 L30 → 大众端不可见
        r = a.post("/api/admin/levels/L30/unpublish", json={"reason": "e2e 测试下架"})
        check("unpublish L30", r.status_code == 200)
        r = a.get("/api/levels/L30")
        check("L30 detail 404 after unpublish", r.status_code == 404)
        r = a.get("/api/search", params={"q": "妈"})
        check("search no L30 after unpublish",
              all(x["id"] != "L30" for x in r.json()["data"]["results"]))

        # 重新发布（回退到上一版本亦可，这里直接重新发布）→ 版本号 +1（连跑幂等）
        r = a.post("/api/admin/levels/L30/publish", json={"changeNote": "e2e 重新发布"})
        repub_cv = r.json()["data"]["contentVersion"]
        check("republish L30 bumps version",
              r.status_code == 200 and repub_cv == cv + 1,
              f"{r.status_code} {r.text[:150]}")
        r = a.get("/api/levels/L30")
        check("L30 back at republished version",
              r.status_code == 200 and r.json()["data"]["contentVersion"] == repub_cv)

        # 回退 → 版本号再 +1，内容回到上一公开版本
        r = a.post("/api/admin/levels/L30/rollback")
        rolled_cv = r.json()["data"]["contentVersion"]
        check("rollback bumps version",
              r.status_code == 200 and rolled_cv == repub_cv + 1,
              f"{r.status_code} {r.text[:150]}")

        # 熔断：全局关 → 提交 503 DETECTION_OFF
        a.post("/api/admin/detection-switches", json={"levelId": None, "enabled": False,
                                                      "reason": "e2e 熔断演练"})
        with httpx.Client(base_url=BASE, headers=HEADERS, timeout=30) as c:
            r = c.get("/api/levels")
            check("availability temporarily_unavailable",
                  next(l for l in r.json()["data"]["levels"] if l["id"] == "L30")
                  ["availability"] == "temporarily_unavailable")
            ra = c.post("/api/audio/uploads", data={"purpose": "recording"},
                        files={"file": ("x.webm", rec_audio, "audio/webm")})
            r = c.post("/api/recordings", json={
                "audioId": ra.json()["data"]["audioId"], "levelId": "L30",
                "contentVersion": rolled_cv, "submissionId": "e2e-off-1"})
            check("submit while fused → 503 DETECTION_OFF",
                  r.status_code == 503 and r.json()["code"] == "DETECTION_OFF",
                  f"{r.status_code} {r.text[:150]}")
        a.post("/api/admin/detection-switches", json={"levelId": None, "enabled": True,
                                                      "reason": "e2e 恢复"})

        # 预览令牌：草稿预览 JSON + 媒体 no-store
        r = a.post("/api/preview/tokens", json={"kind": "level", "id": "L30"})
        tok = r.json()["data"]
        check("preview token issued", r.status_code == 200 and tok["token"])
        r = a.get(f"/api/preview/levels/L30", params={"token": tok["token"]})
        check("preview level json no-store",
              r.status_code == 200 and r.headers.get("cache-control") == "no-store")

        # 非管理员访问预览 → 401/404
        with httpx.Client(base_url=BASE, headers=HEADERS, timeout=30) as c:
            r = c.get(f"/api/preview/levels/L30", params={"token": tok["token"]})
            check("preview without admin → 401", r.status_code == 401)

        # 审计查询
        r = a.get("/api/admin/audit", params={"object_type": "level", "limit": 50})
        actions = [e["action"] for e in r.json()["data"]["entries"]]
        check("audit has publish/unpublish",
              "publish" in actions and "unpublish" in actions)

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
