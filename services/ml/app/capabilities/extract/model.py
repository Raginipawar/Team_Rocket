"""Real extraction: Qwen2.5-7B-Instruct via Ollama, JSON-schema constrained
decoding, temperature 0, Pydantic validation with one repair retry
(technical.md §9.2)."""


class ModelNotLoaded(RuntimeError):
    pass


async def real_extract(payload: dict) -> dict:
    raise ModelNotLoaded(
        "Ollama qwen2.5:7b-instruct not reachable -- start Ollama and pull the "
        "model, or set ML_MOCK_CAPABILITIES=extract"
    )
