"""content 模块用例：公开读模型、搜索、发布/下架/回退、前置检查、
发布时标准曲线预计算、媒体授权读取、预览。"""
from __future__ import annotations

import datetime

import numpy as np
from sqlalchemy.orm import Session

from app import config
from app.content.models import (
    ArticleDraftRow, ArticleRow, ArticleVersionRow, CalibrationTextRow, CategoryRow,
    DetectionSwitchRow, LevelDraftRow, LevelRow, LevelVersionRow, MediaAssetRow,
    MediaRefRow, ReferenceSpeakerRow, SagittalPresetRow,
)
from app.db import JSONText, now
from app.ids import new_id
from app.platform.envelope import ApiError
from app.pinyin_utils import split_pinyin

LAYER_LABEL = {"vowel": "单韵母", "initial": "声母", "syllable": "拼读"}

SAGITTAL_ENUMS = {
    "lips_contact": {"none", "bilabial", "labiodental"},
    "tip_place": {"rest", "dental", "alveolar", "postalveolar", "retroflex"},
    "tip_stricture": {"open", "approximant", "fricative", "closure"},
    "body_stricture": {"open", "approximant", "fricative", "closure"},
    "velum": {"raised", "lowered"},
    "airflow": {"none", "oral", "nasal", "burst", "aspirated_burst", "friction", "affricate"},
}


# ---------------- 读模型 ----------------

def _switch_state(db: Session, level_id: str | None) -> DetectionSwitchRow | None:
    q = db.query(DetectionSwitchRow).filter(DetectionSwitchRow.enabled.is_(False))
    if level_id:
        row = q.filter(DetectionSwitchRow.level_id == level_id).one_or_none()
        if row is not None:
            return row
    return q.filter(DetectionSwitchRow.level_id.is_(None)).one_or_none()


def availability_of(db: Session, level: LevelRow) -> str:
    if level.status != "published":
        return "closed"
    return "temporarily_unavailable" if _switch_state(db, level.id) else "open"


def published_levels(db: Session) -> list[LevelRow]:
    return (db.query(LevelRow).filter(LevelRow.status == "published")
            .order_by(LevelRow.order).all())


def level_summary(db: Session, level: LevelRow) -> dict:
    version = db.get(LevelVersionRow, level.current_version_id) if level.current_version_id else None
    content = JSONText.load(version.content, {}) if version else {}
    demos = content.get("demos") or []
    demo_media = next((d["mediaId"] for d in demos
                       if d.get("speed") == "normal" and d.get("mediaId")), None)
    quizzes = content.get("quizzes") or []
    practice = content.get("practice") or []
    return {
        "id": level.id,
        "order": level.order,
        "layer": level.layer,
        "type": content.get("type") or LAYER_LABEL.get(level.layer, level.layer),
        "targetSound": content.get("targetSound") or "",
        "pinyin": content.get("pinyin") or "",
        "representativeChar": content.get("representativeChar") or "",
        "title": content.get("title") or "",
        "oneLiner": content.get("oneLiner") or "",
        "demoMediaId": demo_media,
        "availability": availability_of(db, level),
        "completionKeys": {
            "quizIds": [q["id"] for q in quizzes if q.get("id")],
            "practiceStepIds": [p["id"] for p in practice if p.get("id")],
        },
    }


def levels_response(db: Session) -> dict:
    levels = published_levels(db)
    summaries = [level_summary(db, lv) for lv in levels]
    published_ids = {lv.id for lv in levels}
    skeleton = [
        {"id": lv.id, "order": lv.order, "layer": lv.layer,
         "targetSound": _draft_target_sound(db, lv.id), "availability": "closed"}
        for lv in db.query(LevelRow).order_by(LevelRow.order).all()
        if lv.status != "published" and lv.skeleton_public
    ]
    pairs = []
    for lv in levels:
        version = db.get(LevelVersionRow, lv.current_version_id)
        content = JSONText.load(version.content, {}) if version else {}
        for other_id in content.get("confusables") or []:
            if other_id in published_ids and other_id > lv.id:
                pairs.append({"a": lv.id, "b": other_id})
    return {"levels": summaries, "skeleton": skeleton, "confusablePairs": pairs}


def _draft_target_sound(db: Session, level_id: str) -> str:
    draft = db.get(LevelDraftRow, level_id)
    if draft:
        return JSONText.load(draft.content, {}).get("targetSound") or ""
    return ""


def _nav(db: Session, level: LevelRow, content: dict) -> dict:
    levels = published_levels(db)
    ids = [lv.id for lv in levels]
    idx = ids.index(level.id) if level.id in ids else -1
    prev_id = ids[idx - 1] if idx > 0 else None
    next_id = ids[idx + 1] if 0 <= idx < len(ids) - 1 else None
    published = set(ids)
    confusables = [c for c in (content.get("confusables") or []) if c in published]
    return {"prev": prev_id, "next": next_id, "confusables": confusables}


def level_sections(content: dict, *, detection_available: bool) -> dict:
    """关卡内容 JSON → demos/quizzes/practice/articulation/detection 负载段。
    发布详情与草稿预览共用同一构造；detection.available 由调用方决定
    （发布版看检测开关，草稿预览恒 False）。"""
    demos = [
        {"mediaId": d["mediaId"], "speed": d.get("speed", "normal"),
         "voice": d.get("voice"), "text": d.get("text", "")}
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
    practice = [
        {"id": p["id"], "title": p.get("title", ""), "instruction": p.get("instruction", ""),
         "repeat": p.get("repeat"), "durationSec": p.get("durationSec"),
         "bodyCue": p.get("bodyCue", ""), "mediaId": p.get("mediaId"),
         "stopNote": p.get("stopNote", "不舒服就停止")}
        for p in (content.get("practice") or [])
    ]
    articulation_raw = content.get("articulation") or {}
    articulation = {
        "media": [
            {"mediaId": m.get("mediaId"), "kind": m.get("kind", "image"),
             "altText": m.get("altText", "")}
            for m in (articulation_raw.get("media") or []) if m.get("mediaId")
        ],
        "description": articulation_raw.get("description", ""),
        "sagittal": articulation_raw.get("sagittal") or {"keyframes": []},
        "model3dMediaId": articulation_raw.get("model3dMediaId"),
    }
    detection_raw = content.get("detection") or {}
    detection = {
        "promptText": detection_raw.get("promptText", ""),
        "sampleMediaId": detection_raw.get("sampleMediaId"),
        "allowedMetrics": detection_raw.get("allowedMetrics", []),
        "reliabilityNote": detection_raw.get("reliabilityNote", ""),
        "available": detection_available,
    }
    return {
        "articulation": articulation,
        "demos": demos,
        "quizzes": quizzes,
        "practice": practice,
        "detection": detection,
    }


def level_detail(db: Session, level_id: str) -> dict:
    """仅已发布详情；含 contentVersion 与 nav；规则阈值与四步模板不下发。"""
    level = db.get(LevelRow, level_id)
    if level is None or level.status != "published" or not level.current_version_id:
        raise ApiError(404, "NOT_FOUND", "关卡不存在或未发布")
    version = db.get(LevelVersionRow, level.current_version_id)
    content = JSONText.load(version.content, {})
    return {
        "id": level.id,
        "contentVersion": version.version,
        "ruleVersion": version.rule_version,
        "order": level.order,
        "layer": level.layer,
        "type": content.get("type") or LAYER_LABEL.get(level.layer, level.layer),
        "targetSound": content.get("targetSound"),
        "pinyin": content.get("pinyin"),
        "representativeChar": content.get("representativeChar"),
        "title": content.get("title"),
        "oneLiner": content.get("oneLiner"),
        "goal": content.get("goal"),
        "applicableIssues": content.get("applicableIssues"),
        "tags": content.get("tags") or [],
        "nav": _nav(db, level, content),
        "misconceptions": content.get("misconceptions") or [],
        "professional": content.get("professional") or {},
        **level_sections(content, detection_available=availability_of(db, level) == "open"),
    }


# ---------------- 搜索（pypinyin 汉字拆声母/韵母映射） ----------------

def search_levels(db: Session, query: str) -> dict:
    query = (query or "").strip()
    if not query:
        return {"results": [], "near": [], "query": query}
    levels = published_levels(db)
    contents: dict[str, dict] = {}
    for lv in levels:
        v = db.get(LevelVersionRow, lv.current_version_id)
        contents[lv.id] = JSONText.load(v.content, {}) if v else {}

    def text_of(cid: str) -> str:
        c = contents[cid]
        return " ".join(filter(None, [
            c.get("targetSound"), c.get("pinyin"), c.get("title"),
            c.get("representativeChar"), " ".join(c.get("tags") or []),
            c.get("oneLiner"),
        ]))

    low = query.lower()
    results = []
    for lv in levels:
        c = contents[lv.id]
        hay = text_of(lv.id).lower()
        score = 0
        if c.get("targetSound", "").lower() == low:
            score = 100
        elif c.get("pinyin", "").lower() == low:
            score = 95
        elif c.get("representativeChar") == query:
            score = 90
        elif low in (c.get("pinyin") or "").lower() or (c.get("pinyin") or "").lower() in low:
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
            if ts and ts.lower() in low and lv.id not in seen:
                near.append(level_summary(db, lv))
                seen.add(lv.id)
            if len(near) >= 3:
                break
        if not near:   # 同层已发布前几关兜底
            for lv in levels[:3]:
                near.append(level_summary(db, lv))
    return {"results": matched, "near": near, "query": query}


def _pinyin_match(query: str, content: dict) -> int:
    """汉字查询 → 拼音声母/韵母映射到关卡（pypinyin）。"""
    from pypinyin import Style, pinyin

    target = (content.get("targetSound") or "").lower()
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


def articles_list(db: Session, category: str | None = None) -> dict:
    rows = (db.query(ArticleRow).filter(ArticleRow.status == "published")
            .order_by(ArticleRow.updated_at.desc()).all())
    out = []
    for a in rows:
        v = db.get(ArticleVersionRow, a.current_version_id) if a.current_version_id else None
        if not v:
            continue
        c = JSONText.load(v.content, {})
        if category and c.get("category") != category:
            continue
        published_levels_now = {lv.id for lv in published_levels(db)}
        out.append({
            "slug": a.slug, "title": c.get("title", ""), "category": c.get("category", ""),
            "summary": c.get("summary", ""),
            "demoMediaId": c.get("demoMediaId"),
            "relatedLevelIds": [lid for lid in (c.get("relatedLevelIds") or [])
                                if lid in published_levels_now],
            "contentVersion": v.version,
        })
    return {"articles": out}


def article_detail(db: Session, slug: str) -> dict:
    a = db.get(ArticleRow, slug)
    if a is None or a.status != "published" or not a.current_version_id:
        raise ApiError(404, "NOT_FOUND", "文章不存在或未发布")
    v = db.get(ArticleVersionRow, a.current_version_id)
    c = JSONText.load(v.content, {})
    published_levels_now = {lv.id for lv in published_levels(db)}
    related = [lid for lid in (c.get("relatedLevelIds") or []) if lid in published_levels_now]
    unavailable = [lid for lid in (c.get("relatedLevelIds") or []) if lid not in published_levels_now]
    return {
        "slug": a.slug,
        "title": c.get("title", ""),
        "category": c.get("category", ""),
        "summary": c.get("summary", ""),
        "markdown": c.get("markdown", ""),
        "contentVersion": v.version,
        "demo": {"mediaId": c.get("demoMediaId"), "text": c.get("demoText", "")},
        "practice": c.get("practice") or [],
        "references": c.get("references") or [],
        "relatedLevels": [{"levelId": lid, "available": True} for lid in related] + [
            {"levelId": lid, "available": False} for lid in unavailable],
    }


# ---------------- 媒体读取守卫 ----------------

def media_publicly_readable(db: Session, media_id: str) -> MediaAssetRow | None:
    """公开媒体每次读取校验当前发布引用（下架后立即不可读）。"""
    asset = db.get(MediaAssetRow, media_id)
    if asset is None or asset.deleted_at is not None:
        return None
    refs = db.query(MediaRefRow).filter(MediaRefRow.media_id == media_id).all()
    for ref in refs:
        lv = db.query(LevelRow).filter(LevelRow.current_version_id == ref.version_id,
                                       LevelRow.status == "published").one_or_none()
        if lv is not None:
            return asset
        ar = db.query(ArticleRow).filter(ArticleRow.current_version_id == ref.version_id,
                                         ArticleRow.status == "published").one_or_none()
        if ar is not None:
            return asset
    return None


def media_in_draft(db: Session, *, kind: str, object_id: str, media_id: str) -> bool:
    """预览媒体：仅令牌绑定的草稿引用的媒体可读。"""
    if kind == "level":
        draft = db.get(LevelDraftRow, object_id)
        content = JSONText.load(draft.content, {}) if draft else {}
        ids = {d.get("mediaId") for d in content.get("demos") or []}
        ids |= {q.get("stimulusMediaId") for q in content.get("quizzes") or []}
        ids |= {o.get("mediaId") for q in content.get("quizzes") or [] for o in q.get("options") or []}
        ids |= {m.get("mediaId") for m in (content.get("articulation") or {}).get("media") or []}
        det = content.get("detection") or {}
        ids.add(det.get("sampleMediaId"))
        return media_id in ids
    draft = db.get(ArticleDraftRow, object_id)
    content = JSONText.load(draft.content, {}) if draft else {}
    return media_id == content.get("demoMediaId")


# ---------------- 发布治理 ----------------

def validate_sagittal_keyframes(frames: list[dict]) -> list[str]:
    errors: list[str] = []
    if not frames:
        return ["声道剖面至少需要一帧"]
    for i, fr in enumerate(frames):
        p = f"剖面第{i + 1}帧"
        for k in ("jaw",):
            v = fr.get(k)
            if not isinstance(v, (int, float)) or not 0 <= v <= 1:
                errors.append(f"{p} jaw 需在 0–1")
        lips = fr.get("lips") or {}
        for k in ("aperture", "rounding"):
            v = lips.get(k)
            if not isinstance(v, (int, float)) or not 0 <= v <= 1:
                errors.append(f"{p} lips.{k} 需在 0–1")
        if lips.get("contact") not in SAGITTAL_ENUMS["lips_contact"]:
            errors.append(f"{p} lips.contact 取值非法")
        tip = fr.get("tongueTip") or {}
        if tip.get("place") not in SAGITTAL_ENUMS["tip_place"]:
            errors.append(f"{p} tongueTip.place 取值非法")
        if tip.get("stricture") not in SAGITTAL_ENUMS["tip_stricture"]:
            errors.append(f"{p} tongueTip.stricture 取值非法")
        body = fr.get("tongueBody") or {}
        for k in ("height", "backness"):
            v = body.get(k)
            if not isinstance(v, (int, float)) or not 0 <= v <= 1:
                errors.append(f"{p} tongueBody.{k} 需在 0–1")
        if body.get("stricture") not in SAGITTAL_ENUMS["body_stricture"]:
            errors.append(f"{p} tongueBody.stricture 取值非法")
        if fr.get("velum") not in SAGITTAL_ENUMS["velum"]:
            errors.append(f"{p} velum 取值非法")
        if fr.get("airflow") not in SAGITTAL_ENUMS["airflow"]:
            errors.append(f"{p} airflow 取值非法")
        if not isinstance(fr.get("voicing"), bool):
            errors.append(f"{p} voicing 需为布尔")
        if not isinstance(fr.get("holdMs"), int) or fr["holdMs"] < 0:
            errors.append(f"{p} holdMs 需为非负整数")
    return errors


def precheck_level(db: Session, content: dict) -> list[str]:
    """发布前置检查：逐项返回缺失/非法（FR-1203/1204）。"""
    missing: list[str] = []
    if not content.get("targetSound"):
        missing.append("缺少目标音")
    if not content.get("oneLiner"):
        missing.append("缺少一句话结论")
    quizzes = content.get("quizzes") or []
    if not quizzes:
        missing.append("缺少听辨题")
    qids = [q.get("id") for q in quizzes]
    if len(qids) != len(set(qids)):
        missing.append("听辨题 id 重复")
    for q in quizzes:
        if len(q.get("options") or []) < 2:
            missing.append(f"听辨题 {q.get('id')} 选项不足 2 个")
        if not isinstance(q.get("answerIndex"), int) or not 0 <= q["answerIndex"] < len(q.get("options") or []):
            missing.append(f"听辨题 {q.get('id')} answerIndex 非法")
        if not q.get("stimulusMediaId"):
            missing.append(f"听辨题 {q.get('id')} 缺少题干音频")
    practice = content.get("practice") or []
    if not 3 <= len(practice) <= 5:
        missing.append("练习步骤须为 3–5 步")
    pids = [p.get("id") for p in practice]
    if len(pids) != len(set(pids)):
        missing.append("练习步骤 id 重复")
    art = content.get("articulation") or {}
    if not art.get("description"):
        missing.append("缺少构形说明")
    frames = (art.get("sagittal") or {}).get("keyframes") or []
    missing.extend(validate_sagittal_keyframes(frames))
    for m in art.get("media") or []:
        if m.get("mediaId") and not m.get("altText"):
            missing.append("构形媒体缺少替代文本")
    demos = content.get("demos") or []
    if not any(d.get("speed") == "normal" and d.get("mediaId") for d in demos):
        missing.append("缺少正常语速示范音频")
    for d in demos:
        if d.get("mediaId") and not d.get("text"):
            missing.append("示范音频缺少对应文字")
    det = content.get("detection") or {}
    if not det.get("promptText"):
        missing.append("缺少朗读提示词")
    if not det.get("evaluationText"):
        missing.append("缺少评测文本")
    if not det.get("sampleMediaId"):
        missing.append("缺少参考示范（标准曲线来源）")
    if not det.get("fourStepTemplates"):
        missing.append("缺少四步反馈模板")
    if not (content.get("misconceptions") or []):
        missing.append("缺少误区说明")
    prof = content.get("professional") or {}
    if not prof.get("description"):
        missing.append("缺少专业折叠说明")
    if not (prof.get("sources") or []):
        missing.append("缺少资料来源与授权")
    # 引用的媒体必须存在且未删除
    all_media = _collect_media_ids(content)
    for mid in all_media:
        if mid and db.get(MediaAssetRow, mid) is None:
            missing.append(f"媒体不存在：{mid}")
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


def compute_standard_curve(db: Session, content: dict) -> dict | None:
    """发布时预计算标准曲线：参考示范 F0 → 按参考发音人音域换算 T 值 → 冻结
    （决策图 #16）。"""
    det = content.get("detection") or {}
    media_id = det.get("sampleMediaId")
    speaker_id = det.get("referenceSpeakerId")
    asset = db.get(MediaAssetRow, media_id) if media_id else None
    speaker = db.get(ReferenceSpeakerRow, speaker_id) if speaker_id else None
    if asset is None or speaker is None:
        return None
    from app.acoustics import analysis as acx
    from app.scoring.usecases import get_provider

    path = config.DATA_DIR / asset.storage_path
    if not path.exists():
        return None
    try:
        provider = get_provider()
        prov = provider.evaluate(str(path), det.get("evaluationText", ""))
        f0res = acx.extract_f0(path)
    except Exception:
        return None
    if not f0res.reliable:
        return None
    import numpy as np

    frames_t = np.array([fr["t"] for fr in f0res.frames], dtype=float)
    frames_hz = np.array([fr.get("hz", np.nan) for fr in f0res.frames], dtype=float)
    segments = []
    for syl in prov.syllables:
        mask = (frames_t >= syl.t0) & (frames_t <= syl.t1) & np.isfinite(frames_hz)
        t_sel, hz_sel = frames_t[mask], frames_hz[mask]
        if t_sel.size < 3:
            continue
        span = t_sel[-1] - t_sel[0]
        tv = acx.to_t_values(hz_sel, speaker.f_lo, speaker.f_hi)
        points = [{"t": round(float((ti - t_sel[0]) / span), 4), "v": round(float(v), 3)}
                  for ti, v in zip(t_sel, tv) if np.isfinite(v)]
        if not points:
            continue
        segments.append({"syllable": syl.text, "toneValue": syl.tone_value, "points": points})
    if not segments:
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
        "scale": "T",
        "algorithmVersion": acx.ALGORITHM_VERSION,
        "referenceSpeakerId": speaker.id,
        "segments": segments,
    }
    if reference_region:
        curve["referenceRegion"] = reference_region
    return curve


def _rebuild_media_refs(db: Session, *, level_id: str | None, article_slug: str | None,
                        version_id: str, content: dict) -> None:
    """发布/回退时重建该对象全部版本的媒体引用；下架时由调用方整体移除。
    引用决定公开可读性（下架后即时不可读）。"""
    if level_id:
        old_ids = [v.id for v in db.query(LevelVersionRow)
                   .filter(LevelVersionRow.level_id == level_id).all()]
        db.query(MediaRefRow).filter(MediaRefRow.version_id.in_(old_ids)).delete(
            synchronize_session=False)
    if article_slug:
        old_ids = [v.id for v in db.query(ArticleVersionRow)
                   .filter(ArticleVersionRow.article_slug == article_slug).all()]
        db.query(MediaRefRow).filter(MediaRefRow.version_id.in_(old_ids)).delete(
            synchronize_session=False)
    for mid in _collect_media_ids(content):
        if mid:
            db.add(MediaRefRow(media_id=mid, version_id=version_id))
    if article_slug and content.get("demoMediaId"):
        db.add(MediaRefRow(media_id=content["demoMediaId"], version_id=version_id))


def publish_level(db: Session, level_id: str, *, admin_actor: str,
                  request_id: str | None, change_note: str | None = None) -> dict:
    """发布（或重新发布）：前置检查 → 标准曲线 → 新版本 → 引用重建 → 审计；
    任一步失败整体回滚。"""
    from app.platform.audit import audit

    level = db.get(LevelRow, level_id)
    draft = db.get(LevelDraftRow, level_id)
    if level is None or draft is None:
        raise ApiError(404, "NOT_FOUND", "关卡不存在")
    content = JSONText.load(draft.content, {})
    missing = precheck_level(db, content)
    if missing:
        raise ApiError(422, "VALIDATION_ERROR",
                       "发布前置检查未通过：" + "；".join(missing),
                       data={"missing": missing})
    curve = compute_standard_curve(db, content)
    if curve is None:
        raise ApiError(422, "VALIDATION_ERROR",
                       "参考示范无法提取有效音高，不能生成标准曲线")
    content["standardCurve"] = curve
    last = (db.query(LevelVersionRow).filter(LevelVersionRow.level_id == level_id)
            .order_by(LevelVersionRow.version.desc()).first())
    version_no = (last.version + 1) if last else 1
    version = LevelVersionRow(
        id=new_id("lv_"), level_id=level_id, version=version_no,
        rule_version=config.RULE_VERSION, content=JSONText.dump(content),
        change_note=change_note, published_by=admin_actor, published_at=now(),
    )
    db.add(version)
    db.flush()
    level.current_version_id = version.id
    level.status = "published"
    level.updated_at = now()
    _rebuild_media_refs(db, level_id=level_id, article_slug=None,
                        version_id=version.id, content=content)
    audit.log(db, action="publish", object_type="level", object_id=level_id,
              actor_type="admin", actor_id=admin_actor,
              before={"status": level.status},
              after={"status": "published", "version": version_no},
              reason=change_note, request_id=request_id)
    db.commit()
    return {"levelId": level_id, "contentVersion": version_no,
            "standardCurveSegments": len(curve["segments"])}


def unpublish_level(db: Session, level_id: str, *, admin_actor: str,
                    request_id: str | None, reason: str | None) -> dict:
    from app.platform.audit import audit

    level = db.get(LevelRow, level_id)
    if level is None or level.status != "published":
        raise ApiError(404, "NOT_FOUND", "关卡不存在或未发布")
    before_version = level.current_version_id
    level.status = "unpublished"
    level.updated_at = now()
    # 移除该关全部引用：公开媒体立即不可读
    old_ids = [v.id for v in db.query(LevelVersionRow)
               .filter(LevelVersionRow.level_id == level_id).all()]
    db.query(MediaRefRow).filter(MediaRefRow.version_id.in_(old_ids)).delete(
        synchronize_session=False)
    affected = _articles_referencing_level(db, level_id)
    audit.log(db, action="unpublish", object_type="level", object_id=level_id,
              actor_type="admin", actor_id=admin_actor,
              before={"status": "published", "version": before_version},
              after={"status": "unpublished"}, reason=reason, request_id=request_id)
    db.commit()
    return {"levelId": level_id, "affectedArticles": affected}


def rollback_level(db: Session, level_id: str, *, admin_actor: str,
                   request_id: str | None) -> dict:
    """回退 = 以上一公开版本内容插入新版本再走发布（不改写历史）。"""
    level = db.get(LevelRow, level_id)
    if level is None or not level.current_version_id:
        raise ApiError(404, "NOT_FOUND", "关卡不存在")
    versions = (db.query(LevelVersionRow).filter(LevelVersionRow.level_id == level_id)
                .order_by(LevelVersionRow.version.desc()).all())
    if len(versions) < 2:
        raise ApiError(422, "VALIDATION_ERROR", "没有更早的公开版本可回退")
    target = versions[1]
    draft = db.get(LevelDraftRow, level_id)
    if draft is None:
        raise ApiError(404, "NOT_FOUND", "关卡草稿不存在")
    # 把上一公开版本内容写回草稿再发布
    draft.content = target.content
    draft.revision += 1
    draft.updated_at = now()
    db.commit()
    return publish_level(db, level_id, admin_actor=admin_actor, request_id=request_id,
                         change_note=f"回退到版本 {target.version}")


def _articles_referencing_level(db: Session, level_id: str) -> list[dict]:
    out = []
    for a in db.query(ArticleRow).filter(ArticleRow.status == "published").all():
        v = db.get(ArticleVersionRow, a.current_version_id) if a.current_version_id else None
        if not v:
            continue
        c = JSONText.load(v.content, {})
        if level_id in (c.get("relatedLevelIds") or []):
            out.append({"slug": a.slug, "title": c.get("title", "")})
    return out


# ---------------- 文章治理 ----------------

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
        missing.append("缺少可播放示范（FR-505）")
    if not (content.get("references") or []):
        missing.append("缺少参考资料（FR-506）")
    if not (content.get("practice") or []):
        missing.append("缺少短练习（FR-502）")
    if content.get("demoMediaId") and db.get(MediaAssetRow, content["demoMediaId"]) is None:
        missing.append("示范媒体不存在")
    return missing


def publish_article(db: Session, slug: str, *, admin_actor: str,
                    request_id: str | None, change_note: str | None = None) -> dict:
    from app.platform.audit import audit

    article = db.get(ArticleRow, slug)
    draft = db.get(ArticleDraftRow, slug)
    if article is None or draft is None:
        raise ApiError(404, "NOT_FOUND", "文章不存在")
    content = JSONText.load(draft.content, {})
    missing = precheck_article(db, content)
    if missing:
        raise ApiError(422, "VALIDATION_ERROR",
                       "文章发布前置检查未通过：" + "；".join(missing),
                       data={"missing": missing})
    last = (db.query(ArticleVersionRow).filter(ArticleVersionRow.article_slug == slug)
            .order_by(ArticleVersionRow.version.desc()).first())
    version_no = (last.version + 1) if last else 1
    version = ArticleVersionRow(
        id=new_id("av_"), article_slug=slug, version=version_no,
        content=JSONText.dump(content), change_note=change_note,
        published_by=admin_actor, published_at=now(),
    )
    db.add(version)
    db.flush()
    article.current_version_id = version.id
    article.status = "published"
    article.updated_at = now()
    _rebuild_media_refs(db, level_id=None, article_slug=slug,
                        version_id=version.id, content=content)
    audit.log(db, action="publish", object_type="article", object_id=slug,
              actor_type="admin", actor_id=admin_actor,
              after={"status": "published", "version": version_no},
              reason=change_note, request_id=request_id)
    db.commit()
    return {"slug": slug, "contentVersion": version_no}


def unpublish_article(db: Session, slug: str, *, admin_actor: str,
                      request_id: str | None, reason: str | None) -> dict:
    from app.platform.audit import audit

    article = db.get(ArticleRow, slug)
    if article is None or article.status != "published":
        raise ApiError(404, "NOT_FOUND", "文章不存在或未发布")
    article.status = "unpublished"
    article.updated_at = now()
    old_ids = [v.id for v in db.query(ArticleVersionRow)
               .filter(ArticleVersionRow.article_slug == slug).all()]
    db.query(MediaRefRow).filter(MediaRefRow.version_id.in_(old_ids)).delete(
        synchronize_session=False)
    audit.log(db, action="unpublish", object_type="article", object_id=slug,
              actor_type="admin", actor_id=admin_actor,
              before={"status": "published"}, after={"status": "unpublished"},
              reason=reason, request_id=request_id)
    db.commit()
    return {"slug": slug}


def rollback_article(db: Session, slug: str, *, admin_actor: str,
                     request_id: str | None) -> dict:
    article = db.get(ArticleRow, slug)
    if article is None:
        raise ApiError(404, "NOT_FOUND", "文章不存在")
    versions = (db.query(ArticleVersionRow).filter(ArticleVersionRow.article_slug == slug)
                .order_by(ArticleVersionRow.version.desc()).all())
    if len(versions) < 2:
        raise ApiError(422, "VALIDATION_ERROR", "没有更早的公开版本可回退")
    draft = db.get(ArticleDraftRow, slug)
    draft.content = versions[1].content
    draft.revision += 1
    draft.updated_at = now()
    db.commit()
    return publish_article(db, slug, admin_actor=admin_actor, request_id=request_id,
                           change_note=f"回退到版本 {versions[1].version}")


# ---------------- 标定文本 / 熔断 ----------------

def get_active_calibration_text(db: Session) -> CalibrationTextRow | None:
    return (db.query(CalibrationTextRow)
            .filter(CalibrationTextRow.active.is_(True))
            .order_by(CalibrationTextRow.id.desc()).first())


def set_detection_switch(db: Session, *, level_id: str | None, enabled: bool,
                         reason: str, admin_actor: str, request_id: str | None) -> dict:
    from app.platform.audit import audit

    q = db.query(DetectionSwitchRow)
    if level_id:
        row = q.filter(DetectionSwitchRow.level_id == level_id).one_or_none()
    else:
        row = q.filter(DetectionSwitchRow.level_id.is_(None)).one_or_none()
    if row is None:
        row = DetectionSwitchRow(level_id=level_id, enabled=enabled, reason=reason,
                                 operated_by=admin_actor, updated_at=now())
        db.add(row)
    else:
        row.enabled = enabled
        row.reason = reason
        row.operated_by = admin_actor
        row.updated_at = now()
    audit.log(db, action="detection_switch", object_type="level",
              object_id=level_id or "global", actor_type="admin", actor_id=admin_actor,
              after={"enabled": enabled}, reason=reason, request_id=request_id)
    db.commit()
    return {"levelId": level_id, "enabled": enabled}
