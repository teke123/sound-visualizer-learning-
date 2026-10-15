"""detection 用例：两步提交、幂等、短同步窗口 + 202 回落、30 秒硬截止、
进程内执行器管线（signal_check → scoring → analyzing → finalizing）、
不可变结果快照与写回守卫（决策图「检测处理模型」）。"""
from __future__ import annotations

import asyncio
import datetime
import hashlib
import logging

from sqlalchemy.orm import Session

from app import config
from app.acoustics import analysis
from app.acoustics.models import AudioRow
from app.acoustics.usecases import audio_path
from app.content.models import DetectionSwitchRow, LevelRow, LevelVersionRow
from app.content_seed_data import GLOBAL_FOUR_STEP_FALLBACKS
from app.db import JSONText, get_session, now
from app.detection.models import AssessmentResultRow, RecordingRow
from app.ids import new_id
from app.platform.envelope import ApiError
from app.scoring.models import PitchRangeRow, PitchRangeSnapshotRow
from app.scoring.provider import ProviderError
from app.scoring import rules as scoring_rules
from app.scoring import usecases as scoring_uc

logger = logging.getLogger("svs.detection")

STAGES = ["queued", "signal_check", "scoring", "analyzing", "finalizing"]


def _payload_hash(audio_id: str, level_id: str, content_version: int) -> str:
    return hashlib.sha256(f"{audio_id}|{level_id}|{content_version}".encode()).hexdigest()


def _stage_failed_code_status(code: str) -> int:
    return {
        "TIMEOUT": 504,
        "PROVIDER_DOWN": 503,
        "PROVIDER_ERROR": 502,
        "SERVER_BUSY": 503,
    }.get(code, 500)


def recording_view(rec: RecordingRow) -> dict:
    """录音对象（契约）：不返回 submissionId。"""
    return {
        "recordingId": rec.id,
        "audioId": rec.audio_id,
        "levelId": rec.level_id,
        "contentVersion": rec.content_version,
        "status": rec.status,
        "stage": rec.stage if rec.status == "processing" else None,
        "error": ({"code": rec.outcome, "retryable": bool(rec.retryable)}
                  if rec.status == "failed" else None),
        "storage": rec.storage,
        "expiresAt": rec.expires_at.isoformat() if (rec.expires_at and rec.storage == "session") else None,
        "createdAt": rec.created_at.isoformat() if rec.created_at else None,
    }


class SubmitOutcome:
    def __init__(self, status: int, recording: RecordingRow, result: dict | None):
        self.status = status
        self.recording = recording
        self.result = result


def submit_recording(db: Session, *, owner_type: str, owner_id: str, user,
                     audio_id: str, level_id: str, content_version: int,
                     submission_id: str, request_id: str | None) -> SubmitOutcome:
    """受理（5.1）：校验 → 幂等 → 建记录/重试 → 投递执行器。"""
    if not submission_id or len(submission_id) > 128:
        raise ApiError(422, "VALIDATION_ERROR", "submissionId 缺失或过长")

    audio = db.get(AudioRow, audio_id)
    if (audio is None or audio.deleted_at is not None or audio.expires_at < now()
            or audio.owner_type != owner_type or audio.owner_id != owner_id
            or audio.purpose != "recording"):
        raise ApiError(404, "NOT_FOUND", "音频不存在、已过期或不属于当前会话")

    level = db.get(LevelRow, level_id)
    if level is None or level.status != "published" or not level.current_version_id:
        raise ApiError(404, "NOT_FOUND", "关卡不存在或未发布")
    version = db.get(LevelVersionRow, level.current_version_id)
    if content_version != version.version:
        raise ApiError(409, "CONTENT_VERSION_CHANGED",
                       "关卡内容已更新，请刷新任务后重试", next_step="请刷新关卡页获取最新任务")

    off = db.query(DetectionSwitchRow).filter(DetectionSwitchRow.enabled.is_(False))
    if (off.filter(DetectionSwitchRow.level_id == level_id).count()
            or off.filter(DetectionSwitchRow.level_id.is_(None)).count()):
        raise ApiError(503, "DETECTION_OFF", "本关检测暂停服务，请稍后再试",
                       next_step="可以先学习本关内容，稍后再来录音")

    # 标定前置（D-20）：无有效音域不受理、不建记录
    effective = scoring_uc.get_effective_range(db, owner_type=owner_type, owner_id=owner_id)
    if effective is None:
        raise ApiError(409, "CALIBRATION_REQUIRED", "需要先完成音域标定才能提交检测",
                       next_step="请先按标定文本完成音域标定")

    payload_hash = _payload_hash(audio_id, level_id, content_version)
    existing = db.query(RecordingRow).filter(
        RecordingRow.owner_type == owner_type, RecordingRow.owner_id == owner_id,
        RecordingRow.submission_id == submission_id).one_or_none()
    if existing is not None:
        if existing.deleted_at is not None or (
                existing.expires_at is not None and existing.expires_at < now()):
            raise ApiError(404, "NOT_FOUND", "录音不存在或已过期")
        if existing.submission_payload_hash != payload_hash:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT",
                           "同一 submissionId 只能绑定同一提交内容")
        if existing.status == "completed":
            result = db.query(AssessmentResultRow).filter(
                AssessmentResultRow.recording_id == existing.id).one_or_none()
            return SubmitOutcome(200, existing,
                                 JSONText.load(result.payload) if result else None)
        if existing.status == "processing":
            return SubmitOutcome(202, existing, None)

    # 新建或可重试失败复活：受理时固定音域快照（epoch、deadline 同步记录）
    snapshot = scoring_uc.create_snapshot(
        db, owner_type=owner_type, owner_id=owner_id,
        f_lo=effective["fLo"], f_hi=effective["fHi"],
        vowel_space=effective.get("vowelSpace"),
        created_from={"kind": "accepted_range", "status": effective["status"],
                      "basis": effective.get("basisCalibrationId")},
    )
    epoch = user.data_epoch if user is not None else 1
    if existing is not None and existing.retryable:   # failed(retryable) 同键重试
        existing.status = "processing"
        existing.stage = "queued"
        existing.attempt += 1
        existing.deadline_at = now() + datetime.timedelta(seconds=config.HARD_DEADLINE_SECONDS)
        existing.epoch_at_start = epoch
        existing.range_snapshot_id = snapshot.id
        existing.accepted_request_id = request_id
        rec = existing
    elif existing is not None:
        # 不可重试失败：幂等重放直接返回失败结论，不复活重跑
        code = existing.outcome or "INTERNAL_ERROR"
        raise ApiError(_stage_failed_code_status(code), code, _failure_message(code),
                       data={"recordingId": existing.id, "retryable": False})
    else:
        rec = RecordingRow(
            id=new_id("rc_"),
            owner_type=owner_type, owner_id=owner_id,
            audio_id=audio_id, level_id=level_id,
            content_version=content_version, rule_version=config.RULE_VERSION,
            submission_id=submission_id, submission_payload_hash=payload_hash,
            status="processing", stage="queued", attempt=1,
            deadline_at=now() + datetime.timedelta(seconds=config.HARD_DEADLINE_SECONDS),
            epoch_at_start=epoch, range_snapshot_id=snapshot.id,
            storage="session", expires_at=audio.expires_at,
            accepted_request_id=request_id, created_at=now(),
        )
        db.add(rec)
    db.commit()

    from app.platform.executor import executor
    future = executor.try_submit(run_pipeline, rec.id)
    if future is None:
        # 队列已满：不留下孤儿 processing 记录
        if existing is not None:   # 重试复活失败 → 回退为原失败态
            rec.status = "failed"
            rec.stage = None
            rec.attempt -= 1
            db.commit()
        else:                      # 新受理 → 撤销
            db.delete(rec)
            db.commit()
        raise ApiError(503, "SERVER_BUSY", "当前处理排队已满，请稍后重试",
                       headers={"Retry-After": "5"})
    rec._future = future  # type: ignore[attr-defined]  路由层等待用
    return SubmitOutcome(202, rec, None)


def _consume_future_result(f: asyncio.Future) -> None:
    """窗口外迟到完成时取走结果，避免 "exception was never retrieved" 告警。"""
    if not f.cancelled():
        f.exception()


async def wait_sync_window(outcome: SubmitOutcome) -> SubmitOutcome:
    """同步窗口（约 8 秒）内等待完成；未完成回落 202。

    超时只结束等待、绝不取消执行器任务：wait_for 的超时取消会顺着
    wrap_future 传给尚未开跑的 concurrent Future（SVS_SYNC_WINDOW 极小时
    必现），管线永不执行、录音滞留 processing 直到硬截止标 TIMEOUT——
    故改用不对参与者做取消的 asyncio.wait。"""
    future = getattr(outcome.recording, "_future", None)
    if future is None:
        return outcome
    wrapped = asyncio.wrap_future(future)
    wrapped.add_done_callback(_consume_future_result)
    await asyncio.wait({wrapped}, timeout=config.SYNC_WINDOW_SECONDS)
    db = get_session()
    try:
        rec = db.get(RecordingRow, outcome.recording.id)
        if rec is not None:
            outcome.recording = rec
            if rec.status == "completed":
                result = db.query(AssessmentResultRow).filter(
                    AssessmentResultRow.recording_id == rec.id).one_or_none()
                outcome.result = JSONText.load(result.payload) if result else None
                outcome.status = 200
        return outcome
    finally:
        db.close()


# ---------------- 管线（执行器线程内运行） ----------------

def run_pipeline(recording_id: str) -> None:
    """signal_check → scoring → analyzing → finalizing；每阶段短事务更新 stage；
    外部调用不持有数据库事务。"""
    db = get_session()
    try:
        rec = db.get(RecordingRow, recording_id)
        if rec is None or rec.status != "processing":
            return
        audio = db.get(AudioRow, rec.audio_id)
        if audio is None:
            _fail(db, rec, "PROVIDER_ERROR", retryable=False)
            return
        path = audio_path(audio)
        level = db.get(LevelRow, rec.level_id)
        version = db.get(LevelVersionRow, level.current_version_id)
        content = JSONText.load(version.content, {})
        det = content.get("detection") or {}

        def set_stage(stage: str) -> None:
            rec.stage = stage
            db.commit()

        set_stage("signal_check")
        signal = analysis.check_signal(path, purpose="recording")
        if signal.verdict != "pass":
            _finalize_quality_fail(db, rec, audio, content, signal.to_dict(), None)
            return

        set_stage("scoring")
        reading: dict | None = None
        cached = scoring_uc.read_score_cache(
            db, owner_type=rec.owner_type, owner_id=rec.owner_id, audio=audio,
            level_id=rec.level_id, content_version=rec.content_version)
        if cached is not None:
            prov = _provider_from_cache(cached["provider"])
            reading = cached["reading"]
        else:
            provider = scoring_uc.get_provider()
            try:
                prov = provider.evaluate(str(path), det.get("evaluationText", ""))
            except ProviderError as e:
                code = "PROVIDER_DOWN" if e.kind == "down" else "PROVIDER_ERROR"
                _fail(db, rec, code, retryable=True)
                return
            except Exception:
                _fail(db, rec, "PROVIDER_ERROR", retryable=True)
                return
            reading_pass, reading = scoring_rules.judge_reading(prov)
            if not reading_pass:
                _finalize_quality_fail(db, rec, audio, content, signal.to_dict(), reading)
                return

        set_stage("analyzing")
        snapshot_row = db.get(PitchRangeSnapshotRow, rec.range_snapshot_id)
        if snapshot_row is None:
            # 受理时必然已写入快照（submit_recording）；缺失属数据完整性破坏，
            # 不用兜底音域静默换算，交外层异常处理标可重试失败（重试生成新快照）
            raise RuntimeError(
                f"range snapshot {rec.range_snapshot_id} missing for recording {rec.id}")
        snapshot = scoring_uc.snapshot_dict(snapshot_row)
        f0res = analysis.extract_f0(path)
        curve = scoring_rules.analyze_user_curve(
            f0res, prov, snapshot, content.get("standardCurve"))
        curve_tags = scoring_rules.curve_phenomena(curve)

        formant_dev = None
        formants_out = None
        if level.layer == "vowel":
            f_out = scoring_rules.analyze_formants(
                str(path), prov, snapshot, (content.get("standardCurve") or {}).get("referenceRegion"))
            formants_out = f_out
            formant_dev = f_out.get("deviation")

        phenomena, four_steps, score = scoring_rules.build_phenomena_and_four_steps(
            provider=prov, curve_phenomena_items=curve_tags,
            formant_deviation=formant_dev, level_content=content,
            fallback_templates=GLOBAL_FOUR_STEP_FALLBACKS,
        )

        set_stage("finalizing")
        result = {
            "levelId": rec.level_id,
            "contentVersion": rec.content_version,
            "ruleVersion": rec.rule_version,
            "providerVersion": prov.provider_version,
            "algorithmVersion": analysis.ALGORITHM_VERSION,
            "quality": {"verdict": "pass", "signal": signal.to_dict(),
                        "reading": reading},
            "score": score,
            "phenomena": phenomena,
            "fourSteps": four_steps,
            "curve": curve,
            "boundaryNote": config.BOUNDARY_NOTE,
        }
        if formants_out is not None:
            result["formants"] = formants_out
        _finalize_completed(db, rec, audio, result, cacheable={
            "provider": _provider_payload(prov), "reading": reading,
        })
    except Exception:
        import traceback

        traceback.print_exc()
        try:
            db.rollback()
            rec = db.get(RecordingRow, recording_id)
            if rec is not None and rec.status == "processing":
                _fail(db, rec, "PROVIDER_ERROR", retryable=True)
        except Exception:
            logger.exception("录音 %s 管线失败后标记 failed 时再出错", recording_id)
    finally:
        db.close()


def _provider_payload(prov) -> dict:  # noqa: ANN001
    return {
        "provider_version": prov.provider_version,
        "overall_score": prov.overall_score,
        "initial_score": prov.initial_score,
        "final_score": prov.final_score,
        "tone_score": prov.tone_score,
        "reading": prov.reading,
        "syllables": [
            {"text": s.text, "pinyin": s.pinyin, "t0": s.t0, "t1": s.t1,
             "initial_ok": s.initial_ok, "final_ok": s.final_ok,
             "tone_ok": s.tone_ok, "tone_value": s.tone_value}
            for s in prov.syllables
        ],
    }


def _provider_from_cache(data: dict):
    """评分缓存命中：重建 ProviderResult（分数/现象/四步可重复，FR-1003）。"""
    from app.scoring.provider import SyllableEval

    return type("CachedProvider", (), {
        "provider_version": data["provider_version"],
        "overall_score": data["overall_score"],
        "initial_score": data.get("initial_score"),
        "final_score": data.get("final_score"),
        "tone_score": data.get("tone_score"),
        "reading": data.get("reading", {}),
        "syllables": [
            SyllableEval(
                text=s["text"], pinyin=s.get("pinyin"), t0=s.get("t0", 0.0),
                t1=s.get("t1", 0.0), initial_ok=s.get("initial_ok", True),
                final_ok=s.get("final_ok", True), tone_ok=s.get("tone_ok", True),
                tone_value=s.get("tone_value"),
            ) for s in data.get("syllables", [])
        ],
    })()


def _finalize_quality_fail(db: Session, rec: RecordingRow, audio: AudioRow,
                           content: dict, signal: dict, reading: dict | None) -> None:
    """QUALITY_FAIL：有效业务结果（200），不填分数与检测现象。"""
    advice = None
    if reading and reading.get("advice"):
        advice = reading["advice"]
    if not advice:
        for dim in ("volume", "noise", "clipping", "duration", "silence"):
            if signal.get(dim, {}).get("advice"):
                advice = signal[dim]["advice"]
                break
    reading_out = reading or {
        "missing": [], "extra": [], "repeated": [], "replaced": [],
        "disordered": False, "advice": None,
    }
    result = {
        "levelId": rec.level_id,
        "contentVersion": rec.content_version,
        "ruleVersion": rec.rule_version,
        "providerVersion": config.PROVIDER_VERSION,
        "algorithmVersion": analysis.ALGORITHM_VERSION,
        "quality": {
            "verdict": "fail",
            "signal": signal,
            "reading": reading_out,
            "retakeAdvice": advice or "请按提示重录一次",
        },
        "boundaryNote": config.BOUNDARY_NOTE,
    }
    _finalize_completed(db, rec, audio, result, cacheable=None)


def _finalize_completed(db: Session, rec: RecordingRow, audio: AudioRow,
                        result: dict, cacheable: dict | None) -> None:
    """完成写入前重校验：未删除、未过期、dataEpoch 未变；按此刻同意状态归档。"""
    from app.identity.models import UserRow
    from app.identity.usecases import consent_granted

    db.refresh(rec)
    db.refresh(audio)
    if rec.status != "processing":
        # 管线跑过硬截止、被调度器标 failed(TIMEOUT) 后醒来收尾：迟到的
        # 完成不得复活已判死的录音（与下方删除/过期/epoch 守卫同款语义）
        db.rollback()
        return
    if rec.deleted_at is not None:
        db.rollback()
        return
    if audio.deleted_at is not None or (rec.expires_at and rec.expires_at < now()):
        db.rollback()
        return
    user = None
    if rec.owner_type == "user":
        user = db.get(UserRow, rec.owner_id)
        if user is None or user.deleted_at is not None:
            db.rollback()
            return
        if user.data_epoch != rec.epoch_at_start:
            db.rollback()
            return
        if consent_granted(db, user):
            rec.storage = "archived"
            rec.expires_at = None
    verdict = result["quality"]["verdict"]
    rec.status = "completed"
    rec.outcome = "scored" if verdict == "pass" else "quality_fail"
    rec.completed_at = now()
    if rec.storage == "archived":
        result["storage"] = "archived"
    else:
        result["storage"] = "session"
        result["expiresAt"] = rec.expires_at.isoformat() if rec.expires_at else None
    db.add(AssessmentResultRow(
        id=new_id("ar_"), recording_id=rec.id,
        payload=JSONText.dump(result), created_at=now(),
    ))
    if cacheable is not None and rec.outcome == "scored":
        scoring_uc.write_score_cache(
            db, owner_type=rec.owner_type, owner_id=rec.owner_id,
            audio_id=rec.audio_id, pcm_sha256=audio.pcm_sha256,
            level_id=rec.level_id, content_version=rec.content_version,
            payload=cacheable)
    db.commit()


def _fail(db: Session, rec: RecordingRow, code: str, *, retryable: bool) -> None:
    rec.status = "failed"
    rec.outcome = code
    rec.retryable = retryable
    rec.completed_at = now()
    db.commit()


# ---------------- 查询 / 超时恢复 ----------------

def get_recording(db: Session, *, owner_type: str, owner_id: str,
                  recording_id: str) -> SubmitOutcome:
    rec = db.get(RecordingRow, recording_id)
    if (rec is None or rec.deleted_at is not None or rec.owner_type != owner_type
            or rec.owner_id != owner_id):
        raise ApiError(404, "NOT_FOUND", "录音不存在或不可见")
    if rec.status == "processing":
        return SubmitOutcome(202, rec, None)
    if rec.status == "completed":
        result = db.query(AssessmentResultRow).filter(
            AssessmentResultRow.recording_id == rec.id).one_or_none()
        return SubmitOutcome(200, rec, JSONText.load(result.payload) if result else None)
    code = rec.outcome or "INTERNAL_ERROR"
    raise ApiError(_stage_failed_code_status(code), code,
                   _failure_message(code),
                   data={"recordingId": rec.id, "retryable": bool(rec.retryable)})


def _failure_message(code: str) -> str:
    return {
        "TIMEOUT": "处理超时，可在此页面用同一提交重试",
        "PROVIDER_DOWN": "评分服务暂不可用，请稍后重试",
        "PROVIDER_ERROR": "评分服务返回异常，请稍后重试",
    }.get(code, "处理失败，请重试")


def sweep_timeouts(db: Session) -> int:
    """processing 超过 deadline → failed(retryable, TIMEOUT)；查询返回 504。"""
    rows = db.query(RecordingRow).filter(
        RecordingRow.status == "processing",
        RecordingRow.deadline_at < now()).all()
    for rec in rows:
        _fail(db, rec, "TIMEOUT", retryable=True)
    return len(rows)


def recover_on_startup(db: Session) -> int:
    """重启恢复：遗留 processing 一律置为 failed(retryable, TIMEOUT)。"""
    rows = db.query(RecordingRow).filter(RecordingRow.status == "processing").all()
    for rec in rows:
        _fail(db, rec, "TIMEOUT", retryable=True)
    return len(rows)


def expire_temp_records(db: Session) -> int:
    """到期的 session 录音/上传/会话标定：置不可读并登记删除。"""
    from app.acoustics.usecases import mark_deleted as mark_audio_deleted
    from app.scoring.usecases import delete_owner_ranges

    n = 0
    for rec in db.query(RecordingRow).filter(
            RecordingRow.storage == "session",
            RecordingRow.deleted_at.is_(None),
            RecordingRow.expires_at.is_not(None),
            RecordingRow.expires_at < now()).all():
        rec.deleted_at = now()
        n += 1
    for audio in db.query(AudioRow).filter(
            AudioRow.deleted_at.is_(None), AudioRow.expires_at < now()).all():
        mark_audio_deleted(db, audio)
        n += 1
    for rng in db.query(PitchRangeRow).filter(
            PitchRangeRow.owner_type == "sid",
            PitchRangeRow.deleted_at.is_(None)).all():
        if rng.expires_at is not None and rng.expires_at < now():
            rng.deleted_at = now()
            n += 1
    db.commit()
    return n
