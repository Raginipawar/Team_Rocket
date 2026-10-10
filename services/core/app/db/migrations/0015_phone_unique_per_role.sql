-- Demo need: only 2 real phones available to test with, so the same phone
-- number must be usable as both a patient account and an ambulance crew
-- account. Was a hard UNIQUE on phone alone; now unique per (phone, role)
-- instead -- one account per role per phone, not one account per phone.
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_phone_key;
ALTER TABLE users ADD CONSTRAINT users_phone_role_key UNIQUE (phone, role);
