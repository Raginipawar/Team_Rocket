-- Hospital self-registration (automatic dashboard access, no approval step
-- for the demo -- spec explicitly dropped the verification workflow).
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS integration_mode text CHECK (integration_mode IN ('manual', 'api')) DEFAULT 'manual';
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS hospital_code text UNIQUE;
UPDATE hospitals SET hospital_code = 'HSP-' || LPAD((FLOOR(random() * 900000) + 100000)::text, 6, '0') WHERE hospital_code IS NULL;
