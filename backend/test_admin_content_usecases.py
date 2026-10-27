"""后台内容用例定向测试：媒体登记/软删、标定文本保存、分类增改删、希望增加处理。

内存 SQLite + 临时 SVS_DATA_DIR（媒体写盘与删除日志都落在临时目录），
不触碰 backend/data 业务库；不依赖讯飞 Provider 与真人语料库。
运行：backend/ 目录下 `py -3 test_admin_content_usecases.py`。
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
# 必须在导入 app.config 前改数据目录（模块常量在导入时定格）
os.environ["SVS_DATA_DIR"] = tempfile.mkdtemp(prefix="svs_admin_usecases_")
os.environ.setdefault("SVS_PROVIDER", "mock")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models_registry  # noqa: F401,E402  注册全部表
from app import config  # noqa: E402
from app.content import media as content_media_uc  # noqa: E402
from app.content import usecases as content_uc  # noqa: E402
from app.content.models import (  # noqa: E402
    ArticleRow, CalibrationTextRow, CategoryRow, LevelRow, MediaAssetRow,
)
from app.db import JSONText, Base, now  # noqa: E402
from app.feedback import usecases as feedback_uc  # noqa: E402
from app.feedback.models import WishRow  # noqa: E402
from app.ids import new_id  # noqa: E402
from app.platform.deletion_log import deletion_log  # noqa: E402
from app.platform.envelope import ApiError  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not ok else ""))


def expect_api_error(name: str, fn, status: int, code: str,
                     contains: str = "") -> None:
    try:
        fn()
    except ApiError as e:
        check(name, e.status == status and e.code == code
              and (contains in e.message if contains else True),
              f"实际 {e.status}/{e.code}/{e.message}")
    else:
        check(name, False, "未抛出 ApiError")


def make_db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng, expire_on_commit=False)()


def wav_bytes(seconds: float) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


def register_audio(db, seconds: float = 1.0, name: str = "demo.wav",
                   mime: str = "audio/wav", raw: bytes | None = None) -> str:
    out = content_media_uc.register_media_asset(
        db, kind="audio", filename=name, mime=mime,
        raw=raw if raw is not None else wav_bytes(seconds),
        purpose="content", license_note="", text="", uploaded_by="admin")
    return out["mediaId"]


def main() -> int:
    db = make_db()
    try:
        # ---- 媒体登记 ----
        raw = wav_bytes(1.5)
        out = content_media_uc.register_media_asset(
            db, kind="audio", filename="demo.wav", mime="audio/wav", raw=raw,
            purpose="demo", license_note="CC-BY-4.0", text="啊", uploaded_by="admin")
        mid = out["mediaId"]
        check("登记返回 mediaId/kind/sizeBytes",
              mid.startswith("md_") and out["kind"] == "audio"
              and out["sizeBytes"] == len(raw), str(out))
        row = db.get(MediaAssetRow, mid)
        path = config.DATA_DIR / row.storage_path
        check("文件写入 MEDIA_DIR 且 storage_path 相对 DATA_DIR",
              path.is_file() and Path(row.storage_path).parts[0] == "media",
              row.storage_path)
        check("资产行登记完整（时长/哈希/署名/许可）",
              abs((row.duration_sec or 0) - 1.5) < 1e-6
              and row.sha256 == hashlib.sha256(raw).hexdigest()
              and row.author == "admin" and row.uploaded_by == "admin"
              and row.license_note == "CC-BY-4.0" and row.text == "啊"
              and row.deleted_at is None,
              f"duration={row.duration_sec}")

        expect_api_error("空文件 → 422", lambda: content_media_uc.register_media_asset(
            db, kind="audio", filename="x.wav", mime="audio/wav", raw=b"",
            purpose="content", license_note="", text="", uploaded_by="admin"),
            422, "VALIDATION_ERROR", "空文件")

        mp3_id = register_audio(db, raw=b"ID3-fake-mp3", name="a.mp3",
                                mime="audio/mpeg")
        check("非 WAV 音频：探测失败记 duration=None 不阻断登记",
              db.get(MediaAssetRow, mp3_id).duration_sec is None)

        bin_id = register_audio(db, raw=b"\x89PNG", name=None, mime=None)
        bin_row = db.get(MediaAssetRow, bin_id)
        check("缺省文件名/MIME：回退 bin 扩展与 octet-stream",
              bin_row.filename == bin_id and bin_row.mime == "application/octet-stream"
              and bin_row.storage_path.endswith(".bin"), bin_row.storage_path)

        # ---- 媒体软删 ----
        expect_api_error("删除不存在媒体 → 404",
                         lambda: content_media_uc.delete_media_asset(db, "md_none"),
                         404, "NOT_FOUND", "媒体不存在")

        lv = LevelRow(id="L99", order=99, layer="vowel", published=False,
                      skeleton_public=True, content=JSONText.dump({"demo": mid}),
                      created_at=now(), updated_at=now())
        db.add(lv)
        db.commit()
        expect_api_error("被关卡内容引用 → 409",
                         lambda: content_media_uc.delete_media_asset(db, mid),
                         409, "INVALID_STATE", "L99")

        art = ArticleRow(slug="ref-art", published=True,
                         content=JSONText.dump({"demoMediaId": mp3_id}),
                         created_at=now(), updated_at=now())
        db.add(art)
        db.commit()
        expect_api_error("被文章内容引用 → 409",
                         lambda: content_media_uc.delete_media_asset(db, mp3_id),
                         409, "INVALID_STATE", "ref-art")

        lv.content = JSONText.dump({})
        db.commit()
        result = content_media_uc.delete_media_asset(db, mid)
        row = db.get(MediaAssetRow, mid)
        pending = deletion_log.read_pending()
        check("软删成功：deleted_at 置位、文件保留、删除日志登记待清理",
              result == {"deleted": True} and row.deleted_at is not None
              and (config.DATA_DIR / row.storage_path).is_file()
              and any(e["kind"] == "file" and e["key"] == row.storage_path
                      for e in pending),
              str(pending))

        # ---- 标定文本 ----
        syls = [{"text": "妈", "pinyin": "ma1"}, {"text": "坡", "pinyin": "po1"},
                {"text": "车", "pinyin": "che1"}, {"text": "米", "pinyin": "mi3"},
                {"text": "布", "pinyin": "bu4"}, {"text": "女", "pinyin": "nv3"}]
        result = content_uc.set_calibration_text(
            db, text_version="t1", text="妈坡车米布女", syllables=syls)
        active = content_uc.get_active_calibration_text(db)
        check("保存标定文本：返回版本号并成为唯一激活行",
              result == {"textVersion": "t1"}
              and active.text_version == "t1"
              and JSONText.load(active.syllables) == syls
              and db.query(CalibrationTextRow)
                  .filter(CalibrationTextRow.active.is_(True)).count() == 1)

        content_uc.set_calibration_text(
            db, text_version="t2", text="妈坡车米布女", syllables=syls)
        rows = db.query(CalibrationTextRow).all()
        check("再次保存：停用旧文本，新版本激活",
              content_uc.get_active_calibration_text(db).text_version == "t2"
              and len(rows) == 2 and sum(1 for r in rows if r.active) == 1)

        expect_api_error("拼音标注非法 → 422",
                         lambda: content_uc.set_calibration_text(
                             db, text_version="t3", text="妈",
                             syllables=[{"text": "妈", "pinyin": "ma"}]),
                         422, "VALIDATION_ERROR", "标定文本拼音标注无效")
        expect_api_error("未覆盖六个单韵母 → 422",
                         lambda: content_uc.set_calibration_text(
                             db, text_version="t4", text="妈爸搭发",
                             syllables=[{"text": "妈", "pinyin": "ma1"},
                                        {"text": "爸", "pinyin": "ba1"},
                                        {"text": "搭", "pinyin": "da1"},
                                        {"text": "发", "pinyin": "fa1"}]),
                         422, "VALIDATION_ERROR", "缺")

        # ---- 分类增改删 ----
        check("新建分类",
              content_uc.create_category(db, name="发音基础", sort=1)
              == {"created": True})
        expect_api_error("重名分类 → 409",
                         lambda: content_uc.create_category(db, name="发音基础"),
                         409, "INVALID_STATE", "分类已存在")

        cat_id = db.query(CategoryRow).filter(CategoryRow.name == "发音基础").one().id
        check("改分类名与排序",
              content_uc.rename_category(db, cat_id, name="进阶发音", sort=2)
              == {"id": cat_id, "name": "进阶发音"})
        expect_api_error("改不存在的分类 → 404",
                         lambda: content_uc.rename_category(db, 9999, name="x"),
                         404, "NOT_FOUND", "分类不存在")

        art.content = JSONText.dump({"category": "进阶发音"})
        db.commit()
        expect_api_error("分类仍被文章使用 → 409",
                         lambda: content_uc.delete_category(db, cat_id),
                         409, "INVALID_STATE", "仍有 1 篇文章使用该分类")
        art.content = JSONText.dump({"category": "其他"})
        db.commit()
        check("删分类（无文章使用）",
              content_uc.delete_category(db, cat_id) == {"deleted": True}
              and db.get(CategoryRow, cat_id) is None)

        # ---- 希望增加处理（feedback 用例） ----
        wish_id = new_id("w_")
        db.add(WishRow(id=wish_id, user_id="u1", content="希望增加 er 音",
                       status="pending", created_at=now()))
        db.commit()
        expect_api_error("wish 状态非法 → 422",
                         lambda: feedback_uc.handle_wish(
                             db, wish_id=wish_id, status="later", admin_actor="admin"),
                         422, "VALIDATION_ERROR", "状态只允许 adopted / rejected")
        check("wish 处理 adopted",
              feedback_uc.handle_wish(db, wish_id=wish_id, status="adopted",
                                      admin_actor="admin")
              == {"wishId": wish_id, "status": "adopted"})
        check("wish 重复处理仍 200（保持原路由行为）",
              feedback_uc.handle_wish(db, wish_id=wish_id, status="rejected",
                                      admin_actor="admin")
              == {"wishId": wish_id, "status": "rejected"})
        expect_api_error("wish 不存在 → 404",
                         lambda: feedback_uc.handle_wish(
                             db, wish_id="w_none", status="adopted",
                             admin_actor="admin"),
                         404, "NOT_FOUND", "希望增加记录不存在")
    finally:
        db.close()

    failed = [(n, d) for n, ok, d in results if not ok]
    print(f"\n==== {len(results) - len(failed)}/{len(results)} passed ====")
    for n, d in failed:
        print(f"FAILED: {n} — {d}")
    shutil.rmtree(config.DATA_DIR, ignore_errors=True)   # 临时数据目录随测试清理
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
