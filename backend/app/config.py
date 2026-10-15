"""运行配置：环境变量 + 缺省值（docs/architecture/03 第 1 节「配置」行）。

Provider 凭据只从环境变量读取；其余为部署可调参数。单进程单 worker 是
全部进程内状态（限流、执行器、调度）的前提，扩容前须迁移这些状态。
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("SVS_DATA_DIR", BACKEND_DIR / "data"))
PRIVATE_DIR = DATA_DIR / "private"     # 用户音频、标定音频
PUBLIC_DIR = DATA_DIR / "public"       # 已发布引用媒体（读取时仍校验发布引用）
DRAFT_DIR = DATA_DIR / "draft"         # 草稿媒体、授权材料
DB_PATH = DATA_DIR / "app.db"
DELETION_LOG_PATH = DATA_DIR / "deletion_log.jsonl"

# --- 基础 ---
ENV: str = os.environ.get("SVS_ENV", "dev")            # dev | prod
HOST: str = os.environ.get("SVS_HOST", "127.0.0.1")
PORT: int = int(os.environ.get("SVS_PORT", "8000"))
# 同源部署为本站地址；开发环境追加前端 dev server 源（CSRF Origin 校验用）
ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in os.environ.get(
        "SVS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",") if o.strip()
]
CSRF_ENFORCED: bool = os.environ.get("SVS_CSRF_ENFORCED", "1") not in ("0", "false", "no")

# 会话签名密钥：未配置时生成并落盘，重启保持稳定
_SECRET_FILE = DATA_DIR / "secret.key"


def _load_or_create_secret() -> str:
    env = os.environ.get("SVS_SECRET")
    if env:
        return env
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if _SECRET_FILE.exists():
        return _SECRET_FILE.read_text(encoding="utf-8").strip()
    value = secrets.token_hex(32)
    _SECRET_FILE.write_text(value, encoding="utf-8")
    return value


SECRET: str = _load_or_create_secret()

# --- 临时数据留存（D-15）---
TEMP_DATA_TTL_HOURS: int = 72          # 私有上传/临时录音/会话标定及缓存
HARD_DELETE_GRACE_HOURS: int = 24      # 本地物理删除上限
PREVIEW_TOKEN_TTL_MINUTES: int = 15    # 预览令牌（D 决策图 #21）

# --- 检测处理模型（决策图「检测处理模型」）---
SYNC_WINDOW_SECONDS: float = float(os.environ.get("SVS_SYNC_WINDOW", "8"))
HARD_DEADLINE_SECONDS: float = float(os.environ.get("SVS_HARD_DEADLINE", "30"))  # 自受理起
RETRY_AFTER_SECONDS: int = 2           # 202 响应 Retry-After
EXECUTOR_WORKERS: int = int(os.environ.get("SVS_EXECUTOR_WORKERS", "4"))
EXECUTOR_QUEUE_LIMIT: int = int(os.environ.get("SVS_EXECUTOR_QUEUE", "32"))

# --- 版本常量（进入缓存键与结果快照）---
RULE_VERSION: str = "rules-1.0.0"
# 声学算法版本：tone_py + parselmouth + 自研共振峰/质量分析
ALGORITHM_VERSION: str = "acx-1.0.0+tp0.1.0+pm0.4.7"
CONSENT_TEXT_VERSION: str = "v1"

CONSENT_TEXT: str = (
    "同意保存后，我们将保存你的学习进度、录音与检测结果，用于生成你的声音档案与进步对比；"
    "当前会话未过期的临时录音与音域标定会一并转存为长期档案。"
    "临时录音最长保留 72 小时，存档内容保留至你删除。"
    "你可以随时删除单条记录、清空档案或撤回同意（撤回将删除全部录音、进度与音域）。"
    "录音仅用于你的学习反馈，不会公开给他人。"
)

BOUNDARY_NOTE: str = "学习参考，不作为普通话等级认定或医学诊断。"

# --- 上传限制 ---
MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024   # 20 MB
MAX_AUDIO_DURATION_SECONDS: float = 60.0   # 单条上传时长上限（质量维度再判过短/过长）

# --- Provider（外部评分服务）---
PROVIDER_NAME: str = os.environ.get("SVS_PROVIDER", "mock")   # mock | xfyun
PROVIDER_VERSION: str = {"mock": "mock-1.0.0", "xfyun": "xfyun-ise-1.0"}.get(PROVIDER_NAME, "unknown")
XFYUN_APP_ID: str = os.environ.get("XFYUN_APP_ID", "")
XFYUN_API_KEY: str = os.environ.get("XFYUN_API_KEY", "")
XFYUN_API_SECRET: str = os.environ.get("XFYUN_API_SECRET", "")
XFYUN_WS_URL: str = os.environ.get("XFYUN_WS_URL", "wss://ise.api.xfyun.cn/v2/open-ise")

# --- 限流（令牌桶：次数 / 窗口秒）---
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "upload": (30, 300),
    "recording_submit": (20, 300),
    "calibration": (10, 600),
    "feature_read": (60, 300),
    "feedback": (10, 600),
    "wish": (10, 600),
    "register": (5, 3600),
    "login": (10, 600),
    "login_fail": (5, 600),
    "auth": (120, 300),
}

# --- 管理员（独立凭据，不与学习账号互通）---
ADMIN_USERNAME: str = os.environ.get("SVS_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD: str = os.environ.get("SVS_ADMIN_PASSWORD", "admin12345")

# --- 调度周期（docs/architecture/03 第 5.6 节）---
SWEEP_INTERVAL_SECONDS: float = 5.0        # 处理超时
EXPIRY_SWEEP_INTERVAL_SECONDS: float = 300  # 临时到期
CLEANUP_INTERVAL_SECONDS: float = 300       # 物理清理
PREVIEW_CLEAN_INTERVAL_SECONDS: float = 900 # 预览令牌清理


def ensure_dirs() -> None:
    for d in (DATA_DIR, PRIVATE_DIR, PUBLIC_DIR, DRAFT_DIR):
        d.mkdir(parents=True, exist_ok=True)
