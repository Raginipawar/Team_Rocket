"""Real mass-casualty allocation: OR-Tools MIP (technical.md Section9,
same tool already used for Person A's pre-positioning solver). Was a plain
round-robin in router.py (patient 1 -> ambulance 1 + hospital 1, patient 2
-> ambulance 2 + hospital 2, wrapping around in list order) -- ignored
acuity, ETA, and hospital capacity entirely.

x[p][a][h] = 1 if patient p is assigned to ambulance a and hospital h.
Maximise sum(x[p,a,h] * (ACUITY_BONUS[p] - time_cost(a,h))), subject to:
each patient assigned at most once, each ambulance used at most once, and
each hospital's per-facility-type capacity not exceeded. The large
per-acuity bonus means the solver strongly prefers assigning more (and
more critical) patients over minimizing time among a fixed set -- coverage
first, speed second, matching the spec's prioritization intent."""

from ortools.linear_solver import pywraplp

from .schemas import Assignment, MCIAllocateRequest, MCIAllocateResponse, Unassigned

ACUITY_BONUS = {"critical": 100000.0, "urgent": 20000.0, "stable": 5000.0}


class SolverFailed(Exception):
    pass


async def real_mci_allocate(req: MCIAllocateRequest) -> MCIAllocateResponse:
    patients, hospitals, ambulances = req.patients, req.hospitals, req.ambulances
    if not patients:
        return MCIAllocateResponse(assignments=[], unassigned=[], objective=0.0)
    if not ambulances or not hospitals:
        return MCIAllocateResponse(
            assignments=[],
            unassigned=[Unassigned(patient_id=p.id, reason="no_ambulances_or_hospitals_available") for p in patients],
            objective=0.0,
        )

    solver = pywraplp.Solver.CreateSolver("CBC")
    if solver is None:
        raise SolverFailed("CBC solver unavailable")

    x = {}
    for pi, p in enumerate(patients):
        for ai, a in enumerate(ambulances):
            for hi, h in enumerate(hospitals):
                # Only create a variable if this hospital even has a capacity
                # entry for this patient's facility need -- otherwise it can
                # never legally take this patient, no point in a free variable.
                if h.capacities_by_type.get(p.facility, 0) > 0:
                    x[pi, ai, hi] = solver.BoolVar(f"x_{pi}_{ai}_{hi}")

    # Each patient assigned to at most one (ambulance, hospital) pair.
    for pi in range(len(patients)):
        vars_for_patient = [x[pi, ai, hi] for ai in range(len(ambulances)) for hi in range(len(hospitals))
                             if (pi, ai, hi) in x]
        if vars_for_patient:
            solver.Add(solver.Sum(vars_for_patient) <= 1)

    # Each ambulance used for at most one patient.
    for ai in range(len(ambulances)):
        vars_for_amb = [x[pi, ai, hi] for pi in range(len(patients)) for hi in range(len(hospitals))
                         if (pi, ai, hi) in x]
        if vars_for_amb:
            solver.Add(solver.Sum(vars_for_amb) <= 1)

    # Each hospital's per-facility-type capacity respected.
    for hi, h in enumerate(hospitals):
        for facility, capacity in h.capacities_by_type.items():
            vars_for_type = [x[pi, ai, hi] for pi, p in enumerate(patients) if p.facility == facility
                              for ai in range(len(ambulances)) if (pi, ai, hi) in x]
            if vars_for_type:
                solver.Add(solver.Sum(vars_for_type) <= capacity)

    objective_terms = []
    for (pi, ai, hi), var in x.items():
        time_cost = ambulances[ai].eta_to_scene + hospitals[hi].eta_sec
        value = ACUITY_BONUS.get(patients[pi].acuity, 1000.0) - time_cost
        objective_terms.append(value * var)
    solver.Maximize(solver.Sum(objective_terms))

    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        raise SolverFailed(f"solver status={status}")

    assignments = []
    assigned_patient_ids = set()
    for (pi, ai, hi), var in x.items():
        if var.solution_value() > 0.5:
            assignments.append(Assignment(
                patient_id=patients[pi].id, ambulance_id=ambulances[ai].id, hospital_id=hospitals[hi].id,
            ))
            assigned_patient_ids.add(patients[pi].id)

    unassigned = []
    for p in patients:
        if p.id in assigned_patient_ids:
            continue
        has_capacity = any(h.capacities_by_type.get(p.facility, 0) > 0 for h in hospitals)
        reason = "no_hospital_capacity_for_facility" if not has_capacity else "no_ambulance_or_hospital_slot_left"
        unassigned.append(Unassigned(patient_id=p.id, reason=reason))

    return MCIAllocateResponse(assignments=assignments, unassigned=unassigned, objective=solver.Objective().Value())
