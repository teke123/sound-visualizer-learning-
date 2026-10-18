"""acoustics 用例：上传、按 audioId 的 F0/共振峰/图片读取（本人所有权）。"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app import config
from app.acoustics import analysis, transcode
from app.acoustics.models import AudioRow, FeatureCacheRow
from app.db import JSONText, now
from app.ids import new_id
from app.platform.deletion_log import deletion_log
from app.platform.envelope import ApiError


def register_upload(db: Session, *, user_id: str, purpose: str,
                    filename: str | None, mime: str | None, raw_bytes: bytes) -> dict:
    """multipart 上传 → 转码规范化 → 落盘 + 登记（不依赖请求事务时长，
    转码完成后再开事务写行）。"""
    if len(raw_bytes) > config.MAX_UPLOAD_BYTES:
        raise ApiError(413, "FILE_TOO_LARGE",
                       f"文件过大（上限 {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB）")
    if purpose not in ("recording", "calibration"):
        raise ApiError(422, "VALIDATION_ERROR", "purpose 必须是 recording 或 calibration")

    audio_id = new_id("au_")
    dest_dir = config.PRIVATE_DIR / audio_id[:4]
    dest_dir.mkdir(parents=True, exist_ok=True)
    src_path = dest_dir / f"{audio_id}.src"
    wav_path = dest_dir / f"{audio_id}.wav"
    src_path.write_bytes(raw_bytes)
    try:
        normalized = transcode.normalize_to_wav(src_path, wav_path)
    finally:
        try:
            src_path.unlink()
        except OSError:
            pass

    if normalized.duration_sec > config.MAX_AUDIO_DURATION_SECONDS:
        wav_path.unlink(missing_ok=True)
        raise ApiError(422, "VALIDATION_ERROR",
                       f"音频时长超过 {int(config.MAX_AUDIO_DURATION_SECONDS)} 秒上限")

    row = AudioRow(
        id=audio_id,
        user_id=user_id,
        purpose=purpose,
        original_filename=filename,
        original_mime=mime,
        storage_path=str(wav_path.relative_to(config.DATA_DIR)),
        duration_sec=normalized.duration_sec,
        pcm_sha256=normalized.pcm_sha256,
        created_at=now(),
        deleted_at=None,
    )
    db.add(row)
    db.commit()
    return {
        "audioId": audio_id,
        "duration": normalized.duration_sec,
        "format": "pcm16k16mono",
    }


def get_audio_for_read(db: Session, *, audio_id: str, user_id: str,
                       purposes: tuple[str, ...] | None = None) -> AudioRow:
    """统一私有读取守卫：归属 + 未删除（统一 404，防枚举）。"""
    row = db.get(AudioRow, audio_id)
    if row is None or row.deleted_at is not None:
        raise ApiError(404, "NOT_FOUND", "音频不存在或已删除")
    if row.user_id != user_id:
        raise ApiError(404, "NOT_FOUND", "音频不存在或已删除")
    if purposes and row.purpose not in purposes:
        raise ApiError(404, "NOT_FOUND", "音频不存在或已删除")
    return row


def audio_path(row: AudioRow) -> Path:
    return config.DATA_DIR / row.storage_path


def mark_deleted(db: Session, row: AudioRow) -> None:
    """立即逻辑失效；文件/缓存进删除日志，由清理任务物理删除。"""
    if row.deleted_at is not None:
        return
    row.deleted_at = now()
    deletion_log.append(kind="file", key=row.storage_path)
    for fc in db.query(FeatureCacheRow).filter(FeatureCacheRow.audio_id == row.id).all():
        deletion_log.append(kind="feature_cache", key=f"{fc.audio_id}:{fc.kind}:{fc.algorithm_version}")
    db.flush()


# ---------------- 特征读取（按需计算 + 缓存） ----------------

def _load_or_compute(db: Session, row: AudioRow, kind: str, compute) -> dict:
    cached = (
        db.query(FeatureCacheRow)
        .filter(FeatureCacheRow.audio_id == row.id, FeatureCacheRow.kind == kind,
                FeatureCacheRow.algorithm_version == analysis.ALGORITHM_VERSION)
        .one_or_none()
    )
    if cached is not None:
        payload = JSONText.load(cached.payload, {})
        # 图片缓存存的是文件路径；文件被清理则重算
        if kind not in ("formants_png", "spectrogram_png") \
                or (config.DATA_DIR / payload.get("path", "?")).exists():
            return payload
    payload = compute()
    db.add(FeatureCacheRow(audio_id=row.id, kind=kind,
                           algorithm_version=analysis.ALGORITHM_VERSION,
                           payload=JSONText.dump(payload), created_at=now()))
    db.commit()
    return payload


def get_f0(db: Session, row: AudioRow) -> dict:
    def compute() -> dict:
        res = analysis.extract_f0(audio_path(row))
        return {
            "algorithmVersion": analysis.ALGORITHM_VERSION,
            "hopMs": int(analysis.F0_HOP_MS),
            "frames": res.frames,
            "voicedRanges": res.voiced_ranges,
            "voicedRatio": round(res.voiced_ratio, 3),
        }

    return _load_or_compute(db, row, "f0", compute)


def get_formants(db: Session, row: AudioRow) -> dict:
    def compute() -> dict:
        res = analysis.extract_formants(audio_path(row))
        return {
            "algorithmVersion": analysis.ALGORITHM_VERSION,
            "frames": res.frames,
            "vowelSegments": res.vowel_segments,
        }

    return _load_or_compute(db, row, "formants", compute)


def get_formants_png(db: Session, row: AudioRow) -> Path:
    if row.purpose != "recording":
        # 标定音频算完即删，不提供图片
        raise ApiError(404, "NOT_FOUND", "资源不存在")

    def compute() -> dict:
        data = get_formants(db, row)
        return {"path": str(_render_formants_png(row.id, data).relative_to(config.DATA_DIR))}

    payload = _load_or_compute(db, row, "formants_png", compute)
    return config.DATA_DIR / payload["path"]


def get_spectrogram_png(db: Session, row: AudioRow) -> Path:
    if row.purpose != "recording":
        raise ApiError(404, "NOT_FOUND", "资源不存在")

    def compute() -> dict:
        return {"path": str(_render_spectrogram_png(row.id, audio_path(row)).relative_to(config.DATA_DIR))}

    payload = _load_or_compute(db, row, "spectrogram_png", compute)
    return config.DATA_DIR / payload["path"]


def _matplotlib_png():
    """Agg 后端 + CJK 字体回退链（默认 DejaVu Sans 无中文字形，标题会变方框）。"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "WenQuanYi Micro Hei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def _render_formants_png(audio_id: str, formants: dict) -> Path:
    """F2(反向 x)–F1(y) 元音散点图。"""
    plt = _matplotlib_png()

    xs, ys = [], []
    for fr in formants.get("frames", []):
        if "f1" in fr and "f2" in fr:
            xs.append(fr["f2"])
            ys.append(fr["f1"])
    fig, ax = plt.subplots(figsize=(5, 4), dpi=110)
    if xs:
        ax.scatter(xs, ys, s=8, alpha=0.35, c="#3b82f6")
    ax.set_xlim(3200, 400)
    ax.set_ylim(1200, 0)
    ax.set_xlabel("F2 (Hz)")
    ax.set_ylabel("F1 (Hz)")
    ax.set_title("共振峰分布")
    out_dir = config.PRIVATE_DIR / "features"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{audio_id}_formants.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def _render_spectrogram_png(audio_id: str, wav_path: Path) -> Path:
    """Praat Spectrogram 热力图（时间 × 频率，Praat 式 50dB 动态范围）。"""
    plt = _matplotlib_png()

    sg = analysis.compute_spectrogram(wav_path)
    vmax = float(sg.values_db.max()) if sg.values_db.size else 0.0
    fig, ax = plt.subplots(figsize=(6, 3), dpi=110)
    im = ax.imshow(sg.values_db, origin="lower", aspect="auto", cmap="inferno",
                   extent=[sg.tmin, sg.tmax, 0.0, sg.fmax],
                   vmin=vmax - analysis.SPECTRO_DYNAMIC_RANGE_DB, vmax=vmax)
    fig.colorbar(im, ax=ax, label="dB")
    ax.set_xlabel("时间 (s)")
    ax.set_ylabel("频率 (Hz)")
    ax.set_title("频谱图")
    out_dir = config.PRIVATE_DIR / "features"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{audio_id}_spectrogram.png"
    fig.savefig(out)
    plt.close(fig)
    return out
