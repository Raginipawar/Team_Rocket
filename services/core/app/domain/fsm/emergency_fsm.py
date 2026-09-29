"""Emergency state machine — technical.md §6.1.

Every transition is a single SQL UPDATE ... WHERE status=<expected> AND version=<expected>;
zero rows updated => 409 CONFLICT. Every transition writes audit_log and publishes a WS event
in the same unit of work (outbox pattern, §10.4).
"""
from __future__ import annotations

# Full allowed transition graph from technical.md §6.1
ALLOWED: dict[str, set[str]] = {
    "received":          {"triaged", "cancelled", "merged_duplicate"},
    "triaged":           {"dispatching", "cancelled"},
    "dispatching":       {"ambulance_assigned", "cancelled"},
    "ambulance_assigned":{"at_scene", "dispatching", "cancelled"},  # dispatching = re-dispatch
    "at_scene":          {"patient_on_board", "refused_transport", "cancelled"},
    "patient_on_board":  {"hospital_selecting"},
    "hospital_selecting":{"hospital_confirmed", "cancelled"},
    # hospital_selecting also allows divert: hospital_confirmed -> hospital_selecting (handled separately)
    "hospital_confirmed":{"arrived_hospital", "hospital_selecting"},  # hospital_selecting = divert
    "arrived_hospital":  {"handed_off"},
    "handed_off":        {"closed"},
    # terminal statuses
    "closed":            set(),
    "cancelled":         set(),
    "refused_transport": set(),
    "merged_duplicate":  set(),
}

ALL_STATUSES = frozenset(ALLOWED.keys())


def validate_transition(from_status: str, to_status: str) -> None:
    """Raise InvalidTransition if the transition is not in the allowed graph.

    Note: InvalidTransition is imported from errors.py at call time to avoid
    circular imports; this module just raises ValueError so the repo layer
    can wrap it.
    """
    allowed = ALLOWED.get(from_status)
    if allowed is None:
        raise ValueError(f"Unknown emergency status: '{from_status}'")
    if to_status not in allowed:
        raise ValueError(
            f"Emergency transition '{from_status}' → '{to_status}' is not allowed. "
            f"Allowed targets: {sorted(allowed) or 'none (terminal state)'}"
        )
