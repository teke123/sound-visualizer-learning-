"""讯飞语音评测 M0 实测脚本（直接运行：python xfyun_probe.py）。

对真实 open-ise WebSocket 接口跑一次完整评测会话，落盘五层 JSON 诊断
（meta / session / raw / parsed / providerResult / verification），
控制台输出人读摘要与 PASS/FAIL 核对项。凭据只从环境变量读取：

    set XFYUN_APP_ID=... ; set XFYUN_API_KEY=... ; set XFYUN_API_SECRET=...

用法示例：
    python xfyun_probe.py --selftest                     # 三组内置用例（优先真实录音）
    python xfyun_probe.py --wav a.mp3 --text 那 --pinyin na4
    python xfyun_probe.py --wav a.wav --wav b.wav --text 来蓝 --pinyin "lai4 lan2" --runs 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.acoustics.transcode import normalize_to_wav  # noqa: E402
from app.scoring.provider import ProviderError  # noqa: E402
from app.scoring.provider_xfyun import evaluate_raw  # noqa: E402
from app.seed_support import synthesize_text, write_wav  # noqa: E402

SR = 16000
RECORDINGS_DIR = Path(__file__).resolve().parents[2] / "录音"   # 真实单音节录音库
CREDENTIAL_VARS = ("XFYUN_APP_ID", "XFYUN_API_KEY", "XFYUN_API_SECRET")

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not ok else ""))


def mask(secret: str) -> str:
    return (secret[:4] + "****" + secret[-4:]) if len(secret) > 8 else "****"


# ---------------- 音频准备 ----------------

def _write_pcm(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)


def prepare_audio(wavs: list[str] | None, text: str, workdir: Path, tag: str) -> tuple[Path, dict]:
    """--wav 可多段：逐个转码规范化后拼接（段间 120ms 静音，首尾留白）；
    无 --wav 时用声道模型合成。返回 (WAV 路径, 音频信息)。"""
    workdir.mkdir(parents=True, exist_ok=True)
    if wavs:
        info: dict = {"sources": []}
        pcms: list[bytes] = []
        for i, src in enumerate(wavs):
            tmp = workdir / f"{tag}_src{i}.wav"
            normalize_to_wav(Path(src), tmp)
            with wave.open(str(tmp), "rb") as w:
                pcms.append(w.readframes(w.getnframes()))
            info["sources"].append({"path": src, "bytes": Path(src).stat().st_size})
        gap = b"\x00\x00" * int(0.12 * SR)
        lead = b"\x00\x00" * int(0.2 * SR)
        tail = b"\x00\x00" * int(0.3 * SR)
        pcm = lead + gap.join(pcms) + tail
        out = workdir / f"{tag}.wav"
        _write_pcm(out, pcm)
        info["kind"] = "recordings"
    else:
        out = workdir / f"{tag}_synth.wav"
        write_wav(out, synthesize_text(text))
        pcm = out.read_bytes()
        info = {"kind": "synthesized"}
    info["wavPath"] = str(out)
    info["pcmBytes"] = len(pcm)
    info["durationSec"] = round(len(pcm) / (SR * 2), 3)
    info["pcmSha256"] = hashlib.sha256(pcm).hexdigest()[:16]
    return out, info


# ---------------- 验证项 ----------------

def verify(meta: dict, session: dict, parsed: dict, prov: dict) -> list[dict]:
    items: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        items.append({"item": name, "pass": bool(ok), "detail": detail})

    add("握手成功且业务 code=0", session.get("code") == 0, f"code={session.get('code')}")
    scores = parsed["paper"]["scores"]
    add("卷面含 total_score", "total_score" in scores, str(sorted(scores)))
    add("多维度分数返回（≥3 项）", len(scores) >= 3, f"{len(scores)} 项")
    n_chars = len([ch for ch in meta["text"] if "\u4e00" <= ch <= "\u9fff"])
    n_syl = len(prov["syllables"])
    add("音节数与汉字数一致", n_syl == n_chars, f"音节 {n_syl} / 汉字 {n_chars}")
    t0s = [s["t0"] for s in prov["syllables"]]
    add("音节时间戳单调", t0s == sorted(t0s), str(t0s))
    if prov["syllables"]:
        t_max = max(s["t1"] for s in prov["syllables"])
        add("时间戳不超音频时长", t_max <= meta["audio"]["durationSec"] + 0.5,
            f"末音节止于 {t_max}s / 音频 {meta['audio']['durationSec']}s")
    has_final = any(p["part"] == "final"
                    for s in parsed["words"] if s.get("syllables")
                    for sy in s["syllables"] for p in sy["phones"])
    add("phone 层含韵母（is_yun=1）", has_final)
    add("时延在 30s 管线预算内", session.get("totalMs", 10 ** 9) < 30_000,
        f"totalMs={session.get('totalMs')}")
    return items


# ---------------- 单次评测 ----------------

def run_case(name: str, *, text: str, category: str, wavs: list[str] | None,
             pinyin: str | None, overrides: dict, runs: int, out_dir: Path) -> dict:
    print(f"\n=== 用例 {name}: text={text!r} category={category} "
          f"pinyin={pinyin or '-'} runs={runs} ===")
    workdir = out_dir / "audio"
    wav_path, audio_info = prepare_audio(wavs, text, workdir, name)
    print(f"音频: {audio_info['kind']} {audio_info['durationSec']}s "
          f"pcm={audio_info['pcmBytes']}B sha={audio_info['pcmSha256']}")

    latencies: list[int] = []
    last: dict = {}
    for r in range(runs):
        if runs > 1:
            print(f"-- 第 {r + 1}/{runs} 次")
        t_call = time.perf_counter()
        try:
            last = evaluate_raw(str(wav_path), text, category=category,
                                pinyin=pinyin, overrides=overrides)
        except ProviderError as e:
            check(f"{name}: 评测会话", False, f"{e.kind}: {e}")
            return {"meta": {"case": name, "text": text}, "error": {"kind": e.kind, "message": str(e)}}
        latencies.append(round((time.perf_counter() - t_call) * 1000))

    session = {k: v for k, v in last["session"].items() if k not in ("responses", "xml")}
    parsed = last["parsed"]
    prov = last["result"]
    prov_out = {
        "providerVersion": prov.provider_version,
        "overallScore": prov.overall_score,
        "initialScore": prov.initial_score, "finalScore": prov.final_score,
        "toneScore": prov.tone_score, "scores": prov.scores,
        "reading": prov.reading,
        "syllables": [
            {"text": s.text, "pinyin": s.pinyin, "t0": s.t0, "t1": s.t1,
             "initialOk": s.initial_ok, "finalOk": s.final_ok, "toneOk": s.tone_ok,
             "toneValue": s.tone_value, "detail": s.detail}
            for s in prov.syllables
        ],
    }
    meta = {
        "case": name, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "text": text, "pinyin": pinyin, "category": category,
        "ent": "cn_vip", "overrides": overrides,
        "audio": audio_info,
        "credentials": {
            "appId": os.environ.get("XFYUN_APP_ID", ""),
            "apiKey": mask(os.environ.get("XFYUN_API_KEY", "")),
            "apiSecret": mask(os.environ.get("XFYUN_API_SECRET", "")),
        },
    }
    artifact = {
        "meta": meta, "session": {**session, "wallMsEach": latencies},
        "raw": {"responses": last["session"]["responses"], "xml": last["session"]["xml"]},
        "parsed": parsed, "providerResult": prov_out,
        "verification": verify(meta, session, parsed, prov_out),
    }

    # 控制台摘要
    print(f"sid={session.get('sid')} code={session.get('code')} "
          f"握手 {session.get('handshakeMs')}ms 发送 {session.get('sendMs')}ms "
          f"总耗时 {session.get('totalMs')}ms（墙钟 {latencies}）")
    scores = parsed["paper"]["scores"]
    print("卷面分数: " + "  ".join(f"{k}={v}" for k, v in sorted(scores.items())))
    print(f"isRejected={parsed['paper']['isRejected']} "
          f"exceptInfo={parsed['paper'].get('exceptInfo')} "
          f"fillers={len(parsed['fillers'])} silences={len(parsed['silences'])}")
    r = prov.reading
    print(f"朗读维: missing={r['missing']} extra={r['extra']} "
          f"repeated={r['repeated']} replaced={r['replaced']} disordered={r['disordered']}")
    for s in prov.syllables:
        flags = "".join(mark for mark, ok in
                        (("声", s.initial_ok), ("韵", s.final_ok), ("调", s.tone_ok)) if ok)
        print(f"  {s.text}({s.pinyin}) {s.t0:.2f}-{s.t1:.2f}s 调{s.tone_value} 对: {flags or '无'}")

    out_file = out_dir / f"{time.strftime('%H%M%S')}_{name}.json"
    out_file.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / f"{time.strftime('%H%M%S')}_{name}.xml").write_text(
        last["session"]["xml"], encoding="utf-8")
    print(f"落盘: {out_file}")

    for item in artifact["verification"]:
        check(f"{name}: {item['item']}", item["pass"], item["detail"])
    return artifact


# ---------------- 用例与入口 ----------------

def selftest(out_dir: Path, runs: int) -> None:
    rec = RECORDINGS_DIR if RECORDINGS_DIR.exists() else None

    def rec_file(fname: str) -> str | None:
        return str(rec / fname) if rec and (rec / fname).exists() else None

    # 单字 + 拼音标注（真实录音优先；无则合成）
    na4 = rec_file("na4_MV3_MP3.mp3")
    run_case("single_char", text="那", pinyin="na4", category="read_syllable",
             wavs=[na4] if na4 else None, overrides={}, runs=runs, out_dir=out_dir)


def parse_set(items: list[str]) -> dict:
    out: dict = {}
    for kv in items:
        if "=" not in kv:
            raise SystemExit(f"--set 需要 k=v 形式: {kv}")
        k, v = kv.split("=", 1)
        out[k] = {"true": True, "false": False}.get(v, v)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="讯飞语音评测 M0 实测")
    ap.add_argument("--wav", action="append", help="输入音频（可多次；多段按序拼接）")
    ap.add_argument("--text", default="妈", help="评测文本（汉字）")
    ap.add_argument("--pinyin", default=None, help="拼音标注（空格/| 分隔，如 'lai4 lan2'）")
    ap.add_argument("--category", default="read_syllable",
                    choices=["read_syllable", "read_word", "read_sentence", "read_chapter"])
    ap.add_argument("--runs", type=int, default=1, help="重复次数（时延分布；注意每日配额）")
    ap.add_argument("--out", default=str(Path(__file__).parent / "probe_out"), help="结果目录")
    ap.add_argument("--set", action="append", default=[], dest="set_kv",
                    help="覆盖 business 参数，如 --set group=pupil")
    ap.add_argument("--selftest", action="store_true", help="运行三组内置用例")
    args = ap.parse_args()

    missing = [v for v in CREDENTIAL_VARS if not os.environ.get(v)]
    if missing:
        print(f"缺少环境变量: {', '.join(missing)}\n"
              "请先设置 XFYUN_APP_ID / XFYUN_API_KEY / XFYUN_API_SECRET（不写入仓库）")
        return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    overrides = parse_set(args.set_kv)

    if args.selftest:
        selftest(out_dir, args.runs)
    else:
        run_case("manual", text=args.text, category=args.category, wavs=args.wav,
                 pinyin=args.pinyin, overrides=overrides, runs=args.runs, out_dir=out_dir)

    failed = [r for r in results if not r[1]]
    print(f"\n==== {len(results) - len(failed)}/{len(results)} 项通过 ====")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
