from app.util.mock import pick, seed_from_payload, unit_float

LANGS = ["hi", "mr", "en", "hi-en", "mr-en"]
SAMPLE_TRANSCRIPTS = {
    "hi": "mere pita ko seene mein dard ho raha hai",
    "mr": "majhya vadilanna chhatit dukhat aahe",
    "en": "my father has chest pain and is sweating",
    "hi-en": "father ko chest pain ho raha hai, please jaldi ambulance bhejo",
    "mr-en": "vadilanna chest pain aahe, please ambulance pathva",
}


def mock_stt(payload: dict) -> dict:
    seed = seed_from_payload(payload)
    lang = payload.get("lang_hint") or pick(seed, LANGS, "lang")
    transcript = SAMPLE_TRANSCRIPTS.get(lang, SAMPLE_TRANSCRIPTS["en"])
    return {
        "transcript": transcript,
        "language": lang,
        "confidence": round(0.7 + unit_float(seed, "conf") * 0.29, 2),
        "segments": [{"start": 0.0, "end": 3.0, "text": transcript}],
    }
