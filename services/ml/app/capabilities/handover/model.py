"""Real handover: LLM (Ollama) with SBAR JSON schema; every clinical statement
must cite a source_spans quote found in transcript/answers/profile, a validator
drops any sentence whose quote can't be fuzzy-matched (>=0.85) (technical.md §9.9).
Regenerated on new follow-up answers or triage confirmation."""


class ModelNotLoaded(RuntimeError):
    pass


async def real_handover(payload: dict) -> dict:
    raise ModelNotLoaded(
        "handover LLM not wired -- start Ollama, or set ML_MOCK_CAPABILITIES=handover"
    )
