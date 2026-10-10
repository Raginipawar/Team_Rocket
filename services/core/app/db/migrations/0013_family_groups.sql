-- Replaces the directional "watch" model (family_connections) with a real
-- group-membership model: one family per user (enforced by UNIQUE on
-- family_members.user_id alone, not per-pair), shared family_id, symmetric
-- visibility between all members. The old family_connections table and
-- health_profiles.family_code column are left in place but unused -- no
-- other code references them after this, so nothing to migrate.
CREATE TABLE IF NOT EXISTS families (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz DEFAULT now(),
    code text UNIQUE NOT NULL,
    name text,
    owner_user_id uuid NOT NULL REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS family_members (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz DEFAULT now(),
    family_id uuid NOT NULL REFERENCES families(id),
    user_id uuid NOT NULL UNIQUE REFERENCES users(id)
);
