"""运行配置：环境变量 + 缺省值。

支持从仓库根目录或 backend/ 目录的 `.env` 文件自动加载未设置的环境变量（不覆盖
进程已显式传入的环境变量）。Provider 凭据与语料库路径（CORPUS_DIR / SVS_CORPUS_DIR）
从环境变量读取；单进程单 worker 是全部进程内状态（限流、执行器、调度）的前提。
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


def _load_dotenv() -> None:
    """轻量级 .env 加载器（零额外依赖）：依次查找 backend/.env 与仓库根 .env，
    仅在 os.environ 中尚未存在对应键时写入。"""
    for env_file in (BACKEND_DIR / ".env", REPO_ROOT / ".env"):
        if not env_file.is_file():
            continue
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = val


_load_dotenv()

DATA_DIR = Path(os.environ.get("SVS_DATA_DIR", BACKEND_DIR / "data"))
PRIVATE_DIR = DATA_DIR / "private"     # 用户录音、标定音频
MEDIA_DIR = DATA_DIR / "media"         # 内容媒体（示范音、构形图、文章配图）
DB_PATH = DATA_DIR / "app.db"
DELETION_LOG_PATH = DATA_DIR / "deletion_log.jsonl"


def _resolve_corpus_dir() -> Path | None:
    raw = (os.environ.get("CORPUS_DIR") or os.environ.get("SVS_CORPUS_DIR") or "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    return p


# 真人标准音节语料库根目录（含 FV1~3、MV1~3 子目录）
CORPUS_DIR: Path | None = _resolve_corpus_dir()

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

# --- 检测处理模型（D-19：短同步 + 30 秒硬截止）---
SYNC_WINDOW_SECONDS: float = float(os.environ.get("SVS_SYNC_WINDOW", "8"))
HARD_DEADLINE_SECONDS: float = float(os.environ.get("SVS_HARD_DEADLINE", "30"))  # 自受理起
# 标定路由等待上限：与录音硬截止解耦（标定不受调度器 sweep 约束，
# 借用 HARD_DEADLINE 会让慢 Provider 场景下标定先于检测误超时）
CALIBRATION_TIMEOUT_SECONDS: float = float(os.environ.get("SVS_CALIBRATION_TIMEOUT", "45"))
RETRY_AFTER_SECONDS: int = 2           # 202 响应 Retry-After
EXECUTOR_WORKERS: int = int(os.environ.get("SVS_EXECUTOR_WORKERS", "4"))
EXECUTOR_QUEUE_LIMIT: int = int(os.environ.get("SVS_EXECUTOR_QUEUE", "32"))

# 声学算法版本：tone_py + parselmouth + 自研共振峰/质量分析
ALGORITHM_VERSION: str = "acx-1.1.0+tp0.1.0+pm0.4.7"

# 未标定用户的默认成人参考音域（Hz，D-20：跳过标定时正常检测）
DEFAULT_ADULT_F0_RANGE: tuple[float, float] = (95.0, 260.0)

# --- 上传限制 ---
MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024   # 20 MB
MAX_AUDIO_DURATION_SECONDS: float = 60.0   # 单条上传时长上限（质量维度再判过短/过长）

# --- Provider（外部评分服务）---
PROVIDER_NAME: str = os.environ.get("SVS_PROVIDER", "mock")   # mock | xfyun
PROVIDER_VERSION: str = {"mock": "mock-1.0.0", "xfyun": "xfyun-ise-1.0"}.get(PROVIDER_NAME, "unknown")
XFYUN_APP_ID: str = os.environ.get("XFYUN_APP_ID", "")
XFYUN_API_KEY: str = os.environ.get("XFYUN_API_KEY", "")
XFYUN_API_SECRET: str = os.environ.get("XFYUN_API_SECRET", "")
XFYUN_WS_URL: str = os.environ.get("XFYUN_WS_URL", "wss://ise-api.xfyun.cn/v2/open-ise")
XFYUN_CATEGORY: str = os.environ.get("XFYUN_CATEGORY", "read_syllable")   # 中文题型：read_syllable | read_word | read_sentence | read_chapter
XFYUN_TIMEOUT_SEC: float = float(os.environ.get("XFYUN_TIMEOUT_SEC", "20"))   # 单次评测整体预算（管线硬截止 30s）

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
    "auth": (120, 300),
}

# --- 管理员（团队自用后台的简单口令）---
ADMIN_USERNAME: str = os.environ.get("SVS_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD: str = os.environ.get("SVS_ADMIN_PASSWORD", "admin12345")

# --- 调度周期 ---
SWEEP_INTERVAL_SECONDS: float = 5.0        # 处理超时
CLEANUP_INTERVAL_SECONDS: float = 300       # 物理清理


def ensure_dirs() -> None:
    for d in (DATA_DIR, PRIVATE_DIR, MEDIA_DIR):
        d.mkdir(parents=True, exist_ok=True)
