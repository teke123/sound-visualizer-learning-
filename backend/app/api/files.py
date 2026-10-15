"""文件响应助手：媒体类型直出（不套 envelope）、Range/206/304/416、ETag。"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, Response

CHUNK = 256 * 1024


def _etag_of(path: Path) -> str:
    st = path.stat()
    return f'W/"{hashlib.sha1(f"{path.name}:{st.st_mtime_ns}:{st.st_size}".encode()).hexdigest()}"'


def serve_file(request: Request, path: Path, media_type: str,
               cache_control: str, etag_extra: str | None = None) -> Response:
    """公开媒体 no-cache + ETag（每次再验证检查发布引用）；
    私人/预览 no-store。支持 Range（206/416）与 If-None-Match（304）。"""
    if not path.exists():
        return Response(status_code=404)
    etag = _etag_of(path) if etag_extra is None else f'W/"{etag_extra}"'
    common = {
        "Cache-Control": cache_control,
        "ETag": etag,
        "Accept-Ranges": "bytes",
    }
    inm = request.headers.get("If-None-Match")
    if inm and etag in inm:
        return Response(status_code=304, headers=common)

    size = path.stat().st_size
    range_header = request.headers.get("Range")
    if range_header:
        try:
            unit, _, spec = range_header.partition("=")
            if unit.strip().lower() != "bytes":
                raise ValueError
            start_s, _, end_s = spec.partition("-")
            if start_s == "":
                suffix = int(end_s)
                start, end = max(0, size - suffix), size - 1
            else:
                start = int(start_s)
                end = int(end_s) if end_s else size - 1
            if start < 0 or end >= size or start > end:
                raise ValueError
        except ValueError:
            return Response(status_code=416, headers={**common, "Content-Range": f"bytes */{size}"})

        headers = {**common, "Content-Range": f"bytes {start}-{end}/{size}",
                   "Content-Length": str(end - start + 1)}
        from fastapi.responses import StreamingResponse

        def _iter():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = f.read(min(CHUNK, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(_iter(), status_code=206, media_type=media_type,
                                 headers=headers)

    return FileResponse(path, media_type=media_type, headers=common)
