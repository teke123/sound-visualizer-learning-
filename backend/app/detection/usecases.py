"""detection 用例：两步提交、幂等、短同步窗口 + 202 回落、30 秒硬截止、
进程内执行器管线（analyzing → scoring → finalizing）、结果快照（D-19）。

录音质量指标（音量/噪声/截幅/时长）与朗读检错照常计算，仅作为提示随
结果返回，不拦截评分与可视化（FR-1301 / D-05）。
"""
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
from app.content.models import LevelRow, MediaAssetRow
from app.content_seed_data import GLOBAL_FOUR_STEP_FALLBACKS
from app.db import JSONText, get_session, now
from app.detection.models import AssessmentResultRow, RecordingRow
from app.ids import new_id
from app.platform.envelope import ApiError
from app.scoring.models import PitchRangeSnapshotRow
from app.scoring.provider import ProviderError
from app.scoring import rules as scoring_rules
from app.scoring import usecases as scoring_uc

logger = logging.getLogger("svs.detection")

STAGES = ["queued", "analyzing", "scoring", "finalizing"]


def _payload_hash(audio_id: str, level_id: str) -> str:
    return hashlib.sha256(f"{audio_id}|{level_id}".encode()).hexdigest()


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
        "status": rec.status,
        "stage": rec.stage if rec.status == "processing" else None,
        "error": ({"code": rec.outcome, "retryable": bool(rec.retryable)}
                  if rec.status == "failed" else None),
        "createdAt": rec.created_at.isoformat() if rec.created_at else None,
    }


class SubmitOutcome:
    def __init__(self, status: int, recording: RecordingRow, result: dict | None):
        self.status = status
        self.recording = recording
        self.result = result


def submit_recording(db: Session, *, user, audio_id: str, level_id: str,
                     submission_id: str, request_id: str | None) -> SubmitOutcome:
    """受理（D-19）：校验 → 幂等 → 建记录/重试 → 投递执行器。

    音域标定可跳过（D-20）：未标定时用默认成人参考范围受理。
    """
    if not submission_id or len(submission_id) > 128:
        raise ApiError(422, "VALIDATION_ERROR", "submissionId 缺失或过长")

    audio = db.get(AudioRow, audio_id)
    if (audio is None or audio.deleted_at is not None
            or audio.user_id != user.id or audio.purpose != "recording"):
        raise ApiError(404, "NOT_FOUND", "音频不存在或不属于当前账号")

    level = db.get(LevelRow, level_id)
    if level is None or not level.published:
        raise ApiError(404, "NOT_FOUND", "关卡不存在或未开放")

    payload_hash = _payload_hash(audio_id, level_id)
    existing = db.query(RecordingRow).filter(
        RecordingRow.user_id == user.id,
        RecordingRow.submission_id == submission_id).one_or_none()
    if existing is not None:
        if existing.deleted_at is not None:
            raise ApiError(404, "NOT_FOUND", "录音不存在或已删除")
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

    # 新建或可重试失败复活：受理时固定音域快照（deadline 同步记录）
    effective = scoring_uc.get_personal_range(db, user_id=user.id)
    if effective is not None:
        snapshot = scoring_uc.create_snapshot(
            db, user_id=user.id,
            f_lo=effective["fLo"], f_hi=effective["fHi"],
            vowel_space=effective.get("vowelSpace"),
            created_from={"kind": "calibration_baseline",
                          "basis": effective.get("basisCalibrationId")},
        )
    else:
        f_lo, f_hi = config.DEFAULT_ADULT_F0_RANGE
        snapshot = scoring_uc.create_snapshot(
            db, user_id=user.id, f_lo=f_lo, f_hi=f_hi,
            vowel_space=None, created_from={"kind": "default_adult_range"},
        )
    if existing is not None and existing.retryable:   # failed(retryable) 同键重试
        existing.status = "processing"
        existing.stage = "queued"
        existing.attempt += 1
        existing.deadline_at = now() + datetime.timedelta(seconds=config.HARD_DEADLINE_SECONDS)
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
            user_id=user.id,
            audio_id=audio_id, level_id=level_id,
            submission_id=submission_id, submission_payload_hash=payload_hash,
            status="processing", stage="queued", attempt=1,
            deadline_at=now() + datetime.timedelta(seconds=config.HARD_DEADLINE_SECONDS),
            range_snapshot_id=snapshot.id,
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

    超时只结束等待、绝不取消执行器任务。
    """
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
    """analyzing（质量指标+声学）→ scoring → finalizing；每阶段短事务更新 stage；
    外部调用不持有数据库事务。"""
    db = get_session()
    try:
        rec = db.get(RecordingRow, recording_id)
        if rec is None or rec.status != "processing":
            return
        audio = db.get(AudioRow, rec.audio_id)
        if audio is None:
            _fail(db, rec, "INTERNAL_ERROR", retryable=False)
            return
        path = audio_path(audio)
        level = db.get(LevelRow, rec.level_id)
        content = JSONText.load(level.content, {}) if level else {}
        det = content.get("detection") or {}

        def set_stage(stage: str) -> None:
            rec.stage = stage
            db.commit()

        # 质量指标照常计算，仅作提示（FR-1301）
        set_stage("analyzing")
        signal = analysis.check_signal(path, purpose="recording")
        f0res = analysis.extract_f0(path)

        set_stage("scoring")
        reading: dict | None = None
        cached = scoring_uc.read_score_cache(
            db, user_id=rec.user_id, audio=audio, level_id=rec.level_id)
        if cached is not None:
            prov = _provider_from_cache(cached["provider"])
            reading = cached["reading"]
        else:
            provider = scoring_uc.get_provider()
            try:
                prov = provider.evaluate(str(path), det.get("evaluationText", ""),
                                         pinyin=det.get("evaluationPinyin"))
            except ProviderError as e:
                code = "PROVIDER_DOWN" if e.kind == "down" else "PROVIDER_ERROR"
                _fail(db, rec, code, retryable=True)
                return
            except Exception:
                _fail(db, rec, "PROVIDER_ERROR", retryable=True)
                return
            reading = scoring_rules.reading_report(prov)

        snapshot_row = db.get(PitchRangeSnapshotRow, rec.range_snapshot_id)
        if snapshot_row is None:
            # 受理时必然已写入快照（submit_recording）；缺失属数据完整性破坏，
            # 不用兜底音域静默换算，交外层异常处理标可重试失败（重试生成新快照）
            raise RuntimeError(
                f"range snapshot {rec.range_snapshot_id} missing for recording {rec.id}")
        # 未标定受理时先落默认成人范围；此处用本次录音有声段 P5–P95 原地升级为
        # 单次录音自适应（FR-1006 二选一），快照语义不变；不足时保持默认范围
        if JSONText.load(snapshot_row.created_from, {}).get("kind") == "default_adult_range":
            adaptive = analysis.adaptive_f0_range(f0res)
            if adaptive is not None:
                snapshot_row.f_lo, snapshot_row.f_hi = adaptive
                snapshot_row.created_from = JSONText.dump({"kind": "recording_adaptive"})
                db.commit()
        snapshot = scoring_uc.snapshot_dict(snapshot_row)
        curve = scoring_rules.analyze_user_curve(
            str(path), prov, snapshot, content.get("standardCurve"))
        curve_tags = scoring_rules.curve_phenomena(curve)

        formant_dev = None
        formants_out = None
        if level is not None and level.layer == "vowel":
            f_out = scoring_rules.analyze_formants(
                str(path), prov, snapshot, (content.get("standardCurve") or {}).get("referenceRegion"))
            formants_out = f_out
            formant_dev = f_out.get("deviation")

        # 送气段/VOT 对比（FR-1005）：参考示范取本关检测任务的 sampleMediaId
        # （seed/CMS 维护），用户侧复用管线已提取的 f0res，避免重复提取音高
        vot_out = None
        if level is not None and level.layer == "initial":
            ref_media_id = det.get("sampleMediaId")
            ref_asset = db.get(MediaAssetRow, ref_media_id) if ref_media_id else None
            if ref_asset is not None and ref_asset.deleted_at is None:
                vot_out = scoring_rules.analyze_vot(
                    str(path), f0res, str(config.DATA_DIR / ref_asset.storage_path),
                    content.get("targetSound") or "", ref_asset.id)

        phenomena, four_steps, score = scoring_rules.build_phenomena_and_four_steps(
            provider=prov, curve_phenomena_items=curve_tags,
            formant_deviation=formant_dev, level_content=content,
            fallback_templates=GLOBAL_FOUR_STEP_FALLBACKS,
            dialect_background=user_dialect(db, rec.user_id),
        )

        set_stage("finalizing")
        result = {
            "levelId": rec.level_id,
            "providerVersion": prov.provider_version,
            "algorithmVersion": analysis.ALGORITHM_VERSION,
            "quality": _quality_payload(signal.to_dict(), reading),
            "score": score,
            "phenomena": phenomena,
            "fourSteps": four_steps,
            "curve": curve,
        }
        if formants_out is not None:
            result["formants"] = formants_out
        if vot_out is not None:
            result["vot"] = vot_out
        _finalize_completed(db, rec, result, cacheable={
            "provider": _provider_payload(prov), "reading": reading,
        })
    except Exception:
        # 自家分析/规则/写库代码的崩溃不伪装成评分服务故障：INTERNAL_ERROR(500)。
        # Provider 调用已在 scoring 阶段内联捕获，此处理论上只见内部异常
        logger.exception("录音 %s 评分管线内部错误", recording_id)
        _fail_after_pipeline_error(db, recording_id, "INTERNAL_ERROR", retryable=True)
    finally:
        db.close()


def user_dialect(db: Session, user_id: str) -> str | None:
    """用户方言区/母语背景（FR-1007 提示用）；注销痕迹读取为空。"""
    from app.identity.models import UserRow

    user = db.get(UserRow, user_id)
    return user.dialect_background if user is not None and user.deleted_at is None else None


def _quality_payload(signal: dict, reading: dict | None) -> dict:
    """录音质量提示（FR-1301/附录 B）：指标 + 改善建议文案，不阻断结果。"""
    advice = None
    if reading and reading.get("advice"):
        advice = reading["advice"]
    if not advice:
        for dim in ("volume", "noise", "clipping", "duration", "silence"):
            if signal.get(dim, {}).get("advice"):
                advice = signal[dim]["advice"]
                break
    quality = {"signal": signal}
    if reading is not None:
        quality["reading"] = reading
    if advice:
        quality["advice"] = advice
    return quality


def _fail_after_pipeline_error(db: Session, recording_id: str, code: str,
                               *, retryable: bool) -> None:
    """管线异常收尾：回滚事务；仍处于 processing 的录音标记为可重试失败
    （重试会重建快照、重跑管线），调度器兜底把漏网的置为 TIMEOUT。"""
    try:
        db.rollback()
        rec = db.get(RecordingRow, recording_id)
        if rec is not None and rec.status == "processing":
            _fail(db, rec, code, retryable=retryable)
    except Exception:
        logger.exception("录音 %s 管线失败后标记 failed 时再出错", recording_id)


def _provider_payload(prov) -> dict:  # noqa: ANN001
    return {
        "provider_version": prov.provider_version,
        "overall_score": prov.overall_score,
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


def _finalize_completed(db: Session, rec: RecordingRow, result: dict,
                        cacheable: dict | None) -> None:
    """完成写入前重校验：未删除、账号未注销。"""
    from app.identity.models import UserRow

    db.refresh(rec)
    if rec.status != "processing":
        # 管线跑过硬截止、被调度器标 failed(TIMEOUT) 后醒来收尾：迟到的
        # 完成不得复活已判死的录音（与下方删除守卫同款语义）
        db.rollback()
        return
    if rec.deleted_at is not None:
        db.rollback()
        return
    user = db.get(UserRow, rec.user_id)
    if user is None or user.deleted_at is not None:
        db.rollback()
        return
    rec.status = "completed"
    rec.outcome = "scored"
    rec.completed_at = now()
    db.add(AssessmentResultRow(
        id=new_id("ar_"), recording_id=rec.id,
        payload=JSONText.dump(result), created_at=now(),
    ))
    if cacheable is not None:
        audio = db.get(AudioRow, rec.audio_id)
        if audio is not None:
            scoring_uc.write_score_cache(
                db, user_id=rec.user_id,
                audio_id=rec.audio_id, pcm_sha256=audio.pcm_sha256,
                level_id=rec.level_id, payload=cacheable)
    db.commit()


def _fail(db: Session, rec: RecordingRow, code: str, *, retryable: bool) -> None:
    rec.status = "failed"
    rec.outcome = code
    rec.retryable = retryable
    rec.completed_at = now()
    db.commit()


# ---------------- 查询 / 超时恢复 ----------------

def get_recording(db: Session, *, user_id: str, recording_id: str) -> SubmitOutcome:
    rec = db.get(RecordingRow, recording_id)
    if rec is None or rec.deleted_at is not None or rec.user_id != user_id:
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
        "INTERNAL_ERROR": "处理遇到问题，请重试；若持续失败请重新录音",
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
