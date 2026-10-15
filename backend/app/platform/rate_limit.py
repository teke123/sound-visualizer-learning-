"""进程内令牌桶限流（docs/architecture/03 第 7 节：上传、评分、标定、反馈、
注册、登录；访客按 sid+IP，登录用户按账号+IP；登录失败另设更严格额度）。

单进程前提下的内存实现；多进程前须迁出（ADR-17）。
"""
from __future__ import annotations

import threading
import time

from app import config
from app.platform.envelope import ApiError


class _Bucket:
    __slots__ = ("capacity", "refill_per_sec", "tokens", "last")

    def __init__(self, capacity: int, window: float):
        self.capacity = float(capacity)
        self.refill_per_sec = capacity / window
        self.tokens = float(capacity)
        self.last = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.refill_per_sec)
        self.last = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    def retry_after(self) -> int:
        need = 1.0 - self.tokens
        return max(1, int(need / self.refill_per_sec) + 1)


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._last_gc = time.monotonic()

    def check(self, bucket: str, subject: str) -> None:
        limits = config.RATE_LIMITS.get(bucket)
        if not limits:
            return
        cap, window = limits
        key = (bucket, subject)
        with self._lock:
            now = time.monotonic()
            if now - self._last_gc > 600:
                self._gc(now)
            b = self._buckets.get(key)
            if b is None:
                b = _Bucket(cap, window)
                self._buckets[key] = b
            if not b.allow():
                raise ApiError(
                    429, "RATE_LIMITED", "请求过于频繁，请稍后再试",
                    headers={"Retry-After": str(b.retry_after())},
                )

    def _gc(self, now: float) -> None:
        # 超过 1 小时未用的桶清掉，防内存缓慢增长
        stale = [k for k, b in self._buckets.items() if now - b.last > 3600]
        for k in stale:
            del self._buckets[k]
        self._last_gc = now


limiter = RateLimiter()


def client_ip(request) -> str:  # noqa: ANN001
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
