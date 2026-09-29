# §6.4 Escalation FSM
ESCALATION_STATES = {
    "open",
    "claimed",
    "resolved",
    "auto_resolved"
}

ALLOWED_TRANSITIONS = {
    "open": ["claimed", "auto_resolved"],
    "claimed": ["resolved", "open"],
    "resolved": [],
    "auto_resolved": []
}

class InvalidTransition(Exception):
    pass

def validate_transition(current: str, new: str) -> None:
    if new not in ALLOWED_TRANSITIONS.get(current, []):
        raise InvalidTransition(f"Cannot transition escalation from {current} to {new}")
