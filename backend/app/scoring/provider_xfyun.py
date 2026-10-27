"""讯飞语音评测（流式版 WebSocket open-ise）适配器。

鉴权：HMAC-SHA256 签名拼接鉴权 URL；音频去 WAV 头后按 1280B/帧 base64 上行。
返回 XML（rec_paper → sentence → word → syll → phone）解析映射到 ProviderResult：

- 卷面 total_score → overall_score；phone/tone/accuracy/fluency/integrity/emotion
  等全部 *_score 原样进 scores（诊断用）；
- word[paper] → syllables[]，时间戳 beg_pos/end_pos 为 10ms 帧，÷100 得秒；
- phone 层 is_yun 区分声母/韵母，perr_msg 判声母/韵母/声调错误；
- dp_message 16/32/64/128 → 漏读/增读/回读/替换；rec_node_type=fil → 增读；
  is_rejected=true → 乱读（乱说乱读得高分拒识）。

实测口径与字段核对记录见 docs/research/10-讯飞语音评测M0实测记录.md。
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import re
import time
import urllib.parse
import wave
import xml.etree.ElementTree as ET

from app import config
from app.scoring.provider import ProviderError, ProviderResult, ScoringProvider, SyllableEval

_FRAME_BYTES = 1280        # 16k/16bit 单声道 40ms 一帧（文档建议，勿超 19200B）
_POSITION_UNIT_MS = 10     # beg_pos/end_pos 单位：10ms 帧
_SEND_BUDGET_SEC = 12.0    # 音频发送预算，余下留给结果返回（管线硬截止 30s）
# 引擎忙/会话超时类错误码 → down（PROVIDER_DOWN，可重试）
_RETRYABLE_CODES = {10114, 10800}

_DP_NAMES = {0: "normal", 16: "missing", 32: "extra", 64: "repeated", 128: "replaced"}


def _auth_url() -> str:
    parsed = urllib.parse.urlparse(config.XFYUN_WS_URL)
    host = parsed.hostname or "ise-api.xfyun.cn"
    path = parsed.path or "/v2/open-ise"
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    signature_origin = f"host: {host}\ndate: {ts}\nGET {path} HTTP/1.1"
    signature = base64.b64encode(hmac.new(
        config.XFYUN_API_SECRET.encode(), signature_origin.encode(), hashlib.sha256).digest()).decode()
    auth = base64.b64encode((
        f'api_key="{config.XFYUN_API_KEY}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    ).encode()).decode()
    return (f"{config.XFYUN_WS_URL}?authorization={urllib.parse.quote(auth)}"
            f"&date={urllib.parse.quote(ts)}&host={host}")


# ---------------- 试题文本 ----------------

def build_exam_text(evaluation_text: str, pinyin: str | None = None,
                    category: str | None = None) -> str:
    """评测文本 → 讯飞试题格式。

    给 pinyin（如 "lai4|lan2"）时用拼音标注（interphonic）格式，声调以标注为准；
    多字 read_syllable/read_word 用「，」分隔；句篇题型原样。
    """
    chars = [ch for ch in evaluation_text if "\u4e00" <= ch <= "\u9fff"]
    if pinyin:
        pys = [p for p in re.split(r"[|，,\s]+", pinyin.strip()) if p]
        if len(pys) != len(chars):
            raise ProviderError(
                "bad_response", f"拼音标注数（{len(pys)}）与汉字数（{len(chars)}）不一致")
        lines = ["<customizer: interphonic>"]
        for ch, py in zip(chars, pys):
            lines += [ch, py]
        return "\n".join(lines)
    if (category or config.XFYUN_CATEGORY) in ("read_syllable", "read_word"):
        return "，".join(chars)
    return evaluation_text


def _read_pcm(wav_path: str) -> bytes:
    try:
        with wave.open(wav_path, "rb") as w:
            spec = (w.getnchannels(), w.getsampwidth(), w.getframerate())
            if spec != (1, 2, 16000):
                raise ProviderError(
                    "bad_response",
                    f"音频须为 16k/16bit/单声道 WAV，实际 {spec[2]}Hz/{spec[1] * 8}bit/"
                    f"{spec[0]}ch: {wav_path}")
            return w.readframes(w.getnframes())
    except ProviderError:
        raise
    except (wave.Error, OSError) as e:
        raise ProviderError("bad_response", f"读取 WAV 失败: {e}") from e


# ---------------- WebSocket 会话 ----------------

def run_session(pcm: bytes, exam_text: str, *, category: str | None = None,
                overrides: dict | None = None) -> dict:
    """一次完整评测会话：握手 → ssb 参数帧 → 音频分片 → 收包至 status=2。

    返回诊断 dict（responses/sid/各阶段耗时/解码后 XML）；业务失败抛 ProviderError。
    overrides 覆盖 business 参数（探针脚本对比参数用）。

    WebSocket 用 websocket-client 库（讯飞官方 Python SDK 同款）：实测
    websockets 库的握手在该网关被直接断连（HTTP 头完全一致也复现），见
    docs/research/10-讯飞语音评测M0实测记录.md。
    """
    import ssl
    import websocket as ws_client
    from websocket import WebSocketBadStatusException, WebSocketTimeoutException, WebSocketException

    if not (config.XFYUN_APP_ID and config.XFYUN_API_KEY and config.XFYUN_API_SECRET):
        raise ProviderError("down", "讯飞评测凭据未配置（XFYUN_APP_ID/API_KEY/API_SECRET）")

    business: dict = {
        "sub": "ise", "ent": "cn_vip",
        "category": category or config.XFYUN_CATEGORY,
        "cmd": "ssb", "aus": 1,
        "aue": "raw", "auf": "audio/L16;rate=16000",
        "text": "\ufeff" + exam_text,       # 试题文本须带 utf-8 BOM
        "tte": "utf-8", "ttp_skip": True,
        "rstcd": "utf8", "rst": "entirety", "ise_unite": "1",
        "extra_ability": "multi_dimension;syll_phone_err_msg",   # 中文百分制推荐组合
        "group": "adult",
    }
    if overrides:
        business.update(overrides)

    frames = [pcm[i:i + _FRAME_BYTES] for i in range(0, len(pcm), _FRAME_BYTES)]
    if not frames:
        raise ProviderError("bad_response", "音频数据为空")
    interval = min(0.04, _SEND_BUDGET_SEC / len(frames))

    diag: dict = {"responses": [], "sid": None, "code": None, "message": None,
                  "framesSent": len(frames), "audioBytes": len(pcm),
                  "handshakeMs": 0, "sendMs": 0, "firstResultMs": 0, "totalMs": 0}
    t0 = time.perf_counter()
    try:
        ws = ws_client.create_connection(
            _auth_url(), timeout=10, sslopt={"cert_reqs": ssl.CERT_NONE})
        try:
            diag["handshakeMs"] = round((time.perf_counter() - t0) * 1000)
            ws.send(json.dumps({
                "common": {"app_id": config.XFYUN_APP_ID},
                "business": business,
                "data": {"status": 0},
            }))
            t_send = time.perf_counter()
            for i, chunk in enumerate(frames):
                last = i == len(frames) - 1
                ws.send(json.dumps({
                    "business": {"cmd": "auw", "aus": 4 if last else (1 if i == 0 else 2)},
                    "data": {"status": 2 if last else 1,
                             "data": base64.b64encode(chunk).decode()},
                }))
                if not last:
                    time.sleep(interval)
            diag["sendMs"] = round((time.perf_counter() - t_send) * 1000)

            deadline = t0 + config.XFYUN_TIMEOUT_SEC
            xml_b64: str | None = None
            while True:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    raise ProviderError("timeout", f"讯飞评测超时（>{config.XFYUN_TIMEOUT_SEC}s）")
                ws.settimeout(max(1.0, remaining))
                try:
                    raw = ws.recv()
                except WebSocketTimeoutException as e:
                    raise ProviderError("timeout", "等待评测结果超时") from e
                if not diag["firstResultMs"]:
                    diag["firstResultMs"] = round((time.perf_counter() - t0) * 1000)
                resp = json.loads(raw)
                diag["responses"].append(resp)
                diag["sid"] = resp.get("sid") or diag["sid"]
                diag["code"], diag["message"] = resp.get("code"), resp.get("message", "")
                if resp.get("code") != 0:
                    kind = "down" if resp.get("code") in _RETRYABLE_CODES else "bad_response"
                    raise ProviderError(
                        kind, f"讯飞返回 code={resp.get('code')}: {resp.get('message')}"
                              f"（sid={diag['sid']}）")
                data = resp.get("data") or {}
                if data.get("status") == 2:
                    xml_b64 = data.get("data")
                    break
            diag["totalMs"] = round((time.perf_counter() - t0) * 1000)
            if not xml_b64:
                raise ProviderError("bad_response", "会话结束但未返回评测结果")
            diag["xml"] = base64.b64decode(xml_b64).decode("utf-8")
            return diag
        finally:
            try:
                ws.close()      # 正常关闭码 1000（文档建议）
            except Exception:
                pass
    except ProviderError:
        raise
    except WebSocketBadStatusException as e:
        raise ProviderError("down", f"讯飞握手失败 HTTP {e.status_code}"
                              "（检查凭据/服务器时钟/IP 白名单）") from e
    except (WebSocketException, OSError, ConnectionError, ssl.SSLError) as e:
        raise ProviderError("down", f"讯飞连接异常: {e}") from e


def evaluate_raw(wav_path: str, evaluation_text: str, *, category: str | None = None,
                 pinyin: str | None = None, overrides: dict | None = None) -> dict:
    """评测入口（Provider 与探针脚本共用）：返回 {session, parsed, result}。"""
    exam = build_exam_text(evaluation_text, pinyin, category)
    pcm = _read_pcm(wav_path)
    diag = run_session(pcm, exam, category=category, overrides=overrides)
    parsed = parse_full(diag["xml"])
    result = _result_from_parsed(parsed)
    _apply_expected_tones(result, evaluation_text, pinyin)
    result.raw["xml"] = diag["xml"]
    result.raw["sid"] = diag["sid"]
    result.raw["examText"] = exam
    return {"session": diag, "parsed": parsed, "result": result}


# ---------------- XML 解析 ----------------

def _f(attr: str | None) -> float | None:
    try:
        return float(attr) if attr not in ("", None) else None
    except ValueError:
        return None


def _i(attr: str | None, default: int = 0) -> int:
    try:
        return int(attr) if attr not in ("", None) else default
    except ValueError:
        return default


def _dp_name(dp: int) -> str:
    return _DP_NAMES.get(dp, f"unknown({dp})")


def _perr_name(is_yun: int | None, perr: int | None) -> str:
    if perr is None:
        return "n/a"
    if is_yun == 0:
        return {0: "initial_ok", 1: "initial_error"}.get(perr, f"unknown({perr})")
    return {0: "ok", 1: "final_error", 2: "tone_error", 3: "final_tone_error"}.get(
        perr, f"unknown({perr})")


def _tone_from_symbol(symbol: str | None) -> int | None:
    for ch in reversed(symbol or ""):
        if ch.isdigit():
            return int(ch)
    return None


def _paper_node(root: ET.Element) -> ET.Element | None:
    rec = root.find(".//rec_paper")
    if rec is not None:
        for child in rec:
            return child
    for child in root:
        if child.tag.startswith("read_"):
            return child
    return None


def parse_full(xml_text: str) -> dict:
    """评测 XML → 全字段结构化 dict（探针脚本全量输出用）。

    结构：paper（卷面属性+全部分数）/ sentences / words[ syllables[ phones ] ] /
    fillers（rec_node_type=fil 增读）/ reading（检错汇总）。未知属性不丢。
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ProviderError("bad_response", f"评测结果 XML 解析失败: {e}") from e
    paper = _paper_node(root)
    if paper is None:
        raise ProviderError("bad_response", "评测结果缺少卷面节点（rec_paper/read_*）")

    paper_out: dict = {
        "tag": paper.tag,
        "content": paper.get("content"),
        "isRejected": (paper.get("is_rejected") or "").lower() in ("true", "1"),
        "exceptInfo": paper.get("except_info", "0"),
        "timeLen": _f(paper.get("time_len")),
        "rootAttrs": dict(root.attrib) if root.tag != paper.tag else {},
        "attrs": {k: v for k, v in paper.attrib.items()},
        "scores": {},
    }
    for k, v in paper.attrib.items():
        if k.endswith("_score") and _f(v) is not None:
            paper_out["scores"][k] = round(_f(v), 2)   # type: ignore[arg-type]

    sentences = []
    for sent in paper.findall(".//sentence"):
        sentences.append({
            "content": sent.get("content"),
            "begPos": _f(sent.get("beg_pos")), "endPos": _f(sent.get("end_pos")),
            "scores": {k: round(_f(v), 2) for k, v in sent.attrib.items()
                       if k.endswith("_score") and _f(v) is not None},
            "attrs": dict(sent.attrib),
        })

    words: list[dict] = []
    fillers: list[dict] = []     # rec_node_type=fil：引擎插入的填充/噪声，不计入增读检错
    silences: list[dict] = []    # rec_node_type=sil/silv：静音段（仅诊断）

    def parse_phone(ph: ET.Element) -> dict:
        is_yun = _i(ph.get("is_yun"), -1) if ph.get("is_yun") is not None else None
        perr = _i(ph.get("perr_msg"), -1) if ph.get("perr_msg") is not None else None
        return {
            "content": ph.get("content"),
            "begPos": _f(ph.get("beg_pos")), "endPos": _f(ph.get("end_pos")),
            "timeLen": _f(ph.get("time_len")),
            "dpMessage": _i(ph.get("dp_message")), "dpMessageName": _dp_name(_i(ph.get("dp_message"))),
            "isYun": is_yun,
            "part": "initial" if is_yun == 0 else ("final" if is_yun == 1 else None),
            "perrMsg": perr, "perrMsgName": _perr_name(is_yun, perr),
            "perrLevelMsg": _i(ph.get("perr_level_msg")) if ph.get("perr_level_msg") else None,
            "monoTone": ph.get("mono_tone"),
            "attrs": dict(ph.attrib),
        }

    def parse_syll(syl: ET.Element) -> dict:
        out = {
            "content": syl.get("content"),
            "symbol": syl.get("symbol"),
            "begPos": _f(syl.get("beg_pos")), "endPos": _f(syl.get("end_pos")),
            "timeLen": _f(syl.get("time_len")),
            "dpMessage": _i(syl.get("dp_message")), "dpMessageName": _dp_name(_i(syl.get("dp_message"))),
            "recNodeType": syl.get("rec_node_type"),
            "toneValue": _tone_from_symbol(syl.get("symbol")),
            "phones": [parse_phone(p) for p in syl.findall("phone")],
        }
        out["initialOk"], out["finalOk"], out["toneOk"] = _syll_flags(out)
        return out

    word_nodes = paper.findall(".//word")
    for w in word_nodes:
        sylls = [parse_syll(s) for s in w.findall("syll")]
        for s in sylls:
            if s["recNodeType"] == "fil":
                fillers.append(s)
            elif s["recNodeType"] in ("sil", "silv"):
                silences.append(s)
        paper_sylls = [s for s in sylls if s["recNodeType"] not in ("fil", "sil", "silv")]
        if not paper_sylls and (w.get("content") or "").lower() in ("sil", "silv", "fil"):
            continue          # 纯静音/填充词节点：不进入期望音节序列
        out = {
            "content": w.get("content"),
            "symbol": w.get("symbol"),
            "begPos": _f(w.get("beg_pos")), "endPos": _f(w.get("end_pos")),
            "timeLen": _f(w.get("time_len")),
            "dpMessage": _i(w.get("dp_message")), "dpMessageName": _dp_name(_i(w.get("dp_message"))),
            "totalScore": _f(w.get("total_score")),
            "toneValue": _tone_from_symbol(w.get("symbol")),
            "syllables": paper_sylls,
        }
        out["initialOk"], out["finalOk"], out["toneOk"] = _word_flags(out)
        words.append(out)
    if not word_nodes:
        # 兜底：音节直接挂在卷面节点下（无 word 层的返回形态）
        for s in paper.findall(".//syll"):
            parsed_syl = parse_syll(s)
            if parsed_syl["recNodeType"] == "fil":
                fillers.append(parsed_syl)
            elif parsed_syl["recNodeType"] in ("sil", "silv"):
                silences.append(parsed_syl)
            else:
                words.append(parsed_syl)

    reading = _reading_from(words, paper_out)
    return {"paper": paper_out, "sentences": sentences, "words": words,
            "fillers": fillers, "silences": silences, "reading": reading}


def _syll_flags(syl: dict) -> tuple[bool, bool, bool]:
    """音节级判定：dp_message 非 0（漏/增/回/替）全错；否则按 phone 层
    is_yun/perr_msg 合成（声母 1=错；韵母 1 韵错、2 调错、3 均错）。"""
    initial_ok = final_ok = tone_ok = True
    if syl["dpMessage"] != 0:
        return False, False, False
    for p in syl["phones"]:
        if p["dpMessage"] != 0:
            initial_ok = final_ok = tone_ok = False
        if p["isYun"] == 0 and p["perrMsg"] not in (0, None):
            initial_ok = False
        if p["isYun"] == 1:
            if p["perrMsg"] in (1, 3):
                final_ok = False
            if p["perrMsg"] in (2, 3):
                tone_ok = False
    return initial_ok, final_ok, tone_ok


def _word_flags(word: dict) -> tuple[bool, bool, bool]:
    """词层判定：词 dp 非 0 全错；否则合成其 paper 音节。"""
    if word["dpMessage"] != 0:
        return False, False, False
    sylls = word["syllables"]
    if not sylls:
        return True, True, True
    return (all(s["initialOk"] for s in sylls),
            all(s["finalOk"] for s in sylls),
            all(s["toneOk"] for s in sylls))


def _reading_from(words: list[dict], paper: dict) -> dict:
    """检错汇总：dp_message 16/32/64/128 → 漏读/增读/回读/替换；
    is_rejected → 乱读。fil/sil 节点是引擎插入的填充与静音，良好朗读也会
    出现（文档示例即有 fil），不计入增读，只留诊断。"""
    reading = {"missing": [], "extra": [], "repeated": [], "replaced": [],
               "disordered": paper["isRejected"], "exceptInfo": paper["exceptInfo"]}

    def add(node: dict) -> None:
        dp, text = node["dpMessage"], node.get("content") or "?"
        if dp == 16:
            reading["missing"].append(text)
        elif dp == 32:
            reading["extra"].append(text)
        elif dp == 64:
            reading["repeated"].append(text)
        elif dp == 128:
            reading["replaced"].append(text)

    for w in words:
        add(w)
        for s in w["syllables"]:
            add(s)
    return reading


def _result_from_parsed(parsed: dict) -> ProviderResult:
    """结构化结果 → ProviderResult（管线消费口径）。"""
    result = ProviderResult(provider_version=config.PROVIDER_VERSION)
    paper = parsed["paper"]
    result.scores = dict(paper["scores"])
    total = paper["scores"].get("total_score")
    result.overall_score = round(float(total), 1) if total is not None else 0.0
    # 声母/韵母分项由规则层按音节三项判定通过率推导（讯飞只有合并的声韵分）

    result.reading = {k: parsed["reading"].get(k, v) for k, v in result.reading.items()}
    result.reading["disordered"] = bool(parsed["reading"]["disordered"])

    for w in parsed["words"]:
        sylls = w.get("syllables")
        if sylls is None:      # 无 word 层时 words 里装的已是音节
            sylls = [w]
        if len(sylls) <= 1:
            syl = sylls[0] if sylls else {}
            beg = syl.get("begPos", w.get("begPos"))
            end = syl.get("endPos", w.get("endPos"))
            result.syllables.append(SyllableEval(
                text=w.get("content") or "?",
                pinyin=w.get("symbol") or syl.get("symbol"),
                t0=round((beg or 0) * _POSITION_UNIT_MS / 1000, 3),
                t1=round((end or 0) * _POSITION_UNIT_MS / 1000, 3),
                initial_ok=w["initialOk"], final_ok=w["finalOk"], tone_ok=w["toneOk"],
                tone_value=w.get("toneValue") if w.get("toneValue") is not None else syl.get("toneValue"),
                detail={"dpMessage": w["dpMessage"], "dpMessageName": w["dpMessageName"],
                        "phones": [
                            {k: p[k] for k in
                             ("content", "part", "perrMsg", "perrMsgName", "perrLevelMsg", "monoTone")}
                            for p in syl.get("phones", [])
                        ]},
            ))
        else:                   # 词语/句子题型：一个 word 多音节，按音节逐个映射
            for syl in sylls:
                result.syllables.append(SyllableEval(
                    text=syl.get("content") or w.get("content") or "?",
                    pinyin=syl.get("symbol") or w.get("symbol"),
                    t0=round((syl.get("begPos") or 0) * _POSITION_UNIT_MS / 1000, 3),
                    t1=round((syl.get("endPos") or 0) * _POSITION_UNIT_MS / 1000, 3),
                    initial_ok=syl["initialOk"], final_ok=syl["finalOk"], tone_ok=syl["toneOk"],
                    tone_value=syl.get("toneValue"),
                    detail={"dpMessage": syl["dpMessage"], "dpMessageName": syl["dpMessageName"],
                            "phones": [
                                {k: p[k] for k in
                                 ("content", "part", "perrMsg", "perrMsgName", "perrLevelMsg", "monoTone")}
                                for p in syl.get("phones", [])
                            ]},
                ))
    return result


def _apply_expected_tones(result: ProviderResult, evaluation_text: str,
                          pinyin: str | None) -> None:
    """期望声调回填：引擎 symbol 调号是识别调型（良好朗读也可能实际读成
    轻声，如 qi9），声调形状分析需要的是期望声调——以拼音标注为唯一来源
    （无标注不做回填，保留识别值）。音节数与标注数一致时才覆盖，错位
    （增读等）保持原值；识别调型与期望不同时另存 detail.recognizedTone。"""
    if not pinyin:
        return
    pys = [p for p in re.split(r"[|，,\s]+", pinyin.strip()) if p]
    tones = [_tone_from_symbol(p) for p in pys]
    if len(tones) != len(result.syllables):
        return
    for syl, tone in zip(result.syllables, tones):
        if syl.tone_value is not None and syl.tone_value != tone:
            syl.detail = {"recognizedTone": syl.tone_value, **syl.detail}
        if tone:
            syl.tone_value = tone


class XfyunProvider(ScoringProvider):
    name = "xfyun"
    version = "xfyun-ise-1.0"

    def evaluate(self, wav_path: str, evaluation_text: str,
                 pinyin: str | None = None) -> ProviderResult:
        return evaluate_raw(wav_path, evaluation_text, pinyin=pinyin)["result"]
