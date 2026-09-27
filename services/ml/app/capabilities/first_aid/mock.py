"""Deterministic first-aid selection (technical.md §9.8: 'No generated medical
text, ever'). Not a mock in the usual sense -- this IS the real
implementation, since first-aid selection must never touch an LLM. Priority
order: absent breathing overrides everything (CPR), then choking, then severe
bleeding, then unresponsive-but-breathing (recovery position), then
facility-specific scripts, then a hardcoded (not generated) generic default."""

from app.util.protocols import load_all_first_aid

_GENERIC_DEFAULT = {
    "protocol_id": "generic_default",
    "title": {"en": "While waiting for the ambulance", "hi": "एम्बुलेंस का इंतज़ार करते समय", "mr": "रुग्णवाहिकेची वाट पाहताना"},
    "steps": {
        "en": ["Keep the person still and calm.", "Keep them warm and monitor their breathing.",
               "Do not give food, water, or medicine unless a paramedic tells you to."],
        "hi": ["व्यक्ति को स्थिर और शांत रखें।", "उन्हें गर्म रखें और सांस पर नज़र रखें।",
               "पैरामेडिक के कहने तक खाना, पानी, या दवा न दें।"],
        "mr": ["व्यक्तीला स्थिर आणि शांत ठेवा.", "त्यांना उबदार ठेवा आणि श्वासावर लक्ष ठेवा.",
               "पॅरामेडिकने सांगेपर्यंत अन्न, पाणी किंवा औषध देऊ नका."],
    },
    "donts": {"en": [], "hi": [], "mr": []},
    "audio": {"en": "generic_default_en.wav", "hi": "generic_default_hi.wav", "mr": "generic_default_mr.wav"},
}

_FACILITY_DEFAULTS = {
    "cardiac": "chest_pain_wait", "stroke": "stroke_signs_wait", "burns": "burns",
    "poisoning": "poisoning", "trauma": "fracture_immobilisation", "obstetric": "labour",
}


def select_first_aid(payload: dict) -> dict:
    protocols = {p["protocol_id"]: p for p in load_all_first_aid()}
    extracted = payload.get("extracted", {})
    facility = payload.get("facility")
    symptoms = set(extracted.get("symptoms", []))

    chosen_id = None
    if extracted.get("breathing") == "absent":
        chosen_id = "hands_only_cpr"
    elif "choking" in symptoms:
        chosen_id = "choking"
    elif extracted.get("bleeding") == "severe":
        chosen_id = "severe_bleeding"
    elif extracted.get("conscious") is False and extracted.get("breathing") == "normal":
        chosen_id = "recovery_position"
    elif "seizure" in symptoms:
        chosen_id = "seizure"
    elif facility in _FACILITY_DEFAULTS:
        chosen_id = _FACILITY_DEFAULTS[facility]

    protocol = protocols.get(chosen_id) if chosen_id else None
    if protocol is None:
        protocol = _GENERIC_DEFAULT

    language = "en"
    return {
        "protocol_id": protocol["protocol_id"],
        "title": protocol["title"].get(language, protocol["title"]["en"]),
        "steps": protocol["steps"].get(language, protocol["steps"]["en"]),
        "donts": protocol["donts"].get(language, protocol["donts"]["en"]),
        "audio_urls": [f"/ml/v1/static/audio/{protocol['audio'].get(language, protocol['audio']['en'])}"],
    }
