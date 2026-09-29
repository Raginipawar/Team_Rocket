# §6.2 Ambulance FSM
AMBULANCE_STATES = {
    "idle",
    "dispatched",
    "en_route",
    "on_scene",
    "transporting",
    "at_hospital",
    "cleaning",
    "out_of_service"
}

ALLOWED_TRANSITIONS = {
    "idle": ["dispatched", "out_of_service"],
    "dispatched": ["en_route", "idle"],
    "en_route": ["on_scene", "idle"],
    "on_scene": ["transporting", "idle"],
    "transporting": ["at_hospital", "idle"],
    "at_hospital": ["cleaning", "idle"],
    "cleaning": ["idle", "out_of_service"],
    "out_of_service": ["idle"]
}

class InvalidTransition(Exception):
    pass

def validate_transition(current: str, new: str) -> None:
    if new not in ALLOWED_TRANSITIONS.get(current, []):
        raise InvalidTransition(f"Cannot transition ambulance from {current} to {new}")
