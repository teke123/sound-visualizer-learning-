"""音频、标定与检测路由（要求登录；D-05/D-19/D-20）。"""
from __future__ import annotations

from typing import Literal, Optional

import asyncio

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
from app.scoring import calibration_sessions as calib_sessions
from app.scoring import usecases as scoring_uc

from app.api.schemas import (AudioUploadResponse, CalibrationSessionView,
                             CalibrationTakeOutcome, Envelope, F0Response,
                             FormantsResponse, PitchCalibrationInfo,
                             PronunciationAdviceResult, RecordingDeleted, RecordingOnly, RecordingWithResult)

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


# ---------------- 标定（FR-1006，可跳过；多录音会话流程） ----------------

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
        "vowelTasks": calib_sessions.VOWEL_TASKS,
    }
    if effective:
        data["pitchRange"] = {"fLo": effective["fLo"], "fHi": effective["fHi"]}
        data["updatedAt"] = effective.get("updatedAt")
    return envelope(request, data)


@router.post("/pitch-calibration/sessions", response_model=Envelope[CalibrationSessionView])
async def create_calibration_session(request: Request,
                                     actor: Actor = Depends(get_actor)):
    """创建或返回当前用户进行中的标定会话（刷新/重开后由此恢复进度）。"""
    user = require_user(actor)
    actor.rate_limit("calibration_session")
    text_row = content_uc.get_active_calibration_text(actor.db)
    if text_row is None:
        raise ApiError(500, "INTERNAL_ERROR", "标定文本未配置，请联系管理员")
    data = calib_sessions.create_or_get_session(actor.db, user_id=user.id,
                                                text_row=text_row)
    return envelope(request, data)


@router.get("/pitch-calibration/sessions/{session_id}",
            response_model=Envelope[CalibrationSessionView])
async def get_calibration_session(request: Request, session_id: str,
                                  actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    session = calib_sessions._owned_session(actor.db, user_id=user.id, session_id=session_id)
    return envelope(request, calib_sessions.session_view(actor.db, session))


class CalibrationTakeBody(BaseModel):
    audioId: str
    kind: Literal["vowel", "pitch"]
    vowel: Optional[str] = None


@router.post("/pitch-calibration/sessions/{session_id}/takes",
             response_model=Envelope[CalibrationTakeOutcome])
async def submit_calibration_take(request: Request, session_id: str,
                                  body: CalibrationTakeBody,
                                  actor: Actor = Depends(get_actor)):
    """提交单条标定录音并验收：accepted / retry_take / additional_take_required /
    vowel_dispersed 及下一任务。"""
    user = require_user(actor)
    user_id = user.id
    actor.rate_limit("calibration_take")
    # 单条验收含质检、共振峰测量与短文评分调用，放线程池执行
    def accept_in_worker():
        from app.db import get_session
        worker_db = get_session()
        try:
            return calib_sessions.accept_take(
                worker_db, user_id=user_id, session_id=session_id,
                audio_id=body.audioId, kind=body.kind, vowel=body.vowel)
        finally:
            worker_db.close()

    result = await asyncio.get_running_loop().run_in_executor(None, accept_in_worker)
    actor.db.rollback()
    session = calib_sessions._owned_session(actor.db, user_id=user_id,
                                            session_id=session_id)
    result["session"] = calib_sessions.session_view(actor.db, session)
    return envelope(request, result)


@router.post("/pitch-calibration/sessions/{session_id}/complete",
             response_model=Envelope[CalibrationSessionView])
async def complete_calibration_session(request: Request, session_id: str,
                                       actor: Actor = Depends(get_actor)):
    """任务齐备后启动最终计算；返回会话状态，由 GET 查询完成结果（幂等）。"""
    user = require_user(actor)
    actor.rate_limit("calibration_complete")
    data = calib_sessions.request_completion(actor.db, user_id=user.id,
                                             session_id=session_id)
    return envelope(request, data)


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


@router.get("/recordings/{recording_id}/pronunciation-advice",
            response_model=Envelope[PronunciationAdviceResult])
async def get_pronunciation_advice(request: Request, recording_id: str,
                                  actor: Actor = Depends(get_actor)):
    from app.db import JSONText
    from app.detection.models import PronunciationAdviceRow, RecordingRow

    user = require_user(actor)
    row = actor.db.query(PronunciationAdviceRow).join(RecordingRow).filter(
        PronunciationAdviceRow.recording_id == recording_id,
        RecordingRow.user_id == user.id, RecordingRow.deleted_at.is_(None),
    ).one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "发音建议不存在或不可见")
    return envelope(request, {"status": row.status, "items": JSONText.load(row.items, [])})


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
