import json
from unittest.mock import Mock

import httpx
import pytest

from app.detection import pronunciation_advice as advice
from app.llm import gemini
from app.llm.errors import LLMSchemaError
from app.scoring.provider import ProviderResult, SyllableEval


def provider(*codes):
    return ProviderResult("xfyun-ise-1.0", syllables=[
        SyllableEval(text=ch, detail={"phones": [
            {"part": "initial", "perrMsg": initial},
            {"part": "final", "perrMsg": final},
        ]})
        for ch, (initial, final) in zip("妈妈", codes)
    ])


DETECTION = {"evaluationText": "妈妈", "evaluationPinyin": "ma1|ma5"}


def test_plan_uses_explicit_diagnostics_and_preserves_repeated_errors():
    assert advice.plan_request(provider((0, 0), (0, 0)), DETECTION, []) is None
    broken = provider((None, 2), (1, 3))
    broken.syllables[1].detail["wordDpMessage"] = 128
    plan = advice.plan_request(broken, DETECTION, ["发音要领"])
    assert list(plan.targets) == ["s0_tone"]
    assert plan.context["syllables"][0]["passed"] == ["final"]
    assert plan.context["syllables"][1]["passed"] == []
    mixed = advice.plan_request(provider((0, 2), (0, 2)), DETECTION, [])
    assert list(mixed.targets) == ["s0_tone", "s1_tone"]
    zero = provider((1, 2))
    zero.syllables[0].text = "啊"
    zero.syllables[0].detail["phones"][0]["content"] = "_a"
    plan = advice.plan_request(zero, {"evaluationText": "啊", "evaluationPinyin": "a4"}, [])
    assert list(plan.targets) == ["s0_tone"]
    assert plan.context["syllables"][0]["passed"] == ["final"]


def test_native_request_and_abstention_are_validated(monkeypatch, tmp_path):
    wav = tmp_path / "recording.wav"
    wav.write_bytes(b"RIFF sample")
    plan = advice.plan_request(provider((0, 2), (0, 2)), DETECTION, ["发音要领"])
    output = {
        "s0_tone": {"status": "explained", "analysis": "音高末尾开始下降。", "nextAction": "试着保持平稳。"},
        "s1_tone": {"status": "unable_to_assess", "reasonCode": "conflicting_evidence"},
    }

    def reply():
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP",
            "content": {"parts": [{"text": json.dumps(output)}]}}]})

    post = Mock(side_effect=lambda *args, **kwargs: reply())
    monkeypatch.setattr(gemini.httpx, "post", post)

    def call():
        return gemini.generate_json(advice.SYSTEM_PROMPT, json.dumps(plan.context), wav, b"PNG",
            schema=advice.response_schema(plan.targets), base_url="https://api.inferera.com",
            model="gemini-4-hydrogen", api_key="test", timeout=4)

    assert call() == output
    post.assert_called_once()
    assert post.call_args.args[0].endswith("/gemini/v1beta/models/gemini-4-hydrogen:generateContent")
    payload = post.call_args.kwargs["json"]
    assert [p["inlineData"]["mimeType"] for p in payload["contents"][0]["parts"][1:]] == [
        "audio/wav", "image/png"]
    assert payload["generationConfig"]["responseJsonSchema"]["required"] == ["s0_tone", "s1_tone"]
    output["s1_tone"]["analysis"] = "不应有分析"
    with pytest.raises(LLMSchemaError):
        call()
