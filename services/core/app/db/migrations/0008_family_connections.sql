-- Family space: a patient's own shareable code (set once, shown to family),
-- and one-directional "I watch them" connections made by entering someone
-- else's code. Applied directly against the live DB this session;
-- documented here for the real migration history.
ALTER TABLE health_profiles ADD COLUMN IF NOT EXISTS family_code text UNIQUE;

CREATE TABLE IF NOT EXISTS family_connections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz DEFAULT now(),
    watcher_user_id uuid NOT NULL REFERENCES users(id),
    watched_user_id uuid NOT NULL REFERENCES users(id),
    UNIQUE (watcher_user_id, watched_user_id)
);
