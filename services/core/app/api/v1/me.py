"""A's file (work-distribution.md §2.2). technical.md §7.3 -- profile,
contacts, push subscriptions.

/me/profile, /me/contacts, /me/emergencies never existed here at all --
only push-subscriptions did -- even though the real patient frontend
(app/patient/{profile,contacts,history}/page.tsx) already calls all three."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db.repos import family as family_repo
from app.db.repos import patient as patient_repo
from app.db.repos import push_subscriptions as push_repo
from app.db.session import get_session
from app.security.deps import CurrentUser, require_role

router = APIRouter()


class ConnectByCodeRequest(BaseModel):
    code: str


class HealthProfileUpdate(BaseModel):
    name: str | None = None
    dob: str | None = None
    sex: str | None = None
    blood_group: str | None = None
    allergies: list[str] = []
    conditions: list[str] = []
    medications: list[str] = []
    home_address: str | None = None
    notes: str | None = None
    version: int


class ContactCreate(BaseModel):
    name: str
    phone: str
    relation: str | None = None
    language: str | None = None


@router.post("/me/push-subscriptions", status_code=204)
async def register_push_subscription(body: dict, user: CurrentUser = Depends(require_role(
    "patient", "paramedic", "hospital_staff", "developer",
))) -> None:
    fcm_token = body["fcm_token"]
    async with get_session() as session:
        await push_repo.add_subscription(session, str(user.id), fcm_token)
        await session.commit()


@router.get("/me/profile")
async def get_profile(user: CurrentUser = Depends(require_role("patient"))) -> dict:
    async with get_session() as session:
        return await patient_repo.get_or_create_health_profile(session, user.id)


@router.put("/me/profile")
async def put_profile(payload: HealthProfileUpdate, user: CurrentUser = Depends(require_role("patient"))) -> dict:
    async with get_session() as session:
        try:
            result = await patient_repo.update_health_profile(
                session, user.id, name=payload.name, dob=payload.dob, sex=payload.sex,
                blood_group=payload.blood_group, allergies=payload.allergies,
                conditions=payload.conditions, medications=payload.medications,
                home_address=payload.home_address, notes=payload.notes,
                expected_version=payload.version,
            )
            await session.commit()
            return result
        except patient_repo.VersionConflict:
            raise HTTPException(status_code=409, detail={"error": {"code": "VERSION_CONFLICT", "message": "Profile was modified elsewhere", "details": {}}})


@router.get("/me/contacts")
async def get_contacts(user: CurrentUser = Depends(require_role("patient"))) -> list[dict]:
    async with get_session() as session:
        return await patient_repo.list_emergency_contacts(session, user.id)


@router.post("/me/contacts", status_code=201)
async def create_contact(payload: ContactCreate, user: CurrentUser = Depends(require_role("patient"))) -> dict:
    async with get_session() as session:
        try:
            result = await patient_repo.create_emergency_contact(
                session, user.id, name=payload.name, phone=payload.phone,
                relation=payload.relation, language=payload.language,
            )
            await session.commit()
            return result
        except patient_repo.TooManyContacts:
            raise HTTPException(status_code=409, detail={"error": {"code": "LIMIT_REACHED", "message": f"Maximum {patient_repo.MAX_CONTACTS} emergency contacts allowed", "details": {}}})


@router.delete("/me/contacts/{contact_id}", status_code=204)
async def delete_contact(contact_id: str, user: CurrentUser = Depends(require_role("patient"))) -> None:
    async with get_session() as session:
        deleted = await patient_repo.delete_emergency_contact(session, user.id, contact_id)
        if not deleted:
            raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Contact not found", "details": {}}})
        await session.commit()


@router.get("/me/emergencies")
async def get_my_emergencies(user: CurrentUser = Depends(require_role("patient"))) -> list[dict]:
    async with get_session() as session:
        rows = await patient_repo.list_my_emergencies(session, user.id)
        return [
            {
                "id": str(r["id"]),
                "status": r["status"],
                "acuity": r["final_acuity"] or r["ai_acuity"],
                "facility": r["final_facility"] or r["ai_facility"],
                "received_at": r["received_at"].isoformat() if r["received_at"] else None,
                "hospital_name": r["hospital_name"],
                "for_self": bool(r["for_self"]),
            }
            for r in rows
        ]


@router.get("/me/family-code")
async def get_family_code(user: CurrentUser = Depends(require_role("patient"))) -> dict:
    async with get_session() as session:
        code = await family_repo.get_or_create_family_code(session, user.id)
        await session.commit()
        return {"code": code}


@router.post("/me/family/connect")
async def connect_family(payload: ConnectByCodeRequest, user: CurrentUser = Depends(require_role("patient"))) -> dict:
    async with get_session() as session:
        try:
            result = await family_repo.connect_by_code(session, user.id, payload.code)
            await session.commit()
            return result
        except family_repo.CodeNotFound:
            raise HTTPException(404, detail={"error": {"code": "NOT_FOUND", "message": "No one has that code", "details": {}}})
        except family_repo.CannotWatchSelf:
            raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": "That's your own code", "details": {}}})


@router.get("/me/family")
async def list_family(user: CurrentUser = Depends(require_role("patient"))) -> list[dict]:
    async with get_session() as session:
        rows = await family_repo.list_watched(session, user.id)
        return [
            {
                "user_id": str(r["id"]), "name": r["name"], "phone": r["phone"],
                "blood_group": r["blood_group"], "active_emergency_status": r["active_emergency_status"],
            }
            for r in rows
        ]


@router.get("/me/family/{watched_user_id}/health")
async def get_family_health(watched_user_id: str, user: CurrentUser = Depends(require_role("patient"))) -> dict:
    async with get_session() as session:
        try:
            return await family_repo.get_watched_health(session, user.id, watched_user_id)
        except family_repo.NotConnected:
            raise HTTPException(403, detail={"error": {"code": "FORBIDDEN", "message": "Not connected to this person", "details": {}}})


@router.get("/me/family/{watched_user_id}/contact")
async def get_family_contact(watched_user_id: str, user: CurrentUser = Depends(require_role("patient"))) -> dict:
    async with get_session() as session:
        try:
            return await family_repo.get_watched_contact(session, user.id, watched_user_id)
        except family_repo.NotConnected:
            raise HTTPException(403, detail={"error": {"code": "FORBIDDEN", "message": "Not connected to this person", "details": {}}})
