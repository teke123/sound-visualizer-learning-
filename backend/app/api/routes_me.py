"""当前会话、档案、学习事件与进度、同意管理、注销路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app import config
from app.api.deps import Actor, get_actor, require_consent, require_user
from app.archive import usecases as archive_uc
from app.identity import usecases as identity_uc
from app.platform.envelope import envelope

router = APIRouter(prefix="/api", tags=["session-archive"])


# ---------------- 当前会话 ----------------

@router.get("/session/recordings")
async def session_recordings(request: Request, actor: Actor = Depends(get_actor)):
    return envelope(request, archive_uc.session_recordings(
        actor.db, owner_type=actor.owner_type, owner_id=actor.owner_id))


@router.post("/session/reset")
async def session_reset(request: Request, actor: Actor = Depends(get_actor)):
    result = archive_uc.session_reset(actor.db, sid=actor.sid,
                                      owner_type=actor.owner_type,
                                      owner_id=actor.owner_id,
                                      is_guest=actor.is_guest)
    if result["newSidIssued"]:
        actor.rotate_sid()
    return envelope(request, result)


# ---------------- 档案（登录且同意） ----------------

@router.get("/me/recordings")
async def my_recordings(request: Request, levelId: str | None = None,
                        cursor: str | None = None, actor: Actor = Depends(get_actor)):
    user = require_consent(actor)
    return envelope(request, archive_uc.my_recordings(actor.db, user=user,
                                                      level_id=levelId, cursor=cursor))


@router.delete("/me/recordings")
async def clear_my_recordings(request: Request, actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    result = archive_uc.clear_archive(actor.db, user=user, request_id=actor.request_id)
    return envelope(request, result)


@router.get("/me/recordings/compare")
async def compare_recordings(request: Request, a: str, b: str,
                             actor: Actor = Depends(get_actor)):
    user = require_consent(actor)
    return envelope(request, archive_uc.compare_recordings(actor.db, user=user, a=a, b=b))


# ---------------- 学习事件与进度 ----------------

class EventItem(BaseModel):
    eventId: str
    levelId: str
    contentVersion: int
    kind: str
    detail: dict


class LearningEventsBody(BaseModel):
    events: list[EventItem]


@router.post("/learning-events")
async def learning_events(request: Request, body: LearningEventsBody,
                          actor: Actor = Depends(get_actor)):
    user = require_consent(actor)
    if not body.events or len(body.events) > archive_uc.EVENT_BATCH_LIMIT:
        from app.platform.envelope import ApiError

        raise ApiError(422, "VALIDATION_ERROR", "事件批次须为 1–50 条")
    result = archive_uc.accept_learning_events(
        actor.db, user=user,
        events=[e.model_dump() for e in body.events])
    return envelope(request, result)


@router.get("/me/progress")
async def my_progress(request: Request, actor: Actor = Depends(get_actor)):
    user = require_consent(actor)
    return envelope(request, archive_uc.derive_progress(actor.db, user=user))


# ---------------- 同意 ----------------

@router.get("/me/consent")
async def get_consent(request: Request, actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    from app.identity.models import ConsentDecisionRow

    rows = (actor.db.query(ConsentDecisionRow)
            .filter(ConsentDecisionRow.user_id == user.id)
            .order_by(ConsentDecisionRow.created_at).all())
    return envelope(request, {
        "status": identity_uc.consent_status(actor.db, user),
        "consentTextVersion": config.CONSENT_TEXT_VERSION,
        "currentConsentTextVersion": config.CONSENT_TEXT_VERSION,
        "consentText": config.CONSENT_TEXT,
        "timeline": [{
            "decision": r.decision, "consentTextVersion": r.consent_text_version,
            "createdAt": r.created_at.isoformat(),
        } for r in rows],
    })


class ConsentBody(BaseModel):
    decision: str                  # granted | rejected
    consentTextVersion: str


@router.post("/me/consent")
async def post_consent(request: Request, body: ConsentBody,
                       actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    if body.decision not in ("granted", "rejected"):
        from app.platform.envelope import ApiError

        raise ApiError(422, "VALIDATION_ERROR", "决定只允许 granted / rejected")
    if body.decision == "granted":
        consent_id, transfer = identity_uc.grant_consent(
            actor.db, user=user, text_version=body.consentTextVersion,
            request_id=actor.request_id)
        return envelope(request, {
            "consent": {"status": "granted",
                        "consentTextVersion": config.CONSENT_TEXT_VERSION},
            "transfer": transfer,
        })
    identity_uc.reject_consent(actor.db, user=user, text_version=body.consentTextVersion,
                               request_id=actor.request_id)
    return envelope(request, {
        "consent": {"status": "rejected", "consentTextVersion": None},
        "transfer": {"status": "none", "transferredCount": 0, "calibrationUpgraded": False},
    })


@router.delete("/me/consent")
async def revoke_consent(request: Request, actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    identity_uc.revoke_consent(actor.db, user=user, request_id=actor.request_id)
    return envelope(request, {"consent": {"status": "revoked"},
                              "dataEpoch": user.data_epoch})


class DeleteAccountBody(BaseModel):
    password: str


@router.delete("/me/account")
async def delete_account(request: Request, body: DeleteAccountBody,
                         actor: Actor = Depends(get_actor)):
    user = require_user(actor)
    identity_uc.delete_account(actor.db, user=user, password=body.password,
                               request_id=actor.request_id)
    actor.clear_auth_cookie()
    actor.rotate_sid()
    return envelope(request, {"deleted": True})
