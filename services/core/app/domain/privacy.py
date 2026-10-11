"""Real per-role response projection (technical.md Section18): a family
viewer must never receive clinical fields (T31), paramedics/hospital staff
need the clinical picture to act, and ops sees everything (audited
elsewhere, per audit.py). Used by both REST responses (api/v1/emergencies.py)
and the WS fan-out (realtime/ws.py) so neither path can leak a shape the
other was careful about.

Family uses an ALLOW-list, not a deny-list: a new clinical field added to
the Emergency model later defaults to HIDDEN from family until someone
explicitly adds it to the allow-list, rather than defaulting to LEAKED.
Every other role uses a deny-list of the few fields that are either another
person's PII or an internal-only signal nobody outside ops needs."""

from typing import Any

_ROLES = ("patient", "family", "paramedic", "hospital_staff", "developer")
# "developer" is the real DB role (db/migrations/0001_init.sql's users.role
# CHECK constraint: patient/paramedic/hospital_staff/developer -- there is
# no "ops" role in the schema; technical.md's "ops" is this role wearing a
# different hat). "family" is never a JWT role at all -- it's assigned
# explicitly by api/v1/emergencies.py's /track/{token} endpoint, since family
# access is by possessing a one-time token, not by being a registered user.

# Fields that identify this as an emergency-shaped payload (vs. an ambulance
# ping, hospital room update, etc.) -- used to decide which policy applies.
_EMERGENCY_MARKER_FIELDS = {"ai_acuity", "final_acuity", "transcript", "extracted", "raw_text"}

# Family: logistics only (status, who's coming, how long, when each step
# happened) -- never the clinical record itself. Per T31, this must never
# include transcript/extracted/raw_text/ai_*/final_*/required_ambulance_type/
# fragility/mlc_flag/prank_*/duplicate_of/predicted_resources/handover_note/
# caller_phone/caller_user_id/language/stt_confidence/location detail.
_EMERGENCY_FAMILY_ALLOWLIST = {
    "id", "status", "version",
    "ambulance_id", "hospital_id", "reservation_id", "ambulance",
    "eta_to_patient_sec", "eta_to_hospital_sec", "eta_low_sec", "eta_high_sec",
    "escalated",
    "received_at", "triaged_at", "assigned_at", "at_scene_at", "on_board_at",
    "hospital_confirmed_at", "arrived_hospital_at", "handed_off_at", "closed_at",
}

# A generic non-emergency payload (ambulance location ping, room status,
# etc.) that somehow reaches a family-role viewer -- no legitimate channel
# grants family that subscription today (realtime/ws.py's channel_allowed),
# but fail safe rather than pass through unfiltered if that ever changes.
_GENERIC_FAMILY_ALLOWLIST = {"id", "status", "name", "eta_sec"}

# Other roles are trusted operational roles that need the clinical picture
# to do their job -- deny-list just the handful of fields that are either
# someone else's PII or an internal-only signal (fraud/dedup scoring) that
# isn't anyone's job outside ops.
_DENY_BY_ROLE: dict[str, set[str]] = {
    "patient": {"ai_probs", "needs_review", "prank_score", "prank_verified", "duplicate_of", "caller_user_id"},
    "paramedic": {"prank_score", "prank_verified", "duplicate_of", "caller_user_id"},
    "hospital_staff": {"prank_score", "prank_verified", "duplicate_of", "caller_user_id", "caller_phone", "raw_text"},
    "developer": set(),  # ops/developer sees everything; access itself is audited (audit.py), not restricted here
}


def _as_dict(obj: Any) -> dict:
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return dict(vars(obj))


def project(role: str, obj: Any) -> dict:
    if role not in _ROLES:
        raise ValueError(f"unknown role: {role}")

    data = _as_dict(obj)

    if role == "family":
        # Misclassifying a non-emergency payload as emergency-shaped just
        # means a couple of extra harmless keys (e.g. "status") pass through
        # under the stricter list -- misclassifying the other way would hide
        # legitimate fields, never leak clinical ones, since both lists are
        # allow-lists. Fail-safe either way.
        is_emergency_shaped = any(k in data for k in _EMERGENCY_MARKER_FIELDS) or "eta_to_patient_sec" in data
        allowlist = _EMERGENCY_FAMILY_ALLOWLIST if is_emergency_shaped else _GENERIC_FAMILY_ALLOWLIST
        return {k: v for k, v in data.items() if k in allowlist}

    deny = _DENY_BY_ROLE.get(role, set())
    return {k: v for k, v in data.items() if k not in deny}
