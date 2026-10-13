# -*- coding: utf-8 -*-
"""Wav2Vec2 模型加载、音频预处理与推理。"""
from __future__ import annotations

import itertools
import os
import threading
import time
from pathlib import Path

import numpy as np
import torch
from scipy.signal import resample_poly

from .audio.decoding import decode_audio

# 国内网络优先走 hf-mirror;已设环境变量 HF_ENDPOINT 时不被覆盖
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

DEFAULT_MODEL_ID = "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn"
# 本地模型目录: 存在则优先本地加载(满足离线演示,不依赖网络)
LOCAL_MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "wav2vec2-large-xlsr-53-chinese-zh-cn"
SAMPLE_RATE = 16000
MIN_DURATION_S = 0.3     # 有效语音不足 0.3s 判漏读
SILENCE_RMS = 1e-3       # 全段 RMS 低于此值判静音(漏读);按实测静音样本 0.0005 与正常录音 ≥0.005 标定

torch.set_num_threads(min(8, os.cpu_count() or 4))


def load_audio(path: str) -> tuple[np.ndarray, dict]:
    """读音频 → 重采样 16k/单声道 → 掐静音 → 归一化。返回 (float32 波形, 统计)。"""
    decoded = decode_audio(path)
    data, sr = decoded.samples, decoded.sample_rate
    rms = float(np.sqrt(np.mean(data ** 2) + 1e-12))
    if sr != SAMPLE_RATE:
        data = resample_poly(data, SAMPLE_RATE, sr).astype(np.float32)
    trimmed = trim_silence(data)
    peak = float(np.max(np.abs(trimmed))) if trimmed.size else 0.0
    if peak > 0:
        trimmed = trimmed / peak * 0.95
    stats = {
        "path": str(path), "orig_sr": sr,
        "orig_duration_s": round(len(data) / SAMPLE_RATE, 3),
        "duration_s": round(len(trimmed) / SAMPLE_RATE, 3),
        "rms": rms,
    }
    return trimmed.astype(np.float32), stats


def trim_silence(x: np.ndarray, top_db: int = 28, pad_ms: int = 150) -> np.ndarray:
    """能量法掐头尾静音(10ms 帧,加平滑与前后保护)。全静音返回空数组。"""
    frame = int(0.01 * SAMPLE_RATE)
    n = len(x) // frame
    if n < 2:
        return x
    rms = np.array([np.sqrt(np.mean(x[i * frame:(i + 1) * frame] ** 2) + 1e-12) for i in range(n)])
    # 阈值 = 相对本段峰值 -top_db dB(不能写成绝对 10**(-top_db/20),手机录音整体偏小会被全掐掉)
    thresh = max(float(rms.max()) * 10 ** (-top_db / 20), 1e-5)
    idx = np.where(rms > thresh)[0]
    if idx.size == 0:
        return x[:0]
    pad = max(1, int(pad_ms / 10))
    a, b = max(0, idx[0] - pad), min(n - 1, idx[-1] + pad)
    return x[a * frame:(b + 1) * frame]


def softmax(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    keys = list(scores.keys())
    vals = np.array([scores[k] for k in keys], dtype=np.float64)
    vals -= vals.max()
    e = np.exp(vals)
    return {k: float(v) for k, v in zip(keys, e / e.sum())}


class AudioAnalyzer:
    """管理 Wav2Vec2 模型、加载锁与推理统计。"""

    def __init__(self):
        self._lock = threading.Lock()
        self.model = None
        self.processor = None
        self.model_id: str | None = None
        self.model_source: str | None = None   # local / hf
        self.device: str | None = None
        self.load_ms: float | None = None
        self.loaded_at: float | None = None
        self.last_error: str | None = None
        self.lib_versions: dict = {}
        self.n_calls = 0
        self.total_infer_ms = 0.0
        self.n_failures = 0

    # ------------------------------------------------------------------ 加载
    def load(self, model_id: str = DEFAULT_MODEL_ID, force: bool = False) -> dict:
        """依次从本地目录、缓存和远程仓库加载模型。"""
        with self._lock:
            if not force and self.model is not None and self.model_id == model_id:
                return {"ok": True, "model_id": self.model_id, "device": self.device,
                        "load_ms": self.load_ms, "cached": True}
            t0 = time.perf_counter()
            # 候选加载源: (source, 是否离线, 来源标签)
            sources = []
            if model_id == DEFAULT_MODEL_ID and LOCAL_MODEL_DIR.is_dir():
                sources.append((str(LOCAL_MODEL_DIR), True, "local"))
            sources.append((model_id, True, "hf-cache"))
            sources.append((model_id, False, "hf"))
            prev_env = os.environ.get("HF_HUB_OFFLINE")
            try:
                from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
                import transformers
                last_err = None
                for source, offline, label in sources:
                    os.environ["HF_HUB_OFFLINE"] = "1" if offline else "0"
                    try:
                        self.processor = Wav2Vec2Processor.from_pretrained(source)
                        self.model = Wav2Vec2ForCTC.from_pretrained(source)
                        last_err = None
                        break
                    except Exception as e:  # 逐级降级
                        last_err = e
                        self.model = self.processor = None
                if last_err is not None:
                    raise last_err
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                self.model.to(self.device).eval()
                self.model_id = model_id
                self.model_source = label
                self.load_ms = round((time.perf_counter() - t0) * 1000, 1)
                self.loaded_at = time.time()
                self.last_error = None
                self.lib_versions = {"torch": torch.__version__,
                                     "transformers": transformers.__version__}
                return {"ok": True, "model_id": model_id, "device": self.device,
                        "load_ms": self.load_ms, "cached": False,
                        "model_source": self.model_source}
            except Exception as e:  # 失败降级:保留错误,API 可重试
                self.last_error = f"{type(e).__name__}: {e}"
                self.n_failures += 1
                return {"ok": False, "error": self.last_error}
            finally:
                if prev_env is None:
                    os.environ.pop("HF_HUB_OFFLINE", None)
                else:
                    os.environ["HF_HUB_OFFLINE"] = prev_env

    def ensure_loaded(self, model_id: str = DEFAULT_MODEL_ID) -> str:
        """懒加载:首次诊断/识别调用时自动加载。"""
        if self.model is None or self.model_id != model_id:
            r = self.load(model_id)
            if not r["ok"]:
                raise RuntimeError(f"模型加载失败: {r['error']}")
        return self.model_id

    def status(self) -> dict:
        return {
            "model_id": self.model_id, "model_source": self.model_source,
            "loaded": self.model is not None,
            "device": self.device, "load_ms": self.load_ms, "loaded_at": self.loaded_at,
            "last_error": self.last_error, "lib_versions": self.lib_versions,
            "n_calls": self.n_calls,
            "avg_infer_ms": round(self.total_infer_ms / self.n_calls, 1) if self.n_calls else None,
            "n_failures": self.n_failures,
            "ready_for_demo": self.model is not None and self.last_error is None,
        }

    # ------------------------------------------------------------------ 推理
    def _forward(self, audio_path: str) -> tuple[torch.Tensor | None, dict]:
        """前向一次,返回 (CPU logits (T,V), 音频统计)。静音/过短返回 (None, stats)。"""
        x, stats = load_audio(audio_path)
        if x.size / SAMPLE_RATE < MIN_DURATION_S or stats["rms"] < SILENCE_RMS:
            return None, stats
        with torch.no_grad():
            t0 = time.perf_counter()
            iv = torch.from_numpy(x).unsqueeze(0).to(self.device)
            logits = self.model(iv).logits[0].detach().cpu().float()
            stats["forward_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        self.n_calls += 1
        self.total_infer_ms += stats["forward_ms"]
        return logits, stats

    def ctc_greedy_text(self, logits: torch.Tensor) -> str:
        """CTC 贪心解码文本(去重复、去 blank)。"""
        ids = logits.argmax(dim=-1).tolist()
        blank = self.processor.tokenizer.pad_token_id
        collapsed = [i for i, _g in itertools.groupby(ids) if i != blank]
        return self.processor.batch_decode([collapsed])[0].strip() if collapsed else ""

    def token_scores(self, logits: torch.Tensor, tokens: list[str]) -> dict[str, float]:
        """CTC 帧级打分:score(token) = logsumexp_t logsoftmax[t, id]。

        单音节发音中,正确字的 token 在多数帧上概率高 → 得分高。
        """
        vocab = self.processor.tokenizer.get_vocab()
        logp = torch.log_softmax(logits, dim=-1)
        scores = {}
        for tok in tokens:
            tid = vocab.get(tok)
            if tid is None:
                continue
            scores[tok] = float(torch.logsumexp(logp[:, tid], dim=0))
        return scores

    def open_candidates(self, logits: torch.Tensor, per_frame_k: int = 3,
                        max_tokens: int = 40) -> list[str]:
        """开集候选:每帧 top-k 中出现过的汉字(不依赖词典,用于发现误读)。"""
        vocab = self.processor.tokenizer.get_vocab()
        id2tok = {i: t for t, i in vocab.items()}
        top = torch.log_softmax(logits, dim=-1).topk(per_frame_k, dim=-1)
        seen: dict[str, float] = {}
        for t in range(logits.shape[0]):
            for k in range(per_frame_k):
                tok = id2tok.get(int(top.indices[t, k]), "")
                if len(tok) == 1 and "一" <= tok <= "鿿":
                    seen[tok] = max(seen.get(tok, -1e9), float(top.values[t, k]))
        return [t for t, _ in sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:max_tokens]]

    def analyze_with_deep_learning(self, audio_path: str) -> dict:
        """识别音频，返回文本、候选字、候选概率和处理耗时。"""
        self.ensure_loaded()
        logits, stats = self._forward(audio_path)
        if logits is None:
            return {"ok": False, "reason": "silent_or_too_short", "text": "",
                    "candidates": [], "confidence": 0.0, "elapsed_ms": 0.0, "audio": stats}
        text = self.ctc_greedy_text(logits)
        chars = self.open_candidates(logits)
        scores = self.token_scores(logits, chars)
        probs = softmax(scores)
        from .pinyin_utils import char_pinyin
        ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
        cands = [{"char": c, "pinyin": char_pinyin(c), "prob": round(p, 4),
                  "score": round(scores.get(c, 0.0), 3)} for c, p in ranked[:10]]
        return {"ok": True, "text": text, "candidates": cands,
                "confidence": round(ranked[0][1], 4) if ranked else 0.0,
                "elapsed_ms": stats.get("forward_ms"), "audio": stats}


_ANALYZER: AudioAnalyzer | None = None


def get_analyzer() -> AudioAnalyzer:
    global _ANALYZER
    if _ANALYZER is None:
        _ANALYZER = AudioAnalyzer()
    return _ANALYZER
