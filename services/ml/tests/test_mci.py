"""Real OR-Tools mass-casualty allocation (technical.md Section9). Was a
plain round-robin (patient i -> ambulance i, hospital i%n), ignoring
acuity/ETA/hospital capacity entirely."""

import asyncio

from app.capabilities.mci.model import real_mci_allocate
from app.capabilities.mci.schemas import Ambulance, Hospital, MCIAllocateRequest, Patient


def test_critical_patients_prioritized_over_stable_when_resources_scarce():
    patients = [
        Patient(id="p_stable", acuity="stable", facility="general"),
        Patient(id="p_critical", acuity="critical", facility="general"),
    ]
    hospitals = [Hospital(id="h1", capacities_by_type={"general": 1}, eta_sec=300)]
    ambulances = [Ambulance(id="a1", type="ALS", eta_to_scene=200)]

    result = asyncio.run(real_mci_allocate(
        MCIAllocateRequest(patients=patients, hospitals=hospitals, ambulances=ambulances)
    ))
    assigned_ids = {a.patient_id for a in result.assignments}
    assert "p_critical" in assigned_ids
    assert "p_stable" not in assigned_ids


def test_hospital_capacity_respected():
    patients = [Patient(id=f"p{i}", acuity="urgent", facility="general") for i in range(5)]
    hospitals = [Hospital(id="h1", capacities_by_type={"general": 2}, eta_sec=300)]
    ambulances = [Ambulance(id=f"a{i}", type="ALS", eta_to_scene=200) for i in range(5)]

    result = asyncio.run(real_mci_allocate(
        MCIAllocateRequest(patients=patients, hospitals=hospitals, ambulances=ambulances)
    ))
    assert len(result.assignments) == 2  # capacity caps it, not ambulance count
    assert len(result.unassigned) == 3


def test_facility_mismatch_cannot_be_assigned_to_wrong_capacity_bucket():
    patients = [Patient(id="p1", acuity="critical", facility="cardiac")]
    hospitals = [Hospital(id="h1", capacities_by_type={"general": 5}, eta_sec=300)]  # no cardiac capacity
    ambulances = [Ambulance(id="a1", type="ALS", eta_to_scene=200)]

    result = asyncio.run(real_mci_allocate(
        MCIAllocateRequest(patients=patients, hospitals=hospitals, ambulances=ambulances)
    ))
    assert result.assignments == []
    assert result.unassigned[0].patient_id == "p1"
    assert result.unassigned[0].reason == "no_hospital_capacity_for_facility"


def test_no_ambulances_leaves_everyone_unassigned_with_clear_reason():
    patients = [Patient(id="p1", acuity="critical", facility="general")]
    hospitals = [Hospital(id="h1", capacities_by_type={"general": 5}, eta_sec=300)]

    result = asyncio.run(real_mci_allocate(
        MCIAllocateRequest(patients=patients, hospitals=hospitals, ambulances=[])
    ))
    assert result.assignments == []
    assert result.unassigned[0].reason == "no_ambulances_or_hospitals_available"
