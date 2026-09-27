"""Synthetic 90-day call history with realistic spatio-temporal patterns
(technical.md §9.15): highway nights, market evenings, residential cardiac
mornings, festival spikes. H3 resolution 8 over a Pune-area bounding box."""

import h3
import numpy as np
import pandas as pd

RNG = np.random.default_rng(33)
N_DAYS = 90
PUNE_CENTER = (18.5204, 73.8567)
GRID_RADIUS_KM = 15

FESTIVAL_DAYS = {23, 45, 46, 67}  # a few arbitrary festival days within the 90-day window


def build_h3_grid(center: tuple, radius_km: float, res: int = 8) -> list[str]:
    center_cell = h3.latlng_to_cell(center[0], center[1], res)
    return list(h3.grid_disk(center_cell, k=int(radius_km / 0.46)))  # res-8 edge ~ 0.46km


def cell_type(cell: str, highway_cells: set, market_cells: set) -> str:
    if cell in highway_cells:
        return "highway"
    if cell in market_cells:
        return "market"
    return "residential"


def hourly_rate(cell_kind: str, hour: int, weekday: int, is_festival: bool) -> float:
    base = 0.05
    if cell_kind == "highway":
        base += 0.15 if hour in (22, 23, 0, 1, 2, 3) else 0.04
    elif cell_kind == "market":
        base += 0.12 if hour in (17, 18, 19, 20) else 0.03
    else:  # residential
        base += 0.10 if hour in (6, 7, 8) else 0.02
        base += 0.03 if weekday >= 5 else 0.0

    if is_festival:
        base *= 2.2
    return base


def main() -> None:
    cells = build_h3_grid(PUNE_CENTER, GRID_RADIUS_KM)
    RNG.shuffle(cells)
    highway_cells = set(cells[:5])
    market_cells = set(cells[5:15])

    rows = []
    for day in range(N_DAYS):
        weekday = day % 7
        is_festival = day in FESTIVAL_DAYS
        for hour in range(24):
            for cell in cells:
                kind = cell_type(cell, highway_cells, market_cells)
                rate = hourly_rate(kind, hour, weekday, is_festival)
                calls = RNG.poisson(rate)
                if calls > 0:
                    rows.append({"h3_cell": cell, "day": day, "hour": hour, "weekday": weekday,
                                 "is_festival": int(is_festival), "cell_kind": kind, "calls": calls})

    df = pd.DataFrame(rows)
    df.to_csv("services/ml/data/demand/calls.csv", index=False)
    print(f"wrote {len(df)} (cell,hour) rows across {len(cells)} cells over {N_DAYS} days, "
          f"total calls: {df['calls'].sum()}")


if __name__ == "__main__":
    main()
