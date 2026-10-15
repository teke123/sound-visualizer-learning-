"""进程内有界执行器：评分、标定、特征提取共用一个全局并发闸门
（docs/architecture/03 第 6 节）。队列已满返回 SERVER_BUSY 语义由调用方映射。
"""
from __future__ import annotations

import concurrent.futures
import threading

from app import config


class BoundedExecutor:
    def __init__(self, workers: int, queue_limit: int) -> None:
        self._sem = threading.BoundedSemaphore(queue_limit)  # 队列上限闸门
        self._pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="svs-exec"
        )
        self._lock = threading.Lock()
        self._in_flight = 0
        self._queued = 0

    def try_submit(self, fn, *args, **kwargs):  # noqa: ANN001, ANN202
        """队列未满则提交并返回 Future；已满返回 None（→ 503 SERVER_BUSY）。"""
        if not self._sem.acquire(blocking=False):
            return None
        with self._lock:
            self._queued += 1

        def _wrapped():
            with self._lock:
                self._queued -= 1
                self._in_flight += 1
            try:
                return fn(*args, **kwargs)
            finally:
                with self._lock:
                    self._in_flight -= 1
                self._sem.release()

        return self._pool.submit(_wrapped)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"workers": self._pool._max_workers,
                    "inFlight": self._in_flight, "queued": self._queued}

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


executor = BoundedExecutor(config.EXECUTOR_WORKERS, config.EXECUTOR_QUEUE_LIMIT)
