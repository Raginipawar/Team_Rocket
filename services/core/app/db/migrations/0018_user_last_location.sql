-- "Call ambulance for them" should use the family member's OWN last known
-- location (their phone, their app), not the caller's current GPS -- the
-- caller may not even be with them. Patient apps ping this periodically
-- while open; the emergency-creation fallback below reads it.
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_location geography(Point,4326);
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_location_accuracy_m real;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_location_at timestamptz;
