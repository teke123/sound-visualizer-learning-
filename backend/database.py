"""
看得见的声音 - 数据访问层
SQLite 持久化：学习记录（含录音二进制 BLOB）、用户进度。

设计要点：
- 学习记录与用户进度在同一事务内更新，保证一致性（有记录必有进度）
- 列表/统计接口绝不携带 BLOB，录音通过 /api/learning-records/{id}/audio 按需拉取
- 时间戳统一存 created_at（ISO8601 UTC），接口层映射为前端 createdAt
"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

DB_PATH = "pronunciation.db"


# ===========================================================================
# CMS 内容审核状态与允许的流转操作
# 草稿/驳回 -> 提交审核 -> 待审核 -> 通过(发布) / 驳回；已发布 -> 下架(回草稿)
# ===========================================================================
UNIT_STATUS_TRANSITIONS = {
    "draft": {"submit_review": "pending_review"},
    "rejected": {"submit_review": "pending_review"},
    "pending_review": {"approve": "published", "reject": "rejected"},
    "published": {"unpublish": "draft"},
}
# 仅草稿/驳回允许编辑内容；检测开关(verified)不受此限，走专用接口
EDITABLE_STATUSES = ("draft", "rejected")


class CmsStateError(ValueError):
    """非法 CMS 状态流转（草稿直接发布、已发布再驳回等）"""

# 12 个发音单元（与 main.py /api/pronunciation-units 保持一致）
DEFAULT_UNITS = [
    {"id": "ma", "pinyin": "mā", "character": "妈"},
    {"id": "ba", "pinyin": "bā", "character": "八"},
    {"id": "pa", "pinyin": "pā", "character": "趴"},
    {"id": "ta", "pinyin": "tā", "character": "他"},
    {"id": "yi", "pinyin": "yī", "character": "一"},
    {"id": "wu", "pinyin": "wǔ", "character": "五"},
    {"id": "yu", "pinyin": "yú", "character": "鱼"},
    {"id": "mao", "pinyin": "māo", "character": "猫"},
    {"id": "gou", "pinyin": "gǒu", "character": "狗"},
    {"id": "niao", "pinyin": "niǎo", "character": "鸟"},
    {"id": "ma_t2", "pinyin": "má", "character": "麻"},
    {"id": "ma_t3", "pinyin": "mǎ", "character": "马"},
]


def _now() -> str:
    """当前时间（ISO8601 UTC）"""
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_cms_columns(conn: sqlite3.Connection) -> None:
    """老库增量迁移：pronunciation_units 缺 CMS 审核/30关正式字段时自动补列。
    新库由 CREATE TABLE 之外的本函数补齐，保证「已有数据不丢、代码升级即迁移」。
    对应 D 的 seed_levels_30.py FIELD MAPPING：demo_audio / practice / version / 审核字段。"""
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(pronunciation_units)").fetchall()}
    additions = {
        "demo_audio": "TEXT NOT NULL DEFAULT ''",          # 示范音频路径（D AdminView 已预留录入位）
        "practice": "TEXT NOT NULL DEFAULT '[]'",          # 练习内容（JSON 数组）
        "version": "INTEGER NOT NULL DEFAULT 1",           # 版本号：每次内容编辑自动 +1，可追溯
        "submit_review_time": "TEXT NOT NULL DEFAULT ''",  # 最近一次提交审核时间
        "review_time": "TEXT NOT NULL DEFAULT ''",         # 最近一次审核完成时间
        "reviewer": "TEXT NOT NULL DEFAULT ''",            # 审核人（第7周接管理员账号）
        "review_comment": "TEXT NOT NULL DEFAULT ''",      # 驳回意见，仅驳回时有值
    }
    for name, ddl in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE pronunciation_units ADD COLUMN {name} {ddl}")


def _write_audit(
    conn: sqlite3.Connection,
    operator: str,
    action: str,
    resource_id: str | None = None,
    remark: str = "",
) -> None:
    """每次 CMS 操作落一条操作日志（操作人/动作/资源/备注/时间）"""
    conn.execute(
        """INSERT INTO audit_log (operator, action, resource_type, resource_id, remark, created_at)
           VALUES (?, ?, 'unit', ?, ?, ?)""",
        (operator or "admin", action, resource_id, remark, _now()),
    )


def _check_transition(current: str, action: str) -> None:
    """按 UNIT_STATUS_TRANSITIONS 校验状态流转，非法动作抛 CmsStateError"""
    allowed = UNIT_STATUS_TRANSITIONS.get(current, {})
    if action not in allowed:
        raise CmsStateError(f"当前状态为「{current}」，不允许执行「{action}」操作")


def init_db(db_path: str = "pronunciation.db") -> None:
    """初始化数据库：建表（幂等）+ 播种核心发音单元"""
    global DB_PATH
    DB_PATH = db_path
    conn = _connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS learning_records (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                pinyin TEXT NOT NULL,
                character TEXT NOT NULL,
                score REAL NOT NULL,
                accuracy REAL NOT NULL,
                fluency REAL NOT NULL,
                pronunciation REAL NOT NULL,
                duration REAL NOT NULL DEFAULT 0,
                feedback TEXT NOT NULL DEFAULT '',
                audio_blob BLOB,
                audio_type TEXT NOT NULL DEFAULT 'audio/webm',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_progress (
                user_id TEXT PRIMARY KEY,
                total_units INTEGER NOT NULL DEFAULT 12,
                completed_units INTEGER NOT NULL DEFAULT 0,
                total_practice INTEGER NOT NULL DEFAULT 0,
                average_score REAL NOT NULL DEFAULT 0,
                last_practice_at TEXT NOT NULL DEFAULT '',
                unit_progress TEXT NOT NULL DEFAULT '[]'
            );

            CREATE INDEX IF NOT EXISTS idx_records_user ON learning_records(user_id, created_at);

            CREATE TABLE IF NOT EXISTS pronunciation_units (
                id TEXT PRIMARY KEY,
                pinyin TEXT NOT NULL DEFAULT '',
                character TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                conclusion TEXT NOT NULL DEFAULT '',
                detail TEXT NOT NULL DEFAULT '',
                mistakes TEXT NOT NULL DEFAULT '[]',
                steps TEXT NOT NULL DEFAULT '[]',
                related TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'draft',
                verified INTEGER NOT NULL DEFAULT 0,
                order_no INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS feedbacks (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'learning',
                page TEXT NOT NULL DEFAULT '',
                unit_id TEXT NOT NULL DEFAULT '',
                rating TEXT NOT NULL DEFAULT '',
                message TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                handle_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS favorites (
                user_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, unit_id)
            );

            CREATE TABLE IF NOT EXISTS media_assets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                file_type TEXT NOT NULL DEFAULT 'audio',
                mime TEXT NOT NULL DEFAULT '',
                size INTEGER NOT NULL DEFAULT 0,
                path TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operator TEXT NOT NULL,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL DEFAULT 'unit',
                resource_id TEXT,
                remark TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            """
        )
        _ensure_cms_columns(conn)
        _seed_units(conn)
        _enrich_appendix_a_units(conn)
        conn.commit()
    finally:
        conn.close()


# 已开放 50 个核心单元（12 个对比单元 + 38 个常用音节，检测已验证，可开放测试）
CORE_UNITS = [
    {"id": "a", "pinyin": "a", "character": "啊", "category": "韵母", "verified": 1,
     "conclusion": "a 是开放元音：嘴巴自然张大，舌头平放，声音响亮通畅",
     "detail": "上下齿距离约两指宽，舌位最低最前，气流不受阻碍。口腔开口度与 F1 共振峰直接相关。"},
    {"id": "i", "pinyin": "i", "character": "一", "category": "韵母", "verified": 1,
     "conclusion": "i 是高前元音：舌面抬向硬腭，嘴角向两侧展开",
     "detail": "舌头前部抬高接近硬腭，上下齿几乎并拢，双唇呈微笑状。F2 共振峰高（约2400Hz）。"},
    {"id": "u_u", "pinyin": "u/ü", "character": "五/鱼", "category": "韵母", "verified": 1,
     "conclusion": "u 和 ü 都是圆唇元音，但舌位不同：u 舌位靠后，ü 舌位靠前",
     "detail": "u 舌根抬高、唇最圆；ü 舌面抬向硬腭同时保持圆唇。可用 wu/yū 对比感受。"},
    {"id": "m", "pinyin": "m", "character": "妈", "category": "声母", "verified": 1,
     "conclusion": "m 是双唇鼻音：双唇闭合，软腭下垂，声音从鼻腔透出",
     "detail": "双唇自然闭合，声带振动，气流大部分从鼻腔流出。手放鼻前可感受到气流。"},
    {"id": "b_p", "pinyin": "b/p", "character": "八/趴", "category": "声母", "verified": 1,
     "conclusion": "b 与 p 的差别是送气：b 不送气，p 送气（有显著气流喷出）",
     "detail": "两者都是双唇清塞音。把手背放嘴前发 ba（无气流）与 pa（有气流）对比感受。"},
    {"id": "d_t", "pinyin": "d/t", "character": "大/他", "category": "声母", "verified": 1,
     "conclusion": "d 与 t 的差别是送气：d 不送气，t 送气",
     "detail": "舌尖抵住上齿龈后突然放开。发 da 时无明显气流，发 ta 时有明显气流冲出。"},
    {"id": "n_l", "pinyin": "n/l", "character": "那/辣", "category": "声母", "verified": 1,
     "conclusion": "n 是鼻音、l 是边音：发 n 时气流走鼻腔，发 l 时气流从舌两侧流出",
     "detail": "n：舌尖抵上齿龈、软腭下垂（可捏鼻验证）；l：舌尖抵上齿龈但软腭抬起，气流从舌侧通过。"},
    {"id": "g_k", "pinyin": "g/k", "character": "歌/可", "category": "声母", "verified": 1,
     "conclusion": "g 与 k 的差别是送气：g 不送气，k 送气",
     "detail": "舌根抬起抵住软腭。发 ga 无气流、发 ka 有明显气流。"},
    {"id": "j_q_x", "pinyin": "j/q/x", "character": "机/七/西", "category": "声母", "verified": 1,
     "conclusion": "j、q、x 是舌面音：舌面前部抬起接近硬腭；j 不送气、q 送气、x 是擦音",
     "detail": "j/q 成阻部位相同（一送气一不送气），x 留窄缝摩擦成声。注意不要发成 z/c/s 或 zh/ch/sh。"},
    {"id": "z_zh", "pinyin": "z/zh", "character": "字/只", "category": "声母", "verified": 1,
     "conclusion": "z（平舌）舌尖抵下齿背，zh（翘舌）舌尖卷向上颚前部",
     "detail": "z/c/s 舌尖平放抵下齿背；zh/ch/sh/r 舌尖卷起抵硬腭前部。这是最常见的辨音难点。"},
    {"id": "ma_tone", "pinyin": "mā/má/mǎ/mà", "character": "妈/麻/马/骂", "category": "声调", "verified": 1,
     "conclusion": "四声是音高走向的变化：阴平高平、阳平上升、上声先降后升、去声急降",
     "detail": "妈mā（55高平）、麻má（35上升）、马mǎ（214先降后升）、骂mà（51急降）。可用手划轨迹辅助。"},
    {"id": "ma", "pinyin": "mā", "character": "妈", "category": "声母", "verified": 1,
     "conclusion": "「妈」完整闭环单元：声母m + 韵母a + 第一声，完成学习-录音-结果-练习-再录音",
     "detail": "先发双唇鼻音 m，随即滑向开口元音 a，音高保持高平。"},
    # ===== 已开放常用音节单元（38 个） =====
    {"id": "ba", "pinyin": "bā", "character": "八", "category": "声母", "verified": 1,
     "conclusion": "b 是不送气双唇塞音：双唇闭合后突然放开",
     "detail": "双唇先闭拢憋气，然后突然放开，声带不振动（清音），无气流冲出。"},
    {"id": "pa", "pinyin": "pā", "character": "趴", "category": "声母", "verified": 1,
     "conclusion": "p 是送气双唇塞音：与 b 部位相同，但有明显气流冲出",
     "detail": "成阻部位与 b 相同，但除阻时有较强气流。手背放嘴前可感受到喷气。"},
    {"id": "ta", "pinyin": "tā", "character": "他", "category": "声母", "verified": 1,
     "conclusion": "t 是送气舌尖中塞音：舌尖抵上齿龈后放开，气流冲出",
     "detail": "舌尖抵住上齿龈，突然放开时气流从口中冲出，声带不振动。"},
    {"id": "yi", "pinyin": "yī", "character": "一", "category": "韵母", "verified": 1,
     "conclusion": "y 是半元音，发音与高前元音 i 相近",
     "detail": "声母 y 由 i 变化而来，舌面抬高接近硬腭，开口度小。"},
    {"id": "wu", "pinyin": "wǔ", "character": "五", "category": "韵母", "verified": 1,
     "conclusion": "w 是半元音，发音与高后元音 u 相近",
     "detail": "声母 w 由 u 变化而来，舌根抬高、双唇收圆突出。"},
    {"id": "yu", "pinyin": "yú", "character": "鱼", "category": "韵母", "verified": 1,
     "conclusion": "yu 实际发 ü 的音：舌面前部抬高同时圆唇",
     "detail": "ü 是撮口呼：舌位同 i，但双唇收圆。注意不要发成 u 或 i。"},
    {"id": "mao", "pinyin": "māo", "character": "猫", "category": "声母", "verified": 1,
     "conclusion": "m + ao 复韵母：从双唇闭合滑向 a-o",
     "detail": "先发双唇鼻音 m，随即元音由 a 滑向 o，舌位由低到高。"},
    {"id": "gou", "pinyin": "gǒu", "character": "狗", "category": "声母", "verified": 1,
     "conclusion": "g + ou 复韵母：不送气舌根音接复合元音",
     "detail": "g 舌根抵软腭不送气，随后元音由 o 滑向 u。"},
    {"id": "niao", "pinyin": "niǎo", "character": "鸟", "category": "声母", "verified": 1,
     "conclusion": "n + iao 三合复韵母：鼻音后元音由 i 经 a 滑向 o",
     "detail": "n 舌尖抵上齿龈鼻音，随后 i-a-o 三个元音连续滑动。"},
    {"id": "ma_t2", "pinyin": "má", "character": "麻", "category": "声调", "verified": 1,
     "conclusion": "阳平（第二声）：音高从 3 度直线上升到 5 度",
     "detail": "麻 má 为高升调（35）。起音中等偏高，逐渐上扬，手可做上划轨迹。"},
    {"id": "ma_t3", "pinyin": "mǎ", "character": "马", "category": "声调", "verified": 1,
     "conclusion": "上声（第三声）：音高先降后升（214）",
     "detail": "马 mǎ 为降升调：先降到低处再回升，音程长、拐点明显。"},
    {"id": "bo", "pinyin": "bō", "character": "波", "category": "声母", "verified": 1,
     "conclusion": "b + o 单韵母：不送气双唇音接圆唇中元音",
     "detail": "先闭双唇发 b，随即开口发 o，舌位后半高，双唇略圆。"},
    {"id": "bi", "pinyin": "bǐ", "character": "比", "category": "声母", "verified": 1,
     "conclusion": "b + i 高前元音：双唇音接齐齿呼",
     "detail": "b 除阻后舌面立即抬高接近硬腭，嘴角向两侧展开，上声调。"},
    {"id": "bu", "pinyin": "bù", "character": "不", "category": "声母", "verified": 1,
     "conclusion": "b + u 高后元音：双唇音接合口呼",
     "detail": "b 除阻后舌根抬高、双唇收圆突出，发 u，去声调。"},
    {"id": "po", "pinyin": "pō", "character": "坡", "category": "声母", "verified": 1,
     "conclusion": "p + o 单韵母：送气双唇音接圆唇中元音",
     "detail": "p 除阻时气流明显冲出，随后发 o，舌位后半高、唇圆。"},
    {"id": "pi", "pinyin": "pí", "character": "皮", "category": "声母", "verified": 1,
     "conclusion": "p + i 高前元音：送气双唇音接齐齿呼",
     "detail": "p 送气后舌面抬向硬腭发 i，阳平调，音高上扬。"},
    {"id": "pu", "pinyin": "pǔ", "character": "普", "category": "声母", "verified": 1,
     "conclusion": "p + u 高后元音：送气双唇音接合口呼",
     "detail": "p 送气后舌根抬高、双唇收圆发 u，上声调。"},
    {"id": "mo", "pinyin": "mō", "character": "摸", "category": "声母", "verified": 1,
     "conclusion": "m + o 单韵母：双唇鼻音接圆唇中元音",
     "detail": "m 双唇闭合、气流走鼻腔，随即发 o，手放鼻前可感受气流。"},
    {"id": "mi", "pinyin": "mǐ", "character": "米", "category": "声母", "verified": 1,
     "conclusion": "m + i 高前元音：双唇鼻音接齐齿呼",
     "detail": "m 鼻音后舌面抬向硬腭发 i，上声调。"},
    {"id": "mu", "pinyin": "mù", "character": "木", "category": "声母", "verified": 1,
     "conclusion": "m + u 高后元音：双唇鼻音接合口呼",
     "detail": "m 鼻音后舌根抬高、双唇收圆发 u，去声调。"},
    {"id": "fa", "pinyin": "fā", "character": "发", "category": "声母", "verified": 1,
     "conclusion": "f 是唇齿清擦音：上齿轻触下唇，气流摩擦成声",
     "detail": "上齿轻触下唇内缘，气流从窄缝中挤出产生摩擦，声带不振动。"},
    {"id": "fei", "pinyin": "fēi", "character": "飞", "category": "声母", "verified": 1,
     "conclusion": "f + ei 复韵母：唇齿擦音接前响复元音",
     "detail": "f 摩擦成声后，元音由 e 滑向 i，前重后轻。"},
    {"id": "da", "pinyin": "dà", "character": "大", "category": "声母", "verified": 1,
     "conclusion": "d + a 开口呼：不送气舌尖中塞音",
     "detail": "舌尖抵上齿龈除阻后发 a，去声调，音高急降。"},
    {"id": "duo", "pinyin": "duō", "character": "多", "category": "声母", "verified": 1,
     "conclusion": "d + uo 复韵母：不送气舌尖音接后响复元音",
     "detail": "d 除阻后元音由 u 滑向 o，后响复元音前轻后重。"},
    {"id": "di", "pinyin": "dì", "character": "地", "category": "声母", "verified": 1,
     "conclusion": "d + i 高前元音：不送气舌尖中塞音接齐齿呼",
     "detail": "d 除阻后舌面抬向硬腭发 i，去声调。"},
    {"id": "du", "pinyin": "dú", "character": "读", "category": "声母", "verified": 1,
     "conclusion": "d + u 高后元音：不送气舌尖中塞音接合口呼",
     "detail": "d 除阻后舌根抬高、双唇收圆发 u，阳平调。"},
    {"id": "te", "pinyin": "tè", "character": "特", "category": "声母", "verified": 1,
     "conclusion": "t + e 单元音：送气舌尖中塞音接不圆唇中元音",
     "detail": "t 送气后发 e，舌位半高偏后、唇不圆，去声调。"},
    {"id": "ti", "pinyin": "tí", "character": "题", "category": "声母", "verified": 1,
     "conclusion": "t + i 高前元音：送气舌尖中塞音接齐齿呼",
     "detail": "t 送气后舌面抬向硬腭发 i，阳平调。"},
    {"id": "tu", "pinyin": "tú", "character": "图", "category": "声母", "verified": 1,
     "conclusion": "t + u 高后元音：送气舌尖中塞音接合口呼",
     "detail": "t 送气后舌根抬高、双唇收圆发 u，阳平调。"},
    {"id": "na", "pinyin": "nà", "character": "那", "category": "声母", "verified": 1,
     "conclusion": "n + a 开口呼：舌尖中鼻音，气流走鼻腔",
     "detail": "n 舌尖抵上齿龈、软腭下垂，气流从鼻腔透出，随即发 a，去声调。"},
    {"id": "ni", "pinyin": "nǐ", "character": "你", "category": "声母", "verified": 1,
     "conclusion": "n + i 高前元音：舌尖中鼻音接齐齿呼",
     "detail": "n 鼻音后舌面抬向硬腭发 i，上声调。"},
    {"id": "nu", "pinyin": "nǔ", "character": "努", "category": "声母", "verified": 1,
     "conclusion": "n + u 高后元音：舌尖中鼻音接合口呼",
     "detail": "n 鼻音后舌根抬高、双唇收圆发 u，上声调。"},
    {"id": "la", "pinyin": "lā", "character": "拉", "category": "声母", "verified": 1,
     "conclusion": "l + a 开口呼：舌尖中边音，气流从舌两侧流出",
     "detail": "l 舌尖抵上齿龈但软腭抬起，气流从舌侧通过，与 n（鼻音）形成对比。"},
    {"id": "li", "pinyin": "lǐ", "character": "里", "category": "声母", "verified": 1,
     "conclusion": "l + i 高前元音：舌尖中边音接齐齿呼",
     "detail": "l 边音后舌面抬向硬腭发 i，上声调。"},
    {"id": "lu", "pinyin": "lù", "character": "路", "category": "声母", "verified": 1,
     "conclusion": "l + u 高后元音：舌尖中边音接合口呼",
     "detail": "l 边音后舌根抬高、双唇收圆发 u，去声调。"},
    {"id": "ge", "pinyin": "gē", "character": "歌", "category": "声母", "verified": 1,
     "conclusion": "g + e 单元音：不送气舌根音接不圆唇中元音",
     "detail": "g 舌根抵软腭不送气，随后发 e，舌位半高偏后、唇不圆。"},
    {"id": "gu", "pinyin": "gǔ", "character": "古", "category": "声母", "verified": 1,
     "conclusion": "g + u 高后元音：不送气舌根音接合口呼",
     "detail": "g 除阻后舌根抬高、双唇收圆发 u，上声调。"},
    {"id": "ka", "pinyin": "kǎ", "character": "卡", "category": "声母", "verified": 1,
     "conclusion": "k + a 开口呼：送气舌根音，气流明显冲出",
     "detail": "k 与 g 成阻部位相同，但除阻时有较强气流冲出，随后发 a，上声调。"},
]


# 核心单元 id 集合（受保护，不可删除）
CORE_UNITS_IDS = {u["id"] for u in CORE_UNITS}

# 发音单元的练习步骤、常见误区和关联单元
APPENDIX_A_ENRICHMENT: dict[str, dict] = {
    "a": {
        "steps": [
            {"title": "听示范", "text": "听 3 遍开口元音 a，注意下巴自然下落。"},
            {"title": "感受开口", "text": "手放下巴下，确认开口约两指宽。"},
            {"title": "慢速跟读", "text": "跟读 5 遍「啊——」，每遍约 1 秒。"},
            {"title": "录音", "text": "清晰朗读单韵母 a，环境安静。"},
            {"title": "看结果", "text": "对照 F1/F2 与练习建议调整。"},
        ],
        "mistakes": [{"title": "开口不够", "text": "声音发扁；试着再张大口。"}],
        "related": ["i", "u_u"],
    },
    "i": {
        "steps": [
            {"title": "听示范", "text": "注意嘴角向两侧展开。"},
            {"title": "摆口型", "text": "上下齿接近，舌面前抬。"},
            {"title": "跟读", "text": "慢速 5 遍「衣——」。"},
            {"title": "录音", "text": "保持口型稳定录音。"},
            {"title": "对比", "text": "与 a 单元对比舌位高低。"},
        ],
        "mistakes": [{"title": "发成 u", "text": "圆唇了；嘴角再拉开。"}],
        "related": ["a", "u_u"],
    },
    "u_u": {
        "steps": [
            {"title": "听 wu 与 yu", "text": "对比 u（舌后）与 ü（舌前）。"},
            {"title": "圆唇", "text": "双唇收圆，注意舌位前后。"},
            {"title": "交替", "text": "wu / yu 各 5 遍。"},
            {"title": "录音", "text": "分别录 wu 与 yu。"},
            {"title": "总结", "text": "记录口型与听感差异。"},
        ],
        "mistakes": [{"title": "u ü 混淆", "text": "ü 时舌面更靠前。"}],
        "related": ["a", "i"],
    },
    "m": {
        "steps": [
            {"title": "听示范", "text": "感受鼻腔振动。"},
            {"title": "鼻音验证", "text": "捏住鼻子发 m，声音应中断。"},
            {"title": "跟读 ma", "text": "m + a 连贯 5 遍。"},
            {"title": "录音", "text": "录「妈」或延长 m 音。"},
            {"title": "看结果", "text": "检查鼻音与开口配合。"},
        ],
        "mistakes": [{"title": "口腔漏气", "text": "双唇未闭严；软腭需下降。"}],
        "related": ["ma", "n_l"],
    },
    "b_p": {
        "steps": [
            {"title": "听 ba / pa", "text": "注意送气差异。"},
            {"title": "手背试气", "text": "pa 有明显气流，ba 无。"},
            {"title": "交替 5 遍", "text": "ba-pa-ba-pa。"},
            {"title": "录音", "text": "各录一遍对比。"},
            {"title": "总结", "text": "记录 VOT/听感差异。"},
        ],
        "mistakes": [{"title": "送气混淆", "text": "b 送气过多会变成 p。"}],
        "related": ["d_t", "g_k"],
    },
    "d_t": {
        "steps": [
            {"title": "听 da / ta", "text": "舌尖抵上齿龈。"},
            {"title": "送气对比", "text": "手背感受 ta 气流。"},
            {"title": "交替练习", "text": "da-ta 各 5 遍。"},
            {"title": "录音", "text": "提交对比录音。"},
            {"title": "调整", "text": "按四步反馈重录。"},
        ],
        "mistakes": [{"title": "成阻部位偏后", "text": "舌位应抵上齿龈而非硬腭。"}],
        "related": ["b_p", "n_l"],
    },
    "n_l": {
        "steps": [
            {"title": "听 na / la", "text": "n 鼻音，l 边音。"},
            {"title": "捏鼻验证", "text": "发 n 时捏鼻声音中断。"},
            {"title": "交替", "text": "na-la 慢速 8 遍。"},
            {"title": "录音", "text": "各录一遍。"},
            {"title": "对比", "text": "看识别结果与建议。"},
        ],
        "mistakes": [{"title": "n/l 混淆", "text": "n 气流走鼻，l 走舌侧。"}],
        "related": ["m", "ma"],
    },
    "g_k": {
        "steps": [
            {"title": "听 ga / ka", "text": "舌根抵软腭。"},
            {"title": "送气", "text": "ka 有明显喷气流。"},
            {"title": "交替", "text": "ga-ka 5 遍。"},
            {"title": "录音", "text": "提交分析。"},
            {"title": "重录", "text": "按建议再录一次。"},
        ],
        "mistakes": [{"title": "部位偏前", "text": "应感到喉后上部成阻。"}],
        "related": ["b_p", "d_t"],
    },
    "j_q_x": {
        "steps": [
            {"title": "听 ji / qi / xi", "text": "舌面前部抬向硬腭。"},
            {"title": "口型", "text": "j/q 成阻，x 留缝摩擦。"},
            {"title": "慢读", "text": "各 3 遍。"},
            {"title": "录音", "text": "录目标音节。"},
            {"title": "对比平翘舌", "text": "与 z/zh 单元对照。"},
        ],
        "mistakes": [{"title": "发成平舌", "text": "舌面再抬高，避免 z/c/s 部位。"}],
        "related": ["z_zh"],
    },
    "z_zh": {
        "steps": [
            {"title": "听 za / zha", "text": "平舌 vs 翘舌。"},
            {"title": "舌位", "text": "z 抵下齿背，zh 卷舌抵硬腭前。"},
            {"title": "交替", "text": "za-zha 8 遍。"},
            {"title": "录音", "text": "提交对比。"},
            {"title": "重录", "text": "按现象调整舌位。"},
        ],
        "mistakes": [{"title": "翘舌不足", "text": "zh 时舌尖再上卷。"}],
        "related": ["j_q_x", "n_l"],
    },
    "ma_tone": {
        "steps": [
            {"title": "听四声", "text": "妈麻马骂 各 2 遍。"},
            {"title": "划轨迹", "text": "手随声调走向移动。"},
            {"title": "连读", "text": "四声连读 3 轮。"},
            {"title": "录音", "text": "录四声或单声。"},
            {"title": "看 F0", "text": "对照曲线与标准走向。"},
        ],
        "mistakes": [{"title": "上声不到位", "text": "214 先降后升要够明显。"}],
        "related": ["ma", "m"],
    },
    "ma": {
        "steps": [
            {"title": "听示范", "text": "妈 mā 高平调。"},
            {"title": "分解", "text": "m（鼻音）+ a（开口）+ 高平调。"},
            {"title": "跟读 5 遍", "text": "慢速后正常语速。"},
            {"title": "录音", "text": "完成检测闭环。"},
            {"title": "再录", "text": "按四步反馈调整后重录。"},
        ],
        "mistakes": [
            {"title": "声调下掉", "text": "阴平应保持高平，结尾勿掉调。"},
            {"title": "鼻音不足", "text": "双唇闭合，软腭降。"},
        ],
        "related": ["m", "a", "ma_tone"],
    },
}


def _seed_units(conn: sqlite3.Connection) -> None:
    """播种核心发音单元（幂等：仅插入不存在的单元）"""
    now = _now()
    for idx, u in enumerate(CORE_UNITS):
        enrich = APPENDIX_A_ENRICHMENT.get(u["id"], {})
        steps = json.dumps(enrich.get("steps", []), ensure_ascii=False)
        mistakes = json.dumps(enrich.get("mistakes", []), ensure_ascii=False)
        related = json.dumps(enrich.get("related", []), ensure_ascii=False)
        exists = conn.execute("SELECT 1 FROM pronunciation_units WHERE id = ?", (u["id"],)).fetchone()
        if exists:
            continue
        conn.execute(
            """INSERT INTO pronunciation_units
               (id, pinyin, character, category, description, conclusion, detail, mistakes, steps,
                related, status, verified, order_no, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', ?, ?, ?, ?)""",
            (u["id"], u["pinyin"], u["character"], u["category"], "", u["conclusion"], u["detail"],
             mistakes, steps, related, u["verified"], idx + 1, now, now),
        )
    _enrich_appendix_a_units(conn)


def _enrich_appendix_a_units(conn: sqlite3.Connection) -> None:
    """为内容为空的发音单元补全练习步骤、常见误区和关联单元"""
    now = _now()
    for uid, enrich in APPENDIX_A_ENRICHMENT.items():
        row = conn.execute(
            "SELECT steps, mistakes, related FROM pronunciation_units WHERE id = ?", (uid,)
        ).fetchone()
        if not row:
            continue
        steps = row["steps"] or "[]"
        mistakes = row["mistakes"] or "[]"
        related = row["related"] or "[]"
        if steps != "[]" and mistakes != "[]" and related != "[]":
            continue
        conn.execute(
            """UPDATE pronunciation_units SET steps=?, mistakes=?, related=?, updated_at=?
               WHERE id=? AND (steps='[]' OR mistakes='[]' OR related='[]')""",
            (
                json.dumps(enrich.get("steps", []), ensure_ascii=False) if steps == "[]" else steps,
                json.dumps(enrich.get("mistakes", []), ensure_ascii=False) if mistakes == "[]" else mistakes,
                json.dumps(enrich.get("related", []), ensure_ascii=False) if related == "[]" else related,
                now,
                uid,
            ),
        )


def _default_progress(user_id: str) -> dict:
    """构造新用户的默认进度（覆盖全部单元）"""
    return {
        "userId": user_id,
        "totalUnits": len(DEFAULT_UNITS),
        "completedUnits": 0,
        "totalPractice": 0,
        "averageScore": 0.0,
        "lastPracticeAt": "",
        "unitProgress": [
            {
                "unitId": u["id"],
                "pinyin": u["pinyin"],
                "character": u["character"],
                "bestScore": 0,
                "practiceCount": 0,
                "lastPracticeAt": "",
                "status": "not_started",
            }
            for u in DEFAULT_UNITS
        ],
    }


def _row_to_progress(row: sqlite3.Row) -> dict:
    unit_progress = json.loads(row["unit_progress"] or "[]")
    return {
        "userId": row["user_id"],
        "totalUnits": row["total_units"],
        "completedUnits": row["completed_units"],
        "totalPractice": row["total_practice"],
        "averageScore": row["average_score"],
        "lastPracticeAt": row["last_practice_at"],
        "unitProgress": unit_progress,
    }


def _record_to_dict(row: sqlite3.Row) -> dict:
    """记录 → 前端字段格式（不含 BLOB，附 audioUrl 指向音频流接口）"""
    return {
        "id": row["id"],
        "userId": row["user_id"],
        "unitId": row["unit_id"],
        "pinyin": row["pinyin"],
        "character": row["character"],
        "score": row["score"],
        "accuracy": row["accuracy"],
        "fluency": row["fluency"],
        "pronunciation": row["pronunciation"],
        "duration": row["duration"],
        "feedback": row["feedback"],
        "audioUrl": f"/api/learning-records/{row['id']}/audio",
        "createdAt": row["created_at"],
    }


def _upsert_progress(conn: sqlite3.Connection, progress: dict) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO user_progress
            (user_id, total_units, completed_units, total_practice, average_score, last_practice_at, unit_progress)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            progress["userId"],
            progress["totalUnits"],
            progress["completedUnits"],
            progress["totalPractice"],
            progress["averageScore"],
            progress["lastPracticeAt"],
            json.dumps(progress["unitProgress"], ensure_ascii=False),
        ),
    )


def create_learning_record(
    user_id: str,
    unit_id: str,
    pinyin: str,
    character: str,
    score: float,
    accuracy: float,
    fluency: float,
    pronunciation: float,
    duration: float,
    feedback: str,
    audio_blob: Optional[bytes],
    audio_type: str = "audio/webm",
) -> str:
    """写学习记录 + 同一事务内同步更新用户进度，返回 record_id"""
    record_id = uuid.uuid4().hex
    created_at = _now()
    conn = _connect()
    try:
        conn.execute("BEGIN")
        # 1. 写入学习记录（含录音二进制）
        conn.execute(
            """
            INSERT INTO learning_records
                (id, user_id, unit_id, pinyin, character, score, accuracy, fluency,
                 pronunciation, duration, feedback, audio_blob, audio_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id, user_id, unit_id, pinyin, character, score, accuracy,
                fluency, pronunciation, duration, feedback, audio_blob, audio_type, created_at,
            ),
        )

        # 2. 读取或初始化用户进度
        row = conn.execute(
            "SELECT * FROM user_progress WHERE user_id = ?", (user_id,)
        ).fetchone()
        progress = _row_to_progress(row) if row else _default_progress(user_id)

        # 3. 根据学习记录更新单元进度
        progress["totalPractice"] += 1
        progress["lastPracticeAt"] = created_at

        unit = next((u for u in progress["unitProgress"] if u["unitId"] == unit_id), None)
        if unit is None:
            unit = {
                "unitId": unit_id,
                "pinyin": pinyin,
                "character": character,
                "bestScore": 0,
                "practiceCount": 0,
                "lastPracticeAt": "",
                "status": "not_started",
            }
            progress["unitProgress"].append(unit)

        unit["practiceCount"] += 1
        unit["lastPracticeAt"] = created_at
        if score >= 80 and unit["status"] != "completed":
            unit["status"] = "completed"
        elif unit["status"] == "not_started":
            unit["status"] = "in_progress"
        if score > unit["bestScore"]:
            unit["bestScore"] = score

        # 完成单元数按状态重算，避免增量维护出错
        progress["completedUnits"] = sum(
            1 for u in progress["unitProgress"] if u["status"] == "completed"
        )
        # 平均分 = 该用户全部记录的平均分（SQL 聚合）
        avg = conn.execute(
            "SELECT AVG(score) FROM learning_records WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        progress["averageScore"] = round(avg, 1) if avg else 0.0

        _upsert_progress(conn, progress)
        conn.commit()
        return record_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_learning_records(user_id: str, limit: int = 20) -> list[dict]:
    """获取指定用户的学习记录（不含 BLOB）"""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM learning_records WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [_record_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_all_learning_records(limit: int = 100) -> list[dict]:
    """获取全部用户的学习记录（后台管理用，不含 BLOB）"""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM learning_records ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_record_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_audio(record_id: str) -> Optional[tuple[bytes, str]]:
    """按记录 id 获取录音二进制与 MIME 类型；不存在返回 None"""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT audio_blob, audio_type FROM learning_records WHERE id = ?",
            (record_id,),
        ).fetchone()
        if row is None or row["audio_blob"] is None:
            return None
        return (row["audio_blob"], row["audio_type"] or "audio/webm")
    finally:
        conn.close()


def get_user_progress(user_id: str) -> dict:
    """获取用户进度；用户不存在时初始化默认进度"""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM user_progress WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            progress = _default_progress(user_id)
            _upsert_progress(conn, progress)
            conn.commit()
            return progress
        return _row_to_progress(row)
    finally:
        conn.close()


def update_user_progress(user_id: str, progress: dict) -> None:
    """手动更新用户进度（兼容原接口）"""
    conn = _connect()
    try:
        conn.execute("BEGIN")
        data = {
            "userId": user_id,
            "totalUnits": progress.get("totalUnits", len(DEFAULT_UNITS)),
            "completedUnits": progress.get("completedUnits", 0),
            "totalPractice": progress.get("totalPractice", 0),
            "averageScore": progress.get("averageScore", 0.0),
            "lastPracticeAt": progress.get("lastPracticeAt", ""),
            "unitProgress": progress.get("unitProgress", []),
        }
        _upsert_progress(conn, data)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_stats() -> dict:
    """后台统计卡片数据（SQL 聚合，不拉全表）"""
    conn = _connect()
    try:
        total_users = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM learning_records"
        ).fetchone()[0]
        total_records = conn.execute(
            "SELECT COUNT(*) FROM learning_records"
        ).fetchone()[0]
        today = datetime.now().strftime("%Y-%m-%d")
        today_records = conn.execute(
            "SELECT COUNT(*) FROM learning_records WHERE date(created_at) = ?",
            (today,),
        ).fetchone()[0]
        avg_row = conn.execute("SELECT AVG(score) FROM learning_records").fetchone()[0]
        avg_score = round(avg_row, 1) if avg_row else 0.0

        completed = total = 0
        for r in conn.execute(
            "SELECT total_units, completed_units FROM user_progress"
        ).fetchall():
            total += r["total_units"]
            completed += r["completed_units"]
        completion_rate = round(completed / total * 100) if total else 0

        return {
            "totalUsers": total_users,
            "totalRecords": total_records,
            "todayRecords": today_records,
            "averageScore": avg_score,
            "completionRate": completion_rate,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 发音单元 CRUD（后台内容管理）
# ---------------------------------------------------------------------------
def _unit_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "pinyin": row["pinyin"],
        "character": row["character"],
        "category": row["category"],
        "description": row["description"],
        "conclusion": row["conclusion"],
        "detail": row["detail"],
        "mistakes": json.loads(row["mistakes"] or "[]"),
        "steps": json.loads(row["steps"] or "[]"),
        "related": json.loads(row["related"] or "[]"),
        "status": row["status"],
        "verified": bool(row["verified"]),
        "order": row["order_no"],
        "demoAudio": row["demo_audio"],
        "practice": json.loads(row["practice"] or "[]"),
        "version": row["version"],
        "submitReviewTime": row["submit_review_time"] or None,
        "reviewTime": row["review_time"] or None,
        "reviewer": row["reviewer"] or None,
        "reviewComment": row["review_comment"] or None,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def get_units(status: str = "") -> list[dict]:
    """获取发音单元列表；status 为空返回全部"""
    conn = _connect()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM pronunciation_units WHERE status = ? ORDER BY order_no", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM pronunciation_units ORDER BY order_no"
            ).fetchall()
        return [_unit_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_unit(unit_id: str) -> Optional[dict]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM pronunciation_units WHERE id = ?", (unit_id,)
        ).fetchone()
        return _unit_to_dict(row) if row else None
    finally:
        conn.close()


def create_unit(data: dict, operator: str = "admin") -> str:
    """录入发音单元：状态恒为草稿 draft（未审核不公开），版本从 1 起。
    状态机口径：录入即草稿，发布必须走 /api/admin/units/{id}/approve 审核流转。"""
    now = _now()
    conn = _connect()
    try:
        unit_id = data.get("id") or uuid.uuid4().hex[:8]
        conn.execute(
            """INSERT INTO pronunciation_units
               (id, pinyin, character, category, description, conclusion, detail, mistakes, steps,
                related, status, verified, order_no, demo_audio, practice, version,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, 1, ?, ?)""",
            (unit_id, data.get("pinyin", ""), data.get("character", ""), data.get("category", "声母"),
             data.get("description", ""), data.get("conclusion", ""), data.get("detail", ""),
             json.dumps(data.get("mistakes", []), ensure_ascii=False),
             json.dumps(data.get("steps", []), ensure_ascii=False),
             json.dumps(data.get("related", []), ensure_ascii=False),
             1 if data.get("verified") else 0, int(data.get("order", 0)),
             data.get("demo_audio", ""),
             json.dumps(data.get("practice", []), ensure_ascii=False),
             now, now),
        )
        _write_audit(conn, operator, "create", unit_id, f"新建单元：{data.get('pinyin', '')}")
        conn.commit()
        return unit_id
    finally:
        conn.close()


def update_unit(unit_id: str, data: dict, operator: str = "admin") -> bool:
    """编辑发音单元（内容编辑，状态机约束）：
    - 内容字段仅草稿/驳回状态可改，待审核/已发布返回 CmsStateError；
    - 状态变更不可走本接口，必须走审核流转接口（submit-review / approve / reject / unpublish）；
    - 每次成功编辑 version 自动 +1，并落操作日志。"""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM pronunciation_units WHERE id = ?", (unit_id,)
        ).fetchone()
        if row is None:
            return False
        cur = _unit_to_dict(row)

        # 状态机约束：status 只允许原值；内容字段（除 verified/order）仅草稿/驳回可改
        if "status" in data and data.get("status") != cur["status"]:
            raise CmsStateError(
                f"状态变更请走审核流转接口（当前「{cur['status']}」），不可直接修改"
            )
        content_keys = {k for k in data if k not in ("verified", "order", "status")}
        if content_keys and cur["status"] not in EDITABLE_STATUSES:
            raise CmsStateError(
                f"当前状态为「{cur['status']}」，不允许编辑；仅草稿/驳回状态可编辑"
            )

        merged = {**cur, **{k: v for k, v in data.items() if k in cur or k == "order"}}
        merged["version"] = int(cur["version"]) + 1
        conn.execute(
            """UPDATE pronunciation_units SET pinyin=?, character=?, category=?, description=?,
               conclusion=?, detail=?, mistakes=?, steps=?, related=?, status=?, verified=?,
               order_no=?, demo_audio=?, practice=?, version=?, updated_at=? WHERE id=?""",
            (merged["pinyin"], merged["character"], merged["category"], merged["description"],
             merged["conclusion"], merged["detail"],
             json.dumps(merged["mistakes"], ensure_ascii=False),
             json.dumps(merged["steps"], ensure_ascii=False),
             json.dumps(merged["related"], ensure_ascii=False),
             merged["status"], 1 if merged["verified"] else 0, merged["order"],
             merged["demoAudio"],
             json.dumps(merged["practice"], ensure_ascii=False),
             merged["version"], _now(), unit_id),
        )
        _write_audit(
            conn, operator, "update", unit_id,
            f"编辑内容（版本 v{cur['version']} → v{merged['version']}）",
        )
        conn.commit()
        return True
    finally:
        conn.close()


def delete_unit(unit_id: str, operator: str = "admin") -> bool:
    """删除发音单元（仅扩展单元；核心单元由路由层保护）。删除也落操作日志。"""
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM pronunciation_units WHERE id = ?", (unit_id,))
        if cur.rowcount > 0:
            _write_audit(conn, operator, "delete", unit_id, "删除单元")
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CMS 审核流转、下架与检测开关
# 返回流转后的单元字典；单元不存在返回 None；非法流转抛 CmsStateError
# ---------------------------------------------------------------------------
def _fetch_unit(conn: sqlite3.Connection, unit_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM pronunciation_units WHERE id = ?", (unit_id,)
    ).fetchone()


def submit_review(unit_id: str, operator: str = "admin") -> dict | None:
    """提交审核：draft/rejected -> pending_review；重提清空上一轮审核结论"""
    conn = _connect()
    try:
        row = _fetch_unit(conn, unit_id)
        if row is None:
            return None
        cur = _unit_to_dict(row)
        _check_transition(cur["status"], "submit_review")
        now = _now()
        conn.execute(
            """UPDATE pronunciation_units
               SET status='pending_review', submit_review_time=?,
                   review_time='', reviewer='', review_comment='', updated_at=?
               WHERE id=?""",
            (now, now, unit_id),
        )
        _write_audit(conn, operator, "submit_review", unit_id, "提交审核")
        conn.commit()
        return _unit_to_dict(_fetch_unit(conn, unit_id))
    finally:
        conn.close()


def approve_unit(unit_id: str, operator: str = "admin") -> dict | None:
    """审核通过（发布）：pending_review -> published，记录审核人与时间"""
    conn = _connect()
    try:
        row = _fetch_unit(conn, unit_id)
        if row is None:
            return None
        cur = _unit_to_dict(row)
        _check_transition(cur["status"], "approve")
        now = _now()
        conn.execute(
            """UPDATE pronunciation_units
               SET status='published', review_time=?, reviewer=?, review_comment='', updated_at=?
               WHERE id=?""",
            (now, operator or "admin", now, unit_id),
        )
        _write_audit(conn, operator, "approve", unit_id, "审核通过并发布")
        conn.commit()
        return _unit_to_dict(_fetch_unit(conn, unit_id))
    finally:
        conn.close()


def reject_unit(unit_id: str, operator: str = "admin", comment: str = "") -> dict | None:
    """审核驳回：pending_review -> rejected，驳回原因必填"""
    if not (comment or "").strip():
        raise CmsStateError("驳回必须填写原因（review_comment）")
    conn = _connect()
    try:
        row = _fetch_unit(conn, unit_id)
        if row is None:
            return None
        cur = _unit_to_dict(row)
        _check_transition(cur["status"], "reject")
        now = _now()
        conn.execute(
            """UPDATE pronunciation_units
               SET status='rejected', review_time=?, reviewer=?, review_comment=?, updated_at=?
               WHERE id=?""",
            (now, operator or "admin", comment.strip(), now, unit_id),
        )
        _write_audit(conn, operator, "reject", unit_id, f"驳回原因：{comment.strip()}")
        conn.commit()
        return _unit_to_dict(_fetch_unit(conn, unit_id))
    finally:
        conn.close()


def unpublish_unit(unit_id: str, operator: str = "admin") -> dict | None:
    """下架：published -> draft，大众端立即不可见（未审核不公开）"""
    conn = _connect()
    try:
        row = _fetch_unit(conn, unit_id)
        if row is None:
            return None
        cur = _unit_to_dict(row)
        _check_transition(cur["status"], "unpublish")
        conn.execute(
            """UPDATE pronunciation_units SET status='draft', updated_at=? WHERE id=?""",
            (_now(), unit_id),
        )
        _write_audit(conn, operator, "unpublish", unit_id, "下架（回到草稿）")
        conn.commit()
        return _unit_to_dict(_fetch_unit(conn, unit_id))
    finally:
        conn.close()


def set_detection(unit_id: str, operator: str = "admin", verified: bool = False) -> dict | None:
    """设置发音单元的检测开关，并记录操作日志。"""
    conn = _connect()
    try:
        row = _fetch_unit(conn, unit_id)
        if row is None:
            return None
        conn.execute(
            "UPDATE pronunciation_units SET verified=?, updated_at=? WHERE id=?",
            (1 if verified else 0, _now(), unit_id),
        )
        _write_audit(
            conn, operator, "set_detection", unit_id,
            f"检测开关：{'开启' if verified else '关闭'}",
        )
        conn.commit()
        return _unit_to_dict(_fetch_unit(conn, unit_id))
    finally:
        conn.close()


def get_audit_logs(resource_id: str = "", limit: int = 100) -> list[dict]:
    """操作日志查询：可按资源 id 过滤，倒序返回"""
    conn = _connect()
    try:
        if resource_id:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE resource_id = ? ORDER BY id DESC LIMIT ?",
                (resource_id, max(1, min(limit, 500))),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "operator": r["operator"],
                "action": r["action"],
                "resourceType": r["resource_type"],
                "resourceId": r["resource_id"],
                "remark": r["remark"],
                "createdAt": r["created_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 用户反馈 CRUD（大众反馈闭环）
# ---------------------------------------------------------------------------
def create_feedback(data: dict) -> str:
    fb_id = uuid.uuid4().hex
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO feedbacks
               (id, user_id, type, page, unit_id, rating, message, status, handle_note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', '', ?)""",
            (fb_id, data.get("userId", "default_user"), data.get("type", "learning"),
             data.get("page", ""), data.get("unitId", ""), data.get("rating", ""),
             data.get("message", ""), _now()),
        )
        conn.commit()
        return fb_id
    finally:
        conn.close()


def get_feedbacks(status: str = "") -> list[dict]:
    conn = _connect()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM feedbacks WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM feedbacks ORDER BY created_at DESC"
            ).fetchall()
        return [
            {
                "id": r["id"], "userId": r["user_id"], "type": r["type"], "page": r["page"],
                "unitId": r["unit_id"], "rating": r["rating"], "message": r["message"],
                "status": r["status"], "handleNote": r["handle_note"], "createdAt": r["created_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def update_feedback_status(fb_id: str, status: str, note: str = "") -> bool:
    conn = _connect()
    try:
        cur = conn.execute(
            "UPDATE feedbacks SET status = ?, handle_note = ? WHERE id = ?",
            (status, note, fb_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 收藏 CRUD（注册用户收藏发音/单元）
# ---------------------------------------------------------------------------
def get_favorites(user_id: str) -> list[str]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT unit_id FROM favorites WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        return [r["unit_id"] for r in rows]
    finally:
        conn.close()


def add_favorite(user_id: str, unit_id: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO favorites (user_id, unit_id, created_at) VALUES (?, ?, ?)",
            (user_id, unit_id, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def remove_favorite(user_id: str, unit_id: str) -> None:
    conn = _connect()
    try:
        conn.execute("DELETE FROM favorites WHERE user_id = ? AND unit_id = ?", (user_id, unit_id))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 媒体资源 CRUD（后台媒体上传）
# ---------------------------------------------------------------------------
def create_media(name: str, file_type: str, mime: str, size: int, path: str) -> str:
    media_id = uuid.uuid4().hex
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO media_assets (id, name, file_type, mime, size, path, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (media_id, name, file_type, mime, size, path, _now()),
        )
        conn.commit()
        return media_id
    finally:
        conn.close()


def get_media_list() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM media_assets ORDER BY created_at DESC"
        ).fetchall()
        return [
            {"id": r["id"], "name": r["name"], "type": r["file_type"], "mime": r["mime"],
             "size": r["size"], "path": r["path"], "createdAt": r["created_at"]}
            for r in rows
        ]
    finally:
        conn.close()


def get_media(media_id: str) -> Optional[dict]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM media_assets WHERE id = ?", (media_id,)
        ).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "name": row["name"], "type": row["file_type"],
                "mime": row["mime"], "size": row["size"], "path": row["path"],
                "createdAt": row["created_at"]}
    finally:
        conn.close()


def delete_media(media_id: str) -> bool:
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM media_assets WHERE id = ?", (media_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 学习记录删除（声音档案用户控制）
# ---------------------------------------------------------------------------
def delete_learning_record(record_id: str, user_id: str = "") -> bool:
    """删除单条学习记录；user_id 非空时校验归属。删除后重算该用户进度。"""
    conn = _connect()
    try:
        conn.execute("BEGIN")
        if user_id:
            cur = conn.execute(
                "DELETE FROM learning_records WHERE id = ? AND user_id = ?", (record_id, user_id)
            )
        else:
            cur = conn.execute("DELETE FROM learning_records WHERE id = ?", (record_id,))
        if cur.rowcount == 0:
            conn.rollback()
            return False
        _recalc_progress(conn, user_id or _record_owner(conn, record_id))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_all_learning_records(user_id: str) -> int:
    """删除用户全部学习记录，返回删除条数，并重置进度"""
    conn = _connect()
    try:
        conn.execute("BEGIN")
        cur = conn.execute("DELETE FROM learning_records WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_progress WHERE user_id = ?", (user_id,))
        conn.commit()
        return cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _record_owner(conn: sqlite3.Connection, record_id: str) -> str:
    row = conn.execute(
        "SELECT user_id FROM learning_records WHERE id = ?", (record_id,)
    ).fetchone()
    return row["user_id"] if row else "default_user"


def _recalc_progress(conn: sqlite3.Connection, user_id: str) -> None:
    """按剩余记录重算用户进度（删除后一致性）"""
    row = conn.execute(
        "SELECT * FROM user_progress WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row is None:
        return
    progress = _row_to_progress(row)
    records = conn.execute(
        "SELECT * FROM learning_records WHERE user_id = ?", (user_id,)
    ).fetchall()
    progress["totalPractice"] = len(records)
    progress["averageScore"] = round(
        (sum(r["score"] for r in records) / len(records)), 1
    ) if records else 0.0
    progress["lastPracticeAt"] = records[0]["created_at"] if records else ""
    for unit in progress["unitProgress"]:
        unit["practiceCount"] = 0
        unit["bestScore"] = 0
        unit["lastPracticeAt"] = ""
        unit["status"] = "not_started"
    for r in records:
        unit = next((u for u in progress["unitProgress"] if u["unitId"] == r["unit_id"]), None)
        if unit is None:
            unit = {"unitId": r["unit_id"], "pinyin": r["pinyin"], "character": r["character"],
                    "bestScore": 0, "practiceCount": 0, "lastPracticeAt": "", "status": "not_started"}
            progress["unitProgress"].append(unit)
        unit["practiceCount"] += 1
        unit["lastPracticeAt"] = r["created_at"]
        if r["score"] > unit["bestScore"]:
            unit["bestScore"] = r["score"]
        if r["score"] >= 80 and unit["status"] != "completed":
            unit["status"] = "completed"
        elif unit["status"] == "not_started":
            unit["status"] = "in_progress"
    progress["completedUnits"] = sum(
        1 for u in progress["unitProgress"] if u["status"] == "completed"
    )
    _upsert_progress(conn, progress)
