# -*- coding: utf-8 -*-
"""app.llm 自测脚本。

用法（在 backend/ 目录下）::

    python tools/test_llm_client.py                # 只跑离线用例
    python tools/test_llm_client.py --live         # 离线 + 真实调用（profile=local）
    python tools/test_llm_client.py --live --profile vision
    python tools/test_llm_client.py --live --profile default --text "用一句话介绍声谱图"

离线用例不联网、不需要 Key，验证配置解析 / Base64 编码 / schema 规范化 / JSON 解析容错。
实时用例会真的打一次模型，验证纯文本、流式、结构化三条链路。
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm import config as llm_config  # noqa: E402
from app.llm import (  # noqa: E402
    LLMConfigError,
    LLMError,
    LLMMediaError,
    LLMSchemaError,
    audio_part,
    chat,
    chat_json,
    chat_stream,
    image_part,
    is_available,
    reset_env_cache,
    resolve,
)
from app.llm.schema import (  # noqa: E402
    build_hint,
    make_response_format,
    normalize_schema,
    parse_json,
    validate,
)

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
_records: list[tuple[str, str, str]] = []


def record(name: str, status: str, detail: str = "") -> None:
    _records.append((name, status, detail))
    mark = {PASS: "[PASS]", FAIL: "[FAIL]", SKIP: "[SKIP]"}[status]
    line = f"{mark} {name}"
    if detail:
        line += f"  — {detail}"
    print(line)


def case(name: str):
    """装饰器：跑一个用例，异常即 FAIL。"""

    def wrap(fn):
        try:
            detail = fn() or ""
            record(name, PASS, str(detail))
        except AssertionError as exc:
            record(name, FAIL, str(exc) or "断言失败")
        except Exception as exc:  # noqa: BLE001
            record(name, FAIL, f"{type(exc).__name__}: {exc}")
        return fn

    return wrap


@contextlib.contextmanager
def _clean_env(env_file: Path | None = None):
    """隔离真实的 backend/.env 与宿主环境变量，造一个干净的配置环境。"""
    saved_env = dict(os.environ)
    saved_file = llm_config.ENV_FILE
    for key in [k for k in os.environ if k.startswith("LLM_")]:
        del os.environ[key]
    llm_config.ENV_FILE = env_file if env_file is not None else Path("<isolated>/.env")
    reset_env_cache()
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved_env)
        llm_config.ENV_FILE = saved_file
        reset_env_cache()


def _make_samples(tmp: Path) -> tuple[Path, Path]:
    """造一张 png 和一段 wav，用于离线编码测试。"""
    png = tmp / "spec.png"
    try:
        from PIL import Image

        Image.new("RGB", (64, 32), (12, 34, 56)).save(png, format="PNG")
    except ImportError:  # 没有 PIL 就手写 1x1 png
        png.write_bytes(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d494844520000000100000001080600000"
                "01f15c4890000000a49444154789c6360000002000100ffff0300000600"
                "0557bfabd40000000049454e44ae426082"
            )
        )

    wav = tmp / "a.wav"
    with wave.open(str(wav), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(16000)
        fh.writeframes(b"\x00\x00" * 1600)  # 0.1s 静音
    return png, wav


def run_offline(tmp: Path) -> None:
    print("\n=== 离线用例 ===")
    png, wav = _make_samples(tmp)
    bad = tmp / "a.flac"
    bad.write_bytes(b"fLaC" + b"\x00" * 64)

    @case("配置：profile 缺项回退到 default")
    def _t1():
        with _clean_env():
            os.environ["LLM_DEFAULT_BASE_URL"] = "http://127.0.0.1:11434/v1"
            os.environ["LLM_DEFAULT_API_KEY"] = "sk-default-key"
            os.environ["LLM_DEFAULT_MODEL"] = "default-model"
            os.environ["LLM_VISION_MODEL"] = "vision-model"
            cfg = resolve("vision")
            assert cfg.base_url == "http://127.0.0.1:11434/v1", cfg.base_url
            assert cfg.api_key == "sk-default-key", "API Key 未回退"
            assert cfg.model == "vision-model", cfg.model
            return "base_url/api_key 回退 default，model 用 profile 自己的"

    @case("配置：显式传参优先级最高")
    def _t2():
        with _clean_env():
            os.environ["LLM_DEFAULT_BASE_URL"] = "http://127.0.0.1:11434/v1"
            os.environ["LLM_DEFAULT_API_KEY"] = "x"
            os.environ["LLM_DEFAULT_MODEL"] = "m1"
            cfg = resolve("default", model="m2", temperature=0.1)
            assert cfg.model == "m2" and cfg.temperature == 0.1
            return "model=m2, temperature=0.1 生效"

    @case("配置：远程地址缺 Key 报 LLMConfigError")
    def _t3():
        with _clean_env():
            os.environ["LLM_DEFAULT_BASE_URL"] = "https://api.example.com/v1"
            os.environ["LLM_DEFAULT_MODEL"] = "m"
            try:
                resolve("default")
            except LLMConfigError as exc:
                assert "API_KEY" in str(exc), str(exc)
                return "提示了应配置的环境变量名"
            raise AssertionError("应当抛 LLMConfigError，但没有")

    @case("配置：本地地址允许空 Key（用占位符）")
    def _t4():
        with _clean_env():
            os.environ["LLM_DEFAULT_BASE_URL"] = "http://127.0.0.1:11434/v1"
            os.environ["LLM_DEFAULT_MODEL"] = "m"
            cfg = resolve("default")
            assert cfg.api_key == "not-needed", cfg.api_key
            return "127.0.0.1 免 Key，占位符 not-needed"

    @case("图像：本地文件 → data URL")
    def _t5():
        part = image_part(png)
        url = part["image_url"]["url"]
        assert part["type"] == "image_url"
        assert url.startswith("data:image/png;base64,"), url[:40]
        assert len(url) > 100
        return f"{len(url)} 字符 data URL"

    @case("音频：wav → input_audio")
    def _t6():
        part = audio_part(wav)
        assert part["type"] == "input_audio"
        assert part["input_audio"]["format"] == "wav"
        return f"format=wav, base64 {len(part['input_audio']['data'])} 字符"

    @case("音频：flac 明确拒绝并给转码提示")
    def _t7():
        try:
            audio_part(bad)
        except LLMMediaError as exc:
            assert "ffmpeg" in str(exc), str(exc)
            return "提示改用 wav/mp3"
        raise AssertionError("flac 应当被拒绝")

    @case("schema：自动补 additionalProperties / required")
    def _t8():
        src = {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["correct", "wrong"]},
                "score": {"type": "integer"},
            },
        }
        norm, strict_ok = normalize_schema(src)
        assert norm["additionalProperties"] is False
        assert sorted(norm["required"]) == ["score", "verdict"]
        assert strict_ok is True
        return f"strict={strict_ok}"

    @case("schema：含可选字段时不上 strict")
    def _t9():
        src = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
            "required": ["a"],
        }
        _, strict_ok = normalize_schema(src)
        assert strict_ok is False, "有可选字段时 strict 必须为 False"
        return "strict=False，避免 OpenAI 400"

    @case("schema：response_format 结构完整")
    def _t10():
        fmt = make_response_format(
            {"type": "object", "properties": {"x": {"type": "number"}}}
        )
        assert fmt["type"] == "json_schema"
        assert fmt["json_schema"]["name"] == "llm_response"
        assert "schema" in fmt["json_schema"]
        return "json_schema + name + strict 齐备"

    @case("JSON 解析：容忍 ```json 围栏")
    def _t11():
        obj = parse_json('```json\n{"a": 1}\n```')
        assert obj == {"a": 1}
        return "围栏已剥离"

    @case("JSON 解析：容忍前后解释文字")
    def _t12():
        obj = parse_json('好的，结果如下：\n{"a": [1, 2]}\n希望有帮助。')
        assert obj == {"a": [1, 2]}
        return "截取了首个 JSON"

    @case("JSON 校验：不符合 schema 时报路径")
    def _t13():
        schema = {
            "type": "object",
            "properties": {"score": {"type": "integer"}},
            "required": ["score"],
        }
        try:
            validate({"score": "高"}, schema)
        except LLMSchemaError as exc:
            assert "score" in str(exc), str(exc)
            return "错误信息含字段路径"
        raise AssertionError("类型不符应当报错")

    @case("提示词：schema 说明可嵌入 system")
    def _t14():
        hint = build_hint({"type": "object", "properties": {"a": {"type": "string"}}})
        assert "JSON" in hint and "properties" in hint
        return f"{len(hint)} 字符提示"


def run_live(profile: str, text_prompt: str) -> None:
    print(f"\n=== 实时用例（profile={profile}）===")

    try:
        cfg = resolve(profile)
        print(f"  base_url = {cfg.base_url}")
        print(f"  model    = {cfg.model}")
        print(f"  api_key  = {cfg.masked_key}")
    except LLMConfigError as exc:
        record("实时：读取配置", SKIP, str(exc))
        return

    if not is_available(profile):
        record("实时：端点可用性", SKIP, "连不上或 /models 不可用，跳过实时用例")
        return
    record("实时：端点可用性", PASS, "GET /models 正常")

    @case("实时：chat 非流式返回文本")
    def _l1():
        out = chat("你是简洁的助手，回答不超过 30 字。", text_prompt, profile=profile)
        assert out.strip(), "返回为空"
        return f"{len(out)} 字：{out.strip()[:40]}"

    @case("实时：chat_stream 返回增量")
    def _l2():
        pieces = list(chat_stream("你是简洁的助手。", text_prompt, profile=profile))
        assert pieces, "没有增量"
        joined = "".join(pieces)
        assert joined.strip(), "增量拼起来为空"
        return f"{len(pieces)} 片 / {len(joined)} 字"

    @case("实时：chat_json 结构化输出")
    def _l3():
        schema = {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["correct", "wrong"]},
                "score": {"type": "integer"},
                "reason": {"type": "string"},
            },
            "required": ["verdict", "score", "reason"],
        }
        obj = chat_json(
            "你是发音评分器，只输出 JSON。",
            "评估这句话：「四是四十」读得准不准，score 用 0-100，"
            "verdict 只能是 correct 或 wrong，reason 一句话。",
            schema=schema,
            profile=profile,
            max_retries=1,
        )
        assert isinstance(obj, dict), type(obj)
        assert obj["verdict"] in ("correct", "wrong"), obj
        return f"verdict={obj['verdict']}, score={obj['score']}"

    @case("实时：is_available 不抛异常")
    def _l4():
        assert is_available(profile, timeout=3) is True
        return "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="app.llm 自测")
    parser.add_argument("--live", action="store_true", help="额外跑真实调用")
    parser.add_argument("--profile", default="local", help="实时用例使用的 profile")
    parser.add_argument("--text", default="用一句话说明什么是声谱图。", help="实时用例的提问")
    args = parser.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="llm-selftest-"))
    try:
        run_offline(tmp)
        if args.live:
            run_live(args.profile, args.text)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total = len(_records)
    failed = sum(1 for _, s, _ in _records if s == FAIL)
    skipped = sum(1 for _, s, _ in _records if s == SKIP)
    passed = total - failed - skipped
    print(f"\n合计 {total} 项：PASS {passed} / FAIL {failed} / SKIP {skipped}")
    if failed:
        print("失败项：")
        for name, status, detail in _records:
            if status == FAIL:
                print(f"  - {name}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
