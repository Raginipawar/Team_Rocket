import os
import asyncio
import uuid
import datetime
import json
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://gh:gh@postgres:5432/goldenhour")
engine = create_async_engine(DATABASE_URL)

NAMESPACE = uuid.NAMESPACE_DNS

def make_uuid(name: str) -> str:
    return str(uuid.uuid5(NAMESPACE, name))

HOSPITALS = [
    {
        "name": "KEM Hospital",
        "lat": 18.5118, "lng": 73.8520,
        "capabilities": ['cardiac_cathlab', 'general_er', 'icu', 'trauma_center']
    },
    {
        "name": "Ruby Hall Clinic",
        "lat": 18.5314, "lng": 73.8446,
        "capabilities": ['cardiac_cathlab', 'stroke_thrombolysis', 'icu', 'neurosurgery']
    },
    {
        "name": "Deenanath Mangeshkar Hospital",
        "lat": 18.5067, "lng": 73.8082,
        "capabilities": ['obstetrics', 'pediatrics', 'general_er', 'icu']
    },
    {
        "name": "Sahyadri Hospital",
        "lat": 18.5196, "lng": 73.8553,
        "capabilities": ['trauma_center', 'burns_unit', 'general_er', 'icu']
    },
    {
        "name": "Jehangir Hospital",
        "lat": 18.5286, "lng": 73.8769,
        "capabilities": ['cardiac_cathlab', 'general_er', 'icu', 'toxicology']
    },
    {
        "name": "Columbia Asia Hospital",
        "lat": 18.5640, "lng": 73.7747,
        "capabilities": ['obstetrics', 'pediatrics', 'general_er']
    },
    {
        "name": "Poona Hospital",
        "lat": 18.5176, "lng": 73.8556,
        "capabilities": ['stroke_thrombolysis', 'neurosurgery', 'general_er', 'icu']
    },
    {
        "name": "Noble Hospital",
        "lat": 18.4649, "lng": 73.8706,
        "capabilities": ['general_er', 'icu']
    }
]

async def main():
    async with engine.begin() as conn:
        print("Seeding hospitals...")
        for i, h in enumerate(HOSPITALS):
            h_id = make_uuid(f"hospital_{h['name']}")
            await conn.execute(text("""
                INSERT INTO hospitals (id, name, location, capabilities, is_active, stabilization_capable, is_simulated, last_confirmed_at)
                VALUES (:id, :name, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), :capabilities, true, true, true, now())
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": h_id,
                "name": h['name'],
                "lat": h['lat'],
                "lng": h['lng'],
                "capabilities": h['capabilities']
            })
            
            # Rooms for this hospital
            rooms = []
            rooms.extend([("resus_bay", "Ground floor, Bay 1"), ("resus_bay", "Ground floor, Bay 2")])
            for idx in range(4): rooms.append(("er_bed", f"ER Area, Bed {idx+1}"))
            for idx in range(2): rooms.append(("icu_bed", f"ICU, Bed {idx+1}"))
            
            if 'cardiac_cathlab' in h['capabilities']: rooms.append(("resus_bay", "Cardiac Resus"))
            if 'trauma_center' in h['capabilities']: rooms.append(("trauma_bay", "Trauma Bay"))
            if 'burns_unit' in h['capabilities']: rooms.append(("burns_unit", "Burns Unit"))
            if 'obstetrics' in h['capabilities']: rooms.extend([("labour_room", "LR 1"), ("labour_room", "LR 2")])
            if 'pediatrics' in h['capabilities']: rooms.append(("pediatric_er", "Peds ER"))
            
            for idx, r in enumerate(rooms):
                r_type, r_code = r
                r_id = make_uuid(f"room_{h_id}_{r_type}_{idx}")
                await conn.execute(text("""
                    INSERT INTO rooms (id, hospital_id, code, type, status, priority_order, version)
                    VALUES (:id, :hospital_id, :code, :type, 'free', :priority_order, 1)
                    ON CONFLICT (id) DO NOTHING
                """), {"id": r_id, "hospital_id": h_id, "code": r_code, "type": r_type, "priority_order": idx + 1})
                
            # Resources
            res = [("defibrillator", 3), ("ventilator", 4)]
            if 'cardiac_cathlab' in h['capabilities']: res.append(("cath_lab", 2))
            if 'stroke_thrombolysis' in h['capabilities']: res.extend([("ct_scanner", 1), ("mri", 1)])
            if 'trauma_center' in h['capabilities'] or 'burns_unit' in h['capabilities']: res.append(("operating_theatre", 2))
            res.extend([("blood_o_neg", 10), ("blood_o_pos", 10)])
            
            for rt, count in res:
                res_id = make_uuid(f"res_{h_id}_{rt}")
                await conn.execute(text("""
                    INSERT INTO hospital_resources (id, hospital_id, type, total, available, reserved, version, reported_at)
                    VALUES (:id, :hospital_id, :type, :total, :total, 0, 1, now())
                    ON CONFLICT (id) DO NOTHING
                """), {"id": res_id, "hospital_id": h_id, "type": rt, "total": count})

            # Staff
            staff = [("emergency_physician", 2), ("er_nurse", 2), ("anesthetist", 1)]
            if 'cardiac_cathlab' in h['capabilities']: staff.append(("cardiologist", 2))
            if 'stroke_thrombolysis' in h['capabilities']: staff.append(("neurologist", 1))
            if 'trauma_center' in h['capabilities']: staff.append(("trauma_surgeon", 2))
            if 'burns_unit' in h['capabilities']: staff.append(("burns_surgeon", 1))
            if 'obstetrics' in h['capabilities']: staff.append(("obstetrician", 2))
            if 'pediatrics' in h['capabilities']: staff.append(("pediatrician", 1))
            if 'toxicology' in h['capabilities']: staff.append(("pulmonologist", 1))
            
            now = datetime.datetime.now(datetime.timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)
            shifts = [(now, now + datetime.timedelta(hours=8)), 
                      (now + datetime.timedelta(hours=8), now + datetime.timedelta(hours=16)),
                      (now + datetime.timedelta(hours=16), now + datetime.timedelta(hours=24))]

            for role, count in staff:
                for idx in range(count):
                    s_id = make_uuid(f"staff_{h_id}_{role}_{idx}")
                    s_name = f"{role.replace('_', ' ').title()} {idx+1}"
                    await conn.execute(text("""
                        INSERT INTO staff (id, hospital_id, name, specialty, is_active)
                        VALUES (:id, :hospital_id, :name, :specialty, true)
                        ON CONFLICT (id) DO NOTHING
                    """), {"id": s_id, "hospital_id": h_id, "name": s_name, "specialty": role})
                    
                    for shift_idx, (start_at, end_at) in enumerate(shifts):
                        shift_id = make_uuid(f"shift_{s_id}_{shift_idx}")
                        await conn.execute(text("""
                            INSERT INTO staff_shifts (id, staff_id, start_at, end_at)
                            VALUES (:id, :staff_id, :start_at, :end_at)
                            ON CONFLICT (id) DO NOTHING
                        """), {"id": shift_id, "staff_id": s_id, "start_at": start_at, "end_at": end_at})
                        
        print("Seeding ambulances...")
        for i in range(1, 16):
            is_als = i <= 6
            a_type = "ALS" if is_als else "BLS"
            ident = f"{a_type}-{i:03d}"
            a_id = make_uuid(f"amb_{ident}")
            lat = 18.5 + (i * 0.005)
            lng = 73.8 + (i * 0.005)
            caps = ["als_kit", "ventilator"] if is_als else ["bls_kit"]
            await conn.execute(text("""
                INSERT INTO ambulances (id, identifier, type, status, current_location, capabilities, version)
                VALUES (:id, :identifier, :type, 'available', ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), :capabilities, 1)
                ON CONFLICT (id) DO NOTHING
            """), {"id": a_id, "identifier": ident, "type": a_type, "lat": lat, "lng": lng, "capabilities": json.dumps(caps)})

        print("Seeding users...")
        dev_id = make_uuid("user_dev")
        await conn.execute(text("""
            INSERT INTO users (id, phone_number, roles, is_active)
            VALUES (:id, '+911234567890', '["developer"]', true)
            ON CONFLICT (id) DO NOTHING
        """), {"id": dev_id})
        
        for i in range(1, 9):
            hs_id = make_uuid(f"user_hstaff_{i}")
            await conn.execute(text("""
                INSERT INTO users (id, phone_number, roles, is_active)
                VALUES (:id, :phone, '["hospital_staff"]', true)
                ON CONFLICT (id) DO NOTHING
            """), {"id": hs_id, "phone": f"+91900000000{i}"})
            
        for i in range(1, 16):
            p_id = make_uuid(f"user_paramedic_{i}")
            await conn.execute(text("""
                INSERT INTO users (id, phone_number, roles, is_active)
                VALUES (:id, :phone, '["paramedic"]', true)
                ON CONFLICT (id) DO NOTHING
            """), {"id": p_id, "phone": f"+9191000000{i:02d}"})

        for i in range(1, 3):
            pat_id = make_uuid(f"user_patient_{i}")
            phone = f"+91920000000{i}"
            await conn.execute(text("""
                INSERT INTO users (id, phone_number, roles, is_active)
                VALUES (:id, :phone, '["patient"]', true)
                ON CONFLICT (id) DO NOTHING
            """), {"id": pat_id, "phone": phone})
            
            hp_id = make_uuid(f"hp_patient_{i}")
            bg = "O+" if i == 1 else "A-"
            conds = ["Diabetic"] if i == 1 else ["Hypertension"]
            await conn.execute(text("""
                INSERT INTO health_profiles (id, user_id, blood_group, allergies, medical_conditions, medications)
                VALUES (:id, :user_id, :bg, '[]', :conds, '[]')
                ON CONFLICT (id) DO NOTHING
            """), {"id": hp_id, "user_id": pat_id, "bg": bg, "conds": json.dumps(conds)})
            
            ec_id = make_uuid(f"ec_patient_{i}")
            await conn.execute(text("""
                INSERT INTO emergency_contacts (id, user_id, name, phone_number, relation)
                VALUES (:id, :user_id, 'Emergency Contact', '+919999999999', 'Family')
                ON CONFLICT (id) DO NOTHING
            """), {"id": ec_id, "user_id": pat_id})
            
        print("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(main())
