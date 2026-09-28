import hashlib


def mock_tts(payload: dict) -> dict:
    h = hashlib.sha256(f"{payload['text']}:{payload['language']}".encode()).hexdigest()
    return {"audio_url": f"/ml/v1/static/audio/{h}.wav", "cached": False}
