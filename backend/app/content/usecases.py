"""content 模块用例：公开读模型、搜索、保存（即生效）、开放切换、
内容完整性检查、标准曲线计算、媒体读取。"""
from __future__ import annotations

import logging

import numpy as np
from sqlalchemy.orm import Session

from app import config
from app.content.models import (
    ArticleRow, CalibrationTextRow, CategoryRow, LevelRow, MediaAssetRow,
    ReferenceSpeakerRow,
)
from app.db import JSONText, now
from app.platform.envelope import ApiError
from app.pinyin_utils import annotated_syllables, main_vowel, split_pinyin

logger = logging.getLogger("svs.content")

LAYER_LABEL = {"vowel": "单韵母", "initial": "声母", "syllable": "拼读"}


# ---------------- 读模型 ----------------

PHONOLOGY_FIELDS = ("ipa", "kind", "initial", "final", "tones", "place", "manner",
                    "aspiration", "voicing", "hu", "finalStructure")


def _phonology_of(content: dict) -> dict | None:
    """关卡内容 phonology 段透传（可选；未填写返回 None，前端按 targetSound/pinyin 兜底）。"""
    raw = content.get("phonology")
    if not isinstance(raw, dict):
        return None
    out = {k: raw.get(k) for k in PHONOLOGY_FIELDS if raw.get(k) is not None}
    return out or None


def availability_of(level: LevelRow) -> str:
    return "open" if level.published else "closed"


def open_levels(db: Session) -> list[LevelRow]:
    return (db.query(LevelRow).filter(LevelRow.published.is_(True))
            .order_by(LevelRow.order).all())


def level_summary(db: Session, level: LevelRow) -> dict:
    content = JSONText.load(level.content, {})
    demos = content.get("demos") or []
    demo_media = next((d["mediaId"] for d in demos
                       if d.get("speed") == "normal" and d.get("mediaId")), None)
    return {
        "id": level.id,
        "order": level.order,
        "layer": level.layer,
        "type": content.get("type") or LAYER_LABEL.get(level.layer, level.layer),
        "targetSound": content.get("targetSound") or "",
        "pinyin": content.get("pinyin") or "",
        "representativeChar": content.get("representativeChar") or "",
        "title": content.get("title") or "",
        "phonology": _phonology_of(content),
        "demoMediaId": demo_media,
        "availability": availability_of(level),
    }


def levels_response(db: Session) -> dict:
    levels = open_levels(db)
    summaries = [level_summary(db, lv) for lv in levels]
    open_ids = {lv.id for lv in levels}
    skeleton = [
        {"id": lv.id, "order": lv.order, "layer": lv.layer,
         "targetSound": JSONText.load(lv.content, {}).get("targetSound") or "",
         "availability": "closed"}
        for lv in db.query(LevelRow).order_by(LevelRow.order).all()
        if not lv.published and lv.skeleton_public
    ]
    pairs = []
    for lv in levels:
        content = JSONText.load(lv.content, {})
        for other_id in content.get("confusables") or []:
            if other_id in open_ids and other_id > lv.id:
                pairs.append({"a": lv.id, "b": other_id})
    return {"levels": summaries, "skeleton": skeleton, "confusablePairs": pairs}


def _nav(db: Session, level: LevelRow, content: dict) -> dict:
    levels = open_levels(db)
    ids = [lv.id for lv in levels]
    idx = ids.index(level.id) if level.id in ids else -1
    prev_id = ids[idx - 1] if idx > 0 else None
    next_id = ids[idx + 1] if 0 <= idx < len(ids) - 1 else None
    opened = set(ids)
    confusables = [c for c in (content.get("confusables") or []) if c in opened]
    return {"prev": prev_id, "next": next_id, "confusables": confusables}


def level_sections(content: dict) -> dict:
    """关卡内容 JSON → demos/quizzes/practice/articulation/detection 负载段。"""
    demos = [
        {"mediaId": d["mediaId"], "speed": d.get("speed", "normal"),
         "voice": d.get("voice")}
        for d in (content.get("demos") or []) if d.get("mediaId")
    ]
    quizzes = [
        {
            "id": q["id"], "stimulusMediaId": q.get("stimulusMediaId"),
            "prompt": q.get("prompt", "听一听，这是哪个音？"),
            "options": [{"text": o.get("text", ""), "mediaId": o.get("mediaId")}
                        for o in (q.get("options") or [])],
            "answerIndex": q.get("answerIndex", 0),
            "explanation": q.get("explanation"),
        }
        for q in (content.get("quizzes") or [])
    ]
    practice = [p for p in (content.get("practice") or []) if isinstance(p, str)]
    articulation_raw = content.get("articulation") or {}
    articulation = {
        "media": [
            {"mediaId": m.get("mediaId"), "kind": m.get("kind", "image"),
             "altText": m.get("altText", ""), "component": m.get("component")}
            for m in (articulation_raw.get("media") or []) if m.get("mediaId")
        ],
        "model3dMediaId": articulation_raw.get("model3dMediaId"),
    }
    detection_raw = content.get("detection") or {}
    detection = {
        "promptText": detection_raw.get("promptText", ""),
        "sampleMediaId": detection_raw.get("sampleMediaId"),
        "allowedMetrics": detection_raw.get("allowedMetrics", []),
    }
    return {
        "articulation": articulation,
        "demos": demos,
        "quizzes": quizzes,
        "practice": practice,
        "detection": detection,
    }


def level_detail(db: Session, level_id: str) -> dict:
    """已开放关卡详情；规则阈值与四步模板不下发。"""
    level = db.get(LevelRow, level_id)
    if level is None or not level.published:
        raise ApiError(404, "NOT_FOUND", "关卡不存在或未开放")
    content = JSONText.load(level.content, {})
    return {
        "id": level.id,
        "order": level.order,
        "layer": level.layer,
        "type": content.get("type") or LAYER_LABEL.get(level.layer, level.layer),
        "targetSound": content.get("targetSound"),
        "pinyin": content.get("pinyin"),
        "representativeChar": content.get("representativeChar"),
        "title": content.get("title"),
        "tags": content.get("tags") or [],
        "phonology": _phonology_of(content),
        "nav": _nav(db, level, content),
        "professional": content.get("professional") or {},
        **level_sections(content),
    }


# ---------------- 搜索（pypinyin 汉字拆声母/韵母映射） ----------------

def _plain_pinyin(s: str) -> str:
    """小写并去拼音声调符号（má → ma）：带调目标音与无声调查询词可互相命中。"""
    import unicodedata
    decomposed = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def search_levels(db: Session, query: str) -> dict:
    query = (query or "").strip()
    if not query:
        return {"results": [], "near": [], "query": query}
    levels = open_levels(db)
    contents: dict[str, dict] = {lv.id: JSONText.load(lv.content, {}) for lv in levels}

    def text_of(cid: str) -> str:
        c = contents[cid]
        return " ".join(filter(None, [
            c.get("targetSound"), c.get("pinyin"), c.get("title"),
            c.get("representativeChar"), " ".join(c.get("tags") or []),
        ]))

    low = _plain_pinyin(query)
    results = []
    for lv in levels:
        c = contents[lv.id]
        hay = _plain_pinyin(text_of(lv.id))
        score = 0
        if _plain_pinyin(c.get("targetSound") or "") == low:
            score = 100
        elif _plain_pinyin(c.get("pinyin") or "") == low:
            score = 95
        elif c.get("representativeChar") == query:
            score = 90
        elif low in _plain_pinyin(c.get("pinyin") or "") or _plain_pinyin(c.get("pinyin") or "") in low:
            score = 70
        elif any(t.lower() == low for t in (c.get("tags") or [])):
            score = 65
        elif low in hay:
            score = 50
        else:
            score = _pinyin_match(query, c)
        if score > 0:
            results.append((score, lv))
    results.sort(key=lambda x: (-x[0], x[1].order))
    matched = [level_summary(db, lv) for _, lv in results[:10]]
    near = []
    if not matched:
        seen: set[str] = set()
        for lv in levels:
            c = contents[lv.id]
            ts = (c.get("targetSound") or "")
            if ts and _plain_pinyin(ts) in low and lv.id not in seen:
                near.append(level_summary(db, lv))
                seen.add(lv.id)
            if len(near) >= 3:
                break
        if not near:   # 同层已开放前几关兜底
            for lv in levels[:3]:
                near.append(level_summary(db, lv))
    return {"results": matched, "near": near, "query": query}


def _pinyin_match(query: str, content: dict) -> int:
    """汉字查询 → 拼音声母/韵母映射到关卡（pypinyin）。"""
    from pypinyin import Style, pinyin

    target = _plain_pinyin(content.get("targetSound") or "")
    if not target:
        return 0
    for ch in query:
        if not ("\u4e00" <= ch <= "\u9fff"):
            continue
        for py in pinyin(ch, style=Style.NORMAL, heteronym=False):
            s = py[0]
            initial, final = split_pinyin(s)
            if target == initial or target == final:
                return 60
            if len(target) == 1 and target in s:
                return 40
    return 0


# ---------------- 文章 ----------------

def article_categories(db: Session) -> list[dict]:
    rows = db.query(CategoryRow).order_by(CategoryRow.sort).all()
    return [{"id": r.id, "name": r.name} for r in rows]


def create_category(db: Session, *, name: str, sort: int = 0) -> dict:
    if db.query(CategoryRow).filter(CategoryRow.name == name).count():
        raise ApiError(409, "INVALID_STATE", "分类已存在")
    db.add(CategoryRow(name=name, sort=sort, created_at=now()))
    db.commit()
    return {"created": True}


def rename_category(db: Session, category_id: int, *, name: str,
                    sort: int = 0) -> dict:
    row = db.get(CategoryRow, category_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "分类不存在")
    row.name = name
    row.sort = sort
    db.commit()
    return {"id": row.id, "name": row.name}


def delete_category(db: Session, category_id: int) -> dict:
    row = db.get(CategoryRow, category_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "分类不存在")
    used = sum(
        1 for a in db.query(ArticleRow).all()
        if (JSONText.load(a.content, {}) or {}).get("category") == row.name)
    if used:
        raise ApiError(409, "INVALID_STATE", f"仍有 {used} 篇文章使用该分类，请先改分类")
    db.delete(row)
    db.commit()
    return {"deleted": True}


def articles_list(db: Session, category: str | None = None) -> dict:
    rows = (db.query(ArticleRow).filter(ArticleRow.published.is_(True))
            .order_by(ArticleRow.updated_at.desc()).all())
    out = []
    for a in rows:
        c = JSONText.load(a.content, {})
        if category and c.get("category") != category:
            continue
        open_ids_now = {lv.id for lv in open_levels(db)}
        out.append({
            "slug": a.slug, "title": c.get("title", ""), "category": c.get("category", ""),
            "summary": c.get("summary", ""),
            "demoMediaId": c.get("demoMediaId"),
            "relatedLevelIds": [lid for lid in (c.get("relatedLevelIds") or [])
                                if lid in open_ids_now],
        })
    return {"articles": out}


def article_detail(db: Session, slug: str) -> dict:
    a = db.get(ArticleRow, slug)
    if a is None or not a.published:
        raise ApiError(404, "NOT_FOUND", "文章不存在")
    c = JSONText.load(a.content, {})
    open_ids_now = {lv.id for lv in open_levels(db)}
    related = [lid for lid in (c.get("relatedLevelIds") or []) if lid in open_ids_now]
    unavailable = [lid for lid in (c.get("relatedLevelIds") or []) if lid not in open_ids_now]
    return {
        "slug": a.slug,
        "title": c.get("title", ""),
        "category": c.get("category", ""),
        "summary": c.get("summary", ""),
        "markdown": c.get("markdown", ""),
        "demo": {"mediaId": c.get("demoMediaId"), "text": c.get("demoText", "")},
        "practice": c.get("practice") or [],
        "references": c.get("references") or [],
        "relatedLevels": [{"levelId": lid, "available": True} for lid in related] + [
            {"levelId": lid, "available": False} for lid in unavailable],
    }


# ---------------- 媒体读取 ----------------

def media_publicly_readable(db: Session, media_id: str) -> MediaAssetRow | None:
    asset = db.get(MediaAssetRow, media_id)
    if asset is None or asset.deleted_at is not None:
        return None
    return asset


# ---------------- 内容完整性检查（FR-1203/1204） ----------------

def precheck_level(db: Session, content: dict) -> list[str]:
    """开放关卡的基本内容完整性检查：逐项返回缺失/非法。"""
    missing: list[str] = []
    if not content.get("targetSound"):
        missing.append("缺少目标音")
    practice = content.get("practice") or []
    if not practice or not all(isinstance(p, str) and p for p in practice):
        missing.append("缺少练习文案")
    art = content.get("articulation") or {}
    for m in art.get("media") or []:
        if m.get("mediaId") and not m.get("altText"):
            missing.append("构形媒体缺少替代文本")
    demos = content.get("demos") or []
    if not any(d.get("speed") == "normal" and d.get("mediaId") for d in demos):
        missing.append("缺少正常语速示范音频")
    det = content.get("detection") or {}
    if not det.get("promptText"):
        missing.append("缺少朗读提示词")
    if not det.get("evaluationText"):
        missing.append("缺少评测文本")
    if not det.get("evaluationPinyin"):
        missing.append("缺少评测拼音标注")
    elif det.get("evaluationText"):
        try:
            annotated_syllables(det["evaluationText"], det["evaluationPinyin"])
        except ValueError as e:
            missing.append(f"评测拼音标注无效：{e}")
    if not det.get("sampleMediaId"):
        missing.append("缺少参考示范音频")
    if not det.get("fourStepTemplates"):
        missing.append("缺少四步反馈模板")
    prof = content.get("professional") or {}
    if not prof.get("description"):
        missing.append("缺少专业与声学说明")
    # 引用的媒体必须存在且未删除
    all_media = _collect_media_ids(content)
    for mid in all_media:
        if mid and db.get(MediaAssetRow, mid) is None:
            missing.append(f"媒体不存在：{mid}")
    return missing


def precheck_article(db: Session, content: dict) -> list[str]:
    missing = []
    if not content.get("title"):
        missing.append("缺少标题")
    if not content.get("category"):
        missing.append("缺少分类")
    else:
        if db.query(CategoryRow).filter(CategoryRow.name == content["category"]).count() == 0:
            missing.append(f"分类不存在：{content['category']}")
    if not content.get("markdown") or len(content["markdown"]) < 30:
        missing.append("正文过短")
    if not content.get("demoMediaId"):
        missing.append("缺少可播放示范")
    if not (content.get("references") or []):
        missing.append("缺少参考资料（FR-506）")
    if not (content.get("practice") or []):
        missing.append("缺少短练习")
    if content.get("demoMediaId") and db.get(MediaAssetRow, content["demoMediaId"]) is None:
        missing.append("示范媒体不存在")
    return missing


def _collect_media_ids(content: dict) -> set[str | None]:
    ids: set[str | None] = set()
    for d in content.get("demos") or []:
        ids.add(d.get("mediaId"))
    for q in content.get("quizzes") or []:
        ids.add(q.get("stimulusMediaId"))
        for o in q.get("options") or []:
            ids.add(o.get("mediaId"))
    art = content.get("articulation") or {}
    for m in art.get("media") or []:
        ids.add(m.get("mediaId"))
    ids.add(art.get("model3dMediaId"))
    det = content.get("detection") or {}
    ids.add(det.get("sampleMediaId"))
    return ids


# ---------------- 标准曲线（检测对比参考） ----------------

def _split_voiced_equal(voiced: list[list[float]], n: int) -> list[tuple[float, float]]:
    """按累计有声时长等分，音节内保留缺口并消费全部有声段。"""
    total = sum(b - a for a, b in voiced)
    if total <= 0 or n <= 0:
        return []
    per = total / n
    segments: list[tuple[float, float]] = []
    start = float(voiced[0][0])
    consumed = 0.0
    cut = 1
    for a, b in voiced:
        while cut < n and cut * per <= consumed + b - a + 1e-9:
            end = min(float(b), float(a + cut * per - consumed))
            segments.append((start, end))
            start = end
            cut += 1
        consumed += b - a
    segments.append((start, float(voiced[-1][1])))
    return segments


def compute_standard_curve(db: Session, content: dict) -> dict | None:
    """标准示范曲线：与用户录音同一条 F0 管线（filtered AC + 四步清洗 +
    degree 1-5 五度坐标），音域用参考
    发音人自身固定音域。音节边界优先复用同一媒体的登记时间戳，缺省按累计有声时长等分，全程
    不调评分 Provider——seed 关卡与后台保存关卡都不消耗评测配额。
    提取失败（如清辅音为主）时返回 None，该关结果页曲线对比降级为不可用，
    不阻断内容保存。"""
    det = content.get("detection") or {}
    media_id = det.get("sampleMediaId")
    speaker_id = det.get("referenceSpeakerId")
    asset = db.get(MediaAssetRow, media_id) if media_id else None
    speaker = db.get(ReferenceSpeakerRow, speaker_id) if speaker_id else None
    if asset is None or speaker is None:
        return None
    from app.acoustics import analysis as acx
    from app.acoustics import f0_pipeline

    path = config.DATA_DIR / asset.storage_path
    if not path.exists():
        return None
    try:
        track = f0_pipeline.extract_track(path)
        voiced = [[float(track.times[a]), float(track.times[b])]
                  for a, b in f0_pipeline._runs(np.isfinite(track.f0)) if b > a]
    except Exception:
        logger.warning("标准曲线计算失败：media=%s speaker=%s", media_id, speaker_id,
                       exc_info=True)
        return None
    try:   # 音节数以评测拼音标注为准（读音与声调同源，不做文本侧推断）
        n = len(annotated_syllables(det.get("evaluationText", ""),
                                    det.get("evaluationPinyin", "")))
    except ValueError:
        logger.warning("标准曲线计算跳过：评测拼音缺失或无效：media=%s", media_id)
        return None
    # 保留已登记/历史示范的音节时间戳；无时间戳时使用本地累计时长回退。
    previous_curve = content.get("standardCurve") or {}
    previous = previous_curve.get("segments", []) if previous_curve.get("sampleMediaId") == media_id else []
    bounds = [(seg["t0"], seg["t1"]) for seg in previous
              if seg.get("t0") is not None and seg.get("t1") is not None
              and 0 <= seg["t0"] < seg["t1"] <= track.duration]
    if len(bounds) != n:
        bounds = _split_voiced_equal(voiced, n) or [(0.0, track.duration)]
    segments = f0_pipeline.process_syllables(track, bounds, speaker.f_lo, speaker.f_hi)
    if not any((seg.get("quality") or {}).get("validFrames", 0) >= f0_pipeline.MIN_DRAW_RUN
               for seg in segments):
        return None
    # 参考元音区（单韵母关共振峰参考）
    reference_region = None
    vowel_space = JSONText.load(speaker.vowel_space) if speaker.vowel_space else None
    target_vowel = (content.get("targetSound") or "")
    if vowel_space and target_vowel in vowel_space:
        ref_v = vowel_space[target_vowel]
        overall = vowel_space.get("overall") or {"f1Std": 100, "f2Std": 200}
        center = [
            round((ref_v["f1Mean"] - overall.get("f1Mean", ref_v["f1Mean"])) / max(overall.get("f1Std", 100), 1), 3),
            round((ref_v["f2Mean"] - overall.get("f2Mean", ref_v["f2Mean"])) / max(overall.get("f2Std", 200), 1), 3),
        ]
        reference_region = {"vowel": target_vowel, "center": center, "radius": 1.5}
    curve = {
        "scale": "degree",
        "algorithmVersion": acx.ALGORITHM_VERSION,
        "referenceSpeakerId": speaker.id,
        "referenceRange": {"fLo": round(float(speaker.f_lo), 1),
                           "fHi": round(float(speaker.f_hi), 1)},
        "sampleMediaId": asset.id,
        "segments": segments,
    }
    if reference_region:
        curve["referenceRegion"] = reference_region
    return curve


def prepare_level_content(db: Session, content: dict) -> dict:
    """保存关卡内容前补齐派生字段（标准曲线）。"""
    curve = compute_standard_curve(db, content)
    if curve is not None:
        content["standardCurve"] = curve
    else:
        content.pop("standardCurve", None)
    return content


# ---------------- 保存与开放切换（保存即生效） ----------------

def save_level(db: Session, level_id: str, content: dict) -> dict:
    level = db.get(LevelRow, level_id)
    if level is None:
        raise ApiError(404, "NOT_FOUND", "关卡不存在")
    content = prepare_level_content(db, content)
    level.content = JSONText.dump(content)
    level.updated_at = now()
    db.commit()
    return {"levelId": level_id}


def set_level_published(db: Session, level_id: str, published: bool) -> dict:
    level = db.get(LevelRow, level_id)
    if level is None:
        raise ApiError(404, "NOT_FOUND", "关卡不存在")
    level.published = bool(published)
    level.updated_at = now()
    db.commit()
    return {"levelId": level_id, "published": level.published}


def save_article(db: Session, slug: str, content: dict, *, create: bool = False) -> dict:
    if create:
        slug = (slug or "").strip()
        if not slug or db.get(ArticleRow, slug) is not None:
            raise ApiError(409, "INVALID_STATE", "slug 缺失或已存在")
        db.add(ArticleRow(slug=slug, published=False,
                          content=JSONText.dump(content),
                          created_at=now(), updated_at=now()))
    else:
        article = db.get(ArticleRow, slug)
        if article is None:
            raise ApiError(404, "NOT_FOUND", "文章不存在")
        article.content = JSONText.dump(content)
        article.updated_at = now()
    db.commit()
    return {"slug": slug}


def set_article_published(db: Session, slug: str, published: bool) -> dict:
    article = db.get(ArticleRow, slug)
    if article is None:
        raise ApiError(404, "NOT_FOUND", "文章不存在")
    article.published = bool(published)
    article.updated_at = now()
    db.commit()
    return {"slug": slug, "published": article.published}


def delete_article(db: Session, slug: str) -> dict:
    article = db.get(ArticleRow, slug)
    if article is None:
        raise ApiError(404, "NOT_FOUND", "文章不存在")
    db.delete(article)
    db.commit()
    return {"slug": slug}


# ---------------- 标定文本 ----------------

def get_active_calibration_text(db: Session) -> CalibrationTextRow | None:
    return (db.query(CalibrationTextRow)
            .filter(CalibrationTextRow.active.is_(True))
            .order_by(CalibrationTextRow.id.desc()).first())


def set_calibration_text(db: Session, *, text_version: str, text: str,
                         syllables: list[dict]) -> dict:
    """标定文本配置：须覆盖六个单韵母（FR-1403）；每字带拼音标注。"""
    try:
        entries = annotated_syllables("".join(s["text"] for s in syllables),
                                      "|".join(s["pinyin"] for s in syllables))
    except ValueError as e:
        raise ApiError(422, "VALIDATION_ERROR", f"标定文本拼音标注无效：{e}")
    found = {v for v in (main_vowel(e["plain"]) for e in entries) if v}
    missing = {"a", "o", "e", "i", "u", "ü"} - found
    if missing:
        raise ApiError(422, "VALIDATION_ERROR",
                       "标定文本须覆盖六个单韵母（缺 " + "、".join(sorted(missing)) + "）")
    for row in db.query(CalibrationTextRow).all():
        row.active = False
    db.add(CalibrationTextRow(text_version=text_version, text=text,
                              syllables=JSONText.dump(syllables),
                              active=True, updated_at=now()))
    db.commit()
    return {"textVersion": text_version}
