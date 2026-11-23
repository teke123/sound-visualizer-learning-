# -*- coding: utf-8 -*-
"""LLM 统一调用入口（仅 OpenAI 协议，后端内部使用）。

三个函数对应三种返回形态：

- :func:`chat`         → ``str``                 非流式，纯文本
- :func:`chat_stream`  → ``Iterator[str]``       流式增量文本（上层可包 SSE）
- :func:`chat_json`    → ``dict | list``         传 schema，返回已校验的 Python 对象

示例::

    from app.llm import chat, chat_json

    print(chat("你是声学助教", "解释一下 VOT"))
    diag = chat_json("你是声学诊断助手", "诊断这段发音", schema={...})
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable, Iterator, Sequence

import openai
from openai import OpenAI

from .config import LLMConfig, resolve
from .content import build_messages
from .errors import LLMError, LLMSchemaError
from .schema import (
    build_hint,
    make_response_format,
    parse_json,
    validate,
    validate_schema_definition,
)

PathLike = Any

# 端点拒绝 response_format 时的报错关键词（用于降级判断，不是精确匹配）
_FORMAT_REJECT_WORDS = (
    "response_format",
    "json_schema",
    "structured",
    "unknown field",
    "unrecognized",
    "not support",
    "unsupported",
    "invalid format",
    "invalid_request",
)

_MODE_ORDER = ("json_schema", "json_object", "text")


@lru_cache(maxsize=8)
def _client_cached(base_url: str, api_key: str, timeout: float) -> OpenAI:
    return OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0)


def _client(cfg: LLMConfig) -> OpenAI:
    return _client_cached(cfg.base_url, cfg.api_key, cfg.timeout)


def _wrap(exc: Exception, cfg: LLMConfig, action: str) -> LLMError:
    """把 SDK 异常翻译成中文可读错误，且绝不带出 API Key。"""
    detail = getattr(exc, "message", None) or str(exc)
    status = getattr(exc, "status_code", None)
    head = f"{action}失败（profile={cfg.profile}, model={cfg.model}, base_url={cfg.base_url}"
    if status:
        head += f", HTTP {status}"
    head += "）"
    if isinstance(exc, openai.APIConnectionError):
        return LLMError(f"{head}：无法连接该地址，请检查服务是否启动 / BaseURL 是否写错。{detail}")
    if isinstance(exc, openai.AuthenticationError):
        return LLMError(f"{head}：API Key 无效或未授权（Key 已脱敏：{cfg.masked_key}）。{detail}")
    if isinstance(exc, openai.NotFoundError):
        return LLMError(f"{head}：模型不存在或接口路径不对，确认 BaseURL 是否包含 /v1。{detail}")
    return LLMError(f"{head}：{detail}")


def _is_format_rejection(exc: Exception) -> bool:
    """判断 4xx 是否由 response_format 不被支持引起（用于降级）。"""
    status = getattr(exc, "status_code", None)
    if status not in (400, 404, 422, 500):
        return False
    text = (getattr(exc, "message", None) or str(exc)).lower()
    return any(word in text for word in _FORMAT_REJECT_WORDS)


def _payload(
    cfg: LLMConfig,
    messages: list[dict],
    *,
    stream: bool,
    response_format: dict | None = None,
) -> dict:
    kwargs: dict[str, Any] = {
        "model": cfg.model,
        "messages": messages,
        "temperature": cfg.temperature,
        "stream": stream,
    }
    if cfg.max_tokens:
        kwargs["max_tokens"] = cfg.max_tokens
    if response_format is not None:
        kwargs["response_format"] = response_format
    return kwargs


def _prepare(
    system, user, images, audios, history, image_max_side,
    profile, model, base_url, api_key, temperature, max_tokens, timeout,
) -> tuple[LLMConfig, list[dict]]:
    cfg = resolve(
        profile=profile,
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    side = image_max_side if image_max_side is not None else cfg.image_max_side
    messages = build_messages(
        system,
        user,
        images=images,
        audios=audios,
        history=history,
        image_max_side=side,
    )
    return cfg, messages


def chat(
    system: str | None = None,
    user: str | None = None,
    *,
    images: PathLike | Iterable[PathLike] | None = None,
    audios: PathLike | Iterable[PathLike] | None = None,
    history: Sequence[dict] | None = None,
    profile: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float | None = None,
    image_max_side: int | None = None,
) -> str:
    """非流式调用，返回完整文本。"""
    cfg, messages = _prepare(
        system, user, images, audios, history, image_max_side,
        profile, model, base_url, api_key, temperature, max_tokens, timeout,
    )
    try:
        resp = _client(cfg).chat.completions.create(**_payload(cfg, messages, stream=False))
    except openai.OpenAIError as exc:
        raise _wrap(exc, cfg, "LLM 调用") from exc
    if not resp.choices:
        return ""
    return resp.choices[0].message.content or ""


def chat_stream(
    system: str | None = None,
    user: str | None = None,
    *,
    images: PathLike | Iterable[PathLike] | None = None,
    audios: PathLike | Iterable[PathLike] | None = None,
    history: Sequence[dict] | None = None,
    profile: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float | None = None,
    image_max_side: int | None = None,
) -> Iterator[str]:
    """流式调用，返回增量文本生成器。

    配置与多模态文件在**调用时**即校验（错误立即抛出，不会等到迭代）；
    网络请求在首次迭代时才发出，stream 在迭代结束后自动关闭。

    上层包 SSE 时直接::

        for piece in chat_stream(...):
            yield f"data: {json.dumps({'content': piece}, ensure_ascii=False)}\\n\\n"
    """
    cfg, messages = _prepare(
        system, user, images, audios, history, image_max_side,
        profile, model, base_url, api_key, temperature, max_tokens, timeout,
    )
    client = _client(cfg)

    def _gen() -> Iterator[str]:
        try:
            stream = client.chat.completions.create(**_payload(cfg, messages, stream=True))
        except openai.OpenAIError as exc:
            raise _wrap(exc, cfg, "LLM 流式调用") from exc
        try:
            for chunk in stream:
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                piece = getattr(choices[0].delta, "content", None)
                if piece:
                    yield piece
        except openai.OpenAIError as exc:
            raise _wrap(exc, cfg, "LLM 流式读取") from exc
        finally:
            stream.close()

    return _gen()


def _with_hint(messages: list[dict], schema: dict) -> list[dict]:
    """把 schema 说明塞进 system（json_object / 纯文本兜底模式用）。"""
    hint = build_hint(schema)
    out = [dict(m) for m in messages]
    if out and out[0].get("role") == "system":
        out[0]["content"] = f"{out[0].get('content', '')}\n\n{hint}".strip()
    else:
        out.insert(0, {"role": "system", "content": hint})
    return out


def chat_json(
    system: str | None = None,
    user: str | None = None,
    *,
    schema: dict,
    images: PathLike | Iterable[PathLike] | None = None,
    audios: PathLike | Iterable[PathLike] | None = None,
    history: Sequence[dict] | None = None,
    profile: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float | None = None,
    image_max_side: int | None = None,
    max_retries: int | None = None,
    allow_strict: bool | None = None,
) -> Any:
    """带 JSON Schema 的结构化调用，返回已校验的 Python 对象（dict / list）。

    兼容性降级链（逐级下探，直到成功）：

    1. ``response_format={"type": "json_schema"}``（端点支持时的最优解）
    2. ``response_format={"type": "json_object"}`` + system 内嵌 schema
    3. 纯文本 + system 内嵌 schema

    解析或校验失败时，把错误回灌给模型重试，最多 ``max_retries`` 次
   （不传时取 ``LLM_<P>_JSON_MAX_RETRIES``，默认 1；``allow_strict`` 同理
    取 ``LLM_<P>_JSON_ALLOW_STRICT``，默认 true）。
    """
    validate_schema_definition(schema)
    cfg, messages = _prepare(
        system, user, images, audios, history, image_max_side,
        profile, model, base_url, api_key, temperature, max_tokens, timeout,
    )
    client = _client(cfg)
    retries = max_retries if max_retries is not None else cfg.json_max_retries
    strict = allow_strict if allow_strict is not None else cfg.json_allow_strict
    json_schema_fmt = make_response_format(schema, allow_strict=strict)

    last_error: LLMSchemaError | None = None
    messages_now = messages

    for attempt in range(retries + 1):
        accepted_any = False
        for mode in _MODE_ORDER:
            fmt = json_schema_fmt if mode == "json_schema" else (
                {"type": "json_object"} if mode == "json_object" else None
            )
            body = messages_now if mode == "json_schema" else _with_hint(messages_now, schema)

            try:
                resp = client.chat.completions.create(
                    **_payload(cfg, body, stream=False, response_format=fmt)
                )
            except openai.OpenAIError as exc:
                if _is_format_rejection(exc):
                    continue  # 该端点不认这种 response_format → 降级
                raise _wrap(exc, cfg, f"LLM 结构化调用（{mode} 模式）") from exc

            accepted_any = True
            content = (resp.choices[0].message.content if resp.choices else "") or ""
            try:
                return validate(parse_json(content), schema)
            except LLMSchemaError as exc:
                last_error = exc
                messages_now = body + [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            f"上面的输出不符合要求：{exc}。"
                            "请只重新输出一个修正后的 JSON，不要解释、不要 Markdown 代码块。"
                        ),
                    },
                ]
                break  # 换下一次 attempt 重试

        if not accepted_any:
            raise LLMError(
                f"该端点不支持结构化输出（profile={cfg.profile}, model={cfg.model}）："
                "json_schema / json_object / 纯文本三种方式均被拒绝，请换模型或换端点。"
            )

    assert last_error is not None
    raise last_error


def is_available(profile: str | None = None, timeout: float = 3.0) -> bool:
    """轻量可用性探测（GET /models）。供上层决定是否降级，不抛异常。"""
    try:
        cfg = resolve(profile=profile, timeout=timeout)
        _client(cfg).models.list()
        return True
    except Exception:  # noqa: BLE001 - 探测失败一律视作不可用
        return False
