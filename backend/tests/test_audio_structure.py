"""验证接口状态、诊断调用、音频解码与评分输出。"""
import importlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from backend.audio.decoding import decode_audio
from backend.audio.models import AcousticFeatures, ScoringEvidence, ScoringReference
from backend.audio.quality import analyze_audio_quality
from backend.audio.scoring import assess_pronunciation, tone_shape_score


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # 主应用初始化数据库前切换到临时库，避免修改开发数据。
    from backend import database

    previous_path = database.DB_PATH
    database.DB_PATH = str(tmp_path_factory.mktemp("database") / "test.db")
    try:
        main = importlib.import_module("backend.main")
        with TestClient(main.app) as test_client:
            yield test_client
    finally:
        database.DB_PATH = previous_path


def test_old_analysis_endpoint_is_removed(client):
    assert client.post("/api/audio/analyze").status_code == 404
    assert "/api/audio/analyze" not in client.get("/openapi.json").json()["paths"]


@pytest.mark.parametrize("endpoint", ["quality", "features", "score"])
def test_new_endpoints_are_explicit_placeholders(client, endpoint):
    response = client.post(f"/api/audio/{endpoint}")
    assert response.status_code == 501
    assert "尚未实现" in response.json()["detail"]


def test_asr_routes_share_b_model_manager(client, monkeypatch):
    from backend.routes import asr

    class ModelManager:
        def status(self):
            return {"loaded": False, "model_id": "test-model"}

        def load(self, model_id, force):
            return {"ok": True, "model_id": model_id, "force": force}

    monkeypatch.setattr(asr, "get_analyzer", lambda: ModelManager())
    assert client.get("/api/asr/status").json()["model_id"] == "test-model"
    response = client.post("/api/asr/load", json={"model_id": "selected", "force": True})
    assert response.json()["model_id"] == "selected"
    assert response.json()["force"] is True
    assert client.post("/api/asr/load").status_code == 200
    assert client.get("/api/levels").json()["count"] == 30


def test_diagnosis_reaches_b_and_preserves_experiment_records(client, monkeypatch, tmp_path):
    from backend.audio import diagnosis

    monkeypatch.setattr(diagnosis, "EXPERIMENT_DIR", tmp_path)
    calls = []

    def diagnose(path, level_id, target_pinyin):
        calls.append((Path(path).read_bytes(), level_id, target_pinyin))
        return {"model_id": "test-model", "level_id": level_id,
                "verdict": {"code": "uncertain"}, "detected": None}

    monkeypatch.setattr(diagnosis, "diagnose", diagnose)
    response = client.post(
        "/api/asr/diagnose", data={"level_id": "L30"},
        files={"file": ("录音.wav", b"test-audio", "audio/wav")},
    )
    assert response.status_code == 200
    assert response.json()["verdict"]["code"] == "uncertain"
    assert calls == [(b"test-audio", "L30", None)]
    record = json.loads((tmp_path / "experiment_log.jsonl").read_text(encoding="utf-8"))
    assert record["verdict"] == "uncertain"
    assert (tmp_path / "audio" / record["audio"]).read_bytes() == b"test-audio"


@pytest.mark.parametrize("data", [{}, {"level_id": "L99"}])
def test_invalid_target_does_not_load_model_or_archive_audio(client, monkeypatch, data):
    from backend.routes import asr

    def unexpected_call(*args, **kwargs):
        pytest.fail("无效目标不应进入模型推理")

    monkeypatch.setattr(asr, "diagnose_upload", unexpected_call)
    response = client.post("/api/asr/diagnose", data=data,
                           files={"file": ("a.wav", b"audio", "audio/wav")})
    assert response.status_code == 422


def test_decode_preserves_sample_rate_amplitude_and_silence(tmp_path):
    stereo = np.zeros((4410, 2), dtype=np.float32)
    stereo[1000:2000] = [0.2, 0.4]
    path = tmp_path / "stereo.wav"
    sf.write(path, stereo, 44100, subtype="FLOAT")
    decoded = decode_audio(path)
    assert decoded.sample_rate == 44100
    np.testing.assert_allclose(decoded.samples, stereo.mean(axis=1))


def test_browser_webm_uses_ffmpeg_fallback(tmp_path):
    import imageio_ffmpeg

    sample = Path(__file__).resolve().parents[2] / "audio/tts_raw/L01_a.wav"
    webm = tmp_path / "browser.webm"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(sample),
                    "-c:a", "libopus", str(webm)], capture_output=True, check=True)
    decoded = decode_audio(webm)
    assert decoded.sample_rate == 16000
    assert decoded.samples.ndim == 1
    assert decoded.samples.size > 1000
    assert np.isfinite(decoded.samples).all()


def test_quality_still_rejects_silence():
    result = analyze_audio_quality(np.zeros(16000, dtype=np.float32), 16000)
    assert result["passed"] is False
    assert {item["key"] for item in result["items"]} == {
        "volume", "noise", "clipping", "duration", "silence",
    }


def test_existing_score_formula_is_preserved():
    features = AcousticFeatures(f0=[190, 200, 210, 0], f1=[], f2=[], energy=[],
                                duration=1, sample_rate=16000, mfcc=[])
    result = assess_pronunciation(
        features, ScoringEvidence(tone_score=80, phoneme_score=90),
        ScoringReference(f0_mean=200, f0_std=10), fluency=85,
    )
    assert result.score == 86.9
    assert result.accuracy == 91.7
    assert result.fluency == 85
    assert result.pronunciation == 87.3


def test_known_tone_rule_is_not_silently_changed():
    # 这是已知算法缺陷的现状记录；修算法时应明确修改此回归用例。
    assert tone_shape_score(np.linspace(100, 300, 100), 1) == 50.0


def test_acoustic_features_are_real_and_do_not_contain_asr_fields():
    from backend.audio.acoustics import analyze_audio

    sample = Path(__file__).resolve().parents[2] / "audio/tts_raw/L01_a.wav"
    decoded = decode_audio(sample)
    result = analyze_audio(decoded.samples, decoded.sample_rate)
    assert result.duration == pytest.approx(1.2)
    assert len(result.f0) > 0
    assert len(result.voiced_flag) == len(result.f0)
    assert len(result.f1) == len(result.f2) > 0
    assert "recognized_text" not in result.model_dump()
    json.dumps(result.model_dump(), allow_nan=False)
