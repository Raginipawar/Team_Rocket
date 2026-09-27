"""Real selection: Ollama qwen2.5:7b-instruct, temperature 0, receives current
facts + answered ids + candidate questions (id + English text) and returns
{question_id}. The LLM never writes question text (technical.md §9.7); if it
returns an unknown id, the caller falls back to mock.pick_next_rule_based."""

from .mock import pick_next_rule_based


class ModelNotLoaded(RuntimeError):
    pass


async def real_followup_next(payload: dict) -> dict:
    raise ModelNotLoaded(
        "Ollama qwen2.5:7b-instruct not reachable for followup selection -- "
        "falls back to rule-based selection automatically; "
        "or set ML_MOCK_CAPABILITIES=followup to skip the LLM attempt"
    )


async def real_followup_parse(payload: dict) -> dict:
    raise ModelNotLoaded(
        "Ollama qwen2.5:7b-instruct not reachable for followup parsing -- "
        "or set ML_MOCK_CAPABILITIES=followup"
    )
