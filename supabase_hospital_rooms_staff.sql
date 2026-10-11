-- Paste into Supabase SQL Editor, run once (after supabase_hospital_demo.sql).
-- Adds rooms and staff as real external tables too, synced the same way
-- resources already are -- not injected directly into our own database.

create table if not exists hospital_rooms (
  code text primary key,
  type text not null,
  status text not null check (status in ('free','occupied','reserved','cleaning','out_of_service'))
);
alter table hospital_rooms disable row level security;

insert into hospital_rooms (code, type, status) values
  ('ER-01','er_bed','free'), ('ER-02','er_bed','free'), ('ER-03','er_bed','occupied'),
  ('ER-04','er_bed','free'), ('ER-05','er_bed','reserved'),
  ('RB-01','resus_bay','free'), ('RB-02','resus_bay','occupied'),
  ('TB-01','trauma_bay','free'), ('TB-02','trauma_bay','free'),
  ('ICU-01','icu_bed','occupied'), ('ICU-02','icu_bed','free'), ('ICU-03','icu_bed','free'),
  ('LR-01','labour_room','free'),
  ('PE-01','pediatric_er','free'), ('PE-02','pediatric_er','occupied')
on conflict (code) do update set type = excluded.type, status = excluded.status;

create table if not exists hospital_staff (
  name text primary key,
  specialty text not null,
  on_duty boolean not null default true
);
alter table hospital_staff disable row level security;

insert into hospital_staff (name, specialty, on_duty) values
  ('Dr. Anika Sharma', 'emergency_physician', true),
  ('Dr. Rohan Mehta', 'cardiologist', true),
  ('Dr. Priya Nair', 'trauma_surgeon', true),
  ('Dr. Karan Joshi', 'anesthetist', false),
  ('Dr. Sana Khan', 'pediatrician', true),
  ('Nurse Vivek Rao', 'er_nurse', true),
  ('Nurse Meera Iyer', 'er_nurse', true),
  ('Nurse Arjun Desai', 'er_nurse', false)
on conflict (name) do update set specialty = excluded.specialty, on_duty = excluded.on_duty;

-- Our sync derives these URLs automatically from whatever base project URL
-- you already saved for hospital_capacity -- you don't need to paste
-- anything new, just hit "Sync now" again after running this script.
-- For reference, the URLs it calls:
--   <Project URL>/rest/v1/hospital_rooms?select=code,type,status
--   <Project URL>/rest/v1/hospital_staff?select=name,specialty,on_duty
--
-- To change something live for a judge demo:
--   update hospital_rooms set status = 'occupied' where code = 'ER-01';
-- then hit "Sync now".
