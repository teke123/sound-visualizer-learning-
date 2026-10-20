"""音频、标定与检测路由（要求登录；D-05/D-19/D-20）。"""
from __future__ import annotations

from typing import Literal, Union

import asyncio
import json

from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from pydantic import BaseModel

from app import config
from app.acoustics import usecases as acoustics_uc
from app.api.deps import Actor, get_actor, require_user
from app.api.files import serve_file
from app.archive import usecases as archive_uc
from app.content import usecases as content_uc
from app.detection import usecases as detection_uc
from app.platform.envelope import ApiError, envelope
from app.scoring import usecases as scoring_uc

from app.api.schemas import (AudioUploadResponse, CalibrationFailResult, CalibrationOkResult,
                             Envelope, F0Response, FormantsResponse, PitchCalibrationInfo,
                             RecordingDeleted, RecordingOnly, RecordingWithResult)

router = APIRouter(prefix="/api", tags=["audio-detection"])


# ---------------- 上传与特征 ----------------

@router.post("/audio/uploads", response_model=Envelope[AudioUploadResponse])
async def upload_audio(request: Request, purpose: str = Form(...),
                       file: UploadFile = File(...),
                       actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    actor.rate_limit("upload")
    # 分块读并在超限时立即中止：一次性 file.read() 会把整个文件载入内存，
    # 超大上传会先吃满 RAM 才被 20MB 上限拒绝
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > config.MAX_UPLOAD_BYTES:
            raise ApiError(413, "FILE_TOO_LARGE",
                           f"文件过大（上限 {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB）")
        chunks.append(chunk)
    raw = b"".join(chunks)
    if not raw:
        raise ApiError(400, "DECODE_FAILED", "没有收到音频内容，请重试")
    result = await asyncio.get_running_loop().run_in_executor(
        None, lambda: acoustics_uc.register_upload(
            actor.db, user_id=user.id,
            purpose=purpose, filename=file.filename, mime=file.content_type,
            raw_bytes=raw))
    return envelope(request, result)


@router.get("/audio/{audio_id}/file")
async def audio_file(request: Request, audio_id: str, actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    row = acoustics_uc.get_audio_for_read(actor.db, audio_id=audio_id, user_id=user.id)
    return serve_file(request, acoustics_uc.audio_path(row), "audio/wav",
                      cache_control="private, no-store")


@router.get("/audio/{audio_id}/f0", response_model=Envelope[F0Response])
async def audio_f0(request: Request, audio_id: str, actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    actor.rate_limit("feature_read")
    row = acoustics_uc.get_audio_for_read(actor.db, audio_id=audio_id, user_id=user.id)
    data = await asyncio.get_running_loop().run_in_executor(
        None, lambda: acoustics_uc.get_f0(actor.db, row))
    return envelope(request, data)


@router.get("/audio/{audio_id}/formants", response_model=Envelope[FormantsResponse])
async def audio_formants(request: Request, audio_id: str,
                         actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    actor.rate_limit("feature_read")
    row = acoustics_uc.get_audio_for_read(actor.db, audio_id=audio_id, user_id=user.id)
    data = await asyncio.get_running_loop().run_in_executor(
        None, lambda: acoustics_uc.get_formants(actor.db, row))
    return envelope(request, data)


@router.get("/audio/{audio_id}/formants.png")
async def audio_formants_png(request: Request, audio_id: str,
                             actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    actor.rate_limit("feature_read")
    row = acoustics_uc.get_audio_for_read(actor.db, audio_id=audio_id, user_id=user.id,
                                          purposes=("recording",))
    path = await asyncio.get_running_loop().run_in_executor(
        None, lambda: acoustics_uc.get_formants_png(actor.db, row))
    return serve_file(request, path, "image/png", cache_control="private, no-store")


@router.get("/audio/{audio_id}/spectrogram.png")
async def audio_spectrogram_png(request: Request, audio_id: str,
                                actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    actor.rate_limit("feature_read")
    row = acoustics_uc.get_audio_for_read(actor.db, audio_id=audio_id, user_id=user.id,
                                          purposes=("recording",))
    path = await asyncio.get_running_loop().run_in_executor(
        None, lambda: acoustics_uc.get_spectrogram_png(actor.db, row))
    return serve_file(request, path, "image/png", cache_control="private, no-store")


def _parse_remap(flo: str | None, fhi: str | None) -> tuple[float, float] | None:
    if flo is None or fhi is None:
        return None
    try:
        lo, hi = float(flo), float(fhi)
    except ValueError:
        raise ApiError(422, "VALIDATION_ERROR", "flo/fhi 必须是数字")
    if not (30.0 < lo < hi < 1000.0):
        raise ApiError(422, "VALIDATION_ERROR", "音域参数无效（须 30 < flo < fhi < 1000）")
    return lo, hi


@router.get("/audio/{audio_id}/f0-hum.wav")
async def audio_f0_hum(request: Request, audio_id: str, flo: str | None = None,
                       fhi: str | None = None, recording_id: str | None = None,
                       side: Literal["user", "reference"] = "user",
                       actor: Actor = Depends(get_actor)):
    """用户实测音高哼鸣（docs §5.2）。"""
    user = require_user(actor)
    actor.rate_limit("feature_read")
    row = acoustics_uc.get_audio_for_read(actor.db, audio_id=audio_id, user_id=user.id)
    remap = _parse_remap(flo, fhi)
    path = await asyncio.get_running_loop().run_in_executor(
        None, lambda: acoustics_uc.get_f0_hum(
            actor.db, row, remap, recording_id=recording_id, side=side))
    return serve_file(request, path, "audio/wav", cache_control="private, no-store")


# ---------------- 标定（FR-1006，可跳过） ----------------

@router.get("/pitch-calibration", response_model=Envelope[PitchCalibrationInfo])
async def get_calibration(request: Request, actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    text_row = content_uc.get_active_calibration_text(actor.db)
    if text_row is None:
        raise ApiError(500, "INTERNAL_ERROR", "标定文本未配置，请联系管理员")
    effective = scoring_uc.get_personal_range(actor.db, user_id=user.id)
    data = {
        "text": text_row.text,
        "textVersion": text_row.text_version,
        "status": effective["status"] if effective else "none",
        "vowelSpaceReady": bool(effective and effective.get("vowelSpace")),
    }
    if effective:
        data["pitchRange"] = {"fLo": effective["fLo"], "fHi": effective["fHi"]}
        data["updatedAt"] = effective.get("updatedAt")
    return envelope(request, data)


class CalibrationBody(BaseModel):
    audioId: str


@router.post("/pitch-calibration", response_model=Envelope[Union[CalibrationOkResult, CalibrationFailResult]])
async def post_calibration(request: Request, body: CalibrationBody,
                           actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    actor.rate_limit("calibration")
    text_row = content_uc.get_active_calibration_text(actor.db)
    if text_row is None:
        raise ApiError(500, "INTERNAL_ERROR", "标定文本未配置，请联系管理员")
    audio = acoustics_uc.get_audio_for_read(
        actor.db, audio_id=body.audioId, user_id=user.id,
        purposes=("calibration",))
    from app.platform.executor import executor

    # 任务线程内自建会话（compute_calibration），不持有请求作用域 actor.db：
    # 504/断连后请求会话先行关闭，线程继续用它写库是未定义行为
    future = executor.try_submit(
        scoring_uc.compute_calibration, audio_id=audio.id,
        syllables=json.loads(text_row.syllables),
        user_id=user.id)
    if future is None:
        raise ApiError(503, "SERVER_BUSY", "当前处理排队已满，请稍后重试",
                       headers={"Retry-After": "5"})
    # 超时只结束等待、绝不取消执行器任务：wait_for 的超时取消会顺着
    # wrap_future 杀死排队中的任务（信号量槽永久泄漏），迟到的任务自行
    # 收尾（与检测 wait_sync_window 同款约束）
    wrapped = asyncio.wrap_future(future)
    wrapped.add_done_callback(
        lambda f: None if f.cancelled() else f.exception())
    done, _ = await asyncio.wait({wrapped}, timeout=config.CALIBRATION_TIMEOUT_SECONDS)
    if not done:
        raise ApiError(504, "TIMEOUT", "标定处理超时，请重试") from None
    result = wrapped.result()
    if not result.get("ok"):
        return envelope(request, {"reason": result["reason"],
                                  "signal": result.get("signal")},
                        code="CALIBRATION_FAIL",
                        message=result["reason"], status=200)
    return envelope(request, result)


# ---------------- 检测提交与查询 ----------------

class RecordingBody(BaseModel):
    audioId: str
    levelId: str
    submissionId: str


@router.post("/recordings", response_model=Envelope[RecordingWithResult],
             responses={202: {"model": Envelope[RecordingOnly], "description": "PROCESSING"}})
async def submit_recording(request: Request, body: RecordingBody,
                           actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    actor.rate_limit("recording_submit")
    outcome = detection_uc.submit_recording(
        actor.db, user=user, audio_id=body.audioId, level_id=body.levelId,
        submission_id=body.submissionId, request_id=actor.request_id)
    outcome = await detection_uc.wait_sync_window(outcome)
    if outcome.status == 200:
        return envelope(request, {"recording": detection_uc.recording_view(outcome.recording),
                                  "result": outcome.result})
    return envelope(request, {"recording": detection_uc.recording_view(outcome.recording)},
                    code="PROCESSING", message="评分处理中，请稍后查询",
                    status=202, headers={"Retry-After": str(config.RETRY_AFTER_SECONDS)})


@router.get("/recordings/{recording_id}", response_model=Envelope[RecordingWithResult],
             responses={202: {"model": Envelope[RecordingOnly], "description": "PROCESSING"}})
async def get_recording(request: Request, recording_id: str,
                        actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    outcome = detection_uc.get_recording(actor.db, user_id=user.id,
                                         recording_id=recording_id)
    if outcome.status == 200:
        return envelope(request, {"recording": detection_uc.recording_view(outcome.recording),
                                  "result": outcome.result})
    return envelope(request, {"recording": detection_uc.recording_view(outcome.recording)},
                    code="PROCESSING", message="评分处理中，请稍后查询",
                    status=202, headers={"Retry-After": str(config.RETRY_AFTER_SECONDS)})


@router.delete("/recordings/{recording_id}", response_model=Envelope[RecordingDeleted])
async def delete_recording(request: Request, recording_id: str,
                           actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    from app.detection.models import RecordingRow

    rec = actor.db.query(RecordingRow).filter(
        RecordingRow.id == recording_id,
        RecordingRow.user_id == user.id).one_or_none()
    if rec is None:
        raise ApiError(404, "NOT_FOUND", "录音不存在或不可见")
    already = rec.deleted_at is not None
    if not already:
        archive_uc.delete_recording(actor.db, rec)
        actor.db.commit()
    return envelope(request, {"deleted": True, "alreadyDeleted": already})
