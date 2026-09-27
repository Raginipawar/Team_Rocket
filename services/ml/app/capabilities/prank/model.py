"""Real prank scoring: Isolation Forest on caller-behaviour features + rule-based
reasons, threshold at 5% FPR on validation (technical.md §9.4). Policy (never
block; critical bypasses verification) lives in core, not here."""


class ModelNotLoaded(RuntimeError):
    pass


async def real_prank(payload: dict) -> dict:
    raise ModelNotLoaded(
        "prank Isolation Forest not trained -- run training/prank/train.py, "
        "or set ML_MOCK_CAPABILITIES=prank"
    )
