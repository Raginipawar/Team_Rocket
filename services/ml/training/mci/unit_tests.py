import pytest
import asyncio
from services.ml.app.capabilities.mci.schemas import MCIAllocateRequest, Patient, Hospital, Ambulance
from services.ml.app.capabilities.mci.model import allocate_mci

@pytest.mark.asyncio
async def test_empty_input():
    req = MCIAllocateRequest(patients=[], hospitals=[], ambulances=[])
    res = await allocate_mci(req)
    assert len(res.assignments) == 0
    assert len(res.unassigned) == 0

@pytest.mark.asyncio
async def test_capacity_respected():
    req = MCIAllocateRequest(
        patients=[Patient(id=str(i), acuity="stable", facility="ICU") for i in range(5)],
        hospitals=[Hospital(id="h1", capacities_by_type={"ICU": 2}, eta_sec=100)],
        ambulances=[Ambulance(id=str(i), type="ALS", eta_to_scene=10) for i in range(5)]
    )
    res = await allocate_mci(req)
    assert len(res.assignments) <= 2
    assert len(res.unassigned) >= 3

@pytest.mark.asyncio
async def test_critical_patients_assigned_first():
    req = MCIAllocateRequest(
        patients=[
            Patient(id="p_stable1", acuity="stable", facility="ER"),
            Patient(id="p_stable2", acuity="stable", facility="ER"),
            Patient(id="p_crit", acuity="critical", facility="ER")
        ],
        hospitals=[Hospital(id="h1", capacities_by_type={"ER": 1}, eta_sec=100)],
        ambulances=[Ambulance(id="a1", type="ALS", eta_to_scene=10)]
    )
    res = await allocate_mci(req)
    assert len(res.assignments) == 1
    assert res.assignments[0].patient_id == "p_crit"

@pytest.mark.asyncio
async def test_max_share_per_hospital():
    # 4 patients, max share is (4+2)//3 = 2
    req = MCIAllocateRequest(
        patients=[Patient(id=str(i), acuity="stable", facility="ER") for i in range(4)],
        hospitals=[
            Hospital(id="h1", capacities_by_type={"ER": 10}, eta_sec=10),
            Hospital(id="h2", capacities_by_type={"ER": 10}, eta_sec=1000)
        ],
        ambulances=[Ambulance(id=str(i), type="ALS", eta_to_scene=10) for i in range(4)]
    )
    res = await allocate_mci(req)
    h1_count = sum(1 for a in res.assignments if a.hospital_id == "h1")
    assert h1_count <= 2
