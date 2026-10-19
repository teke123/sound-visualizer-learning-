# -*- coding: utf-8 -*-
"""
看得见的声音 - 本地大模型服务（Ollama 封装）

职责：
- 封装对 Ollama 本地服务（http://localhost:11434）的调用
- 提供非流式对话 chat() 与流式对话 chat_stream()
- 供 /api/llm/chat、/api/llm/chat/stream、CMS 初筛等复用

说明：
- 使用标准库 urllib，避免引入额外 HTTP 依赖
- 同步调用，由 FastAPI 的同步 def 接口自动放入线程池，不阻塞事件循环
- 模型名可用环境变量 LLM_MODEL 覆盖，默认 qwen2.5:7b-instruct-q4_K_M（第 6 周量化模型）
"""
import json
import os
import urllib.request

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
# 第 6 周：LLM 本地量化部署（Qwen2.5-7B-Instruct，GGUF Q4_K_M 4bit 量化）
# 量化预处理在模型下载阶段完成（ollama pull qwen2.5:7b-instruct-q4_K_M），
# 后端 Python 代码不实现量化算法，仅调用 Ollama 推理服务。
OLLAMA_MODEL = os.environ.get("LLM_MODEL", "qwen2.5:7b-instruct-q4_K_M")

# 量化模型元信息（第 6 周交付口径，与 week6 部署说明一致）
QUANT_INFO = {
    "name": "Qwen2.5-7B-Instruct",
    "ollama_model": "qwen2.5:7b-instruct-q4_K_M",
    "quant_method": "GGUF Q4_K_M",
    "bits": 4,
    "file_size_gb": 4.7,
    "original_fp16_size_gb": 14.0,
    "compression_ratio": 0.66,  # 相比 FP16 原版体积压缩约 66%
    "note": "4bit 量化属于权重有损压缩，将 32bit 浮点权重压缩为 4bit 整型，降低显存占用，"
            "实现普通 PC 离线本地推理；量化预处理在模型下载阶段完成，后端仅调用 Ollama 推理服务。",
}


def _build_payload(messages: list[dict], temperature: float, stream: bool) -> dict:
    return {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": stream,
        "options": {"temperature": temperature},
    }


def _post(payload: dict, timeout: int = 180):
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=timeout)


def chat(messages: list[dict], temperature: float = 0.7) -> str:
    """非流式对话，返回完整回复文本"""
    payload = _build_payload(messages, temperature, stream=False)
    with _post(payload) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("message", {}).get("content", "")


def chat_stream(messages: list[dict], temperature: float = 0.7):
    """流式对话，逐段 yield 回复文本片段（供前端打字机效果）"""
    payload = _build_payload(messages, temperature, stream=True)
    with _post(payload) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            piece = data.get("message", {}).get("content", "")
            if piece:
                yield piece
            if data.get("done"):
                break


def is_available() -> bool:
    """检查 Ollama 服务是否可访问"""
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_model_info() -> dict:
    """返回量化模型部署信息（第 6 周）"""
    info = dict(QUANT_INFO)
    info["available"] = is_available()
    return info
