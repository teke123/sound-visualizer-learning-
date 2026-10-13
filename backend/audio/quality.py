"""根据音量、噪声估计、截幅、时长和静音比例评估录音质量。"""
import numpy as np
import librosa

FRAME_LENGTH = 2048
HOP_LENGTH = 512

def analyze_audio_quality(y: np.ndarray, sr: int) -> dict:
    """计算五项质量指标，返回 pass / warn / fail 状态和总体结论。"""
    eps = 1e-8
    rms = librosa.feature.rms(y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)[0]
    rms = rms[rms > eps]
    duration = len(y) / sr

    items: list[dict] = []

    # 1. 音量（平均 RMS → dBFS）
    avg_db = 20 * np.log10(rms.mean() + eps) if len(rms) else -120
    if -30 <= avg_db <= -6:
        vol_status, vol_msg = "pass", f"音量适中（{avg_db:.0f}dBFS）"
    elif -45 <= avg_db < -30 or -6 < avg_db <= -2:
        vol_status, vol_msg = "warn", f"音量偏低（{avg_db:.0f}dBFS），建议靠近麦克风" if avg_db < -30 else f"音量偏高（{avg_db:.0f}dBFS），建议稍离远一些"
    else:
        vol_level = "低" if avg_db < -45 else "高"
        vol_status, vol_msg = "fail", f"音量过{vol_level}（{avg_db:.0f}dBFS），请调整距离后重录"
    items.append({"name": "音量", "key": "volume", "status": vol_status, "message": vol_msg})

    # 2. 噪声（SNR 估计：高能量帧均值 / 低能量帧均值）
    if len(rms) >= 10:
        sorted_rms = np.sort(rms)
        high = sorted_rms[-max(1, len(sorted_rms) // 10):].mean()
        low = sorted_rms[:max(1, len(sorted_rms) // 3)].mean()
        snr_db = 20 * np.log10((high + eps) / (low + eps))
    else:
        snr_db = 0.0
    if snr_db >= 15:
        noise_status, noise_msg = "pass", f"环境噪声低（SNR≈{snr_db:.0f}dB）"
    elif snr_db >= 8:
        noise_status, noise_msg = "warn", f"存在背景噪声（SNR≈{snr_db:.0f}dB），建议在安静环境录制"
    else:
        noise_status, noise_msg = "fail", f"背景噪声过大（SNR≈{snr_db:.0f}dB），请到安静环境重录"
    items.append({"name": "噪声", "key": "noise", "status": noise_status, "message": noise_msg})

    # 3. 截幅（峰值接近满幅的比例）
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    clip_ratio = float(np.mean(np.abs(y) > 0.99)) if len(y) else 0.0
    if clip_ratio < 0.001:
        clip_status, clip_msg = "pass", f"无截幅（峰值{peak:.2f}）"
    elif clip_ratio < 0.01:
        clip_status, clip_msg = "warn", f"接近截幅（峰值{peak:.2f}），音量已到临界"
    else:
        clip_status, clip_msg = "fail", "声音截幅（爆音），请远离麦克风或降低音量后重录"
    items.append({"name": "截幅", "key": "clipping", "status": clip_status, "message": clip_msg})

    # 4. 时长（有效时长 0.8~10s）
    if 0.8 <= duration <= 10:
        dur_status, dur_msg = "pass", f"时长合适（{duration:.1f}秒）"
    elif 0.4 <= duration < 0.8 or 10 < duration <= 15:
        dur_level = "短" if duration < 0.8 else "长"
        dur_status, dur_msg = "warn", f"时长偏{dur_level}（{duration:.1f}秒）"
    else:
        dur_status, dur_msg = "fail", f"时长达不到要求（{duration:.1f}秒），请完整朗读后重录"
    items.append({"name": "时长", "key": "duration", "status": dur_status, "message": dur_msg})

    # 5. 静音比（能量低于阈值的帧占比）
    silence_ratio = float(np.mean(rms < 0.01)) if len(rms) else 1.0
    if silence_ratio < 0.4:
        sil_status, sil_msg = "pass", f"有效发声占比高（静音比{silence_ratio:.0%}）"
    elif silence_ratio < 0.7:
        sil_status, sil_msg = "warn", f"静音偏多（静音比{silence_ratio:.0%}），请连贯朗读"
    else:
        sil_status, sil_msg = "fail", "有效语音过少（多为静音），请对着麦克风清晰朗读后重录"
    items.append({"name": "静音比", "key": "silence", "status": sil_status, "message": sil_msg})

    # 总体结论
    statuses = [i["status"] for i in items]
    if "fail" in statuses:
        passed, score, summary = False, 40, "录音质量不达标，请按提示调整后重录"
    elif "warn" in statuses:
        passed, score, summary = True, 75, "录音可用，但存在可改进项，建议重录以获得更准结果"
    else:
        passed, score, summary = True, 100, "录音质量良好，可以正常分析"
    return {
        "passed": passed,
        "score": score,
        "summary": summary,
        "items": items,
    }

