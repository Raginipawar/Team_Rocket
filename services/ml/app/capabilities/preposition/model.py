"""Real pre-positioning: OR-Tools MIP (technical.md §9.16, §11.15).

x[i][j] = 1 if idle ambulance i relocates to cover candidate zone j (only
allowed if ambulance i can reach zone j within COVERAGE_MIN minutes).
y[j] = 1 if zone j ends up covered by at least one assigned ambulance.
Maximise sum(forecast[j] * y[j]) - RELOCATION_PENALTY * sum(x[i][j] * distance_km(i,j)),
subject to: each ambulance assigned to at most one zone, y[j] can only be 1
if some ambulance covers it, and for a HIGH-demand zone (top quartile of
forecast), if it's covered at all it must be covered by at least one ALS
unit -- the >=1-ALS-per-high-demand-zone constraint from §11.15."""

import math

from ortools.linear_solver import pywraplp

COVERAGE_MIN = 8.0
ASSUMED_SPEED_KMH = 30.0
RELOCATION_PENALTY = 0.05  # utility points lost per km relocated


class SolverFailed(Exception):
    pass


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def real_preposition(payload: dict) -> dict:
    ambulances = payload["idle_ambulances"]
    forecast = payload["forecast"]  # [{h3_cell, predicted_calls, lat, lng}]
    if not ambulances or not forecast:
        return {"suggestions": []}

    sorted_forecast = sorted(forecast, key=lambda f: -f["predicted_calls"])
    high_demand_threshold = sorted_forecast[max(0, len(sorted_forecast) // 4 - 1)]["predicted_calls"]

    solver = pywraplp.Solver.CreateSolver("CBC")
    if solver is None:
        raise SolverFailed("CBC solver unavailable")

    x = {}
    reachable = {}
    for i, amb in enumerate(ambulances):
        for j, zone in enumerate(forecast):
            dist_km = _haversine_km(amb["location"]["lat"], amb["location"]["lng"], zone["lat"], zone["lng"])
            eta_min = (dist_km / ASSUMED_SPEED_KMH) * 60
            if eta_min <= COVERAGE_MIN:
                x[i, j] = solver.BoolVar(f"x_{i}_{j}")
                reachable[i, j] = dist_km

    y = {j: solver.BoolVar(f"y_{j}") for j in range(len(forecast))}

    for i in range(len(ambulances)):
        solver.Add(solver.Sum(x[i, j] for j in range(len(forecast)) if (i, j) in x) <= 1)

    for j in range(len(forecast)):
        covering_vars = [x[i, j] for i in range(len(ambulances)) if (i, j) in x]
        if covering_vars:
            solver.Add(y[j] <= solver.Sum(covering_vars))
        else:
            solver.Add(y[j] == 0)

        # >=1 ALS per high-demand zone, if covered at all.
        if forecast[j]["predicted_calls"] >= high_demand_threshold:
            als_vars = [x[i, j] for i in range(len(ambulances))
                        if (i, j) in x and ambulances[i].get("type") == "ALS"]
            if als_vars:
                solver.Add(y[j] <= solver.Sum(als_vars))
            else:
                solver.Add(y[j] == 0)  # no ALS can reach this high-demand zone -> can't claim coverage

    objective = solver.Sum(forecast[j]["predicted_calls"] * y[j] for j in range(len(forecast)))
    objective -= RELOCATION_PENALTY * solver.Sum(reachable[i, j] * x[i, j] for (i, j) in x)
    solver.Maximize(objective)

    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        raise SolverFailed(f"solver status={status}")

    suggestions = []
    for (i, j), var in x.items():
        if var.solution_value() > 0.5:
            zone = forecast[j]
            suggestions.append({
                "ambulance_id": ambulances[i]["id"],
                "target": {"lat": zone["lat"], "lng": zone["lng"]},
                "h3_cell": zone["h3_cell"],
                "expected_coverage_gain": round(zone["predicted_calls"], 3),
            })

    return {"suggestions": suggestions}
