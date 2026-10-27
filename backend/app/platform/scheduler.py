"""进程内 asyncio 周期任务：处理超时 / 物理清理 / 自检。"""
from __future__ import annotations

import asyncio
import contextlib
import logging

from app import config
from app.db import get_session
from app.platform.deletion_log import deletion_log

logger = logging.getLogger("svs.scheduler")


async def _run_every(interval: float, fn) -> None:  # noqa: ANN001
    while True:
        try:
            await asyncio.sleep(interval)
            fn()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("scheduled task failed: %s", fn)


def sweep_timeouts() -> None:
    from app.detection.usecases import sweep_timeouts as sweep

    db = get_session()
    try:
        n = sweep(db)
        if n:
            logger.warning("marked %d recording(s) as TIMEOUT", n)
    finally:
        db.close()


def physical_cleanup() -> None:
    """按删除日志物理删除文件与缓存（幂等重试，积压过多时告警）。"""
    pending = deletion_log.read_pending()
    for entry in pending:
        kind, key = entry.get("kind"), entry.get("key")
        try:
            if kind == "file":
                path = config.DATA_DIR / key
                if path.exists():
                    path.unlink()
            elif kind == "feature_cache":
                audio_id, fkind, algo = key.split(":", 2)
                from app.acoustics.models import FeatureCacheRow

                db = get_session()
                try:
                    for row in db.query(FeatureCacheRow).filter(
                            FeatureCacheRow.audio_id == audio_id,
                            FeatureCacheRow.kind.in_(("f0", "formants", "formants_png"))).all():
                        db.delete(row)
                    db.commit()
                finally:
                    db.close()
            deletion_log.mark_done(entry)
        except Exception:
            logger.exception("cleanup failed for %s:%s", kind, key)
    if len(deletion_log.read_pending()) > 50:
        logger.warning("cleanup backlog large: %d", len(deletion_log.read_pending()))


def self_check() -> None:
    from app.platform.executor import executor

    stats = executor.stats()
    backlog = len(deletion_log.read_pending())
    logger.info("self-check executor=%s cleanupBacklog=%d", stats, backlog)


def start() -> list[asyncio.Task]:
    return [
        asyncio.create_task(_run_every(config.SWEEP_INTERVAL_SECONDS, sweep_timeouts)),
        asyncio.create_task(_run_every(config.CLEANUP_INTERVAL_SECONDS, physical_cleanup)),
        asyncio.create_task(_run_every(3600.0, self_check)),
    ]


def stop(tasks: list[asyncio.Task]) -> None:
    for t in tasks:
        with contextlib.suppress(Exception):
            t.cancel()
