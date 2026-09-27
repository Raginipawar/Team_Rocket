"""Real pre-positioning: OR-Tools MIP maximising forecast demand covered within
8 min, penalising relocation distance, keeping >=1 ALS per high-demand zone
(technical.md §9.16). Runs every 15 min; suggestions are declinable by the
paramedic (technical.md §11.15)."""


class ModelNotLoaded(RuntimeError):
    pass


async def real_preposition(payload: dict) -> dict:
    raise ModelNotLoaded(
        "OR-Tools solver not wired -- install ortools and implement the MIP, "
        "or set ML_MOCK_CAPABILITIES=preposition"
    )
