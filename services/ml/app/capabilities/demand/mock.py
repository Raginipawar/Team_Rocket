from app.util.mock import seed_from_payload, unit_float

# Pune-ish placeholder H3 res-8 cells; replace with the real demo-area grid.
DEMO_CELLS = [f"88{i:x}2a34fffffff" for i in range(12)]


def mock_demand(payload: dict) -> dict:
    seed = seed_from_payload(payload)
    cells = []
    for i, cell in enumerate(DEMO_CELLS):
        base = 1 + unit_float(seed, f"c{i}") * 6
        cells.append({
            "h3_cell": cell,
            "predicted_calls": round(base, 2),
            "lo": round(max(0, base - 1.5), 2),
            "hi": round(base + 1.5, 2),
        })
    return {"cells": cells}
