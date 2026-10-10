-- Real ambulance registration/approval workflow, replacing the fixed
-- phone+password login with OTP (same as patient) plus a Live/Demo
-- registration step. kyc_verified was already the real dispatch-eligibility
-- gate (db/repos/ambulances.py find_candidates), this adds what was missing
-- around it: a human-readable status, the registration form data, and a
-- capabilities list for clinical-specialty dispatch matching.
ALTER TABLE ambulances ADD COLUMN IF NOT EXISTS registration_status text
    CHECK (registration_status IN ('pending', 'approved', 'rejected', 'demo'))
    DEFAULT 'approved';
ALTER TABLE ambulances ADD COLUMN IF NOT EXISTS registration_data jsonb;
ALTER TABLE ambulances ADD COLUMN IF NOT EXISTS capabilities text[] DEFAULT '{}';
ALTER TABLE ambulances ADD COLUMN IF NOT EXISTS rejection_reason text;

-- Existing seeded demo ambulances are already kyc_verified=true from the
-- demo seed migration -- mark them 'approved' explicitly (not 'demo') so the
-- distinction stays meaningful for ambulances actually registered through
-- the new demo-fill flow going forward.
UPDATE ambulances SET registration_status = 'approved' WHERE kyc_verified = true AND registration_status IS NULL;
UPDATE ambulances SET registration_status = 'pending' WHERE kyc_verified = false AND registration_status IS NULL;

-- Give the seeded ALS demo ambulances real capabilities so cardiac/trauma
-- dispatch matching has something real to match against in the demo, not
-- just an always-empty array.
UPDATE ambulances SET capabilities = ARRAY['general', 'cardiac'] WHERE registration_no IN ('MH12-DEMO-01', 'MH12-DEMO-02') AND capabilities = '{}';
UPDATE ambulances SET capabilities = ARRAY['general', 'trauma'] WHERE registration_no IN ('MH12-DEMO-04', 'MH12-DEMO-05') AND capabilities = '{}';
UPDATE ambulances SET capabilities = ARRAY['general'] WHERE capabilities = '{}' AND type = 'ALS';
