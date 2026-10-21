-- Photo attachment for an emergency, same "never blocks the real pipeline"
-- principle as audio: stored directly in Postgres (bytea) rather than wiring
-- up a new object-storage bucket under time pressure -- a few hundred KB per
-- emergency is trivial for Postgres and this is demo-scale traffic, not
-- production volume. photo_analysis holds whatever the ML service's
-- photo-triage capability returns (both the vision-LLM read and the
-- fine-tuned classifier's read, see services/ml/app/capabilities/photo_triage).
ALTER TABLE emergencies ADD COLUMN IF NOT EXISTS photo_data bytea;
ALTER TABLE emergencies ADD COLUMN IF NOT EXISTS photo_mime text;
ALTER TABLE emergencies ADD COLUMN IF NOT EXISTS photo_analysis jsonb;
ALTER TABLE emergencies ADD COLUMN IF NOT EXISTS photo_uploaded_at timestamptz;
