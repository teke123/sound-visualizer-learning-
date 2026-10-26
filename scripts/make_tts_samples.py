# -*- coding: utf-8 -*-
"""用微软 Edge TTS(edge-tts,官方免费接口,标准普通话)合成诊断评测样本。

用途: 人工录音无法自证"读得对不对",改用标准 TTS 合成音作为标准读音基准,
      并用合成错误样本验证 误读/漏读/声调错位 诊断能力。
      声母关呼读音(bō/dē/fō/rī 等无同音常用汉字)直接"音标朗读"——
      edge-tts 对拼音串有专门处理(读 bō 即发"玻"音),比借汉字更准。

用法:
  python scripts/make_tts_samples.py            # 全部生成
  python scripts/make_tts_samples.py --only L30 # 只生成指定关卡(如 L30_ma1)
输出:
  audio/tts_raw/  30 关标准读音 + L30 四声专项(妈/麻/马/骂)
  audio/tts_err/  合成错误样本(误读·声母/韵母、平翘舌、声调、多音节、静音)

音色 zh-CN-XiaoxiaoNeural(微软标准普通话女声),语速 -10%(单字发音更清晰)。
edge-tts 输出 mp3 → ffmpeg 转 16k 单声道 wav。
"""
import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import imageio_ffmpeg
import edge_tts
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RAW_DIR = ROOT / "audio" / "tts_raw"
ERR_DIR = ROOT / "audio" / "tts_err"
VOICE = "zh-CN-XiaoxiaoNeural"
RATE = "-10%"
SR = 16000

# 每关读什么(对照 30 关冻结表;选读音唯一的汉字)
LEVEL_CHAR = {
    "L01": "啊", "L02": "哦", "L03": "婀", "L04": "一", "L05": "乌", "L06": "迂",
    "L30": "妈",
}
# 声母关呼读音(bō/dē/fō/rī 等)没有同音常用汉字,直接读 levels.py 的目标拼音(音标朗读)
PY_LEVELS = ("L07", "L08", "L09", "L10", "L11", "L12", "L13", "L14", "L15", "L16",
             "L17", "L18", "L19", "L20", "L21", "L22", "L23", "L24", "L25", "L26",
             "L27", "L28", "L29")
# L30 四声专项(验证声调闭环)
L30_TONES = {"L30_ma1": "妈", "L30_ma2": "麻", "L30_ma3": "马", "L30_ma4": "骂"}
# 错误样本: 文件名 → (读什么, 目标关卡, 验证的诊断项)
ERR_SAMPLES = {
    "L07_as_p": ("坡", "L07", "误读·声母(b→p)"),
    "L07_as_ba": ("八", "L07", "误读·韵母(bō→bā)"),
    "L21_as_z": ("资", "L21", "误读·声母(zh→z 平翘舌)"),
    "L30_tone3": ("马", "L30", "声调错位定位(实测报告三声)"),
    "L30_tone4": ("骂", "L30", "声调错位定位(实测报告四声)"),
    "L30_extra": ("妈妈", "L30", "多音节(多读)"),
}


async def _synth(text: str, out_mp3: str) -> None:
    c = edge_tts.Communicate(text, voice=VOICE, rate=RATE)
    await c.save(out_mp3)


def _to_wav(mp3: str, wav: str) -> None:
    """mp3 → 16k 单声道 wav(用项目自带的 imageio-ffmpeg)。"""
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", mp3,
                        "-ar", "16000", "-ac", "1", "-f", "wav", wav],
                       capture_output=True)
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", errors="replace")[-200:]
        raise RuntimeError(f"ffmpeg 转码失败: {err}")


def _make_silence(wav: str, seconds: float = 1.5) -> None:
    """纯静音 wav(漏读样本)。"""
    sf.write(wav, np.zeros(int(SR * seconds), dtype=np.float32), SR)


async def main() -> int:
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ERR_DIR.mkdir(parents=True, exist_ok=True)

    from backend.levels import LEVELS_BY_ID

    jobs: list[tuple[str, str, Path]] = []   # (要合成文本, 文件名, 输出目录)
    for lid, ch in LEVEL_CHAR.items():
        if only and not lid.startswith(only):
            continue
        jobs.append((ch, f"{lid}_{ch}.wav", RAW_DIR))
    for lid in PY_LEVELS:
        if only and not lid.startswith(only):
            continue
        py = LEVELS_BY_ID[lid].target_pinyin
        jobs.append((py, f"{lid}_{py}.wav", RAW_DIR))
    for name, ch in L30_TONES.items():
        if only and not name.startswith(only):
            continue
        jobs.append((ch, f"{name}.wav", RAW_DIR))
    for name, (ch, _lid, _what) in ERR_SAMPLES.items():
        if only and not name.startswith(only):
            continue
        jobs.append((ch, f"{name}.wav", ERR_DIR))

    n_ok = 0
    for text, fname, out_dir in jobs:
        wav = out_dir / fname
        if wav.exists() and not only:
            print(f"跳过(已存在): {wav.name}")
            continue
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()   # Windows 下必须关闭句柄,ffmpeg 才能读、之后才能删
        try:
            await _synth(text, tmp.name)
            _to_wav(tmp.name, str(wav))
            n_ok += 1
            print(f"生成: {wav.name}  ← 读「{text}」")
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    # 漏读样本: 纯静音
    sil = ERR_DIR / "L30_silence.wav"
    if (not only or only.startswith("L30")) and not sil.exists():
        _make_silence(str(sil))
        print(f"生成: {sil.name}  ← 1.5s 静音(漏读)")
    print(f"完成: 合成 {n_ok} 条 → {RAW_DIR.name} / {ERR_DIR.name}")
    print("下一步: python scripts/batch_eval.py")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
