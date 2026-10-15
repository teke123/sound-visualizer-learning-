"""identity 用例：注册、登录（安全绑定 sid + 归属迁移）、退出、同意决定、
撤回、注销、dataEpoch。自研轻量认证（ADR-5/#8）：argon2 + 服务端会话表。"""
from __future__ import annotations

import datetime
import hashlib
import re

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.orm import Session

from app import config
from app.db import now
from app.ids import new_id, new_token
from app.identity.models import (
    AnonSessionRow, AuthSessionRow, ConsentDecisionRow, UserRow, UsernameTombstoneRow,
)
from app.platform.envelope import ApiError

_ph = PasswordHasher()
USERNAME_RE = re.compile(r"^[\w\u4e00-\u9fff]{3,32}$", re.UNICODE)

AUTH_SESSION_TTL = datetime.timedelta(days=30)


# ---------------- sid（匿名会话） ----------------

def ensure_sid(db: Session, cookie_sid: str | None) -> tuple[str, bool]:
    """返回 (sid, 新签发?)。首次按需签发不可猜测随机 ID（决策图 #4）。"""
    if cookie_sid:
        row = db.get(AnonSessionRow, cookie_sid)
        if row is not None:
            return cookie_sid, False
    sid = new_token(18)
    db.add(AnonSessionRow(sid=sid, created_at=now()))
    db.commit()
    return sid, True


def rotate_sid(db: Session, old_sid: str | None) -> str:
    """退出 / 切换账号 / 访客重置：轮换 sid，断开旧绑定。"""
    if old_sid:
        row = db.get(AnonSessionRow, old_sid)
        if row is not None:
            row.bound_user_id = None
    sid = new_token(18)
    db.add(AnonSessionRow(sid=sid, created_at=now()))
    db.commit()
    return sid


# ---------------- 注册 / 认证 ----------------

def register_user(db: Session, *, username: str, password: str, request_id: str | None) -> dict:
    if not USERNAME_RE.match(username or ""):
        raise ApiError(422, "VALIDATION_ERROR",
                       "用户名须为 3–32 位字母、数字、下划线或中文")
    if not password or len(password) < 8:
        raise ApiError(422, "VALIDATION_ERROR", "密码至少 8 位")
    lower = username.lower()
    if db.query(UserRow).filter(UserRow.username_lower == lower,
                                UserRow.deleted_at.is_(None)).count():
        raise ApiError(409, "USERNAME_TAKEN", "用户名已被使用")
    tomb = hashlib.sha256(lower.encode("utf-8")).hexdigest()
    if db.get(UsernameTombstoneRow, tomb):
        raise ApiError(409, "USERNAME_TAKEN", "用户名已被使用")
    user = UserRow(
        id=new_id("u_"), username=username, username_lower=lower,
        password_hash=_ph.hash(password), data_epoch=1,
        created_at=now(),
    )
    db.add(user)
    from app.platform.audit import audit

    audit.log(db, action="register", object_type="user", object_id=user.id,
              actor_type="user", actor_id=user.id, request_id=request_id)
    db.commit()
    return {"accountId": user.id, "username": user.username}


def verify_login(db: Session, *, username: str, password: str) -> UserRow:
    lower = (username or "").lower()
    user = db.query(UserRow).filter(UserRow.username_lower == lower,
                                    UserRow.deleted_at.is_(None)).one_or_none()
    if user is None:
        raise ApiError(401, "INVALID_CREDENTIALS", "用户名或密码不正确")
    try:
        _ph.verify(user.password_hash, password or "")
    except VerifyMismatchError:
        raise ApiError(401, "INVALID_CREDENTIALS", "用户名或密码不正确") from None
    if _ph.check_needs_rehash(user.password_hash):
        user.password_hash = _ph.hash(password)
    return user


def create_auth_session(db: Session, user_id: str) -> str:
    token = new_token(24)
    db.add(AuthSessionRow(session_id=token, user_id=user_id,
                          created_at=now(), expires_at=now() + AUTH_SESSION_TTL))
    db.commit()
    return token


def resolve_auth_user(db: Session, auth_cookie: str | None) -> UserRow | None:
    if not auth_cookie:
        return None
    row = db.get(AuthSessionRow, auth_cookie)
    if row is None or row.revoked_at is not None or row.expires_at < now():
        return None
    user = db.get(UserRow, row.user_id)
    if user is None or user.deleted_at is not None:
        return None
    return user


def bind_sid_to_user(db: Session, *, sid: str, user_id: str) -> None:
    """登录绑定：sid 下临时资源归属改为账号（audio/recording/缓存/会话音域）。"""
    from app.acoustics.models import AudioRow
    from app.detection.models import RecordingRow
    from app.scoring.models import PitchRangeRow
    from app.scoring.usecases import migrate_score_cache_owner

    anon = db.get(AnonSessionRow, sid)
    if anon is not None:
        anon.bound_user_id = user_id
    for row in db.query(AudioRow).filter(AudioRow.owner_type == "sid",
                                         AudioRow.owner_id == sid).all():
        row.owner_type, row.owner_id = "user", user_id
    for row in db.query(RecordingRow).filter(RecordingRow.owner_type == "sid",
                                             RecordingRow.owner_id == sid).all():
        row.owner_type, row.owner_id = "user", user_id
    for row in db.query(PitchRangeRow).filter(PitchRangeRow.owner_type == "sid",
                                              PitchRangeRow.owner_id == sid).all():
        row.owner_type, row.owner_id = "user", user_id
    migrate_score_cache_owner(db, from_type="sid", from_id=sid,
                              to_type="user", to_id=user_id)
    db.flush()


def logout(db: Session, *, auth_cookie: str | None, sid: str | None) -> None:
    if auth_cookie:
        row = db.get(AuthSessionRow, auth_cookie)
        if row and row.revoked_at is None:
            row.revoked_at = now()
    db.commit()


# ---------------- 同意 ----------------

def consent_status(db: Session, user: UserRow) -> str:
    """当前状态从历史派生：无记录为 none，否则最近一次决定。"""
    last = (db.query(ConsentDecisionRow).filter(ConsentDecisionRow.user_id == user.id)
            .order_by(ConsentDecisionRow.created_at.desc(), ConsentDecisionRow.id.desc())
            .first())
    if last is None:
        return "none"
    return last.decision


def consent_granted(db: Session, user: UserRow) -> bool:
    return consent_status(db, user) == "granted"


def grant_consent(db: Session, *, user: UserRow, text_version: str,
                  request_id: str | None) -> tuple[str, dict]:
    """授予同意；已是 granted 不追加记录，只重跑转存（转存重试入口）。"""
    from app.archive.usecases import transfer_session_records
    from app.platform.audit import audit

    if text_version != config.CONSENT_TEXT_VERSION:
        raise ApiError(409, "CONTENT_VERSION_CHANGED",
                       "同意文案版本已更新，请刷新后重新查看")
    status = consent_status(db, user)
    consent_id = None
    if status != "granted":
        consent_id = new_id("cd_")
        db.add(ConsentDecisionRow(
            id=consent_id, user_id=user.id, decision="granted",
            consent_text_version=text_version, request_id=request_id, created_at=now(),
        ))
        audit.log(db, action="consent_granted", object_type="user", object_id=user.id,
                  actor_type="user", actor_id=user.id, request_id=request_id)
    # 转存（单事务；含音域升级）
    sid = _bound_sid(db, user.id)
    transfer = {"status": "none", "transferredCount": 0, "calibrationUpgraded": False}
    if sid:
        transfer = transfer_session_records(db, sid=sid, user_id=user.id,
                                            consent_id=consent_id)
    db.commit()
    return consent_id or "existing", transfer


def _bound_sid(db: Session, user_id: str) -> str | None:
    row = db.query(AnonSessionRow).filter(AnonSessionRow.bound_user_id == user_id) \
        .order_by(AnonSessionRow.created_at.desc()).first()
    return row.sid if row else None


def reject_consent(db: Session, *, user: UserRow, text_version: str,
                   request_id: str | None) -> None:
    if text_version != config.CONSENT_TEXT_VERSION:
        raise ApiError(409, "CONTENT_VERSION_CHANGED", "同意文案版本已更新，请刷新后重新查看")
    db.add(ConsentDecisionRow(
        id=new_id("cd_"), user_id=user.id, decision="rejected",
        consent_text_version=text_version, request_id=request_id, created_at=now(),
    ))
    db.commit()


def revoke_consent(db: Session, *, user: UserRow, request_id: str | None) -> None:
    """撤回：dataEpoch+1、按 D-17 全量删除、反馈去引用、审计匿名化。重复调用幂等。"""
    from app.archive.usecases import purge_user_data
    from app.platform.audit import audit

    if consent_status(db, user) == "revoked":
        return
    db.add(ConsentDecisionRow(
        id=new_id("cd_"), user_id=user.id, decision="revoked",
        consent_text_version=config.CONSENT_TEXT_VERSION,
        request_id=request_id, created_at=now(),
    ))
    user.data_epoch += 1
    purge_user_data(db, user_id=user.id, request_id=request_id,
                    include_learning=True, include_ranges=True)
    audit.log(db, action="consent_revoked", object_type="user", object_id=user.id,
              actor_type="user", actor_id=user.id, request_id=request_id,
              after={"dataEpoch": user.data_epoch})
    db.commit()


def delete_account(db: Session, *, user: UserRow, password: str,
                   request_id: str | None) -> None:
    """注销：校验密码 → 撤回范围清理 → 用户名墓碑 → 匿名化 → 全部会话失效。"""
    from app.archive.usecases import purge_user_data
    from app.platform.audit import audit

    try:
        _ph.verify(user.password_hash, password or "")
    except VerifyMismatchError:
        raise ApiError(401, "INVALID_CREDENTIALS", "密码不正确") from None
    db.add(ConsentDecisionRow(
        id=new_id("cd_"), user_id=user.id, decision="revoked",
        consent_text_version=config.CONSENT_TEXT_VERSION,
        request_id=request_id, created_at=now(),
    ))
    user.data_epoch += 1
    purge_user_data(db, user_id=user.id, request_id=request_id,
                    include_learning=True, include_ranges=True)
    db.add(UsernameTombstoneRow(
        username_hash=hashlib.sha256(user.username_lower.encode("utf-8")).hexdigest(),
        created_at=now(),
    ))
    for row in db.query(AuthSessionRow).filter(AuthSessionRow.user_id == user.id).all():
        row.revoked_at = now()
    user.deleted_at = now()
    user.username = f"deleted_{user.id[:8]}"
    user.username_lower = user.username
    user.password_hash = ""
    audit.anonymize_user(db, user.id)
    audit.log(db, action="account_deleted", object_type="user", object_id=user.id,
              actor_type="anonymized", request_id=request_id)
    db.commit()
