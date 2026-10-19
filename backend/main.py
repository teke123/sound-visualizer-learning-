"""
看得见的声音 - 智能发音学习平台 后端服务
使用FastAPI + Librosa + PyTorch(深度学习)实现音频分析和发音评估
"""
import os
import io
import json
import tempfile
import numpy as np
from typing import Optional
from uuid import uuid4

# 必须在 import torch 之前设置：Wav2Vec2 使用 weight_norm，MPS(Apple Silicon)
# 暂未实现该算子，开启 fallback 让不支持的算子回退 CPU，其余仍走 MPS 加速。
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

# 防御 IDE 注入的 Python shim（如 CodeBuddy 通过 PYTHONPATH 注入 sitecustomize，
# 会拦截 librosa 写 __pycache__ 临时文件时的 unlink 操作，导致 SystemExit → 接口 500）。
# 注意：sitecustomize 在解释器启动时已加载，本进程内清理无法撤销已注入的行为；
# 正确的做法是用 start-dev.sh（env -u PYTHONPATH）或 `env -u PYTHONPATH python3 main.py` 启动。
# 此处仍清理环境变量，供后续 subprocess（ffmpeg 等）不继承 shim。
_pythonpath = os.environ.get("PYTHONPATH", "")
_shim_markers = ("codebuddy", "genie", "vendor/shim", "extensions/genie")
if any(m in _pythonpath.lower() for m in _shim_markers):
    print(
        "[警告] 检测到 IDE 注入的 Python shim（PYTHONPATH 含 vendor/shim），"
        "可能导致音频分析接口 500。建议改用 ./start-dev.sh 或 "
        "`env -u PYTHONPATH python3 main.py` 启动。"
    )
    parts = [p for p in _pythonpath.split(os.pathsep) if p and not any(m in p.lower() for m in _shim_markers)]
    os.environ["PYTHONPATH"] = os.pathsep.join(parts)

from fastapi import FastAPI, Header, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel
import librosa
import torch

import database
import llm_service
from database import CmsStateError
from audio_analyzer import (
    analyze_with_deep_learning,
    analyze_audio_quality,
    estimate_formants,
    compute_fluency_score,
    asr_status,
    load_asr_model,
    standard_tone_curve,
    UNIT_REFERENCE,
    unit_verified,
)
from feedback_engine import build_four_step_feedback, compute_reliability
import cms_routes

app = FastAPI(title="看得见的声音 API", version="1.0.0")

# 启动时初始化 SQLite 数据库（幂等建表）
# 用 database.DB_PATH 而非写死默认值，便于测试脚本先指向临时库
database.init_db(database.DB_PATH)

# CMS 管理接口（四状态机 / 下架 / 检测开关 / 操作日志，第 6 周 C）
app.include_router(cms_routes.router)

# CORS配置 - 允许所有本地开发端口
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据模型
class PhonemeResult(BaseModel):
    phoneme: str          # 声母 / 韵母 / 声调
    expected: str
    detected: str
    score: float
    feedback: str

class AudioAnalysisResult(BaseModel):
    f0: list[float]
    f1: list[float]
    f2: list[float]
    energy: list[float]
    duration: float
    sample_rate: int
    mfcc: list[list[float]]
    #新增voiced判定与概率
    voiecd_flag:list[bool] = []
    voiced_probs:list[float] = []

    # 深度学习分析结果
    recognized_text: str = ""
    detected_tone: int = 0
    tone_score: float = 0.0
    phoneme_score: float = 0.0
    phonemes: list[PhonemeResult] = []
    # 标准声调曲线（由后端生成，供前端对比展示）
    standard_f0: list[float] = []

class FeedbackItem(BaseModel):
    type: str  # error, warning, suggestion
    category: str  # tone, pronunciation, fluency, rhythm, quality
    phenomenon: str  # ① 现象
    link: str        # ② 可能相关环节
    hint: str        # ③ 可感知提示
    practice: str    # ④ 安全短练习
    severity: int = 1
    # 兼容旧字段
    message: str = ""
    detail: str = ""
    improvement: str = ""

class PronunciationAssessment(BaseModel):
    score: float
    accuracy: float
    fluency: float
    pronunciation: float
    feedback: list[FeedbackItem]
    audio_analysis: AudioAnalysisResult
    # 录音质量五维（RES-01）
    quality: dict = {}
    # 结果可靠性（RES-07）
    reliability: str = "reliable"  # reliable / reference_only / not_available
    reliability_note: str = ""
    # 边界声明（RES-08）
    boundary: dict = {}
    # 是否可评价（录音不合格时 False，停止评价 AC-07）
    evaluable: bool = True

# 结果边界声明（RES-07/08）：不作为等级认定与医学诊断，明示影响因素
BOUNDARY = {
    "statement": "检测结果基于声学特征（基频/共振峰）与语音识别模型，仅用于发音学习参考，不作为普通话水平等级认定依据，也不构成医学诊断。",
    "scope": "当前开放检测的为已开放的 50 个核心单元（12 个对比单元 + 38 个常用音节，声学特征已验证）；其余内容为学习模式，检测功能将随验证逐步开放。",
    "factors": [
        "录音环境：背景噪声、回声影响特征提取",
        "录音条件：距离、音量、截幅影响基频估计",
        "模型置信度：语音识别在噪声/口音下的置信度有限",
    ],
}

# 标准发音参数（附录A核心单元 + 兼容旧单元）
STANDARD_PARAMS = {
    "ma": {"f0_mean": 200, "f0_std": 10, "f1_range": (200, 400), "f2_range": (800, 1200), "tone": 1},
    "a": {"f0_mean": 200, "f0_std": 12, "f1_range": (500, 900), "f2_range": (1000, 1500), "tone": 1},
    "i": {"f0_mean": 220, "f0_std": 10, "f1_range": (200, 350), "f2_range": (2200, 2900), "tone": 1},
    "u_u": {"f0_mean": 190, "f0_std": 15, "f1_range": (250, 420), "f2_range": (700, 1000), "tone": 1},
    "m": {"f0_mean": 200, "f0_std": 12, "f1_range": (200, 400), "f2_range": (800, 1200), "tone": 1},
    "b_p": {"f0_mean": 200, "f0_std": 12, "f1_range": (200, 450), "f2_range": (900, 1300), "tone": 1},
    "d_t": {"f0_mean": 200, "f0_std": 12, "f1_range": (200, 450), "f2_range": (900, 1300), "tone": 1},
    "n_l": {"f0_mean": 200, "f0_std": 12, "f1_range": (200, 450), "f2_range": (900, 1300), "tone": 1},
    "g_k": {"f0_mean": 200, "f0_std": 12, "f1_range": (200, 450), "f2_range": (900, 1300), "tone": 1},
    "j_q_x": {"f0_mean": 210, "f0_std": 12, "f1_range": (200, 350), "f2_range": (2200, 2900), "tone": 1},
    "z_zh": {"f0_mean": 200, "f0_std": 12, "f1_range": (200, 450), "f2_range": (1000, 1400), "tone": 1},
    "ma_tone": {"f0_mean": 200, "f0_std": 15, "f1_range": (200, 450), "f2_range": (900, 1300), "tone": 1},
    "ba": {"f0_mean": 200, "f0_std": 10, "f1_range": (200, 400), "f2_range": (800, 1200), "tone": 1},
    "pa": {"f0_mean": 200, "f0_std": 10, "f1_range": (200, 400), "f2_range": (800, 1200), "tone": 1},
    "ta": {"f0_mean": 200, "f0_std": 10, "f1_range": (200, 400), "f2_range": (800, 1200), "tone": 1},
    "yi": {"f0_mean": 200, "f0_std": 10, "f1_range": (200, 350), "f2_range": (1800, 2400), "tone": 1},
    "wu": {"f0_mean": 180, "f0_std": 15, "f1_range": (250, 400), "f2_range": (600, 900), "tone": 3},
    "yu": {"f0_mean": 220, "f0_std": 15, "f1_range": (200, 350), "f2_range": (1800, 2200), "tone": 2},
    "ma_t2": {"f0_mean": 220, "f0_std": 20, "f1_range": (200, 400), "f2_range": (800, 1200), "tone": 2},
    "ma_t3": {"f0_mean": 180, "f0_std": 25, "f1_range": (200, 400), "f2_range": (800, 1200), "tone": 3},
}

def analyze_audio(audio_data: np.ndarray, sr: int) -> AudioAnalysisResult:
    """分析音频，提取声学特征（共振峰使用LPC真实估计，无随机值）"""
    #原始信号可能存在直流偏移或高频能量不足，影响F0与LCP求解稳定性
    #对输入音频做基频预处理：去均值 + 预加重

    # 1) 确保为浮点 numpy 数组，并把多声道混成单声道（按最后一个维度平均）
    y_orig = np.asarray(audio_data, dtype=np.float32)
    if y_orig.ndim > 1:
        # 通常 librosa.load 返回 1-D，但为保险处理多通道输入：
        # 假设形状为 (n_samples, n_channels) 或 (n_channels, n_samples)，
        # 使用 axis=-1 对常见形态 (n_samples, n_channels) 生效。
        y_orig = np.mean(y_orig, axis=-1)

    # 如果音频为空，快速返回一个空的结果（避免后续函数报错）
    if y_orig.size == 0:
        return AudioAnalysisResult(
            f0=[],
            f1=[],
            f2=[],
            energy=[],
            duration=0.0,
            sample_rate=sr,
            mfcc=[],
        )

    # 2) 计算并保留原始能量（用于质量检测/比较）
    energy = librosa.feature.rms(y=y_orig)[0].tolist()

    # 3) 去均值（demean）
    y = y_orig - float(np.mean(y_orig))

    # 4) 预加重（pre-emphasis），常用系数 alpha = 0.97
    alpha = 0.97
    y_pre = np.empty_like(y)
    y_pre[0] = y[0]
    if y_pre.size > 1:
        y_pre[1:] = y[1:] - alpha * y[:-1]

    # 基频F0的提取
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y_pre, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'), sr=sr
    )
    f0 = np.nan_to_num(f0, nan=0.0).tolist()
    
    # MFCC特征  --> 使用预加重信号，得到略好一点的高频特征
    mfcc = librosa.feature.mfcc(y=y_pre, sr=sr, n_mfcc=13)
    mfcc_list = mfcc.tolist()
    
    
    # 共振峰（LPC线性预测真实估计）  -->  使用预加重信号，提高短时谱分辨率
    f1, f2 = estimate_formants(y_pre, sr)
    
    duration = len(y_orig) / sr
    
    return AudioAnalysisResult(
        f0=f0,
        f1=f1,
        f2=f2,
        energy=energy,
        duration=duration,
        sample_rate=sr,
        mfcc=mfcc_list,
        #voiced_flag和voiced_probs上版没有保留，只能靠f0>0判断是否有声
        voiced_flag = voiced_flag,
        voiced_probs = voiced_probs
    )

def assess_pronunciation(
    audio_analysis: AudioAnalysisResult,
    unit_id: str,
    fluency: float,
    quality: dict,
) -> PronunciationAssessment:
    """评估发音质量：四步反馈 + 录音质量 + 结果可靠性（RES-01/05/07）"""
    standard = STANDARD_PARAMS.get(unit_id, STANDARD_PARAMS["ma"])
    ref = UNIT_REFERENCE.get(unit_id) or {}
    targets = ref.get("targets") or [ref.get("pinyin", "ma1")]

    # 计算基频相似度
    f0_array = np.array(audio_analysis.f0)
    f0_voiced = f0_array[f0_array > 0]

    if len(f0_voiced) > 0:
        f0_mean = np.mean(f0_voiced)
        f0_std = np.std(f0_voiced)
        f0_similarity = max(0, 100 - abs(f0_mean - standard["f0_mean"]) / standard["f0_mean"] * 100)
        tone_stability = max(0, 100 - f0_std / standard["f0_std"] * 20)
    else:
        f0_mean = 0
        f0_std = 0
        f0_similarity = 0
        tone_stability = 0

    # 流利度：由调用方传入（真实VAD计算）
    fluency = fluency if fluency > 0 else 50.0

    # 发音准确度 = 音素级深度学习评分 与 基频相似度 加权
    phoneme_score = audio_analysis.phoneme_score  # 0-100，来自Wav2Vec2音素对比
    if phoneme_score > 0:
        accuracy = (phoneme_score * 0.5 + f0_similarity * 0.3 + tone_stability * 0.2)
    else:
        accuracy = (f0_similarity * 0.6 + tone_stability * 0.4)

    # 声调评估（深度学习声调评分 + 基频稳定性）
    tone_score = audio_analysis.tone_score  # 0-100，来自F0曲线形状与识别声调
    if tone_score > 0:
        tone_combined = tone_score * 0.6 + tone_stability * 0.4
    else:
        tone_combined = tone_stability

    pronunciation = (accuracy * 0.5 + tone_combined * 0.3 + fluency * 0.2)
    score = (accuracy * 0.35 + tone_combined * 0.25 + fluency * 0.2 + pronunciation * 0.2)

    # 四步反馈（现象 → 环节 → 提示 → 练习，规则模板来自 feedback_engine）
    quality_warn = next((i for i in quality["items"] if i["status"] == "warn"), None)
    feedback_items = build_four_step_feedback(
        tone_combined=tone_combined,
        f0_mean=f0_mean,
        f0_std=f0_std,
        ref_f0=float(standard["f0_mean"]),
        detected_tone=audio_analysis.detected_tone,
        ref_tone=int(standard["tone"]),
        fluency=fluency,
        phonemes=[p.model_dump() for p in audio_analysis.phonemes],
        quality_warn=quality_warn,
    )

    # 结果可靠性（RES-07）
    voiced_ratio = len(f0_voiced) / max(len(f0_array), 1)
    recognized = bool(audio_analysis.recognized_text)
    hits = sum(1 for p in audio_analysis.phonemes if p.score >= 80)
    reliability, note = compute_reliability(
        quality_passed=quality["passed"],
        voiced_ratio=voiced_ratio,
        recognized=recognized,
        phoneme_hits=hits,
        total_targets=len(targets),
    )

    return PronunciationAssessment(
        score=round(score, 1),
        accuracy=round(accuracy, 1),
        fluency=round(fluency, 1),
        pronunciation=round(pronunciation, 1),
        feedback=[FeedbackItem(**f) for f in feedback_items],
        audio_analysis=audio_analysis,
        quality=quality,
        reliability=reliability,
        reliability_note=note,
        boundary=BOUNDARY,
    )

@app.get("/")
async def root():
    return {"message": "看得见的声音 API", "version": "1.0.0"}

@app.get("/api/pronunciation-units")
async def get_pronunciation_units():
    """获取已发布发音单元（数据库驱动，含 verified 分级开放标记）"""
    units = database.get_units("published")
    return {"code": 200, "data": units}

@app.post("/api/audio/analyze")
async def analyze_audio_file(
    audio: UploadFile = File(...),
    unit_id: str = Form(...)
):
    """分析上传的音频文件（分级开放：仅已验证核心单元可检测）"""
    try:
        # 分级开放策略（GROW-08）：未验证单元禁止检测，杜绝未经验证的评价
        if not unit_verified(unit_id):
            return JSONResponse(
                status_code=400,
                content={
                    "code": 400,
                    "message": f"「{unit_id}」的检测任务尚未通过验证，暂不开放检测；请在首批核心单元中选择",
                },
            )

        # 读取音频数据
        audio_bytes = await audio.read()
        
        # 根据content_type确定文件扩展名
        content_type = audio.content_type or ""
        if "webm" in content_type:
            suffix = ".webm"
        elif "ogg" in content_type:
            suffix = ".ogg"
        elif "mp3" in content_type:
            suffix = ".mp3"
        else:
            suffix = ".wav"
        
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        
        # 如果是webm/ogg格式，先用ffmpeg转换为wav
        wav_path = tmp_path
        if suffix in [".webm", ".ogg", ".mp3"]:
            wav_path = tmp_path + ".wav"
            import subprocess
            try:
                result = subprocess.run(
                    ["ffmpeg", "-i", tmp_path, "-ar", "16000", "-ac", "1", "-y", wav_path],
                    capture_output=True, text=True
                )
            except FileNotFoundError:
                # 服务端没装 ffmpeg。浏览器录的是 webm/ogg（opus），librosa/soundfile
                # 解不了，必须先转 wav。这是部署环境问题，必须把话说清楚，
                # 否则会被误判成「后端没启动」或「录音有问题」（实测踩过）。
                return JSONResponse(
                    status_code=500,
                    content={
                        "code": 500,
                        "message": (
                            "服务端缺少 ffmpeg：浏览器录音（webm/ogg）需要先转成 wav 才能分析。"
                            "请在服务器上安装 ffmpeg 并确保它在 PATH 中，然后点「重录」再试一次。"
                        ),
                    },
                )
            if result.returncode != 0:
                print(f"FFmpeg转换失败: {result.stderr}")
                # 如果转换失败，尝试直接加载
                wav_path = tmp_path
        
        # 使用librosa加载音频
        y, sr = librosa.load(wav_path, sr=None)
        
        # 删除临时文件
        os.unlink(tmp_path)
        if wav_path != tmp_path and os.path.exists(wav_path):
            os.unlink(wav_path)
        
        # 录音质量五维检测（RES-01）：音量/噪声/截幅/时长/静音
        quality = analyze_audio_quality(y, sr)

        # 录音不合格：停止评价，引导重录（AC-07）
        if not quality["passed"]:
            return {
                "code": 200,
                "message": quality["summary"],
                "data": {
                    "evaluable": False,
                    "score": 0,
                    "accuracy": 0,
                    "fluency": 0,
                    "pronunciation": 0,
                    "feedback": [],
                    "audio_analysis": None,
                    "quality": quality,
                    "reliability": "not_available",
                    "reliability_note": "录音质量不达标，无法可靠评价。请按上方提示调整后重录。",
                    "boundary": BOUNDARY,
                },
            }

        # 分析音频（声学特征：F0/MFCC/能量/共振峰）
        analysis = analyze_audio(y, sr)
        
        # 深度学习分析（Wav2Vec2语音识别 + 音素对比 + 声调评估）
        f0_array = np.array(analysis.f0)
        f0_voiced = f0_array[f0_array > 0]
        deep = analyze_with_deep_learning(y, sr, unit_id, f0_voiced)
        analysis.recognized_text = deep["recognized_text"]
        analysis.detected_tone = deep["detected_tone"]
        analysis.tone_score = deep["tone_score"]
        analysis.phoneme_score = deep["phoneme_score"]
        # compare_phonemes 返回 dict 列表；转成 PhonemeResult 对象，
        # 供 assess_pronunciation 中 p.model_dump() / p.score 使用（多目标单元必现）
        analysis.phonemes = [PhonemeResult(**p) for p in deep["phonemes"]]
        
        # 真实流利度（VAD停顿/语速分析）
        fluency = compute_fluency_score(y, sr)
        
        # 标准声调曲线（由后端基于目标单元声调生成，供前端对比展示）
        ref = UNIT_REFERENCE.get(unit_id)
        if ref:
            n_frames = len(analysis.f0) or 100
            analysis.standard_f0 = standard_tone_curve(ref["tone"], n_frames).tolist()
        
        # 评估发音（四步反馈 + 可靠性 + 边界声明）
        assessment = assess_pronunciation(analysis, unit_id, fluency, quality)
        
        return {
            "code": 200,
            "message": "分析完成",
            "data": assessment.model_dump()
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"分析失败: {str(e)}"}
        )

@app.get("/api/asr/status")
async def get_asr_status():
    """获取深度学习模型加载状态（调试用）"""
    return {"code": 200, "data": asr_status()}

@app.post("/api/asr/load")
async def load_asr_endpoint():
    """手动触发深度学习模型加载（可选，用于预热）"""
    ok = load_asr_model()
    return {"code": 200, "data": {"loaded": ok, **asr_status()}}


# ---------------------------------------------------------------------------
# 本地大模型对话（Ollama，Z 组）
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str = "user"          # system / user / assistant
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    temperature: float = 0.7


@app.post("/api/llm/chat")
def llm_chat(req: ChatRequest):
    """本地大模型对话（转发 Ollama），返回模型结果 JSON"""
    if not llm_service.is_available():
        return JSONResponse(
            status_code=503,
            content={"code": 503, "message": "本地大模型服务（Ollama）未运行，请先启动"},
        )
    try:
        reply = llm_service.chat(
            [m.model_dump() for m in req.messages], temperature=req.temperature
        )
        return {"code": 200, "data": {"model": llm_service.OLLAMA_MODEL, "reply": reply}}
    except Exception as e:  # noqa: BLE001
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"大模型调用失败: {str(e)}"},
        )


@app.post("/api/llm/chat/stream")
def llm_chat_stream(req: ChatRequest):
    """本地大模型流式对话（SSE），逐段返回回复文本，供前端打字机效果"""
    def gen():
        try:
            for piece in llm_service.chat_stream(
                [m.model_dump() for m in req.messages], temperature=req.temperature
            ):
                yield f"data: {json.dumps({'content': piece}, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/llm/model-info")
def llm_model_info():
    """第 6 周：量化模型部署信息（Qwen2.5-7B GGUF Q4_K_M 4bit 量化）"""
    return {"code": 200, "data": llm_service.get_model_info()}


class UserProgress(BaseModel):
    userId: str
    totalUnits: int = 12
    completedUnits: int = 0
    totalPractice: int = 0
    averageScore: float = 0.0
    lastPracticeAt: str = ""
    unitProgress: list[dict] = []

@app.get("/api/users/{user_id}/progress")
async def get_user_progress(user_id: str):
    """获取用户进度（读 SQLite，用户不存在时自动初始化）"""
    progress = database.get_user_progress(user_id)
    return {"code": 200, "data": progress}

@app.post("/api/users/{user_id}/progress")
async def update_user_progress(user_id: str, progress: UserProgress):
    """更新用户进度（写入 SQLite，兼容旧调用方）"""
    database.update_user_progress(user_id, progress.model_dump())
    return {"code": 200, "message": "进度已更新"}

@app.get("/api/users/{user_id}/learning-records")
async def get_learning_records(user_id: str, limit: int = 20):
    """获取用户学习记录（不含音频 BLOB，音频走 /audio 接口）"""
    records = database.get_learning_records(user_id, limit)
    return {"code": 200, "data": records}

@app.post("/api/learning-records")
async def create_learning_record(
    userId: str = Form(...),
    unitId: str = Form(...),
    pinyin: str = Form(...),
    character: str = Form(...),
    score: float = Form(...),
    accuracy: float = Form(...),
    fluency: float = Form(...),
    pronunciation: float = Form(...),
    duration: float = Form(0.0),
    feedback: str = Form(""),
    audio: UploadFile = File(...),
):
    """创建学习记录：录音二进制(multipart) + 评估结果一并落库，同一事务更新进度"""
    audio_bytes = await audio.read()
    audio_type = audio.content_type or "audio/webm"
    record_id = database.create_learning_record(
        user_id=userId,
        unit_id=unitId,
        pinyin=pinyin,
        character=character,
        score=score,
        accuracy=accuracy,
        fluency=fluency,
        pronunciation=pronunciation,
        duration=duration,
        feedback=feedback,
        audio_blob=audio_bytes,
        audio_type=audio_type,
    )
    print(f"[database] 学习记录已保存 record_id={record_id} user={userId} unit={unitId} score={score}")
    return {"code": 200, "message": "记录已保存", "data": {"id": record_id}}

@app.get("/api/learning-records/{record_id}/audio")
async def get_record_audio(record_id: str):
    """按需返回录音二进制流（后台管理 / 历史记录重听共用）"""
    result = database.get_audio(record_id)
    if result is None:
        return JSONResponse(status_code=404, content={"code": 404, "message": "录音不存在"})
    blob, mime = result
    return Response(content=blob, media_type=mime)

@app.get("/api/admin/learning-records")
async def admin_learning_records(limit: int = 100):
    """后台管理：获取全部用户的学习记录（不含 BLOB）"""
    records = database.get_all_learning_records(limit)
    return {"code": 200, "data": records}

@app.get("/api/admin/stats")
async def admin_stats():
    """后台管理：全量统计卡片数据（SQL 聚合）"""
    stats = database.get_stats()
    return {"code": 200, "data": stats}


# ---------------------------------------------------------------------------
# 发音单元管理（后台 CMS 落库，内容可生长 GROW-01）
# ---------------------------------------------------------------------------
@app.get("/api/units")
async def get_units(status: str = ""):
    """发音单元列表（status=published 仅返回已发布）"""
    units = database.get_units(status)
    return {"code": 200, "data": units}


@app.get("/api/units/{unit_id}")
async def get_unit(unit_id: str):
    """获取单个发音单元详情"""
    unit = database.get_unit(unit_id)
    if unit is None:
        return JSONResponse(status_code=404, content={"code": 404, "message": "单元不存在"})
    return {"code": 200, "data": unit}


@app.post("/api/units")
async def create_unit(payload: dict, x_operator: str | None = Header(default=None)):
    """新增发音单元（后台录入，字段与文档 UNIT-01~10 对齐）。
    第 6 周 C：录入即草稿 draft，发布必须走 /api/admin/units/{id}/approve。"""
    try:
        unit_id = database.create_unit(payload, x_operator or "admin")
        return {"code": 200, "message": "单元已创建（草稿，待提交审核）", "data": {"id": unit_id}}
    except Exception as e:
        return JSONResponse(status_code=400, content={"code": 400, "message": f"创建失败: {str(e)}"})


@app.put("/api/units/{unit_id}")
async def update_unit(unit_id: str, payload: dict, x_operator: str | None = Header(default=None)):
    """编辑发音单元（第 6 周 C：内容编辑仅限草稿/驳回，状态变更走审核流转接口）"""
    try:
        ok = database.update_unit(unit_id, payload, x_operator or "admin")
    except CmsStateError as exc:
        return JSONResponse(status_code=400, content={"code": 400, "message": str(exc)})
    if not ok:
        return JSONResponse(status_code=404, content={"code": 404, "message": "单元不存在"})
    return {"code": 200, "message": "单元已更新"}


@app.delete("/api/units/{unit_id}")
async def delete_unit(unit_id: str, x_operator: str | None = Header(default=None)):
    """删除发音单元（核心单元受保护，仅允许删除扩展单元）"""
    if unit_id in database.CORE_UNITS_IDS:
        return JSONResponse(status_code=400, content={"code": 400, "message": "核心单元受保护，不可删除；可改为草稿状态下线"})
    ok = database.delete_unit(unit_id, x_operator or "admin")
    if not ok:
        return JSONResponse(status_code=404, content={"code": 404, "message": "单元不存在"})
    return {"code": 200, "message": "单元已删除"}


# ---------------------------------------------------------------------------
# 用户反馈闭环（FB-01~07：提交 / 后台列表 / 处理状态）
# ---------------------------------------------------------------------------
@app.post("/api/feedback")
async def submit_feedback(payload: dict):
    """用户提交反馈（看懂了吗/内容纠错/新增需求/结果反馈）"""
    fb_id = database.create_feedback(payload)
    return {"code": 200, "message": "感谢反馈，我们会尽快处理", "data": {"id": fb_id}}


@app.get("/api/admin/feedback")
async def admin_feedback(status: str = ""):
    """后台：反馈处理列表（支持按状态过滤）"""
    items = database.get_feedbacks(status)
    return {"code": 200, "data": items}


@app.put("/api/admin/feedback/{fb_id}")
async def handle_feedback(fb_id: str, payload: dict):
    """后台：更新反馈处理状态（pending/adopted/rejected + 处理说明）"""
    status = payload.get("status", "pending")
    note = payload.get("handleNote", "")
    ok = database.update_feedback_status(fb_id, status, note)
    if not ok:
        return JSONResponse(status_code=404, content={"code": 404, "message": "反馈不存在"})
    return {"code": 200, "message": "处理状态已更新"}


# ---------------------------------------------------------------------------
# 收藏（发音库收藏，注册用户粒度）
# ---------------------------------------------------------------------------
@app.get("/api/users/{user_id}/favorites")
async def get_favorites(user_id: str):
    """获取用户收藏的单元 id 列表"""
    ids = database.get_favorites(user_id)
    return {"code": 200, "data": ids}


@app.post("/api/users/{user_id}/favorites/{unit_id}")
async def add_favorite(user_id: str, unit_id: str):
    """收藏发音单元"""
    database.add_favorite(user_id, unit_id)
    return {"code": 200, "message": "已收藏"}


@app.delete("/api/users/{user_id}/favorites/{unit_id}")
async def remove_favorite(user_id: str, unit_id: str):
    """取消收藏"""
    database.remove_favorite(user_id, unit_id)
    return {"code": 200, "message": "已取消收藏"}


# ---------------------------------------------------------------------------
# 媒体资源（后台媒体上传，文件存 uploads/ 目录，记录入 SQLite）
# ---------------------------------------------------------------------------
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/api/media/upload")
async def upload_media(
    file: UploadFile = File(...),
    file_type: str = Form("audio"),
):
    """上传媒体文件（音频/图片），返回可访问 URL"""
    data = await file.read()
    ext = os.path.splitext(file.filename or "")[1] or ".bin"
    fname = f"{uuid4().hex}{ext}"
    fpath = os.path.join(UPLOAD_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(data)
    media_id = database.create_media(
        name=file.filename or fname,
        file_type=file_type,
        mime=file.content_type or "application/octet-stream",
        size=len(data),
        path=fname,
    )
    return {"code": 200, "message": "上传成功", "data": {"id": media_id, "url": f"/api/media/{media_id}/file"}}


@app.get("/api/media")
async def list_media():
    """媒体资源列表"""
    items = database.get_media_list()
    for it in items:
        it["url"] = f"/api/media/{it['id']}/file"
    return {"code": 200, "data": items}


@app.get("/api/media/{media_id}/file")
async def get_media_file(media_id: str):
    """访问媒体文件内容"""
    media = database.get_media(media_id)
    if media is None:
        return JSONResponse(status_code=404, content={"code": 404, "message": "媒体不存在"})
    fpath = os.path.join(UPLOAD_DIR, media["path"])
    if not os.path.exists(fpath):
        return JSONResponse(status_code=404, content={"code": 404, "message": "媒体文件缺失"})
    with open(fpath, "rb") as f:
        content = f.read()
    return Response(content=content, media_type=media["mime"])


@app.delete("/api/media/{media_id}")
async def delete_media(media_id: str):
    """删除媒体资源（同时删除磁盘文件）"""
    media = database.get_media(media_id)
    if media is None:
        return JSONResponse(status_code=404, content={"code": 404, "message": "媒体不存在"})
    fpath = os.path.join(UPLOAD_DIR, media["path"])
    if os.path.exists(fpath):
        os.unlink(fpath)
    database.delete_media(media_id)
    return {"code": 200, "message": "媒体已删除"}


# ---------------------------------------------------------------------------
# 学习记录删除（声音档案：用户对自己数据的控制权 ARC-03/06）
# ---------------------------------------------------------------------------
@app.delete("/api/learning-records/{record_id}")
async def delete_learning_record(record_id: str):
    """删除单条学习记录（默认校验 default_user 归属）"""
    ok = database.delete_learning_record(record_id, user_id="default_user")
    if not ok:
        return JSONResponse(status_code=404, content={"code": 404, "message": "记录不存在或无权限"})
    return {"code": 200, "message": "记录已删除"}


@app.delete("/api/users/{user_id}/learning-records")
async def delete_all_learning_records(user_id: str):
    """清空用户全部学习记录（声音档案清空）"""
    count = database.delete_all_learning_records(user_id)
    return {"code": 200, "message": f"已删除 {count} 条记录", "data": {"deleted": count}}


@app.websocket("/ws/audio-stream")
async def audio_stream_websocket(websocket: WebSocket):
    """WebSocket实时音频流分析"""
    await websocket.accept()
    
    try:
        while True:
            # 接收音频数据
            data = await websocket.receive_bytes()
            
            # 将字节数据转换为numpy数组
            audio_array = np.frombuffer(data, dtype=np.float32)
            
            # 实时分析（简化版）
            if len(audio_array) > 0:
                # 计算能量
                energy = float(np.sqrt(np.mean(audio_array ** 2)))
                
                # 发送实时数据
                await websocket.send_json({
                    "type": "realtime_data",
                    "energy": energy,
                    "samples": len(audio_array)
                })
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
