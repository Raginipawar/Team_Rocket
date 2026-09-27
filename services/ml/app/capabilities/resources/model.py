"""Real resource prediction: LightGBM one-vs-rest multi-label over a
clinician-style mapping table + noise (technical.md §9.10). prob>=0.5 -> prep
checklist; top items feed B's reservation bundle (§11.5)."""


class ModelNotLoaded(RuntimeError):
    pass


async def real_resources(payload: dict) -> dict:
    raise ModelNotLoaded(
        "resources LightGBM model not trained -- run training/resources/train.py, "
        "or set ML_MOCK_CAPABILITIES=resources"
    )
