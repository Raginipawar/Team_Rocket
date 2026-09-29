from ortools.sat.python import cp_model
from .schemas import MCIAllocateRequest, MCIAllocateResponse, Assignment, Unassigned

async def allocate_mci(req: MCIAllocateRequest) -> MCIAllocateResponse:
    model = cp_model.CpModel()
    
    num_p = len(req.patients)
    num_h = len(req.hospitals)
    num_a = len(req.ambulances)
    
    if num_p == 0:
        return MCIAllocateResponse(assignments=[], unassigned=[], objective=0.0)
    
    # Variables: assign[p][h][a] = 1 if patient p goes to hospital h in ambulance a
    assign = {}
    for p in range(num_p):
        for h in range(num_h):
            for a in range(num_a):
                assign[(p, h, a)] = model.NewBoolVar(f'assign_p{p}_h{h}_a{a}')
                
    # Each patient assigned to at most 1 hospital and 1 ambulance
    for p in range(num_p):
        model.AddAtMostOne([assign[(p, h, a)] for h in range(num_h) for a in range(num_a)])
        
    # Capacity constraints: sum of assignments to hospital h for required facility <= capacity
    for h, hosp in enumerate(req.hospitals):
        # group patients by needed facility
        facility_patients = {}
        for p, pat in enumerate(req.patients):
            fac = pat.facility
            if fac not in facility_patients:
                facility_patients[fac] = []
            facility_patients[fac].append(p)
            
        for fac, p_list in facility_patients.items():
            cap = hosp.capacities_by_type.get(fac, 0)
            model.AddSum([assign[(p, h, a)] for p in p_list for a in range(num_a)]) <= cap
            
    # Max share per hospital: <= 33% of total patients (rounded up)
    max_share = max(1, (num_p + 2) // 3)
    for h in range(num_h):
        model.AddSum([assign[(p, h, a)] for p in range(num_p) for a in range(num_a)]) <= max_share
        
    # Objective: Minimize weighted time, maximize assignments (especially for critical)
    # We negate the objective for maximization OR use minimization
    # Let's minimize a score:
    # If not assigned: huge penalty (larger for critical)
    # If assigned: time = eta_to_scene + eta_hosp
    
    # Track if assigned
    is_assigned = []
    for p in range(num_p):
        var = model.NewBoolVar(f'is_assigned_p{p}')
        model.Add(var == sum([assign[(p, h, a)] for h in range(num_h) for a in range(num_a)]))
        is_assigned.append(var)
        
    objective_terms = []
    
    # Penalty for unassigned
    for p, pat in enumerate(req.patients):
        weight = 1000000 if pat.acuity == 'critical' else 100000
        # Add penalty if NOT assigned: weight * (1 - is_assigned[p])
        objective_terms.append(weight * (1 - is_assigned[p]))
        
        # Time cost if assigned
        for h, hosp in enumerate(req.hospitals):
            for a, amb in enumerate(req.ambulances):
                time_val = int(amb.eta_to_scene + hosp.eta_sec)
                objective_terms.append(time_val * assign[(p, h, a)])
                
    model.Minimize(sum(objective_terms))
    
    solver = cp_model.CpSolver()
    # Set time limit
    solver.parameters.max_time_in_seconds = 2.0
    status = solver.Solve(model)
    
    assignments = []
    unassigned = []
    objective_val = 0.0
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        objective_val = solver.ObjectiveValue()
        for p, pat in enumerate(req.patients):
            assigned = False
            for h, hosp in enumerate(req.hospitals):
                for a, amb in enumerate(req.ambulances):
                    if solver.Value(assign[(p, h, a)]):
                        assignments.append(Assignment(
                            patient_id=pat.id,
                            ambulance_id=amb.id,
                            hospital_id=hosp.id
                        ))
                        assigned = True
            if not assigned:
                unassigned.append(Unassigned(patient_id=pat.id, reason="No capacity or constraints prevented assignment"))
    else:
        # Fallback if infeasible (shouldn't happen with our formulation unless hard constraints clash severely, 
        # but all hard constraints can be met trivially by assigning no one)
        for pat in req.patients:
            unassigned.append(Unassigned(patient_id=pat.id, reason="Solver could not find a feasible solution"))
            
    return MCIAllocateResponse(
        assignments=assignments,
        unassigned=unassigned,
        objective=objective_val
    )
