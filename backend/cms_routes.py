"""CMS 管理路由（对齐 SRS 05：三态发布状态机 + 检测开关 + 版本 + 操作日志）

口径：
- 表：pronunciation_units（database.py 原生 sqlite3，不动其它表）；
- 状态值：draft / published / unpublished（SRS 附录 C：草稿 -> 已发布 -> 已下架 -> 已发布；
  发布须过 FR-1203 前置校验；大众端按 published 过滤）；
- 检测开关独立于发布状态（FR-1202/1204），走 set-detection 专用接口；
- 响应格式：{"code": 200, "data": ...}，错误 {"code": 400, "message": ...}。

鉴权：本组路由全部要求管理员鉴权（NFR-16：发布 / 下架 / 检测开关 / 版本回退
须经鉴权，由管理员账号操作）；鉴权中间件待账号体系接入，操作人由服务端
会话提供，不接受客户端传入。
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend import database
from backend.database import CmsStateError

router = APIRouter(prefix="/api/admin", tags=["CMS管理接口"])


def _ok(data):
    return {"code": 200, "data": data}


def _fail(message: str, status_code: int = 400):
    return JSONResponse(status_code=status_code, content={"code": status_code, "message": message})


def _get_or_404(unit_id: str) -> dict:
    unit = database.get_unit(unit_id)
    if unit is None:
        raise KeyError(unit_id)
    return unit


def _run(action, unit_id: str, *args):
    """统一执行流转动作：404 转 KeyError，非法流转转 CmsStateError"""
    try:
        result = action(unit_id, *args)
    except CmsStateError as exc:
        return _fail(str(exc))
    if result is None:
        return _fail(f"发音单元 {unit_id} 不存在", 404)
    return {"code": 200, "message": "操作成功", "data": result}


# ---------------------------------------------------------------------------
# CMS 单元列表 / 详情（管理员视角：全状态可见）
# ---------------------------------------------------------------------------
@router.get("/units")
def list_units(status: str = ""):
    """CMS 单元列表，可按状态筛选：?status=draft/published/unpublished"""
    return _ok(database.get_units(status))


@router.get("/units/{unit_id}")
def get_unit(unit_id: str):
    """CMS 单元详情（含治理字段）"""
    try:
        unit = _get_or_404(unit_id)
    except KeyError:
        return _fail(f"发音单元 {unit_id} 不存在", 404)
    return _ok(unit)


# ---------------------------------------------------------------------------
# CMS 发布状态机（SRS 附录 C 三态：草稿 / 已发布 / 已下架）
# ---------------------------------------------------------------------------
@router.post("/units/{unit_id}/publish")
def publish_unit(unit_id: str):
    """发布：draft/unpublished -> published（须过 FR-1203 前置校验与关卡依赖规则；
    content_version +1 并落版本快照，大众端可见）"""
    return _run(database.publish_unit, unit_id)


@router.post("/units/{unit_id}/unpublish")
def unpublish_unit(unit_id: str):
    """下架：published -> unpublished（已下架），大众端立即不可见（NFR-11）"""
    return _run(database.unpublish_unit, unit_id)


# ---------------------------------------------------------------------------
# 检测开关（FR-1204：不能稳定评分的关只学不测，禁止假分）
# ---------------------------------------------------------------------------
@router.post("/units/{unit_id}/set-detection")
def set_detection(unit_id: str, payload: dict):
    """更新单元的 verified 检测开关（开放仅当已发布且满足 FR-1204）。"""
    verified = bool((payload or {}).get("verified", False))
    return _run(database.set_detection, unit_id, verified)


# ---------------------------------------------------------------------------
# 操作日志
# ---------------------------------------------------------------------------
@router.get("/audit-logs")
def audit_logs(resource_id: str = "", limit: int = 100):
    """操作日志查询：?resource_id=L01 查单个资源，?limit=200 调整条数"""
    return _ok(database.get_audit_logs(resource_id, limit))
