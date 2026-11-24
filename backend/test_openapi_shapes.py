"""schema 真实性测试：实际响应必须能通过 OpenAPI 文档声明的响应模型校验。

背景：路由直返 JSONResponse，FastAPI 对 response_model 不做运行时校验/过滤
（零行为变化的刻意取舍）。因此「文档与实现一致」需要独立的回归断言：
逐端点发真实请求，把响应体按 Envelope[X] / X 严格校验（extra=forbid，
多余字段即视为契约漂移——实现加了字段而 schemas.py 没跟上时会在这里暴露）。

运行：backend/ 目录下 `py -3 test_openapi_shapes.py`（TestClient 走 ASGI，
不占 8000 端口；可直接与运行中的服务共存，共写同一 SQLite）。
合成音频用法与 e2e_test.py 相同（app/seed_support.py）。
"""
from __future__ import annotations

import io
import os
import re
import sys
import time
import wave
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from pydantic import ConfigDict, ValidationError

sys.path.insert(0, str(Path(__file__).parent))
# 本测试只做契约形状校验：未显式指定 Provider 时钉在 mock，避免默认讯飞时打到真实 API
os.environ.setdefault("SVS_PROVIDER", "mock")
# TestClient 请求不带 Origin/Referer，CSRF 写校验需在本脚本内关闭
os.environ.setdefault("SVS_CSRF_ENFORCED", "0")
import main as backend_main  # noqa: E402
from app import config  # noqa: E402
from app.acoustics import transcode  # noqa: E402
from app.api.schemas import (  # noqa: E402
    AssessmentResult, AudioUploadResponse, AuthLoginResponse, ArchiveListResponse,
    CalibrationSessionView, CalibrationTakeOutcome, DeletedResponse, FeedbackResponse,
    F0Response, FormantsResponse, HealthData, LevelDetail,
    LevelsResponse, MeContext, MeProgress, PitchCalibrationInfo, ProfileResponse,
    ProgressLevel, RecordingDeleted, RecordingWithResult, RegisterResponse, SearchResponse,
    Envelope,
)

ORIGIN = {"Origin": "http://localhost:5173"}   # 过 CSRF（同 e2e_test.py）

results: list[tuple[str, bool, str]] = []
_strict_cache: dict = {}


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not ok else ""))


def strict(cls):
    """同结构但禁止多余字段的版本：实现多吐的字段（schema 未跟上）会校验失败。"""
    cached = _strict_cache.get(cls)
    if cached is None:
        cached = _strict_cache[cls] = type(
            f"{cls.__name__}Strict", (cls,), {"model_config": ConfigDict(extra="forbid")})
    return cached


def _fmt(err: ValidationError) -> str:
    parts = [f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in err.errors()[:3]]
    return " | ".join(parts) + (f" (+{len(err.errors()) - 3} more)" if len(err.errors()) > 3 else "")


def expect(name: str, resp, data_model=None, *, enveloped=True,
           status: int = 200, code: str = "OK"):
    """断言 HTTP 状态 / 业务码，并把整个响应体按 Envelope[data_model] 严格校验。

    enveloped=False 用于唯一不走 envelope 的 /api/health（直接按 data_model 校验）。
    返回响应体 dict 便于后续流程断言。
    """
    problems: list[str] = []
    if resp.status_code != status:
        problems.append(f"HTTP {resp.status_code}（期望 {status}）")
    body = None
    try:
        body = resp.json()
    except Exception:
        problems.append("响应不是 JSON")
        body = None
    if body is not None:
        if enveloped and body.get("code") != code:
            problems.append(f"code={body.get('code')!r}（期望 {code!r}）")
        checks = []
        if data_model is not None:
            if enveloped:
                checks.append((f"Envelope[{data_model.__name__}]",
                               strict(Envelope[data_model]), body))
                checks.append((data_model.__name__, strict(data_model), body.get("data")))
            else:
                checks.append((data_model.__name__, strict(data_model), body))
        for label, model, payload in checks:
            try:
                model.model_validate(payload)
            except ValidationError as e:
                problems.append(f"{label} 校验失败：{_fmt(e)}")
    check(name, not problems, "; ".join(problems)[:400] or resp.text[:200])
    return body


def wav_bytes(samples: np.ndarray, rate: int = transcode.SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def silence_bytes(seconds: float = 2.0) -> bytes:
    n = int(transcode.SAMPLE_RATE * seconds)
    return wav_bytes(np.zeros(n, dtype=np.float32)
                     + np.random.default_rng(1).standard_normal(n) * 1e-4)


def corpus_wav_bytes(pinyin: str, speaker: str = "MV1") -> bytes:
    """按带调拼音标注从真人标准音节语料库读取并拼接为 44.1kHz 单声道 WAV 字节。

    采样率必须与语料一致：语料经转码回到 44.1k 后若按 16 kHz 标签写出，
    上传再规范化时全部频率会被拉低到 0.363 倍，元音/声调特征失真。
    """
    corpus = config.CORPUS_DIR
    if corpus is None or not corpus.is_dir():
        raise RuntimeError("请先在 .env 或环境变量配置 CORPUS_DIR")
    syls = [{"stem": s} for s in re.split(r"[|，,\s]+", pinyin.strip()) if s]
    chunks: list[np.ndarray] = []
    gap = np.zeros(int(0.08 * transcode.SAMPLE_RATE), dtype=np.float32)
    tmp_dir = config.DATA_DIR / "tmp_test"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for idx, s in enumerate(syls):
        stem = s["stem"]
        src = corpus / speaker / f"{stem}_{speaker}.wav"
        dst = tmp_dir / f"{speaker}_{stem}_{idx}.wav"
        transcode.normalize_to_wav(src, dst)
        chunks.append(transcode.read_pcm_samples(dst))
        dst.unlink(missing_ok=True)
        if idx + 1 < len(syls):
            chunks.append(gap)
    return wav_bytes(np.concatenate(chunks) if chunks else np.zeros(transcode.SAMPLE_RATE, dtype=np.float32))


def upload(c: TestClient, audio: bytes, purpose: str, name: str) -> str:
    r = c.post("/api/audio/uploads", data={"purpose": purpose},
               files={"file": (name, audio, "audio/webm")})
    expect(f"upload {purpose} → AudioUploadResponse", r, AudioUploadResponse)
    return r.json()["data"]["audioId"]


def main() -> int:
    with TestClient(backend_main.app, headers=ORIGIN) as c:
        # ---- 平台与内容（公开） ----
        r = c.get("/api/health")
        expect("health → HealthData（唯一非 envelope 端点）", r, HealthData, enveloped=False)

        r = c.get("/api/me/context")
        body = expect("me/context（访客）→ MeContext", r, MeContext)
        check("  访客 context authenticated=false",
              body["data"]["authenticated"] is False)

        r = c.get("/api/levels")
        body = expect("levels → LevelsResponse", r, LevelsResponse)
        # 与种子数据同源对比（关卡随内容追加）
        from app.content_seed_data import LEVELS
        check(f"  levels 共 {len(LEVELS)} 关（与种子一致）",
              len(body["data"]["levels"]) == len(LEVELS),
              str(len(body["data"].get("levels", []))))

        check("  levels 无 completionKeys（字段已删除）",
              all("completionKeys" not in l for l in body["data"]["levels"]))

        r = c.get("/api/levels/L01")
        body = expect("levels/L01 → LevelDetail", r, LevelDetail)
        practice = body["data"].get("practice") or []
        check("  L01 含 quiz 与纯文本 practice",
              len(body["data"].get("quizzes") or []) > 0
              and isinstance(practice, list) and len(practice) > 0
              and all(isinstance(p, str) and p for p in practice),
              str(practice)[:200])
        check("  L01 无 misconceptions（字段已删除）",
              "misconceptions" not in body["data"])

        r = c.get("/api/search", params={"q": "妈"})
        body = expect("search 妈 → SearchResponse", r, SearchResponse)
        check("  search 妈 命中 L30", body["data"]["results"][0]["id"] == "L30",
              str(body["data"]["results"][:1]))
        r = c.get("/api/search", params={"q": "123"})
        body = expect("search 无命中 → SearchResponse", r, SearchResponse)
        check("  无命中时 near 兜底非空（前端相近关数据源）",
              len(body["data"]["near"]) > 0, str(body["data"]["near"]))

        # ---- 未登录保护 ----
        r = c.get("/api/me/recordings")
        expect("me/recordings 未登录 → 401", r, None, status=401, code="AUTH_REQUIRED")

        # ---- 账号：注册 / 登录 ----
        # 用户名策略为 3–32 位小写英文字母或数字（identity.usecases），不能用中文
        username = f"shape{int(time.time())}"
        r = c.post("/api/auth/register", json={"username": username,
                                               "password": "password123",
                                               "dialectBackground": "yue",
                                               "gender": "female"})
        body = expect("auth/register（带方言背景与性别）→ RegisterResponse", r, RegisterResponse)
        check("  注册回显 dialectBackground=yue / gender=female",
              body["data"].get("dialectBackground") == "yue"
              and body["data"].get("gender") == "female")
        r = c.post("/api/auth/register", json={"username": f"{username}x",
                                               "password": "password123",
                                               "dialectBackground": "cantonese"})
        expect("auth/register 方言代码非法 → 422", r, None, status=422,
               code="VALIDATION_ERROR")
        r = c.post("/api/auth/register", json={"username": f"{username}y",
                                               "password": "password123",
                                               "gender": "unknown"})
        expect("auth/register 性别代码非法 → 422", r, None, status=422,
               code="VALIDATION_ERROR")
        r = c.post("/api/auth/login", json={"username": username,
                                            "password": "password123"})
        body = expect("auth/login → AuthLoginResponse", r, AuthLoginResponse)
        check("  login context.authenticated=true",
              body["data"]["context"]["authenticated"] is True)

        r = c.get("/api/me/context")
        body = expect("me/context（已登录未标定）→ MeContext", r, MeContext)
        check("  calibration status=none",
              body["data"]["calibration"]["status"] == "none")
        check("  context 下发 dialectBackground=yue（FR-107）",
              body["data"].get("dialectBackground") == "yue")
        check("  context 下发 gender=female（FR-107）",
              body["data"].get("gender") == "female")

        r = c.patch("/api/me/profile", json={"dialectBackground": "wu",
                                             "gender": "male"})
        body = expect("PATCH me/profile → ProfileResponse", r, ProfileResponse)
        check("  profile 更新为 wu / male",
              body["data"]["dialectBackground"] == "wu"
              and body["data"]["gender"] == "male")
        r = c.patch("/api/me/profile", json={"dialectBackground": None,
                                             "gender": None})
        body = expect("PATCH me/profile 清除 → ProfileResponse", r, ProfileResponse)
        check("  profile 清除为空",
              body["data"]["dialectBackground"] is None
              and body["data"]["gender"] is None)
        r = c.patch("/api/me/profile", json={"dialectBackground": "wu",
                                             "gender": "female"})
        body = expect("PATCH me/profile（恢复）→ ProfileResponse", r, ProfileResponse)
        check("  profile 恢复为 wu / female",
              body["data"]["dialectBackground"] == "wu"
              and body["data"]["gender"] == "female")

        # ---- 未标定直接检测（D-20） ----
        rec_audio = upload(c, corpus_wav_bytes("ma1", "MV1"),
                           "recording", "rec.webm")
        r = c.post("/api/recordings", json={
            "audioId": rec_audio, "levelId": "L30",
            "submissionId": f"shape-{time.time()}"})
        if r.status_code == 202:  # 契约允许：同步窗口未完成 → 按 Retry-After 轮询
            pending_id = r.json()["data"]["recording"]["recordingId"]
            for _ in range(40):
                r = c.get(f"/api/recordings/{pending_id}")
                if r.status_code == 200:
                    break
                time.sleep(0.3)
        body = expect("recordings POST（未标定）→ RecordingWithResult", r, RecordingWithResult)
        rec_id = body["data"]["recording"]["recordingId"]
        check("  结果含 quality/curve", bool(body["data"]["result"]["quality"])
              and body["data"]["result"]["curve"] is not None)
        strict(AssessmentResult).model_validate(body["data"]["result"])
        check("  result 可单独通过 AssessmentResult 严格校验", True)
        four_steps = body["data"]["result"].get("fourSteps") or []
        check("  fourSteps 每步 practice 为非空字符串（短练习文案）",
              all(isinstance(s.get("practice"), str) and s["practice"]
                  for s in four_steps),
              str(four_steps)[:200])

        r = c.get(f"/api/recordings/{rec_id}")
        expect("recordings/{id} GET → RecordingWithResult", r, RecordingWithResult)

        r = c.get(f"/api/audio/{rec_audio}/f0")
        body = expect("audio f0 → F0Response", r, F0Response)
        check("  f0 frames 非空", len(body["data"]["frames"]) > 0)
        r = c.get(f"/api/audio/{rec_audio}/formants")
        expect("audio formants → FormantsResponse", r, FormantsResponse)

        # ---- 声母关 VOT（FR-1005 送气段对比；未标定 → 同时覆盖自适应音域路径）----
        levels_body = c.get("/api/levels").json()["data"]["levels"]
        initials = [l for l in levels_body
                    if l["layer"] == "initial" and l["availability"] == "open"]
        vot_level = next((l for l in initials if l["id"] == "L08"), None)
        if vot_level is None:   # 兜底：任一开放的声母关（全量种子下就是 L08）
            vot_level = initials[0]
        vot_audio = upload(c, corpus_wav_bytes("po1", "MV1"),   # L08 坡
                           "recording", "rec-vot.webm")
        r = c.post("/api/recordings", json={
            "audioId": vot_audio, "levelId": vot_level["id"],
            "submissionId": f"shape-vot-{time.time()}"})
        if r.status_code == 202:
            pending_id = r.json()["data"]["recording"]["recordingId"]
            for _ in range(40):
                r = c.get(f"/api/recordings/{pending_id}")
                if r.status_code == 200:
                    break
                time.sleep(0.3)
        body = expect("声母关提交（发音证据）→ RecordingWithResult", r, RecordingWithResult)
        evidence = body["data"]["result"].get("pronunciationEvidence")
        check("  result.pronunciationEvidence 字段存在",
              evidence is not None, str(evidence)[:200])

        # ---- 标定（多录音会话流程）----
        r = c.get("/api/pitch-calibration")
        body = expect("pitch-calibration GET（未标定）→ PitchCalibrationInfo", r,
                      PitchCalibrationInfo)
        tasks = body["data"].get("vowelTasks") or []
        check("  任务配置：四元音各 2 条",
              [v["key"] for v in tasks] == ["i", "u", "a", "ü"]
              and all(v["targetTakes"] == 2 for v in tasks), str(tasks)[:120])

        r = c.post("/api/pitch-calibration/sessions")
        body = expect("标定会话创建 → CalibrationSessionView", r, CalibrationSessionView)
        session_id = body["data"]["sessionId"]
        next_task = body["data"]["nextTask"]
        check("  初始待办 = 元音 i 第 1 条",
              next_task and next_task["kind"] == "vowel" and next_task["vowel"] == "i",
              str(next_task))

        def submit_take(audio_id: str, kind: str, vowel: str | None = None, name: str = "t"):
            r = c.post(f"/api/pitch-calibration/sessions/{session_id}/takes",
                       json={"audioId": audio_id, "kind": kind, "vowel": vowel})
            return expect(f"标定单条验收 {kind} {vowel or ''} → CalibrationTakeOutcome",
                          r, CalibrationTakeOutcome)

        # 元音 i：两条差异大的录音 → 补第三条 → 一致对保留、离群条替换
        yi_id = upload(c, corpus_wav_bytes("yi1", "FV1"), "calibration", "cal-i1.webm")
        body = submit_take(yi_id, "vowel", "i")
        check("  元音 i 第 1 条 accepted", body["data"]["outcome"] == "accepted",
              str(body["data"]["outcome"]))
        ma_id = upload(c, corpus_wav_bytes("ma1", "FV1"), "calibration", "cal-i2.webm")
        body = submit_take(ma_id, "vowel", "i")
        check("  元音 i 两条差异大 → additional_take_required",
              body["data"]["outcome"] == "additional_take_required",
              str(body["data"]["outcome"]))
        ma_id2 = upload(c, corpus_wav_bytes("ma1", "FV1"), "calibration", "cal-i3.webm")
        body = submit_take(ma_id2, "vowel", "i")
        check("  元音 i 第三条后选定一致对 → accepted",
              body["data"]["outcome"] == "accepted", str(body["data"]["outcome"]))
        statuses = {t["audioId"]: t["status"] for t in body["data"]["session"]["takes"]}
        check("  未参与锚点的 yi1 录音标记 replaced", statuses.get(yi_id) == "replaced",
              str(statuses))

        # 元音 u/a/ü：同一语料音节各两条 → 直接通过；静音质检不过 → retry_take
        for key, stem in (("u", "wu1"), ("a", "a1"), ("ü", "yu2")):
            for n in (1, 2):
                aid = upload(c, corpus_wav_bytes(stem, "FV1"), "calibration",
                             f"cal-{key}{n}.webm")
                body = submit_take(aid, "vowel", key)
                check(f"  元音 {key} 第 {n} 条 accepted",
                      body["data"]["outcome"] == "accepted", str(body["data"]["outcome"]))
                if key == "u" and n == 1:
                    sil_id = upload(c, silence_bytes(2), "calibration", "sil-cal.webm")
                    body = submit_take(sil_id, "vowel", "u")
                    check("  静音元音录音 → retry_take",
                          body["data"]["outcome"] == "retry_take" and body["data"]["reason"],
                          str(body["data"]["outcome"]))

        # 短文
        passage_id = upload(c, corpus_wav_bytes("ma1|ma2|ma3|ma4", "MV1"),
                            "calibration", "cal-pitch.webm")
        body = submit_take(passage_id, "pitch")
        check("  短文验收通过且任务齐备",
              body["data"]["outcome"] == "accepted"
              and body["data"]["session"]["nextTask"] is None,
              str(body["data"]["session"].get("nextTask")))

        # 任务齐备后乱序提交 → 422
        extra_id = upload(c, corpus_wav_bytes("ma1", "FV1"), "calibration", "cal-extra.webm")
        r = c.post(f"/api/pitch-calibration/sessions/{session_id}/takes",
                   json={"audioId": extra_id, "kind": "vowel", "vowel": "i"})
        check("  任务完成后乱序提交 → 422", r.status_code == 422, r.text[:120])

        # 最终计算：发起 → 轮询 GET 至 done
        r = c.post(f"/api/pitch-calibration/sessions/{session_id}/complete")
        body = expect("会话完成请求 → CalibrationSessionView", r, CalibrationSessionView)
        for _ in range(80):
            r = c.get(f"/api/pitch-calibration/sessions/{session_id}")
            body = expect("会话查询 → CalibrationSessionView", r, CalibrationSessionView)
            if body["data"]["calcState"] == "done":
                break
            time.sleep(0.3)
        check("  calcState=done 且 result.pitchRange 有效",
              body["data"]["calcState"] == "done"
              and bool(body["data"]["result"])
              and body["data"]["result"]["pitchRange"]["fLo"] > 0
              and body["data"]["result"]["pitchRange"]["fHi"] > body["data"]["result"]["pitchRange"]["fLo"],
              str(body["data"].get("result"))[:160])

        r = c.post(f"/api/pitch-calibration/sessions/{session_id}/complete")
        body2 = expect("重复完成请求（幂等）→ CalibrationSessionView", r, CalibrationSessionView)
        check("  重复请求返回同一完成状态",
              body2["data"]["status"] == "completed"
              and body2["data"]["result"]["rangeSnapshotId"]
              == body["data"]["result"]["rangeSnapshotId"])

        r = c.get("/api/pitch-calibration")
        body = expect("pitch-calibration GET（已标定）→ PitchCalibrationInfo", r,
                      PitchCalibrationInfo)
        check("  已标定带 pitchRange", bool(body["data"].get("pitchRange")))

        # ---- 标定后提交 + 质量提示不拦截 ----
        rec2_audio = upload(c, corpus_wav_bytes("ma1", "MV1"),
                            "recording", "rec2.webm")
        r = c.post("/api/recordings", json={
            "audioId": rec2_audio, "levelId": "L30",
            "submissionId": f"shape-arc-{time.time()}"})
        if r.status_code == 202:  # 契约允许：同步窗口未完成 → 按 Retry-After 轮询
            pending_id = r.json()["data"]["recording"]["recordingId"]
            for _ in range(40):
                r = c.get(f"/api/recordings/{pending_id}")
                if r.status_code == 200:
                    break
                time.sleep(0.3)
        body = expect("标定后提交 → RecordingWithResult", r, RecordingWithResult)
        rec2_id = body["data"]["recording"]["recordingId"]

        sil_rec = upload(c, silence_bytes(3), "recording", "sil-rec.webm")
        r = c.post("/api/recordings", json={
            "audioId": sil_rec, "levelId": "L30",
            "submissionId": f"shape-sil-{time.time()}"})
        if r.status_code == 202:
            pending_id = r.json()["data"]["recording"]["recordingId"]
            for _ in range(40):
                r = c.get(f"/api/recordings/{pending_id}")
                if r.status_code == 200:
                    break
                time.sleep(0.3)
        body = expect("静音录音（质量提示不拦截）→ RecordingWithResult", r,
                      RecordingWithResult)
        check("  质量提示存在且仍有分数",
              bool(body["data"]["result"]["quality"]["signal"])
              and body["data"]["result"].get("score") is not None)

        # ---- 档案 / 学习 ----
        r = c.get("/api/me/recordings", params={"levelId": "L30"})
        expect("me/recordings → ArchiveListResponse", r, ArchiveListResponse)

        # learning-events 接口已下线：路由不存在 → 404
        r = c.post("/api/learning-events", json={"events": []})
        check("learning-events 已删除 → 404", r.status_code == 404,
              f"HTTP {r.status_code}")

        # 进度 = 由未删除检测录音派生（上文已给 L30 提交多条录音）
        r = c.get("/api/me/progress")
        body = expect("me/progress → MeProgress", r, MeProgress)
        for lv in body["data"]["levels"]:
            strict(ProgressLevel).model_validate(lv)
        check("  progress levels 逐项通过 ProgressLevel 严格校验", True)
        check("  L30 完成（由检测录音派生）",
              any(x["levelId"] == "L30" and x["completed"]
                  for x in body["data"]["levels"]))

        r = c.post("/api/feedback", json={"type": "clarity", "content": "很有帮助"})
        expect("feedback → FeedbackResponse", r, FeedbackResponse)
        r = c.post("/api/feedback/wishes", json={"content": "希望增加声调对比"})
        expect("feedback/wishes → FeedbackResponse", r, FeedbackResponse)

        r = c.delete(f"/api/recordings/{rec2_id}")
        expect("recordings/{id} DELETE → RecordingDeleted", r, RecordingDeleted)

        # ---- 清理 ----
        r = c.request("DELETE", "/api/me/account", json={"password": "password123"})
        expect("me/account DELETE → DeletedResponse", r, DeletedResponse)

    failed = [(n, d) for n, ok, d in results if not ok]
    print(f"\n==== {len(results) - len(failed)}/{len(results)} passed ====")
    for n, d in failed:
        print(f"FAILED: {n} — {d}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
