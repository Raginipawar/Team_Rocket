"""Real triage model: MuRIL / IndicBERT v2 fine-tuned, two heads (technical.md §9.3).
Not trained yet -- fine-tuning happens on Kaggle/Colab (A7 in wd-person-a-intake-dispatch.md).
Until services/ml/artifacts/triage/ has a checkpoint, `real_triage` raises so the
caller falls back per the ML_MODE=mock / capability-mock switch, never silently
returns a fake result labelled as real."""


class ModelNotLoaded(RuntimeError):
    pass


async def real_triage(payload: dict) -> dict:
    raise ModelNotLoaded(
        "triage checkpoint not found in services/ml/artifacts/triage/ -- "
        "run training/triage/train.py or set ML_MOCK_CAPABILITIES=triage"
    )
