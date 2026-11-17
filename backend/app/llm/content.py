# -*- coding: utf-8 -*-
"""多模态内容组装：本地文件 → Base64 → OpenAI 协议的 content part。

调用方只传路径，不关心编码细节：

    build_content("看看这张语谱图", images="out/spec.png")
    build_content("这段发音哪里不对", audios="samples/a.wav")
"""
from __future__ import annotations

import base64
import io
import mimetypes
from pathlib import Path
from typing import Iterable, Sequence

from .errors import LLMMediaError

# OpenAI 协议：图像走 image_url(data URL)，音频走 input_audio 且 format 仅 wav / mp3
_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
_AUDIO_FORMAT = {
    ".wav": "wav",
    ".mp3": "mp3",
}

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_AUDIO_BYTES = 25 * 1024 * 1024

PathLike = str | Path


def _as_list(value: PathLike | Sequence[PathLike] | None) -> list[Path]:
    if value is None:
        return []
    if isinstance(value, (str, Path)):
        return [Path(value)]
    return [Path(v) for v in value]


def _read(path: Path, limit: int, kind: str) -> bytes:
    if not path.is_file():
        raise LLMMediaError(f"{kind}文件不存在：{path}")
    size = path.stat().st_size
    if size == 0:
        raise LLMMediaError(f"{kind}文件为空：{path}")
    if size > limit:
        raise LLMMediaError(
            f"{kind}文件过大（{size / 1024 / 1024:.1f} MB > "
            f"{limit / 1024 / 1024:.0f} MB）：{path}"
        )
    return path.read_bytes()


def _sniff_image_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _shrink_if_needed(data: bytes, mime: str, max_side: int) -> tuple[bytes, str]:
    """可选降采样：仅当最长边超过 max_side 时才处理，失败则原样返回。"""
    try:
        from PIL import Image
    except ImportError:
        return data, mime
    try:
        with Image.open(io.BytesIO(data)) as img:
            if max(img.size) <= max_side:
                return data, mime
            scale = max_side / max(img.size)
            new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
            img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
            img = img.resize(new_size, Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue(), "image/png"
    except Exception:  # noqa: BLE001 - 缩放只是优化，失败不阻断
        return data, mime


def image_part(path: PathLike, *, max_side: int | None = None) -> dict:
    """把本地图像编码为 OpenAI 的 image_url part（data URL 形式）。"""
    p = Path(path)
    data = _read(p, MAX_IMAGE_BYTES, "图像")
    mime = _IMAGE_MIME.get(p.suffix.lower()) or _sniff_image_mime(data)
    if mime is None:
        mime = mimetypes.guess_type(p.name)[0] or ""
    if not mime.startswith("image/"):
        raise LLMMediaError(
            f"无法识别的图像格式：{p.suffix or p.name}（支持 png/jpg/jpeg/webp/gif）"
        )
    if max_side:
        data, mime = _shrink_if_needed(data, mime, int(max_side))
    b64 = base64.b64encode(data).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


def audio_part(path: PathLike) -> dict:
    """把本地音频编码为 OpenAI 的 input_audio part（仅 wav / mp3）。"""
    p = Path(path)
    fmt = _AUDIO_FORMAT.get(p.suffix.lower())
    if fmt is None:
        raise LLMMediaError(
            f"OpenAI 协议的 input_audio 仅支持 wav / mp3，当前为 "
            f"{p.suffix or '<无扩展名>'}：{p.name}。"
            "请先转码（例如 ffmpeg -i in.flac out.wav）再传入。"
        )
    data = _read(p, MAX_AUDIO_BYTES, "音频")
    b64 = base64.b64encode(data).decode("ascii")
    return {"type": "input_audio", "input_audio": {"data": b64, "format": fmt}}


def build_content(
    text: str | None = None,
    images: PathLike | Iterable[PathLike] | None = None,
    audios: PathLike | Iterable[PathLike] | None = None,
    *,
    image_max_side: int | None = None,
) -> str | list[dict]:
    """纯文本时返回 str；带图像/音频时返回 content part 列表。"""
    image_list = _as_list(images)
    audio_list = _as_list(audios)

    if not image_list and not audio_list:
        return text or ""

    parts: list[dict] = []
    if text:
        parts.append({"type": "text", "text": text})
    for item in image_list:
        parts.append(image_part(item, max_side=image_max_side))
    for item in audio_list:
        parts.append(audio_part(item))
    return parts


def build_messages(
    system: str | None = None,
    user: str | None = None,
    *,
    images: PathLike | Iterable[PathLike] | None = None,
    audios: PathLike | Iterable[PathLike] | None = None,
    history: Sequence[dict] | None = None,
    image_max_side: int | None = None,
) -> list[dict]:
    """组装 messages：system（可选）→ history（可选）→ 本轮 user（含多模态）。"""
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    for item in history or []:
        role = item.get("role")
        if role not in ("user", "assistant"):
            raise LLMMediaError(f"history 中的 role 只能是 user/assistant，收到 {role!r}")
        messages.append({"role": role, "content": item.get("content", "")})

    content = build_content(user, images, audios, image_max_side=image_max_side)
    if content == "" and not messages:
        raise LLMMediaError("system / user / 图像 / 音频 不能全为空")
    messages.append({"role": "user", "content": content})
    return messages
