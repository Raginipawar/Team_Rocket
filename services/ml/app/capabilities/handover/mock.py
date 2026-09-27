def mock_handover(payload: dict) -> dict:
    triage = payload.get("triage", {})
    extracted = payload.get("extracted", {})
    transcript = payload.get("transcript", "")
    return {
        "situation": f"{extracted.get('age', 'Unknown age')} y/o, acuity {triage.get('acuity', 'unknown')}",
        "background": f"Reported: {', '.join(extracted.get('symptoms', [])) or 'none listed'}",
        "assessment": f"Suspected facility need: {triage.get('facility', 'general')}",
        "recommendation": "Standard ER workup on arrival",
        "source_spans": [{"field": "symptoms", "quote": transcript[:80]}] if transcript else [],
    }
