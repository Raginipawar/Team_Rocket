import logging
from uuid import UUID
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...security.deps import require_role
from ...db.engine import get_db
from ...domain.reservations import accept_hospital_request, reject_hospital_request, walk_in_override
from ...domain.handoff import record_patient_received
from ...domain.clinical import handle_unknown_patient_merge
from ...domain.notify import notify_patient_and_family
from ...domain.integration_sync import sync_hospital_from_api, SyncError
from ...db.repos.hospitals import get_hospital, update_last_confirmed
from ...db.repos.rooms import list_rooms, patch_room
from ...db.repos.resources import get_resources, patch_resource
from ...db.repos.hospital_requests import list_pending_requests, list_all_requests, get_hospital_request, list_incoming_ambulances
from ...db.repos.staff import get_active_staff, list_staff_members, create_staff_member, get_shifts, update_shifts
from ...db.repos.analytics import get_hospital_analytics

router = APIRouter(prefix="/hospital", tags=["hospital"])


def _hospital_latlng(hospital) -> dict | None:
    if hospital.location is None:
        return None
    from geoalchemy2.shape import to_shape
    point = to_shape(hospital.location)
    return {"lat": point.y, "lng": point.x}
logger = logging.getLogger("hospital")

class AcceptRequest(BaseModel):
    room_id: Optional[UUID] = None
    staff_ids: Optional[List[UUID]] = None

class RejectRequest(BaseModel):
    reason_code: str
    note: Optional[str] = None

class IntegrationUpdate(BaseModel):
    integration_mode: str  # "manual" | "api"
    endpoint_url: Optional[str] = None
    api_key: Optional[str] = None  # omitted/None: leave the stored key unchanged


class RoomUpdate(BaseModel):
    status: str
    version: int
    override_reason: Optional[str] = None

class ResourceUpdate(BaseModel):
    available: int
    total: Optional[int] = None
    version: int

class HandoffReceived(BaseModel):
    receiving_staff_ids: Optional[List[UUID]] = None

class PatientMergeRequest(BaseModel):
    phone: str

class StaffCreate(BaseModel):
    name: str
    role: str

class ShiftsUpdate(BaseModel):
    shifts: List[dict]

def _check_scope(user, target_hospital_id: UUID):
    # user.hospital_id is a plain str (CurrentUser, security/deps.py);
    # target_hospital_id is a real uuid.UUID (ORM-mapped) -- UUID != str is
    # ALWAYS true in Python regardless of value, so this rejected every
    # single caller, including ones accessing their own real hospital.
    # Same bug class already found and fixed in domain/ops.py's claimer check.
    if str(user.hospital_id) != str(target_hospital_id):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied for this hospital"}})

def _calculate_freshness(last_confirmed_at: Optional[datetime]) -> str:
    if not last_confirmed_at:
        return "stale"
    delta = (datetime.now(timezone.utc) - last_confirmed_at).total_seconds()
    if delta < 1800:
        return "fresh"
    elif delta < 7200:
        return "aging"
    return "stale"

@router.get("/dashboard")
async def get_dashboard(
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    hospital_id = user.hospital_id
    hospital = await get_hospital(db, hospital_id)
    if not hospital:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Hospital not found"}})
    
    pending_requests = await list_pending_requests(db, hospital_id)
    rooms = await list_rooms(db, hospital_id)
    resources = await get_resources(db, hospital_id)
    staff_on_duty = await get_active_staff(db, hospital_id)
    incoming = await list_incoming_ambulances(db, hospital_id, at_door=False)
    at_door = await list_incoming_ambulances(db, hospital_id, at_door=True)
    
    # get_hospital/list_rooms return real ORM objects (db/repos/hospitals.py),
    # not dicts -- r.get(...)/hospital.get(...) would raise AttributeError on
    # every single real call (confirmed: this is exactly what happened the
    # first time this endpoint was ever hit with a real request).
    rooms_grouped: dict[str, list] = {}
    for r in rooms:
        rtype = getattr(r, "type", "unknown")
        rooms_grouped.setdefault(rtype, []).append({
            "id": str(r.id), "code": r.code, "type": r.type, "status": r.status,
            "priority_order": r.priority_order, "version": r.version,
        })

    return {
        "hospital": {"id": str(hospital.id), "name": hospital.name,
                     # Never included at all -- the dashboard's own "Incoming"
                     # map passes this straight to hospitals=[...] (app/hospital/
                     # page.tsx), so with no location it always rendered an
                     # empty array: no hospital pin, map just defaulted to a
                     # wide generic view with nothing to center/zoom on.
                     "location": _hospital_latlng(hospital),
                     "last_confirmed_at": hospital.last_confirmed_at.isoformat() if hospital.last_confirmed_at else None,
                     "hospital_code": hospital.hospital_code,
                     "integration_mode": hospital.integration_mode or "manual",
                     "integration_endpoint_url": hospital.integration_endpoint_url,
                     # Masked, never the real key, once one's been set -- the
                     # settings page shows "a key is saved", not the key itself.
                     "integration_api_key_set": bool(hospital.integration_api_key),
                     "integration_last_synced_at": hospital.integration_last_synced_at.isoformat() if hospital.integration_last_synced_at else None},
        "pending_requests": pending_requests,
        "rooms": rooms_grouped,
        "resources": resources,
        "staff_on_duty": staff_on_duty,
        "freshness": _calculate_freshness(hospital.last_confirmed_at),
        "incoming": incoming,
        "at_door": at_door,
    }


@router.patch("/integration")
async def update_integration(
    payload: IntegrationUpdate,
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db),
):
    """The registration form's Manual/API choice previously had nowhere to
    actually go afterward -- "API integration" was selectable but there was
    no settings page to enter an endpoint or key. This is deliberately
    minimal: stores the endpoint/key so the choice means something real, not
    a full integration gateway (no connection testing, webhooks or
    field-level permission UI -- those stay out of scope for now)."""
    if payload.integration_mode not in ("manual", "api"):
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": "integration_mode must be manual or api", "details": {}}})
    if payload.integration_mode == "api" and not payload.endpoint_url and not (await db.execute(
        text("SELECT integration_endpoint_url FROM hospitals WHERE id = :id"), {"id": user.hospital_id},
    )).scalar_one_or_none():
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": "endpoint_url is required to enable API integration", "details": {}}})

    if payload.api_key:
        await db.execute(
            text("UPDATE hospitals SET integration_mode = :mode, integration_endpoint_url = :url, integration_api_key = :key WHERE id = :id"),
            {"mode": payload.integration_mode, "url": payload.endpoint_url, "key": payload.api_key, "id": user.hospital_id},
        )
    else:
        await db.execute(
            text("UPDATE hospitals SET integration_mode = :mode, integration_endpoint_url = :url WHERE id = :id"),
            {"mode": payload.integration_mode, "url": payload.endpoint_url, "id": user.hospital_id},
        )
    await db.commit()

    # "Enter the link and key, data shows up" -- a separate Sync now click
    # after Save was one extra step nobody wants during a demo. A failed
    # first sync (bad URL/key typo) is reported back in the same response
    # rather than silently left for a later click to surface.
    sync_result = None
    if payload.integration_mode == "api":
        try:
            sync_result = await sync_hospital_from_api(db, str(user.hospital_id))
            await db.commit()
        except SyncError as e:
            sync_result = {"error": str(e)}

    return {"status": "updated", "integration_mode": payload.integration_mode, "sync": sync_result}


@router.post("/integration/sync")
async def sync_integration(
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db),
):
    """The settings page could toggle API mode and save an endpoint/key, but
    nothing ever actually called it -- this is the missing piece. Manually
    triggered (a real connected system would call this on its own schedule;
    this hackathon doesn't have a job scheduler to do that automatically
    yet, see domain/lifecycle_monitor.py's own doc comment on that gap)."""
    try:
        result = await sync_hospital_from_api(db, str(user.hospital_id))
    except SyncError as e:
        raise HTTPException(status_code=400, detail={"error": {"code": "SYNC_FAILED", "message": str(e), "details": {}}})
    await db.commit()
    return {"status": "synced", **result}


@router.post("/integration/disconnect")
async def disconnect_integration(
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text("UPDATE hospitals SET integration_mode = 'manual', integration_endpoint_url = NULL, "
             "integration_api_key = NULL, integration_last_synced_at = NULL WHERE id = :id"),
        {"id": user.hospital_id},
    )
    await db.commit()
    return {"status": "disconnected"}


@router.get("/requests")
async def get_requests(
    status: Optional[str] = Query(None),
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    hospital_id = user.hospital_id
    requests = await list_all_requests(db, hospital_id, status=status)
    return {"requests": requests}

@router.post("/requests/{request_id}/accept")
async def accept_request(
    request_id: UUID,
    payload: AcceptRequest,
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    # accept_hospital_request's real signature has no hospital_id/actor_id
    # params at all (room_id, staff_ids, responder_id) and does no ownership
    # check itself -- the previous call would have raised TypeError on the
    # very first real accept, and _check_scope (defined above, never called
    # anywhere) meant any hospital_staff user could accept another
    # hospital's request. Both fixed together.
    req = await get_hospital_request(db, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Request not found"}})
    _check_scope(user, req.hospital_id)
    try:
        await accept_hospital_request(
            db,
            request_id=request_id,
            room_id=payload.room_id,
            staff_ids=payload.staff_ids or [],
            responder_id=user.id,
        )
        try:
            hosp = await get_hospital(db, req.hospital_id)
            await notify_patient_and_family(
                db, str(req.emergency_id), "Hospital confirmed",
                f"{hosp.name if hosp else 'A hospital'} has confirmed and is preparing for you.",
                {"status": "hospital_confirmed"},
            )
        except Exception:
            logger.exception("notify_patient_and_family failed for emergency %s (hospital_confirmed)", req.emergency_id)
        await db.commit()
        return {"status": "accepted"}
    except ValueError as e:
        raise HTTPException(status_code=409, detail={"error": {"code": "RESOURCE_UNAVAILABLE", "message": str(e)}})

@router.post("/requests/{request_id}/reject")
async def reject_request(
    request_id: UUID,
    payload: RejectRequest,
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    req = await get_hospital_request(db, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Request not found"}})
    _check_scope(user, req.hospital_id)
    await reject_hospital_request(
        db,
        request_id=request_id,
        reason_code=payload.reason_code,
        note=payload.note,
        responder_id=user.id,
    )
    await db.commit()
    return {"status": "rejected"}

@router.patch("/rooms/{room_id}")
async def update_room(
    room_id: UUID,
    payload: RoomUpdate,
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    if payload.status == "reserved":
        if not payload.override_reason:
            raise HTTPException(status_code=409, detail={"error": {"code": "ROOM_RESERVED", "message": "Cannot override without reason"}})
        # walk in override logic
        await walk_in_override(db, room_id=room_id, hospital_id=user.hospital_id, reason=payload.override_reason, version=payload.version, actor_id=user.id)
    else:
        await patch_room(db, room_id=room_id, status=payload.status, version=payload.version, override_reason=None)
    await db.commit()
    return {"status": "updated"}

@router.patch("/resources/{resource_id}")
async def update_resource(
    resource_id: UUID,
    payload: ResourceUpdate,
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    await patch_resource(db, resource_id=resource_id, available=payload.available, total=payload.total, version=payload.version)
    await db.commit()
    return {"status": "updated"}

@router.post("/availability/confirm")
async def confirm_availability(
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    await update_last_confirmed(db, hospital_id=user.hospital_id)
    await db.commit()
    return {"status": "confirmed"}

@router.post("/handoffs/{emergency_id}/received")
async def handoff_received(
    emergency_id: UUID,
    payload: HandoffReceived,
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    await record_patient_received(db, emergency_id=emergency_id, hospital_id=user.hospital_id, receiving_staff_ids=payload.receiving_staff_ids, actor_id=user.id)
    await db.commit()
    return {"status": "recorded"}

@router.get("/staff")
async def get_staff(
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    staff = await list_staff_members(db, hospital_id=user.hospital_id)
    return {"staff": staff}

@router.post("/staff")
async def create_staff(
    payload: StaffCreate,
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    staff = await create_staff_member(db, hospital_id=user.hospital_id, name=payload.name, role=payload.role)
    await db.commit()
    return staff

@router.get("/staff/{staff_id}/shifts")
async def get_staff_shifts(
    staff_id: UUID,
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    shifts = await get_shifts(db, staff_id=staff_id, hospital_id=user.hospital_id)
    return {"shifts": shifts}

@router.post("/staff/{staff_id}/shifts")
async def update_staff_shifts(
    staff_id: UUID,
    payload: ShiftsUpdate,
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    await update_shifts(db, staff_id=staff_id, hospital_id=user.hospital_id, shifts=payload.shifts)
    await db.commit()
    return {"status": "updated"}

@router.get("/patients")
async def list_unidentified_patients(
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    # The frontend (app/hospital/patients/page.tsx) has always called this --
    # it just never existed on the backend (404 -> "Could not load"). Only
    # patients still unidentified (merged_into_user_id IS NULL) at THIS
    # hospital's emergencies.
    rows = (await db.execute(text("""
        SELECT p.temp_id, p.emergency_id, p.est_age, p.sex, p.created_at,
               em.status, em.received_at, (p.merged_into_user_id IS NOT NULL) AS merged
        FROM patients p
        JOIN emergencies em ON em.id = p.emergency_id
        WHERE em.hospital_id = :hid AND p.is_unknown = true
        ORDER BY em.received_at DESC NULLS LAST, p.created_at DESC
        LIMIT 100
    """), {"hid": user.hospital_id})).mappings().all()
    def _display(r) -> str:
        bits = ["Unknown"]
        if r["est_age"]:
            bits.append(f"~{r['est_age']}y")
        if r["sex"]:
            bits.append(r["sex"])
        return ", ".join(bits)

    return {"patients": [
        {
            "temp_id": r["temp_id"] or str(r["emergency_id"]),
            "emergency_id": str(r["emergency_id"]),
            "display": _display(r),
            "status": r["status"],
            "merged": bool(r["merged"]),
            "received_at": r["received_at"].isoformat() if r["received_at"] else None,
        }
        for r in rows
    ]}


@router.post("/patients/{temp_id}/merge")
async def merge_patient(
    temp_id: UUID,
    payload: PatientMergeRequest,
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    # Real signature is handle_unknown_patient_merge(db, temp_id, phone,
    # merged_by) -- the previous hospital_id=... keyword doesn't match any
    # real parameter name, would have raised TypeError on the first call.
    await handle_unknown_patient_merge(db, temp_id=str(temp_id), phone=payload.phone, merged_by=user.id)
    await db.commit()
    return {"status": "merged"}

@router.get("/analytics")
async def hospital_analytics(
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    data = await get_hospital_analytics(db, hospital_id=user.hospital_id, from_date=from_date, to_date=to_date)
    return {"data": data}
