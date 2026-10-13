"""CMS 管理路由（第 6 周 C：四状态机 + 下架 + 检测开关 + 操作日志）

从 week4 迁移而来，对齐仓库现有口径：
- 表：pronunciation_units（database.py 原生 sqlite3，不动其它表）；
- 状态值：draft / pending_review / rejected / published（仓库前台按 published 过滤）；
- 响应格式：{"code": 200, "data": ...}，错误 {"code": 400, "message": ...}。

鉴权口径（与 week4 一致，第 7 周管理员账号上线后替换）：
操作人经请求头 X-Operator 传入，缺省为 admin；本周不做登录鉴权。
"""
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from backend import database
from backend.database import CmsStateError

router = APIRouter(prefix="/api/admin", tags=["CMS管理接口"])


def get_operator(x_operator: str | None = Header(default=None)) -> str:
    """从请求头识别操作人；没传就记为 admin（第 7 周接管理员登录后替换）"""
    return x_operator or "admin"


def _ok(data):
    return {"code": 200, "data": data}


def _fail(message: str, status_code: int = 400):
    return JSONResponse(status_code=status_code, content={"code": status_code, "message": message})


def _get_or_404(unit_id: str) -> dict:
    unit = database.get_unit(unit_id)
    if unit is None:
        raise KeyError(unit_id)
    return unit


def _run(action, unit_id: str, operator: str, *args):
    """统一执行流转动作：404 转 KeyError，非法流转转 CmsStateError"""
    try:
        result = action(unit_id, operator, *args)
    except CmsStateError as exc:
        return _fail(str(exc))
    if result is None:
        return _fail(f"发音单元 {unit_id} 不存在", 404)
    return {"code": 200, "message": "操作成功", "data": result}


# ---------------------------------------------------------------------------
# CMS 单元列表 / 详情（管理员视角：全状态可见）
# ---------------------------------------------------------------------------
@router.get("/units")
def list_units(status: str = "", operator: str = Header(default="admin", alias="X-Operator")):
    """CMS 单元列表，可按状态筛选：?status=draft/pending_review/rejected/published"""
    return _ok(database.get_units(status))


@router.get("/units/{unit_id}")
def get_unit(unit_id: str):
    """CMS 单元详情（含审核字段）"""
    try:
        unit = _get_or_404(unit_id)
    except KeyError:
        return _fail(f"发音单元 {unit_id} 不存在", 404)
    return _ok(unit)


# ---------------------------------------------------------------------------
# CMS 审核流转四状态机
# ---------------------------------------------------------------------------
@router.post("/units/{unit_id}/submit-review")
def submit_review(unit_id: str, operator: str = Header(default="admin", alias="X-Operator")):
    """提交审核：draft/rejected -> pending_review（重提自动清空上一轮审核结论）"""
    return _run(database.submit_review, unit_id, operator)


@router.post("/units/{unit_id}/approve")
def approve_unit(unit_id: str, operator: str = Header(default="admin", alias="X-Operator")):
    """审核通过并发布：pending_review -> published（发布后大众端可见）"""
    return _run(database.approve_unit, unit_id, operator)


@router.post("/units/{unit_id}/reject")
def reject_unit(
    unit_id: str,
    payload: dict,
    operator: str = Header(default="admin", alias="X-Operator"),
):
    """审核驳回：pending_review -> rejected，请求体必须带 review_comment"""
    return _run(database.reject_unit, unit_id, operator, (payload or {}).get("review_comment", ""))


@router.post("/units/{unit_id}/unpublish")
def unpublish_unit(unit_id: str, operator: str = Header(default="admin", alias="X-Operator")):
    """下架：published -> draft，大众端立即不可见"""
    return _run(database.unpublish_unit, unit_id, operator)


# ---------------------------------------------------------------------------
# 检测开关（CON-04：不能稳定评分的关只学不测，禁止假分）
# ---------------------------------------------------------------------------
@router.post("/units/{unit_id}/set-detection")
def set_detection(
    unit_id: str,
    payload: dict,
    operator: str = Header(default="admin", alias="X-Operator"),
):
    """更新单元的 verified 检测开关。"""
    verified = bool((payload or {}).get("verified", False))
    return _run(database.set_detection, unit_id, operator, verified)


# ---------------------------------------------------------------------------
# 操作日志
# ---------------------------------------------------------------------------
@router.get("/audit-logs")
def audit_logs(resource_id: str = "", limit: int = 100):
    """操作日志查询：?resource_id=L01 查单个资源，?limit=200 调整条数"""
    return _ok(database.get_audit_logs(resource_id, limit))
