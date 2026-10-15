"""看得见的声音 · 后端服务入口（单进程模块化单体，同源部署）。

- 组装 FastAPI 应用：/api 路由、/admin 管理台、OpenAPI（契约真源）；
- lifespan：建库、遗留 processing 恢复、定时任务启停；
- 运行：python main.py（backend/ 目录下）。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app import config
from app.db import create_all, get_session
from app.platform import scheduler
from app.platform.envelope import register_exception_handlers
from app.platform.request_context import RequestContextMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("svs")


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    create_all()
    # 重启恢复：遗留 processing 记录置为 failed(retryable, TIMEOUT)
    from app.detection.usecases import recover_on_startup

    db = get_session()
    try:
        n = recover_on_startup(db)
        if n:
            logger.warning("startup recovery: %d processing -> TIMEOUT", n)
    finally:
        db.close()
    tasks = scheduler.start()
    logger.info("backend started (env=%s provider=%s)", config.ENV, config.PROVIDER_NAME)
    yield
    scheduler.stop(tasks)


def create_app() -> FastAPI:
    app = FastAPI(
        title="看得见的声音 API",
        version="1.0.0",
        description="普通话发音学习平台后端（契约见 docs/decision-map-backend.md）",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware)

    from app.api import (
        routes_admin, routes_audio, routes_auth, routes_feedback, routes_me,
        routes_platform, routes_preview,
    )

    app.include_router(routes_platform.router)
    app.include_router(routes_auth.router)
    app.include_router(routes_audio.router)
    app.include_router(routes_me.router)
    app.include_router(routes_feedback.router)
    app.include_router(routes_preview.router)
    app.include_router(routes_admin.router)

    # 管理台单页（自建轻量后台，调用同一用例；部署预案见 routes_admin 模块注释）
    @app.get("/admin", include_in_schema=False)
    async def admin_page():
        return FileResponse(config.BACKEND_DIR / "app" / "admin_ui" / "index.html")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=config.HOST, port=config.PORT, workers=1, log_level="info")
