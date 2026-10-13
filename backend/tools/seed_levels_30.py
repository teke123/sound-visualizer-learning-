#!/usr/bin/env python3
"""从关卡配置读取 L01–L30，并写入 SQLite 发音单元草稿。

已存在的关卡 ID 会跳过。目标音写入 pinyin，分组写入 category，
关卡顺序写入 order_no，教学内容通过 CMS 编辑和审核。

用法：
    python backend/tools/seed_levels_30.py --dry-run
    python backend/tools/seed_levels_30.py --db backend/pronunciation.db
    python backend/tools/seed_levels_30.py --rollback

--dry-run 预览关卡；--rollback 删除配置中的 L01–L30 关卡记录。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TOOLS_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
FREEZE_JSON = PROJECT_DIR / "src" / "data" / "levels.freeze.json"

sys.path.insert(0, str(BACKEND_DIR))
import database  # noqa: E402

LEVEL_ID_RE = re.compile(r"^L\d{2}$")


def load_frozen_levels() -> list[dict]:
    """读取前端同一份冻结表，保证前后端关卡身份一致"""
    if not FREEZE_JSON.exists():
        raise SystemExit(f"[错误] 找不到冻结表：{FREEZE_JSON}")
    payload = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
    levels = payload["levels"]
    validate(levels)
    return levels


def validate(levels: list[dict]) -> None:
    """冻结表自检：30 关 = 6 单韵母 + 23 声母 + 1 拼读，ID / 顺序连续"""
    groups: dict[str, int] = {}
    for lv in levels:
        groups[lv["group"]] = groups.get(lv["group"], 0) + 1
    codes = [lv["code"] for lv in levels]
    orders = [lv["order"] for lv in levels]
    if len(levels) != 30:
        raise SystemExit(f"[错误] 冻结表应为 30 关，实际 {len(levels)} 关")
    if groups.get("final") != 6 or groups.get("initial") != 23 or groups.get("syllable") != 1:
        raise SystemExit(f"[错误] 分组数量不符：应为 6 单韵母 + 23 声母 + 1 拼读，实际 {groups}")
    if codes != [f"L{i:02d}" for i in range(1, 31)]:
        raise SystemExit("[错误] 关卡 ID 必须连续为 L01–L30")
    if orders != list(range(1, 31)):
        raise SystemExit("[错误] 关卡顺序必须为 1–30")
    print(f"[校验] 冻结表通过：{len(levels)} 关 = 6 单韵母 + 23 声母 + 1 拼读")


GROUP_CN = {"final": "单韵母", "initial": "声母", "syllable": "拼读"}


def level_to_row(lv: dict) -> dict:
    """将关卡配置映射为发音单元草稿字段。"""
    return {
        "id": lv["code"],
        "pinyin": lv["target"],           # 关卡目标音
        "character": lv["char"],
        "category": GROUP_CN.get(lv["group"], lv["group"]),
        "description": f"{lv['code']} 目标音「{lv['target']}」（{GROUP_CN.get(lv['group'])}）",
        "conclusion": "",                 # 教学结论由 CMS 录入
        "detail": (
            f"关卡 ID {lv['code']}，顺序 {lv['order']}，目标音 {lv['target']}。"
            "示范 / 练习 / 检测开关 / 审核状态由 CMS 录入后生效。"
        ),
        "mistakes": [],
        "steps": [],
        "related": [],
        "status": "draft",                # 草稿审核状态
        "verified": False,                # 检测开关默认关闭（分级开放检测）
        "order": lv["order"],
    }


def pick_db_path(explicit: str | None) -> str:
    """依次使用显式路径、DB_PATH 环境变量和已存在的默认数据库。"""
    if explicit:
        return explicit
    env_db = os.environ.get("DB_PATH")
    if env_db:
        return env_db
    canonical = BACKEND_DIR / "pronunciation.db"
    legacy = PROJECT_DIR / "pronunciation.db"
    if canonical.exists():
        return str(canonical)
    if legacy.exists():
        print(f"[提示] 未发现 {canonical.name}（后端默认库），改用已存在的根目录副本：{legacy}")
        print("       若你平时用 `npm run backend` 启动后端，请改用 --db backend/pronunciation.db")
        return str(legacy)
    return str(canonical)


def main() -> int:
    parser = argparse.ArgumentParser(description="30 关 L01–L30 冻结表 → SQLite 草稿播种")
    parser.add_argument("--db", help="SQLite 文件路径（默认自动选择 pronunciation.db）")
    parser.add_argument("--dry-run", action="store_true", help="只打印将写入的关卡，不写库")
    parser.add_argument("--rollback", action="store_true", help="删除本脚本写入的 30 关草稿")
    args = parser.parse_args()

    levels = load_frozen_levels()
    db_path = pick_db_path(args.db)
    print(f"[数据库] {db_path}")

    if args.dry_run:
        for lv in levels:
            print(f"  {lv['code']}  #{lv['order']:>2}  {GROUP_CN.get(lv['group'], ''):<4} 目标音={lv['target']:<6} 例字={lv['char']}")
        print("[dry-run] 未写入数据库")
        return 0

    database.init_db(db_path)  # 幂等：确保表存在 + 原有单元播种
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if args.rollback:
            codes = [lv["code"] for lv in levels]
            placeholders = ",".join("?" for _ in codes)
            cur = conn.execute(
                f"DELETE FROM pronunciation_units WHERE id IN ({placeholders})", codes
            )
            conn.commit()
            print(f"[回滚] 已删除 {cur.rowcount} 条 L01–L30 草稿")
            return 0

        created, skipped = 0, 0
        for lv in levels:
            row = level_to_row(lv)
            exists = conn.execute(
                "SELECT 1 FROM pronunciation_units WHERE id = ?", (row["id"],)
            ).fetchone()
            if exists:
                skipped += 1
                continue
            database.create_unit(row)
            created += 1
            print(f"  + {row['id']}  目标音 {row['pinyin']}  （草稿，未公开）")

        total = conn.execute("SELECT COUNT(*) FROM pronunciation_units").fetchone()[0]
        published = conn.execute(
            "SELECT COUNT(*) FROM pronunciation_units WHERE status = 'published'"
        ).fetchone()[0]
        print(f"[完成] 新增 {created} 关，跳过已存在 {skipped} 关；表内共 {total} 行，其中已发布 {published} 行")
        print("[提醒] 这 30 关是 draft：大众端 /api/units?status=published 不会返回它们，")
        print("       发布请通过 CMS 提交审核。")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
