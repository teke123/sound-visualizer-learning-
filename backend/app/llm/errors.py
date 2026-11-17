# -*- coding: utf-8 -*-
"""LLM 接入层异常。

统一从 ``app.llm`` 导出，调用方只需 ``except LLMError``。
"""


class LLMError(Exception):
    """LLM 调用失败的基类。消息面向人类，不含 API Key。"""


class LLMConfigError(LLMError):
    """配置缺失/非法（env 未配 base_url、model、api_key 等）。"""


class LLMMediaError(LLMError):
    """图像/音频文件不可读、格式不受 OpenAI 协议支持、体积超限。"""


class LLMSchemaError(LLMError):
    """结构化输出不符合给定 JSON Schema，或返回内容不是合法 JSON。"""
