-- The registration form already lets a hospital choose "API integration",
-- but there was nowhere afterward to actually enter the endpoint/key --
-- a dead-end choice. Minimal real settings (not a full gateway: no
-- connection testing, webhooks or field-level permission UI -- those are
-- out of scope for now, this just makes the choice actually go somewhere).
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS integration_endpoint_url text;
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS integration_api_key text;
ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS integration_last_synced_at timestamptz;
