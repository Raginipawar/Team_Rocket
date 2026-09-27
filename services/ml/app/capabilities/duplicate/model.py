"""Real duplicate check: intfloat/multilingual-e5-base cosine similarity + spatial
(<=500m) / temporal (<=15min) gate, DBSCAN clustering for MCI trigger (technical.md §9.5)."""


class ModelNotLoaded(RuntimeError):
    pass


async def real_duplicate(payload: dict) -> dict:
    raise ModelNotLoaded(
        "multilingual-e5-base not loaded -- download the embedding model, "
        "or set ML_MOCK_CAPABILITIES=duplicate"
    )
