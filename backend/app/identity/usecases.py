"""identity 用例：注册、登录、退出、注销。
自研轻量认证：argon2 + 服务端会话表。"""
from __future__ import annotations

import datetime
import re

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.orm import Session

from app.db import now
from app.ids import new_id, new_token
from app.identity.models import SessionRow, UserRow
from app.platform.envelope import ApiError

_ph = PasswordHasher()
# 用户名只允许小写字母与数字：输入域限定后无需大小写折叠列或特殊排序规则
USERNAME_RE = re.compile(r"^[a-z0-9]{3,32}$")

AUTH_SESSION_TTL = datetime.timedelta(days=30)

# 方言区/母语背景代码集（FR-107）：稳定代码便于分组统计与提示匹配；
# 标签文案由前端维护，后端只认代码
DIALECT_CODES = frozenset({
    "mandarin_north", "mandarin_southwest", "wu", "yue", "min", "xiang", "gan",
    "hakka", "english", "japanese", "korean", "other",
})

# 性别代码集（FR-107）：稳定代码便于音高参考与分组统计；标签文案由前端维护
GENDER_CODES = frozenset({"male", "female", "other"})


def _validated_dialect(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if value not in DIALECT_CODES:
        raise ApiError(422, "VALIDATION_ERROR",
                       "方言区/母语背景取值不在支持列表内")
    return value


def _validated_gender(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if value not in GENDER_CODES:
        raise ApiError(422, "VALIDATION_ERROR", "性别取值不在支持列表内")
    return value


def register_user(db: Session, *, username: str, password: str,
                  dialect_background: str | None = None,
                  gender: str | None = None) -> dict:
    if not USERNAME_RE.match(username or ""):
        raise ApiError(422, "VALIDATION_ERROR",
                       "用户名须为 3–32 位小写英文字母或数字")
    if not password or len(password) < 8:
        raise ApiError(422, "VALIDATION_ERROR", "密码至少 8 位")
    dialect = _validated_dialect(dialect_background)
    gender_code = _validated_gender(gender)
    if db.query(UserRow).filter(UserRow.username == username).count():
        raise ApiError(409, "USERNAME_TAKEN", "用户名已被使用")
    user = UserRow(
        id=new_id("u_"), username=username,
        password_hash=_ph.hash(password), created_at=now(),
        dialect_background=dialect, gender=gender_code,
    )
    db.add(user)
    db.commit()
    return {"accountId": user.id, "username": user.username,
            "dialectBackground": user.dialect_background,
            "gender": user.gender}


def update_profile(db: Session, *, user: UserRow,
                   dialect_background: str | None,
                   gender: str | None) -> dict:
    """设置/修改/清除方言区背景与性别（FR-106 / FR-107）；传 null 或空串即清除。"""
    user.dialect_background = _validated_dialect(dialect_background)
    user.gender = _validated_gender(gender)
    db.commit()
    return {"accountId": user.id, "username": user.username,
            "dialectBackground": user.dialect_background,
            "gender": user.gender}


def verify_login(db: Session, *, username: str, password: str) -> UserRow:
    username = (username or "").lower()
    user = db.query(UserRow).filter(UserRow.username == username).one_or_none()
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
    db.add(SessionRow(session_id=token, kind="user", user_id=user_id,
                      created_at=now(), expires_at=now() + AUTH_SESSION_TTL))
    db.commit()
    return token


def resolve_auth_user(db: Session, auth_cookie: str | None) -> UserRow | None:
    if not auth_cookie:
        return None
    row = db.get(SessionRow, auth_cookie)
    if row is None or row.kind != "user" or row.revoked_at is not None \
            or row.expires_at < now():
        return None
    return db.get(UserRow, row.user_id)


def logout(db: Session, *, auth_cookie: str | None) -> None:
    if auth_cookie:
        row = db.get(SessionRow, auth_cookie)
        if row and row.revoked_at is None:
            row.revoked_at = now()
    db.commit()


def delete_account(db: Session, *, user: UserRow, password: str) -> None:
    """注销（FR-108）：校验密码 → 音频文件进删除日志 → 删除账号。
    用户行删除后全部从属数据（会话/录音/音频/缓存/音域/反馈/标定）由外键级联清除，
    用户名随之释放。"""
    try:
        _ph.verify(user.password_hash, password or "")
    except VerifyMismatchError:
        raise ApiError(401, "INVALID_CREDENTIALS", "密码不正确") from None
    from app.acoustics.models import AudioRow
    from app.platform.deletion_log import deletion_log

    for audio in db.query(AudioRow).filter(AudioRow.user_id == user.id).all():
        deletion_log.append(kind="file", key=audio.storage_path)
    db.delete(user)
    db.commit()
