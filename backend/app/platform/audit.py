"""审计与删除日志（docs/architecture/03 第 5.4 / 8 节）。

- audit_log 覆盖提交检测、发布、下架、回退、熔断、同意、撤回、删除、注销、转存；
  撤回/注销后匿名化，只保留操作骨架。
- 删除日志独立于数据库追加写入（data/deletion_log.jsonl），供物理清理任务
  幂等重试，也供备份恢复后重放。
"""
from __future__ import annotations

import json
import threading
from typing import Any

from sqlalchemy.orm import Session

from app import config
from app.db import now


class AuditLogger:
    """写审计行；匿名化仅清除可识别字段，保留操作骨架。"""

    def log(
        self,
        db: Session,
        *,
        action: str,
        object_type: str,
        object_id: str | None,
        actor_type: str = "system",       # user | admin | system
        actor_id: str | None = None,
        before: Any = None,
        after: Any = None,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> None:
        from app.platform.models import AuditLogRow

        db.add(AuditLogRow(
            id=None,
            request_id=request_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            before_state=json.dumps(before, ensure_ascii=False) if before is not None else None,
            after_state=json.dumps(after, ensure_ascii=False) if after is not None else None,
            reason=reason,
            created_at=now(),
        ))

    def anonymize_user(self, db: Session, user_id: str) -> None:
        """撤回/注销后：该用户的审计行去掉可识别 actor 信息，保留骨架。"""
        from app.platform.models import AuditLogRow

        rows = db.query(AuditLogRow).filter(AuditLogRow.actor_id == user_id).all()
        for row in rows:
            row.actor_type = "anonymized"
            row.actor_id = None
        db.flush()


audit = AuditLogger()


class DeletionLog:
    """独立于数据库的追加式删除日志。kind: file | feature_cache | score_cache。"""

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
