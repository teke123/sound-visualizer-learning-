# -*- coding: utf-8 -*-
"""结构化输出：JSON Schema 规范化、response_format 构造、解析与校验。

要点：
- OpenAI 的 ``json_schema`` + ``strict`` 要求每个 object 都有
  ``additionalProperties: false`` 且 ``required`` 覆盖全部字段，否则直接 400；
  这里自动补齐，并判断能否真的上 strict。
- 校验用调用方给的**原始** schema（宽松），不用补齐后的版本。
"""
from __future__ import annotations

import copy
import json
import re
from typing import Any

from .errors import LLMSchemaError

try:  # 运行时依赖，requirements.txt 已声明
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    Draft202012Validator = None  # type: ignore[assignment]

_FENCE_RE = re.compile(r"^\s*```(?:json|JSON)?\s*(.*?)\s*```\s*$", re.S)


class _Compat:
    """记录 schema 是否满足 OpenAI strict 的硬性要求。"""

    def __init__(self) -> None:
        self.strict_ok = True


def _normalize(node: Any, state: _Compat) -> Any:
    if isinstance(node, list):
        return [_normalize(item, state) for item in node]
    if not isinstance(node, dict):
        return node

    out = dict(node)

    props = out.get("properties")
    if isinstance(props, dict) and props:
        new_props = {key: _normalize(value, state) for key, value in props.items()}
        out["properties"] = new_props
        out.setdefault("type", "object")
        required = out.get("required")
        if required is None:
            out["required"] = list(new_props.keys())
        elif set(required) != set(new_props.keys()):
            # 有可选字段 → 不能上 strict（strict 强制全字段必填）
            state.strict_ok = False
        out.setdefault("additionalProperties", False)
        if out.get("additionalProperties") is not False:
            state.strict_ok = False

    if "items" in out:
        out["items"] = _normalize(out["items"], state)
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        if key in out:
            out[key] = _normalize(out[key], state)
    for key in ("$defs", "definitions"):
        if isinstance(out.get(key), dict):
            out[key] = {name: _normalize(sub, state) for name, sub in out[key].items()}
    return out


def normalize_schema(schema: dict) -> tuple[dict, bool]:
    """返回 (补齐后的 schema, 是否可上 strict)。"""
    state = _Compat()
    return _normalize(copy.deepcopy(schema), state), state.strict_ok


def make_response_format(
    schema: dict, *, name: str = "llm_response", allow_strict: bool = True
) -> dict:
    """构造 chat.completions 的 response_format（json_schema 模式）。"""
    normalized, strict_ok = normalize_schema(schema)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "schema": normalized,
            "strict": bool(strict_ok and allow_strict),
        },
    }


def build_hint(schema: dict, *, extra: str | None = None) -> str:
    """给 json_object / 纯文本模式用的 schema 说明，附加到 system 消息。"""
    body = json.dumps(schema, ensure_ascii=False, indent=2)
    text = (
        "你必须只输出一个合法的 JSON（不要 Markdown 代码块、不要任何解释文字），"
        "并且严格符合下面的 JSON Schema：\n"
        f"{body}"
    )
    if extra:
        text += "\n" + extra
    return text


def parse_json(text: str) -> Any:
    """从模型回复里取出 JSON 对象/数组；容忍 ```json 围栏与前后废话。"""
    if text is None:
        raise LLMSchemaError("模型返回为空，无法解析 JSON")
    raw = text.strip()
    if not raw:
        raise LLMSchemaError("模型返回为空字符串，无法解析 JSON")

    fence = _FENCE_RE.match(raw)
    if fence:
        raw = fence.group(1).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 兜底：截取第一个 { 或 [ 到最后一个配对的 } 或 ]
    starts = [i for i in (raw.find("{"), raw.find("[")) if i != -1]
    if starts:
        start = min(starts)
        closer = "}" if raw[start] == "{" else "]"
        end = raw.rfind(closer)
        if end > start:
            snippet = raw[start : end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError as exc:
                raise LLMSchemaError(f"返回内容不是合法 JSON：{exc.msg}（位置 {exc.pos}）") from exc

    raise LLMSchemaError(f"返回内容不是合法 JSON：{raw[:120]!r}")


def validate(obj: Any, schema: dict) -> Any:
    """按原始 schema 校验；不合法则抛 LLMSchemaError（带首个错误路径）。"""
    if Draft202012Validator is None:  # pragma: no cover
        raise LLMSchemaError("缺少 jsonschema 依赖，请 pip install -r backend/requirements.txt")

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(obj), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        path = "/".join(str(p) for p in first.absolute_path) or "<root>"
        raise LLMSchemaError(f"JSON 不符合 schema：{path} → {first.message}")
    return obj


def validate_schema_definition(schema: dict) -> None:
    """确认调用方给的 schema 本身是合法的 JSON Schema。"""
    if not isinstance(schema, dict):
        raise LLMSchemaError("schema 必须是 dict（JSON Schema 对象）")
    if Draft202012Validator is None:  # pragma: no cover
        return
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # noqa: BLE001 - jsonschema 抛 SchemaError
        raise LLMSchemaError(f"schema 定义不合法：{exc}") from exc
