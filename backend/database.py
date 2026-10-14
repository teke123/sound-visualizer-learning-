"""
看得见的声音 - 数据访问层（重构占位骨架）

意图（重构时按此恢复实现）：
- 持久化：学习记录（含录音二进制）、用户进度、发音单元（CMS）、简单账号与同意记录、
  反馈、媒体、版本快照、操作日志；
- 一致性不变量：
    1) 进度只能由学习记录派生（同事务更新），不提供任何手动覆写入口；
    2) 列表/统计接口绝不携带录音 BLOB，音频按记录 id 单独拉取；
    3) 时间戳统一 created_at（ISO8601 UTC），「今日」等口径必须与存储时区一致；
    4) 删除记录后按剩余记录重算进度（lastPracticeAt 取最新一条，需 ORDER BY）。
- 发音单元内容（目录、教学文案、练习步骤）不写在代码里，由 CMS 录入并存于库中；
- 操作人不接受客户端传入，待管理员鉴权（NFR-16）接入后由服务端会话提供。
"""

DB_PATH = "pronunciation.db"


# ===========================================================================
# CMS 关卡发布状态机（SRS 05 附录 C）
# 草稿 -> 已发布（须满足 FR-1203 发布前置条件）
# 已发布 -> 已下架（大众端即时不可见）
# 已下架 -> 已发布（须重新满足 FR-1203）
# 检测开关是独立状态（关闭/开放），开放仅当关卡已发布且满足 FR-1204
# ===========================================================================
UNIT_STATUS_TRANSITIONS = {
    "draft": {"publish": "published"},
    "published": {"unpublish": "unpublished"},
    "unpublished": {"publish": "published"},
}
# 仅草稿/已下架允许编辑内容；检测开关不受此限，走专用接口
EDITABLE_STATUSES = ("draft", "unpublished")


class CmsStateError(ValueError):
    """非法 CMS 状态流转（迁移不在 SRS 附录 C 状态机内，或前置条件不满足）"""


def init_db(db_path: str = DB_PATH) -> None:
    """意图：幂等建表 + 增量迁移（老库补列不丢数据）。实现待重构。"""
    raise NotImplementedError("重构占位：数据库初始化")


# ---------------------------------------------------------------------------
# 发音单元（CMS 内容管理；内容数据只存库里，代码不带目录）
# ---------------------------------------------------------------------------
def get_units(status: str = "") -> list[dict]:
    """意图：单元列表，status 为空返回全部（大众端只查 published）。"""
    raise NotImplementedError("重构占位：单元列表")


def get_unit(unit_id: str) -> dict | None:
    """意图：单个单元详情（含治理字段：发布状态 / 检测开关 / 版本），不存在返回 None。"""
    raise NotImplementedError("重构占位：单元详情")


def create_unit(data: dict) -> str:
    """意图：录入单元，状态恒为草稿；字段需经请求模型校验（不收裸 dict）。"""
    raise NotImplementedError("重构占位：录入单元")


def update_unit(unit_id: str, data: dict) -> bool:
    """意图：编辑内容（仅草稿/已下架），version 自动 +1，落操作日志。"""
    raise NotImplementedError("重构占位：编辑单元")


def delete_unit(unit_id: str) -> bool:
    """意图：删除扩展单元（核心单元由路由层保护），落操作日志。"""
    raise NotImplementedError("重构占位：删除单元")


def publish_unit(unit_id: str) -> dict | None:
    """意图：draft/unpublished -> published；须先通过 FR-1203 发布前置校验，
    并满足关卡依赖规则（如 L30 待 L01、L09 均已发布）；content_version +1，
    落版本快照与操作日志（FR-1408）。"""
    raise NotImplementedError("重构占位：发布")


def unpublish_unit(unit_id: str) -> dict | None:
    """意图：published -> unpublished（已下架），大众端立即不可见（NFR-11）。"""
    raise NotImplementedError("重构占位：下架")


def set_detection(unit_id: str, verified: bool = False) -> dict | None:
    """意图：设置检测开关（开放仅当关卡已发布且满足 FR-1204；
    不能稳定评分的关只学不测，禁止假分），落操作日志。"""
    raise NotImplementedError("重构占位：检测开关")


def get_audit_logs(resource_id: str = "", limit: int = 100) -> list[dict]:
    """意图：CMS 操作日志查询，可按资源过滤。"""
    raise NotImplementedError("重构占位：操作日志")


# ---------------------------------------------------------------------------
# 学习记录与用户进度（进度由记录派生，无手动覆写入口）
# ---------------------------------------------------------------------------
def create_learning_record(
    user_id: str | None,
    unit_id: str,
    quality: dict,
    scores: dict,
    phenomena: list[dict],
    four_steps: list[dict],
    reliability: str,
    rule_version: int,
    content_version: int,
    duration: float,
    audio_blob: bytes | None,
    audio_type: str = "audio/webm",
    consent_id: str | None = None,
) -> str:
    """意图：写学习记录 + 同一事务内派生更新用户进度，返回 record_id。

    字段口径 = SRS 附录 B / FR-1010：quality 为两维结论（不合格时不填
    scores/phenomena）；scores 仅含本关已开放维度（如声韵分/调型分/总分）；
    结果快照携带规则版本与内容版本（FR-1208）；consent_id 记录写入档案
    所依据的同意记录（访客为 None，仅本会话可访问，NFR-09）。"""
    raise NotImplementedError("重构占位：创建学习记录")


def get_learning_records(user_id: str, limit: int = 20) -> list[dict]:
    """意图：用户学习记录（不含 BLOB，附 audioUrl）。"""
    raise NotImplementedError("重构占位：学习记录列表")


def get_audio(record_id: str) -> tuple[bytes, str] | None:
    """意图：按记录 id 取录音二进制与 MIME，不存在返回 None。"""
    raise NotImplementedError("重构占位：录音读取")


def get_user_progress(user_id: str) -> dict:
    """意图：读用户进度；totalUnits 以当前已发布单元数为准（不硬编码）。"""
    raise NotImplementedError("重构占位：用户进度")


def delete_learning_record(record_id: str, user_id: str) -> bool:
    """意图：删除单条记录（校验归属；归属须在删除前解析），重算进度。"""
    raise NotImplementedError("重构占位：删除记录")


def delete_all_learning_records(user_id: str) -> int:
    """意图：清空用户记录并重置进度，返回删除条数。"""
    raise NotImplementedError("重构占位：清空记录")


# ---------------------------------------------------------------------------
# 用户反馈 / 媒体
# ---------------------------------------------------------------------------
def create_feedback(data: dict) -> str:
    raise NotImplementedError("重构占位：提交反馈")


def get_feedbacks(status: str = "") -> list[dict]:
    raise NotImplementedError("重构占位：反馈列表")


def update_feedback_status(fb_id: str, status: str, note: str = "") -> bool:
    raise NotImplementedError("重构占位：反馈处理")


def create_media(name: str, file_type: str, mime: str, size: int, path: str) -> str:
    raise NotImplementedError("重构占位：媒体登记")


def get_media_list() -> list[dict]:
    raise NotImplementedError("重构占位：媒体列表")


def get_media(media_id: str) -> dict | None:
    raise NotImplementedError("重构占位：媒体详情")


def delete_media(media_id: str) -> bool:
    raise NotImplementedError("重构占位：删除媒体")
