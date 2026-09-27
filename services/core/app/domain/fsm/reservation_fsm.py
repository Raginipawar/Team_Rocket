# §6.3 Reservation FSM
RESERVATION_STATES = {
    "held",
    "confirmed",
    "consumed",
    "released",
    "expired"
}

ALLOWED_TRANSITIONS = {
    "held": ["confirmed", "released", "expired"],
    "confirmed": ["consumed", "released"],
    "consumed": [],
    "released": [],
    "expired": []
}

class InvalidTransition(Exception):
    pass

def validate_transition(current: str, new: str) -> None:
    if new not in ALLOWED_TRANSITIONS.get(current, []):
        raise InvalidTransition(f"Cannot transition reservation from {current} to {new}")
