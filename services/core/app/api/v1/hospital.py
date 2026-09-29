from uuid import UUID
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...security.deps import require_role
from ...db.engine import get_db
from ...domain.reservations import accept_hospital_request, reject_hospital_request, walk_in_override
from ...domain.handoff import record_patient_received
from ...domain.clinical import handle_unknown_patient_merge
from ...db.repos.hospitals import get_hospital, update_last_confirmed
from ...db.repos.rooms import list_rooms, patch_room
from ...db.repos.resources import get_resources, patch_resource
from ...db.repos.hospital_requests import list_pending_requests, list_all_requests
from ...db.repos.staff import get_active_staff, list_staff_members, create_staff_member, get_shifts, update_shifts
from ...db.repos.analytics import get_hospital_analytics

router = APIRouter(prefix="/hospital", tags=["hospital"])

class AcceptRequest(BaseModel):
    room_id: Optional[UUID] = None
    staff_ids: Optional[List[UUID]] = None

class RejectRequest(BaseModel):
    reason_code: str
    note: Optional[str] = None

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
    if user.hospital_id != target_hospital_id:
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
    
    rooms_grouped = {}
    for r in rooms:
        rtype = r.get("type", "unknown")
        if rtype not in rooms_grouped:
            rooms_grouped[rtype] = []
        rooms_grouped[rtype].append(r)
        
    return {
        "hospital": hospital,
        "pending_requests": pending_requests,
        "rooms": rooms_grouped,
        "resources": resources,
        "staff_on_duty": staff_on_duty,
        "freshness": _calculate_freshness(hospital.get("last_confirmed_at"))
    }

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
    try:
        res = await accept_hospital_request(
            db, 
            request_id=request_id, 
            hospital_id=user.hospital_id,
            room_id=payload.room_id,
            staff_ids=payload.staff_ids,
            actor_id=user.id
        )
        return {"status": "accepted", "reservation": res}
    except ValueError as e:
        raise HTTPException(status_code=409, detail={"error": {"code": "RESOURCE_UNAVAILABLE", "message": str(e)}})

@router.post("/requests/{request_id}/reject")
async def reject_request(
    request_id: UUID,
    payload: RejectRequest,
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    await reject_hospital_request(
        db,
        request_id=request_id,
        hospital_id=user.hospital_id,
        reason_code=payload.reason_code,
        note=payload.note,
        actor_id=user.id
    )
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
    return {"status": "updated"}

@router.patch("/resources/{resource_id}")
async def update_resource(
    resource_id: UUID,
    payload: ResourceUpdate,
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    await patch_resource(db, resource_id=resource_id, available=payload.available, total=payload.total, version=payload.version)
    return {"status": "updated"}

@router.post("/availability/confirm")
async def confirm_availability(
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    await update_last_confirmed(db, hospital_id=user.hospital_id)
    return {"status": "confirmed"}

@router.post("/handoffs/{emergency_id}/received")
async def handoff_received(
    emergency_id: UUID,
    payload: HandoffReceived,
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    await record_patient_received(db, emergency_id=emergency_id, hospital_id=user.hospital_id, receiving_staff_ids=payload.receiving_staff_ids, actor_id=user.id)
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
    return {"status": "updated"}

@router.post("/patients/{temp_id}/merge")
async def merge_patient(
    temp_id: UUID,
    payload: PatientMergeRequest,
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    res = await handle_unknown_patient_merge(db, temp_id=temp_id, phone=payload.phone, hospital_id=user.hospital_id)
    return {"status": "merged", "patient_id": res}

@router.get("/analytics")
async def hospital_analytics(
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    user = Depends(require_role('hospital_staff')),
    db: AsyncSession = Depends(get_db)
):
    data = await get_hospital_analytics(db, hospital_id=user.hospital_id, from_date=from_date, to_date=to_date)
    return {"data": data}
