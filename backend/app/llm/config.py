# -*- coding: utf-8 -*-
"""LLM 配置解析（场景配置档 / profile）。

设计目标：业务代码不写死模型，只写 ``profile="vision"``；换模型/换平台只改 .env。

环境变量命名（``<P>`` = profile 名大写、``-``/``.`` 转 ``_``）::

    LLM_PROFILE           可选，不传 profile 参数时使用的默认档名（默认 "default"）
    LLM_<P>_BASE_URL      例 https://api.openai.com/v1
    LLM_<P>_API_KEY       例 sk-xxx（本地服务可留空）
    LLM_<P>_MODEL         例 gpt-4o-mini
    LLM_<P>_TEMPERATURE   可选，默认 0.7
    LLM_<P>_MAX_TOKENS    可选，不填则不下发
    LLM_<P>_TIMEOUT       可选，秒，默认 120
    LLM_<P>_IMAGE_MAX_SIDE          可选，图像降采样最长边（像素），不填则不降采样
    LLM_<P>_JSON_MAX_RETRIES        可选，结构化输出校验失败重试次数，默认 1
    LLM_<P>_JSON_ALLOW_STRICT       可选，是否允许 json_schema strict 模式，默认 true

回退规则：若 profile 非 default 且某项未配置，则回退到 ``LLM_DEFAULT_<X>``；
显式传参（model / base_url / api_key ...）优先级最高。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .errors import LLMConfigError

DEFAULT_PROFILE = "default"

# backend/app/llm/config.py -> backend/
_BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = _BACKEND_DIR / ".env"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal"}
_PLACEHOLDER_KEY = "not-needed"

_dotenv_loaded = False


def load_env(path: str | os.PathLike | None = None, override: bool = False) -> bool:
    """加载 backend/.env（系统环境变量优先）。返回是否真的读到了文件。

    可重复调用；测试里想换 env 文件时传 path 即可。
    """
    global _dotenv_loaded
    target = Path(path) if path else ENV_FILE
    if not target.is_file():
        return False
    try:
        from dotenv import load_dotenv
    except ImportError as exc:  # pragma: no cover - 依赖缺失时给出可读提示
        raise LLMConfigError(
            "缺少 python-dotenv，请先 pip install -r backend/requirements.txt"
        ) from exc
    load_dotenv(target, override=override)
    _dotenv_loaded = True
    return True


def _ensure_env_loaded() -> None:
    if not _dotenv_loaded:
        load_env()


def reset_env_cache() -> None:
    """清掉「.env 已加载」标记，下次 resolve 会重新读取 .env。

    主要给测试用：如果测试清空/回滚了 os.environ，需要调用它，
    否则 .env 里的值不会再次被读回。
    """
    global _dotenv_loaded
    _dotenv_loaded = False


def _prefix(profile: str) -> str:
    return "LLM_" + profile.upper().replace("-", "_").replace(".", "_")


def _raw(profile: str, field: str) -> str:
    """取 ``LLM_<P>_<FIELD>``，缺失时回退 ``LLM_DEFAULT_<FIELD>``。"""
    value = os.environ.get(f"{_prefix(profile)}_{field}", "").strip()
    if value:
        return value
    if profile != DEFAULT_PROFILE:
        return os.environ.get(f"LLM_DEFAULT_{field}", "").strip()
    return ""


def _is_local(base_url: str) -> bool:
    try:
        return (urlparse(base_url).hostname or "").lower() in _LOCAL_HOSTS
    except ValueError:
        return False


@dataclass(frozen=True)
class LLMConfig:
    """一次调用用到的完整配置。"""

    profile: str
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int | None = None
    timeout: float = 120.0
    image_max_side: int | None = None
    json_max_retries: int = 1
    json_allow_strict: bool = True

    @property
    def masked_key(self) -> str:
        """用于日志/报错的脱敏 Key。"""
        if not self.api_key or self.api_key == _PLACEHOLDER_KEY:
            return self.api_key or "<empty>"
        if len(self.api_key) <= 8:
            return self.api_key[:2] + "***"
        return f"{self.api_key[:5]}***{self.api_key[-4:]}"


def resolve(
    profile: str | None = None,
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float | None = None,
    image_max_side: int | None = None,
    json_max_retries: int | None = None,
    json_allow_strict: bool | None = None,
) -> LLMConfig:
    """解析出一次调用要用的配置；显式传参 > profile env > default env。"""
    _ensure_env_loaded()

    p = (profile or os.environ.get("LLM_PROFILE", "").strip() or DEFAULT_PROFILE)
    env_prefix = _prefix(p)

    resolved_base = (base_url or _raw(p, "BASE_URL") or "").rstrip("/")
    resolved_model = model or _raw(p, "MODEL")
    resolved_key = api_key if api_key is not None else _raw(p, "API_KEY")

    if not resolved_base:
        raise LLMConfigError(
            f"profile '{p}' 未配置 base_url：请在 backend/.env 设置 "
            f"{env_prefix}_BASE_URL（或回退的 LLM_DEFAULT_BASE_URL）"
        )
    if not resolved_model:
        raise LLMConfigError(
            f"profile '{p}' 未配置 model：请在 backend/.env 设置 {env_prefix}_MODEL"
        )
    if not resolved_key:
        if _is_local(resolved_base):
            # 本地 Ollama / vLLM 通常不校验 Key，但 OpenAI SDK 要求非空字符串
            resolved_key = _PLACEHOLDER_KEY
        else:
            raise LLMConfigError(
                f"profile '{p}' 未配置 api_key：请在 backend/.env 设置 "
                f"{env_prefix}_API_KEY（或回退的 LLM_DEFAULT_API_KEY）"
            )

    def _num(env_field: str, default: float) -> float:
        raw = _raw(p, env_field)
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError as exc:
            raise LLMConfigError(
                f"{env_prefix}_{env_field} 不是合法数字：{raw!r}"
            ) from exc

    def _int(env_field: str) -> int | None:
        raw = _raw(p, env_field)
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError as exc:
            raise LLMConfigError(
                f"{env_prefix}_{env_field} 不是合法整数：{raw!r}"
            ) from exc

    def _bool(env_field: str, default: bool) -> bool:
        raw = _raw(p, env_field).lower()
        if not raw:
            return default
        if raw in ("1", "true", "yes", "on", "y"):
            return True
        if raw in ("0", "false", "no", "off", "n"):
            return False
        raise LLMConfigError(
            f"{env_prefix}_{env_field} 不是合法布尔值：{raw!r}"
            "（可用 1/0、true/false、yes/no、on/off）"
        )

    temp = temperature if temperature is not None else _num("TEMPERATURE", 0.7)
    limit = max_tokens if max_tokens is not None else None
    if limit is None:
        raw_tokens = _raw(p, "MAX_TOKENS")
        if raw_tokens:
            try:
                limit = int(raw_tokens)
            except ValueError as exc:
                raise LLMConfigError(
                    f"{env_prefix}_MAX_TOKENS 不是合法整数：{raw_tokens!r}"
                ) from exc
    limit = limit or None

    tmo = timeout if timeout is not None else _num("TIMEOUT", 120.0)
    side = image_max_side if image_max_side is not None else _int("IMAGE_MAX_SIDE")
    raw_retries = json_max_retries if json_max_retries is not None else _int("JSON_MAX_RETRIES")
    retries = 1 if raw_retries is None else raw_retries
    strict = json_allow_strict if json_allow_strict is not None else _bool("JSON_ALLOW_STRICT", True)

    return LLMConfig(
        profile=p,
        base_url=resolved_base,
        api_key=resolved_key,
        model=resolved_model,
        temperature=float(temp),
        max_tokens=limit,
        timeout=float(tmo),
        image_max_side=side,
        json_max_retries=retries,
        json_allow_strict=strict,
    )


def configured_profiles() -> list[str]:
    """扫描环境变量，列出已配置的 profile 名（供排查用，不含 Key）。"""
    _ensure_env_loaded()
    found: set[str] = set()
    for key in os.environ:
        if not key.startswith("LLM_") or "_" not in key[4:]:
            continue
        for suffix in ("BASE_URL", "API_KEY", "MODEL"):
            if key.endswith("_" + suffix):
                name = key[4 : -(len(suffix) + 1)]
                if name and name != "DEFAULT":
                    found.add(name.lower().replace("_", "-"))
                elif name == "DEFAULT":
                    found.add(DEFAULT_PROFILE)
    return sorted(found)
