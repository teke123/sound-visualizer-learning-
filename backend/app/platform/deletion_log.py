"""删除日志：独立于数据库的追加式记录（data/deletion_log.jsonl），
供物理清理任务幂等重试删除录音/媒体对应的文件与特征缓存。"""
from __future__ import annotations

import json
import threading

from app import config
from app.db import now


class DeletionLog:
    """kind: file | feature_cache | score_cache。"""

    def __init__(self, path=None):  # noqa: ANN001
        self.path = path or config.DELETION_LOG_PATH
        self._lock = threading.Lock()

    def append(self, *, kind: str, key: str, meta: dict | None = None) -> None:
        entry = {"kind": kind, "key": key, "meta": meta or {}, "ts": now().isoformat()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_pending(self) -> list[dict]:
        if not self.path.exists():
            return []
        seen: dict[str, dict] = {}
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                k = f"{entry.get('kind')}:{entry.get('key')}"
                if entry.get("done"):
                    seen.pop(k, None)
                else:
                    seen[k] = entry
        return list(seen.values())

    def mark_done(self, entry: dict) -> None:
        entry = dict(entry)
        entry["done"] = True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


deletion_log = DeletionLog()
