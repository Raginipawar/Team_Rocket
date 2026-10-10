-- Developer/ops demo account for debugging the deployed system (bypasses
-- per-emergency ownership checks in _authorize_emergency_access).
INSERT INTO public.users (id, created_at, updated_at, role, name, phone, language, password_hash, hospital_id, ambulance_id, telegram_user_id, is_active) VALUES ('bdd25f83-15bf-417b-9476-30bd4eacccaf','2026-10-04 16:00:59.130027+00',NULL,'developer','Test Dev','+919000000003','en','$argon2id$v=19$m=65536,t=3,p=4$KbpR/yh4pIH8cfJIuR0vPw$UZFJSpewp2COCBj9sKg9roGpDAuyqnqF+nz1H/rBDns',NULL,NULL,NULL,true) ON CONFLICT (id) DO NOTHING;
