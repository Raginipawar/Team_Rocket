-- Paste into Supabase SQL Editor, run once. Creates a table that looks
-- like a real hospital's own capacity system and seeds it with realistic
-- numbers (not round demo numbers like 20/20).
--
-- `type` values must match this app's known resource types exactly --
-- the sync only accepts these, anything else comes back as "skipped"
-- rather than silently dropped.

create table if not exists hospital_capacity (
  type text primary key,
  label text not null,
  available int not null,
  total int not null,
  updated_at timestamptz not null default now()
);

alter table hospital_capacity disable row level security;

insert into hospital_capacity (type, label, available, total) values
  ('ventilator',       'Ventilators',               4,  10),
  ('cath_lab',         'Cath Labs',                  1,  2),
  ('ct_scanner',       'CT Scanners',                1,  3),
  ('mri',              'MRI Suites',                 0,  1),
  ('defibrillator',    'Defibrillators',             7,  12),
  ('blood_o_neg',      'Blood -- O Negative (units)', 6,  25),
  ('blood_o_pos',      'Blood -- O Positive (units)', 18, 40),
  ('blood_a_pos',      'Blood -- A Positive (units)', 12, 30),
  ('blood_b_pos',      'Blood -- B Positive (units)', 9,  28),
  ('blood_ab_pos',     'Blood -- AB Positive (units)', 3, 10),
  ('dialysis',         'Dialysis Machines',          2,  6),
  ('operating_theatre','Operating Theatres',         3,  8)
on conflict (type) do update set
  available = excluded.available, total = excluded.total, updated_at = now();

-- Query our sync actually calls (GET with this exact select list):
--   <Project URL>/rest/v1/hospital_capacity?select=type,available,total
--
-- To change a number live for a judge demo, just run e.g.:
--   update hospital_capacity set available = 0 where type = 'ventilator';
-- then hit "Sync now" on the hospital settings page.
