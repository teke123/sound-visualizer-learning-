"""讯飞语音评测（WebSocket open-ise）适配器。

实现按公开文档口径编写，属于 M0「实现期验证」项：维度字段、音节时间戳、
声母代表音节评测形式、p95 时延、留存条款均须用真实凭据验证后才能作为
「可评判」依据；未配置凭据时不启用。

鉴权：HMAC-SHA256 签名拼接鉴权 URL；音频以 base64 帧分片上行；
结果 XML 中的 syllable/phone/tone 检错映射到 ProviderResult。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import datetime
import urllib.parse
import xml.etree.ElementTree as ET

from app import config
from app.scoring.provider import ProviderError, ProviderResult, ScoringProvider, SyllableEval


def _auth_url() -> str:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    signature_origin = f"host: ise.api.xfyun.cn\ndate: {ts}\nGET /v2/open-ise HTTP/1.1"
    signature = base64.b64encode(hmac.new(
        config.XFYUN_API_SECRET.encode(), signature_origin.encode(), hashlib.sha256).digest()).decode()
    auth = base64.b64encode((
        f'api_key="{config.XFYUN_API_KEY}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    ).encode()).decode()
    return (f"{config.XFYUN_WS_URL}?authorization={urllib.parse.quote(auth)}"
            f"&date={urllib.parse.quote(ts)}&host=ise.api.xfyun.cn")


def _parse_xml_result(xml_text: str) -> ProviderResult:
    """解析评测 XML（read_syllable/rec_paper 读音候选树）。

    字段口径以实测为准（M0 待验证项）；以下解析按公开示例文档实现，
    无法解析时抛 bad_response。
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ProviderError("bad_response", f"评测结果 XML 解析失败: {e}") from e

    result = ProviderResult(provider_version=config.PROVIDER_VERSION)
    rec = root.find(".//read_syllable")
    if rec is None:
        # 回退：rec_paper 总分
        paper = root.find(".//rec_paper")
        total = paper.get("read_score") if paper is not None else None
        if total is None:
            raise ProviderError("bad_response", "评测结果缺少分数节点")
        result.overall_score = round(float(total), 1)
        return result

    total = rec.get("read_score")
    result.overall_score = round(float(total), 1) if total else 0.0
    result.initial_score = float(rec["initial_score"]) if rec.get("initial_score") else None
    result.final_score = float(rec["final_score"]) if rec.get("final_score") else None
    result.tone_score = float(rec["tone_score"]) if rec.get("tone_score") else None

    for syl in root.findall(".//syllable"):
        text = syl.get("content") or syl.get("word") or "?"
        t0 = float(syl.get("bg", "0")) / 1000.0 if syl.get("bg") else 0.0
        t1 = float(syl.get("ed", "0")) / 1000.0 if syl.get("ed") else 0.0
        symbol = syl.get("symbol", "")
        tone_value = None
        for ch in symbol:
            if ch.isdigit():
                tone_value = int(ch)
                break
        # 讯飞 dp_message：0 正确；[16,24] 之间为声母/韵母/声调类检错；其它异常
        dp = int(syl.get("dp_message", "0"))
        result.syllables.append(SyllableEval(
            text=text, t0=t0, t1=t1, tone_value=tone_value,
            initial_ok=dp == 0 or (syl.get("initial_dp_message", "0") == "0"),
            final_ok=dp == 0 or (syl.get("final_dp_message", "0") == "0"),
            tone_ok=dp == 0 or (syl.get("tone_dp_message", "0") == "0"),
            detail={"dpMessage": dp},
        ))
    missing = [e.get("content", "?") for e in root.findall(".//omitted")]
    extra = [e.get("content", "?") for e in root.findall(".//transcendent")]
    repeated = [e.get("content", "?") for e in root.findall(".//repeated")]
    if root.find(".//is_chaos") is not None or root.get("is_reject") == "1":
        result.reading["disordered"] = True
    result.reading["missing"] = missing
    result.reading["extra"] = extra
    result.reading["repeated"] = repeated
    return result


class XfyunProvider(ScoringProvider):
    name = "xfyun"
    version = "xfyun-ise-1.0"

    def evaluate(self, wav_path: str, evaluation_text: str) -> ProviderResult:
        if not (config.XFYUN_APP_ID and config.XFYUN_API_KEY and config.XFYUN_API_SECRET):
            raise ProviderError("down", "讯飞评测凭据未配置（XFYUN_APP_ID/API_KEY/API_SECRET）")
        raise ProviderError(
            "bad_response",
            "讯飞适配器待 M0 实测验证后启用；当前请使用 SVS_PROVIDER=mock",
        )
