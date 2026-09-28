"""A provides to B (work-distribution.md §4.1). Real body: technical.md §18 --
per-role response projection (patient/family/paramedic/hospital/ops), used by
both REST responses and WS event fan-out so a family viewer never sees
clinical fields (tested by T31). Needs the real emergency/ambulance/hospital
row shapes from B's models to know what to strip -- stub passes through
unfiltered so callers can wire the call site today; DO NOT rely on this for
privacy before the real projections land."""

from typing import Any

_ROLES = ("patient", "family", "paramedic", "hospital_staff", "ops")


def project(role: str, obj: Any) -> dict:
    if role not in _ROLES:
        raise ValueError(f"unknown role: {role}")
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return dict(obj)
    return dict(vars(obj))
