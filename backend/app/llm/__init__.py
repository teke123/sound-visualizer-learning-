# -*- coding: utf-8 -*-
"""``app.llm`` —— 后端内部 LLM 接入层（仅 OpenAI 协议）。

**不注册任何 FastAPI 路由**，不对外暴露；供声学反馈等后端模块在进程内直接调用。

公开 API::

    from app.llm import chat, chat_stream, chat_json, is_available
    from app.llm import LLMError, LLMConfigError, LLMMediaError, LLMSchemaError
    from app.llm import resolve, LLMConfig, DEFAULT_PROFILE

配置：``backend/.env``（见 ``backend/.env.example``），支持多 profile，全部参数均可
由环境变量配置::

    LLM_PROFILE                              不传 profile 参数时的默认档名
    LLM_DEFAULT_BASE_URL / _API_KEY / _MODEL / _TEMPERATURE / _MAX_TOKENS / _TIMEOUT
    LLM_<P>_*                                同上按档名覆盖；未配项回退 LLM_DEFAULT_*
    LLM_<P>_IMAGE_MAX_SIDE / _JSON_MAX_RETRIES / _JSON_ALLOW_STRICT
"""
from .client import chat, chat_json, chat_stream, is_available
from .config import (
    DEFAULT_PROFILE,
    ENV_FILE,
    LLMConfig,
    configured_profiles,
    load_env,
    reset_env_cache,
    resolve,
)
from .content import audio_part, build_content, build_messages, image_part
from .errors import LLMConfigError, LLMError, LLMMediaError, LLMSchemaError

__all__ = [
    "chat",
    "chat_stream",
    "chat_json",
    "is_available",
    "resolve",
    "LLMConfig",
    "DEFAULT_PROFILE",
    "ENV_FILE",
    "configured_profiles",
    "load_env",
    "reset_env_cache",
    "build_messages",
    "build_content",
    "image_part",
    "audio_part",
    "LLMError",
    "LLMConfigError",
    "LLMMediaError",
    "LLMSchemaError",
]
