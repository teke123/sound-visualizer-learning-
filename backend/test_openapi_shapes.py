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
import sys
import time
import wave
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from pydantic import ConfigDict, ValidationError

sys.path.insert(0, str(Path(__file__).parent))
import main as backend_main  # noqa: E402
from app import config  # noqa: E402
from app.acoustics import transcode  # noqa: E402
from app.api.schemas import (  # noqa: E402
    ArchiveCompareResponse, ArticleCategoriesResponse, ArticleDetail, ArticlesResponse,
    AssessmentResult, AudioUploadResponse, AuthLoginResponse, ArchiveListResponse,
    CalibrationFailResult, CalibrationOkResult, DeletedResponse, FeedbackResponse,
    F0Response, FormantsResponse, HealthData, LearningEventsResponse, LevelDetail,
    LevelsResponse, MeContext, MeProgress, PitchCalibrationInfo, ProfileResponse,
    RecordingDeleted, RecordingWithResult, RegisterResponse, SearchResponse,
    WishResponse, Envelope,
)
from app.pinyin_utils import expected_syllables  # noqa: E402

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
    return wav_bytes(np.zeros(n, dtype=np.float32)
                     + np.random.default_rng(1).standard_normal(n) * 1e-4)


def corpus_wav_bytes(text: str, speaker: str = "MV1") -> bytes:
    """从真人标准音节语料库读取单音节或多音节并拼接为 16kHz 单声道 WAV 字节。"""
    corpus = config.CORPUS_DIR
    if corpus is None or not corpus.is_dir():
        raise RuntimeError("请先在 .env 或环境变量配置 CORPUS_DIR")
    syls = expected_syllables(text)
    chunks: list[np.ndarray] = []
    gap = np.zeros(int(0.08 * 16000), dtype=np.float32)
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
    return wav_bytes(np.concatenate(chunks) if chunks else np.zeros(16000, dtype=np.float32))


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
        check("  levels 共 30 关", len(body["data"]["levels"]) == 30,
              str(len(body["data"].get("levels", []))))

        r = c.get("/api/levels/L01")
        body = expect("levels/L01 → LevelDetail", r, LevelDetail)
        check("  L01 含 quiz 与 practice",
              len(body["data"].get("quizzes") or []) > 0
              and len(body["data"].get("practice") or []) > 0)

        r = c.get("/api/search", params={"q": "妈"})
        body = expect("search 妈 → SearchResponse", r, SearchResponse)
        check("  search 妈 命中 L30", body["data"]["results"][0]["id"] == "L30",
              str(body["data"]["results"][:1]))
        r = c.get("/api/search", params={"q": "123"})
        body = expect("search 无命中 → SearchResponse", r, SearchResponse)
        check("  无命中时 near 兜底非空（前端相近关数据源）",
              len(body["data"]["near"]) > 0, str(body["data"]["near"]))

        r = c.get("/api/article-categories")
        expect("article-categories → ArticleCategoriesResponse", r, ArticleCategoriesResponse)
        r = c.get("/api/articles")
        body = expect("articles → ArticlesResponse", r, ArticlesResponse)
        slug = body["data"]["articles"][0]["slug"]
        r = c.get(f"/api/articles/{slug}")
        expect(f"articles/{slug} → ArticleDetail", r, ArticleDetail)

        # ---- 未登录保护 ----
        r = c.get("/api/me/recordings")
        expect("me/recordings 未登录 → 401", r, None, status=401, code="AUTH_REQUIRED")

        # ---- 账号：注册 / 登录 ----
        username = f"shape用户_{int(time.time())}"
        r = c.post("/api/auth/register", json={"username": username,
                                               "password": "password123",
                                               "dialectBackground": "yue"})
        body = expect("auth/register（带方言背景）→ RegisterResponse", r, RegisterResponse)
        check("  注册回显 dialectBackground=yue",
              body["data"].get("dialectBackground") == "yue")
        r = c.post("/api/auth/register", json={"username": f"{username}x",
                                               "password": "password123",
                                               "dialectBackground": "cantonese"})
        expect("auth/register 方言代码非法 → 422", r, None, status=422,
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

        r = c.patch("/api/me/profile", json={"dialectBackground": "wu"})
        body = expect("PATCH me/profile → ProfileResponse", r, ProfileResponse)
        check("  profile 更新为 wu", body["data"]["dialectBackground"] == "wu")
        r = c.patch("/api/me/profile", json={"dialectBackground": None})
        body = expect("PATCH me/profile 清除 → ProfileResponse", r, ProfileResponse)
        check("  profile 清除为空", body["data"]["dialectBackground"] is None)
        r = c.patch("/api/me/profile", json={"dialectBackground": "wu"})
        body = expect("PATCH me/profile（恢复）→ ProfileResponse", r, ProfileResponse)
        check("  profile 恢复为 wu", body["data"]["dialectBackground"] == "wu")

        # ---- 未标定直接检测（D-20） ----
        rec_audio = upload(c, corpus_wav_bytes("妈", "MV1"),
                           "recording", "rec.webm")
        r = c.post("/api/recordings", json={
            "audioId": rec_audio, "levelId": "L30",
            "submissionId": f"shape-{time.time()}"})
        body = expect("recordings POST（未标定）→ RecordingWithResult", r, RecordingWithResult)
        rec_id = body["data"]["recording"]["recordingId"]
        check("  结果含 quality/curve", bool(body["data"]["result"]["quality"])
              and body["data"]["result"]["curve"] is not None)
        strict(AssessmentResult).model_validate(body["data"]["result"])
        check("  result 可单独通过 AssessmentResult 严格校验", True)

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
        vot_audio = upload(c, corpus_wav_bytes(vot_level["representativeChar"], "MV1"),
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
        body = expect("声母关提交（VOT）→ RecordingWithResult", r, RecordingWithResult)
        vot = body["data"]["result"].get("vot") or {}
        check("  result.vot 存在且 status=ok", vot.get("status") == "ok",
              str(vot)[:200])
        check("  vot.user/reference 含 onsetSec/voicingOnsetSec/votMs 且数值>=0",
              all(
                  isinstance(vot.get(side, {}).get(k), (int, float))
                  and vot[side][k] >= 0
                  and vot[side]["votMs"] > 0
                  for side in ("user", "reference")
                  for k in ("onsetSec", "voicingOnsetSec", "votMs")
              ), str(vot)[:200])
        check("  vot.referenceMediaId 非空", bool(vot.get("referenceMediaId")))

        # ---- 标定 ----
        r = c.get("/api/pitch-calibration")
        expect("pitch-calibration GET（未标定）→ PitchCalibrationInfo", r,
               PitchCalibrationInfo)

        cal_id = upload(c, corpus_wav_bytes("妈坡车米布女妈麻马骂", "MV1"),
                        "calibration", "cal.webm")
        r = c.post("/api/pitch-calibration", json={"audioId": cal_id})
        body = expect("pitch-calibration POST → CalibrationOkResult", r, CalibrationOkResult)
        check("  标定结果 status=personal", body["data"]["status"] == "personal")

        r = c.get("/api/pitch-calibration")
        body = expect("pitch-calibration GET（已标定）→ PitchCalibrationInfo", r,
                      PitchCalibrationInfo)
        check("  已标定带 pitchRange", bool(body["data"].get("pitchRange")))

        sil_cal = upload(c, silence_bytes(3), "calibration", "sil-cal.webm")
        r = c.post("/api/pitch-calibration", json={"audioId": sil_cal})
        expect("pitch-calibration 静音 → CalibrationFailResult", r,
               CalibrationFailResult, code="CALIBRATION_FAIL")

        # ---- 标定后提交 + 质量提示不拦截 ----
        rec2_audio = upload(c, corpus_wav_bytes("妈", "MV1"),
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
        r = c.get("/api/me/recordings/compare", params={"a": rec_id, "b": rec2_id})
        expect("me/recordings/compare → ArchiveCompareResponse", r,
               ArchiveCompareResponse)

        d30 = c.get("/api/levels/L30").json()["data"]
        events = [{"eventId": f"shape-quiz-{q['id']}", "levelId": "L30",
                   "kind": "listen_quiz",
                   "detail": {"questionId": q["id"],
                              "choiceIndex": q["answerIndex"]}}
                  for q in d30["quizzes"]]
        events += [{"eventId": f"shape-step-{p['id']}", "levelId": "L30",
                    "kind": "practice_done", "detail": {"stepId": p["id"]}}
                   for p in d30["practice"]]
        r = c.post("/api/learning-events", json={"events": events})
        expect("learning-events → LearningEventsResponse", r, LearningEventsResponse)
        r = c.get("/api/me/progress")
        body = expect("me/progress → MeProgress", r, MeProgress)
        check("  L30 完成", any(x["levelId"] == "L30" and x["completed"]
                                for x in body["data"]["levels"]))

        r = c.post("/api/feedback", json={"type": "clarity", "content": "很有帮助"})
        expect("feedback → FeedbackResponse", r, FeedbackResponse)
        r = c.post("/api/wishes", json={"content": "希望增加声调对比"})
        expect("wishes → WishResponse", r, WishResponse)

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
