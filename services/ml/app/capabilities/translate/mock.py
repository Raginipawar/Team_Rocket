def mock_translate(payload: dict) -> dict:
    text = payload["text"]
    target = payload["target_lang"]
    return {"translated_text": f"[{target}] {text}", "cached": False}
