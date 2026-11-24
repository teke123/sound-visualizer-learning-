"""Gemini native multimodal structured output through the configured gateway."""
import base64
import json
from pathlib import Path
from urllib.parse import quote

import httpx

from .errors import LLMError, LLMSchemaError
from .schema import validate


def generate_json(system: str, text: str, audio: Path, image: bytes | None, *,
                  schema: dict, base_url: str, model: str, api_key: str, timeout: float):
    def inline(mime_type: str, data: bytes) -> dict:
        return {"inlineData": {"mimeType": mime_type,
                               "data": base64.b64encode(data).decode("ascii")}}

    parts = [{"text": text}, inline("audio/wav", audio.read_bytes())]
    if image:
        parts.append(inline("image/png", image))
    response = httpx.post(
        f"{base_url.rstrip('/')}/gemini/v1beta/models/{quote(model, safe='')}:generateContent",
        headers={"x-goog-api-key": api_key},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseMimeType": "application/json",
                                 "responseJsonSchema": schema},
        },
        timeout=timeout,
    )
    if not response.is_success:
        raise LLMError(f"Gemini returned HTTP {response.status_code}")
    payload = response.json()
    candidates = payload.get("candidates") or []
    if not candidates or candidates[0].get("finishReason") != "STOP":
        raise LLMSchemaError("模型未完整返回结构化发音建议")
    parts = candidates[0].get("content", {}).get("parts", [])
    result = validate(json.loads("".join(p.get("text", "") for p in parts if not p.get("thought"))), schema)
    for item in result.values():
        if item["status"] == "explained" and not all(
            item[field].strip() for field in ("analysis", "nextAction")
        ):
            raise LLMSchemaError("模型返回空白发音建议")
    return result
