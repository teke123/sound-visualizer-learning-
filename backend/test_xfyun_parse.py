"""讯飞评测 XML 解析离线测试（无凭据、不发网络请求）。

- 文档示例：从官方 API 文档的返回示例中提取 base64 XML（文档文件不在则跳过）；
- 检错路径：手工构造 read_syllable XML 覆盖漏读/增读(fil)/乱读/调型错误；
- 试题文本：纯文本分隔与拼音标注（interphonic）两种格式。
"""
from __future__ import annotations

import base64
import re
import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from app.scoring.provider import ProviderError  # noqa: E402
from app.scoring.provider_xfyun import (  # noqa: E402
    _apply_expected_tones, _read_pcm, _result_from_parsed, build_exam_text, parse_full)

DOC = Path(__file__).resolve().parents[2] / "文档" / "讯飞语音API文档.md"


def _doc_example_xml() -> str | None:
    if not DOC.exists():
        return None
    text = DOC.read_text(encoding="utf-8")
    m = re.search(r'"data":\s*"([A-Za-z0-9+/=]{500,})"', text)
    return base64.b64decode(m.group(1)).decode("utf-8") if m else None


@pytest.mark.skipif(_doc_example_xml() is None, reason="官方文档示例不可用")
def test_parse_doc_example() -> None:
    parsed = parse_full(_doc_example_xml())

    paper = parsed["paper"]
    assert paper["tag"] == "read_sentence"
    assert paper["scores"]["total_score"] == pytest.approx(92.51)
    assert paper["scores"]["phone_score"] == pytest.approx(100.0)
    assert paper["scores"]["tone_score"] == pytest.approx(100.0)
    assert paper["scores"]["accuracy_score"] == pytest.approx(100.0)
    assert paper["scores"]["fluency_score"] == pytest.approx(87.62)
    assert paper["scores"]["integrity_score"] == pytest.approx(100.0)
    assert paper["scores"]["emotion_score"] == pytest.approx(87.32)
    assert paper["isRejected"] is False

    # 今天天气怎么样 = 7 字；首个 word「今」带 1 个 fil 填充，尾部有 sil 静音词
    assert len(parsed["words"]) == 7
    assert parsed["words"][0]["content"] == "今"
    assert parsed["words"][0]["symbol"] == "jin1"
    assert len(parsed["fillers"]) == 1
    assert parsed["fillers"][0]["recNodeType"] == "fil"
    assert len(parsed["silences"]) == 1

    result = _result_from_parsed(parsed)
    assert result.overall_score == pytest.approx(92.5)
    assert result.tone_score == pytest.approx(100.0)
    assert len(result.scores) >= 6
    assert len(result.syllables) == 7
    s0 = result.syllables[0]
    assert s0.text == "今" and s0.pinyin == "jin1"
    assert s0.t0 == pytest.approx(0.01) and s0.t1 == pytest.approx(0.22)
    assert s0.tone_value == 1
    assert s0.initial_ok and s0.final_ok and s0.tone_ok
    # symbol 调号是识别调型：示例里「气」实际被读成轻声 qi9
    assert result.syllables[3].tone_value == 9
    assert result.syllables[6].tone_value == 4    # 样 yang4
    # fil 是引擎插入的填充，良好朗读也会出现 → 不计入增读检错
    assert result.reading["missing"] == [] and result.reading["extra"] == []
    assert result.reading["disordered"] is False
    # 时间戳单调不减
    t0s = [s.t0 for s in result.syllables]
    assert t0s == sorted(t0s)

    # 期望声调回填：识别 qi9 → 期望 4，识别值保留在 detail
    _apply_expected_tones(result, "今天天气怎么样", None)
    assert result.syllables[3].tone_value == 4
    assert result.syllables[3].detail["recognizedTone"] == 9


ERROR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<xml_result>
  <read_syllable lang="cn" tte="utf-8" version="7,0,0,1024">
    <rec_paper>
      <read_syllable content="妈，麻" is_rejected="true" except_info="1"
                     total_score="0.000000" phone_score="0.000000" tone_score="0.000000">
        <word beg_pos="0" content="妈" end_pos="22" symbol="ma1" time_len="22">
          <syll beg_pos="0" content="妈" dp_message="16" end_pos="22"
                rec_node_type="paper" symbol="ma1" time_len="22"/>
          <syll beg_pos="0" content="ma1" dp_message="32" end_pos="5"
                rec_node_type="fil" time_len="5"/>
        </word>
        <word beg_pos="22" content="麻" end_pos="45" symbol="ma2" time_len="23">
          <syll beg_pos="22" content="麻" dp_message="0" end_pos="45"
                rec_node_type="paper" symbol="ma2" time_len="23">
            <phone beg_pos="22" content="m" dp_message="0" end_pos="26" is_yun="0"
                   perr_msg="0" rec_node_type="paper" time_len="4"/>
            <phone beg_pos="26" content="a" dp_message="0" end_pos="45" is_yun="1"
                   mono_tone="TONE2" perr_msg="2" perr_level_msg="1"
                   rec_node_type="paper" time_len="19"/>
          </syll>
        </word>
        <word beg_pos="45" content="sil" end_pos="60" symbol="" time_len="15">
          <syll beg_pos="45" content="sil" dp_message="0" end_pos="60"
                rec_node_type="sil" time_len="15"/>
        </word>
      </read_syllable>
    </rec_paper>
  </read_syllable>
</xml_result>
"""


def test_parse_error_paths() -> None:
    parsed = parse_full(ERROR_XML)
    reading = parsed["reading"]
    assert reading["missing"] == ["妈"]          # dp_message=16 漏读
    assert reading["extra"] == []                # fil/sil 填充不计增读
    assert reading["disordered"] is True         # is_rejected=true 乱读
    assert reading["exceptInfo"] == "1"

    result = _result_from_parsed(parsed)
    assert result.overall_score == pytest.approx(0.0)
    assert len(result.syllables) == 2            # sil 词节点被排除
    s0, s1 = result.syllables
    assert not (s0.initial_ok and s0.final_ok and s0.tone_ok)   # 漏读 → 全错
    assert s1.initial_ok and s1.final_ok and not s1.tone_ok     # perr_msg=2 仅调型错
    assert s1.tone_value == 2
    assert s1.detail["phones"][1]["perrMsgName"] == "tone_error"


# 2026-10-15 真实接口返回（read_syllable + interphonic「那 na4」，sid=ise000deab9…）
REAL_SYLLABLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
  <xml_result>
      <read_syllable lan="cn" type="study" version="7,0,0,1024">
          <rec_paper>
              <read_syllable beg_pos="0" content="那。" end_pos="79" except_info="0"
                             fluency_score="0.000000" integrity_score="0.000000"
                             phone_score="100.000000" time_len="79"
                             tone_score="100.000000" total_score="100.000000">
                  <sentence beg_pos="0" content="那" end_pos="79" time_len="79">
                      <word beg_pos="0" content="那" end_pos="79" symbol="na4" time_len="79">
                          <syll beg_pos="0" content="silv" dp_message="0" end_pos="15"
                                rec_node_type="silv" time_len="15">
                              <phone beg_pos="0" content="silv" dp_message="0" end_pos="15"
                                     rec_node_type="silv" time_len="15"></phone>
                          </syll>
                          <syll beg_pos="15" content="那" dp_message="0" end_pos="50"
                                rec_node_type="paper" symbol="na4" time_len="35">
                              <phone beg_pos="15" content="n" dp_message="0" end_pos="28"
                                     is_yun="0" perr_level_msg="0" perr_msg="0"
                                     rec_node_type="paper" time_len="13"></phone>
                              <phone beg_pos="28" content="a" dp_message="0" end_pos="50"
                                     is_yun="1" mono_tone="TONE4" perr_level_msg="0"
                                     perr_msg="0" rec_node_type="paper" time_len="22"></phone>
                          </syll>
                          <syll beg_pos="50" content="silv" dp_message="0" end_pos="79"
                                rec_node_type="silv" time_len="29">
                              <phone beg_pos="50" content="silv" dp_message="0" end_pos="79"
                                     rec_node_type="silv" time_len="29"></phone>
                          </syll>
                      </word>
                  </sentence>
              </read_syllable>
          </rec_paper>
      </read_syllable>
  </xml_result>
"""


def test_parse_real_single_syllable() -> None:
    parsed = parse_full(REAL_SYLLABLE_XML)
    assert parsed["paper"]["tag"] == "read_syllable"
    assert len(parsed["words"]) == 1
    assert parsed["words"][0]["content"] == "那"
    assert len(parsed["silences"]) == 2         # 字内前后 silv 静音段

    result = _result_from_parsed(parsed)
    assert result.overall_score == pytest.approx(100.0)
    assert result.scores["phone_score"] == pytest.approx(100.0)
    assert result.scores["fluency_score"] == pytest.approx(0.0)   # 单字题型不适用，原样保留
    assert len(result.syllables) == 1
    s = result.syllables[0]
    assert s.text == "那" and s.pinyin == "na4"
    assert s.t0 == pytest.approx(0.15) and s.t1 == pytest.approx(0.50)
    assert s.tone_value == 4
    assert s.initial_ok and s.final_ok and s.tone_ok
    assert result.reading["disordered"] is False


def test_build_exam_text() -> None:
    assert build_exam_text("妈麻马骂", None, "read_syllable") == "妈，麻，马，骂"
    assert build_exam_text("妈麻马骂", None, "read_word") == "妈，麻，马，骂"
    assert build_exam_text("今天天气怎么样", None, "read_sentence") == "今天天气怎么样"
    assert build_exam_text("来蓝", "lai4|lan2", "read_syllable") == (
        "<customizer: interphonic>\n来\nlai4\n蓝\nlan2")
    assert build_exam_text("来蓝", "lai4 lan2") == (
        "<customizer: interphonic>\n来\nlai4\n蓝\nlan2")
    with pytest.raises(ProviderError):
        build_exam_text("来蓝", "lai4")


def test_read_pcm_format_guard(tmp_path: Path) -> None:
    bad = tmp_path / "bad.wav"
    with wave.open(str(bad), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)          # 非 16k
        w.writeframes(b"\x00" * 1600)
    with pytest.raises(ProviderError) as ei:
        _read_pcm(str(bad))
    assert ei.value.kind == "bad_response"
