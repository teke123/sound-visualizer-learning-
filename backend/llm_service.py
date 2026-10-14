# -*- coding: utf-8 -*-
"""本地大模型服务（Ollama 封装，重构占位骨架）。

意图：封装对本地 Ollama 的非流式/流式对话与可用性探测，
供 /api/llm/chat 与反馈话术生成复用；模型与地址经环境变量覆盖。
"""


def chat(messages: list[dict], temperature: float = 0.7) -> str:
    """意图：非流式对话，返回完整回复文本。"""
    raise NotImplementedError("重构占位：LLM 对话")


def chat_stream(messages: list[dict], temperature: float = 0.7):
    """意图：流式对话，逐段 yield 回复片段。"""
    raise NotImplementedError("重构占位：LLM 流式对话")


def is_available() -> bool:
    """意图：探测 Ollama 服务是否可访问。"""
    raise NotImplementedError("重构占位：LLM 可用性探测")
