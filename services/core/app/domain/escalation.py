from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from services.core.app.db.models import Escalation # type: ignore
from services.core.app.db.repos.escalations import create_escalation, get_escalation

async def raise_escalation(
    db: AsyncSession,
    escalation_type: str,
    emergency_id: UUID | None,
    context: dict,
) -> Escalation:
    options = []
    
    if escalation_type == "mass_casualty":
        options = [
            {"id": "opt1", "action": "mci_allocation_plan", "label": "Call MCI Allocate", "is_default": True},
            {"id": "opt2", "action": "widen_radius", "label": "Widen search radius"},
            {"id": "opt3", "action": "manual_override", "label": "Manual Assignment"}
        ]
    elif escalation_type == "no_ambulance":
        options = [
            {"id": "opt1", "action": "widen_40km_bls", "label": "Widen 40km + BLS", "is_default": True},
            {"id": "opt2", "action": "force_assign_nearest", "label": "Force-assign nearest"},
            {"id": "opt3", "action": "notify_108", "label": "Notify 108 Public EMS"}
        ]
    elif escalation_type == "no_hospital":
        options = [
            {"id": "opt1", "action": "stabilise_nearest", "label": "Stabilise at nearest capable", "is_default": True},
            {"id": "opt2", "action": "best_partial_match", "label": "Best partial match"},
            {"id": "opt3", "action": "force_assign", "label": "Force assign"},
            {"id": "opt4", "action": "widen_radius", "label": "Widen radius"}
        ]
    elif escalation_type == "system_anomaly":
        options = [
            {"id": "opt1", "action": "conservative_fallback", "label": "Conservative default fallback", "is_default": True},
            {"id": "opt2", "action": "manual_review", "label": "Manual Review"}
        ]
        
    esc = await create_escalation(
        db,
        type=escalation_type,
        emergency_id=emergency_id,
        context_data=context,
        status="open",
        resolution_options=options
    )
    return esc

async def execute_escalation_option(
    db: AsyncSession, escalation_id: UUID, option_id: str, actor_type: str, actor_id: str
) -> None:
    esc = await get_escalation(db, escalation_id)
    if not esc: return
    
    if esc.type == "mass_casualty" and option_id == "opt1":
        # call mci_allocate
        pass
    elif esc.type == "no_ambulance" and option_id == "opt1":
        # widen to 40km+BLS for critical
        pass
    elif esc.type == "no_hospital" and option_id == "opt1":
        # stabilise at nearest stabilisation-capable
        pass
        
    esc.status = "resolved"
    esc.resolution_option_id = option_id
    await db.flush()
