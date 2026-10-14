"""
看得见的声音 - 智能发音学习平台 后端服务（重构占位骨架）

本文件只保留应用框架与路由意图：
- FastAPI 应用、CORS、路由挂载（CMS 发布治理 / ASR 诊断 / 声学特征）；
- 其余业务端点（学习记录、进度、反馈、媒体、LLM）为 501 意图占位，
  待重构逐个恢复实现；
- 发音单元的内容 CRUD 只保留 CMS 入口（cms_routes.py），大众端只读列表
  由已发布单元派生。
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend import cms_routes
from backend.routes import audio, asr

app = FastAPI(title="看得见的声音 API", version="2.0.0-rebuild")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CMS 管理接口（发音单元唯一的内容 CRUD 入口：三态发布状态机 / 下架 / 检测开关 / 操作日志）
app.include_router(cms_routes.router)
app.include_router(asr.router)
app.include_router(audio.router)


@app.get("/")
async def root():
    return {"message": "看得见的声音 API", "version": "2.0.0-rebuild"}


# ---------------------------------------------------------------------------
# 大众端发音单元（只读；内容管理唯一入口是 CMS 的 /api/admin/units/*）
# ---------------------------------------------------------------------------
@app.get("/api/units")
async def get_published_units():
    """意图：已发布单元只读列表（大众端学习页/发音库数据源；不含草稿与治理字段）。"""
    raise HTTPException(501, "重构占位：已发布单元列表")


# ---------------------------------------------------------------------------
# 学习记录与用户进度（进度只读派生，无覆写入口）
# ---------------------------------------------------------------------------
@app.get("/api/users/{user_id}/progress")
async def get_user_progress(user_id: str):
    """意图：读用户进度（由学习记录派生；totalUnits 随已发布单元数变化）。"""
    raise HTTPException(501, "重构占位：用户进度读取")


@app.get("/api/users/{user_id}/learning-records")
async def get_learning_records(user_id: str, limit: int = 20):
    """意图：学习记录列表（不含音频 BLOB）。"""
    raise HTTPException(501, "重构占位：学习记录列表")


@app.post("/api/learning-records")
async def create_learning_record():
    """意图：录音二进制(multipart) + 检测结果快照（质量两维、分数、现象、四步、
    可靠性、双版本号——FR-1010/附录 B）一并落库，同事务更新进度；
    写入档案以服务端会话与同意记录为准（NFR-15）。"""
    raise HTTPException(501, "重构占位：创建学习记录")


@app.get("/api/learning-records/{record_id}/audio")
async def get_record_audio(record_id: str):
    """意图：按需返回录音二进制流（档案重听 / 后台共用）。"""
    raise HTTPException(501, "重构占位：录音读取")


@app.delete("/api/learning-records/{record_id}")
async def delete_learning_record(record_id: str):
    """意图：删除单条记录（校验归属），并重算进度。"""
    raise HTTPException(501, "重构占位：删除学习记录")


@app.delete("/api/users/{user_id}/learning-records")
async def delete_all_learning_records(user_id: str):
    """意图：清空用户全部学习记录（声音档案清空）。"""
    raise HTTPException(501, "重构占位：清空学习记录")


# ---------------------------------------------------------------------------
# 本地大模型对话（Ollama）——2.0 功能（FR-1601）：仅用于四步反馈话术的
# 生成/改写，须经管理员逐条确认后才展示；质量、分数、现象标签、可靠性
# 一律由评分模块给出，模型不得触碰。
# ---------------------------------------------------------------------------
@app.post("/api/llm/chat")
async def llm_chat():
    """意图：非流式对话；服务不可用时返回 503 与中文说明。"""
    raise HTTPException(501, "重构占位：LLM 对话")


@app.post("/api/llm/chat/stream")
async def llm_chat_stream():
    """意图：SSE 流式对话，供前端打字机效果。"""
    raise HTTPException(501, "重构占位：LLM 流式对话")


# ---------------------------------------------------------------------------
# 用户反馈闭环（提交 / 后台列表 / 处理状态）
# ---------------------------------------------------------------------------
@app.post("/api/feedback")
async def submit_feedback():
    """意图：用户提交反馈（看懂了吗/内容纠错/新增需求/结果反馈）。"""
    raise HTTPException(501, "重构占位：提交反馈")


@app.get("/api/admin/feedback")
async def admin_feedback(status: str = ""):
    """意图：后台反馈处理列表（按状态过滤）。"""
    raise HTTPException(501, "重构占位：反馈列表")


@app.put("/api/admin/feedback/{fb_id}")
async def handle_feedback(fb_id: str):
    """意图：更新反馈处理状态（pending/adopted/rejected + 说明）。"""
    raise HTTPException(501, "重构占位：反馈处理")


# ---------------------------------------------------------------------------
# 媒体资源（后台媒体上传；文件存 uploads/，元数据入库）
# ---------------------------------------------------------------------------
@app.post("/api/media/upload")
async def upload_media():
    """意图：上传音频/图片，返回可访问 URL。"""
    raise HTTPException(501, "重构占位：媒体上传")


@app.get("/api/media")
async def list_media():
    raise HTTPException(501, "重构占位：媒体列表")


@app.get("/api/media/{media_id}/file")
async def get_media_file(media_id: str):
    """意图：访问媒体文件内容。"""
    raise HTTPException(501, "重构占位：媒体文件")


@app.delete("/api/media/{media_id}")
async def delete_media(media_id: str):
    """意图：删除媒体（连同磁盘文件）。"""
    raise HTTPException(501, "重构占位：删除媒体")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
