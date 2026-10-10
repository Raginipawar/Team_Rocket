-- DRAFT (see note in 0001_init.sql). Adds a column both db/repos/rooms.py
-- (patch_room) and domain/reservations.py (walk_in_override) already assume
-- exists for technical.md §11.7 walk-in override, but which was never in the
-- original schema or ORM models -- found by actually running the code
-- against the real database, not just reading it.

ALTER TABLE rooms ADD COLUMN IF NOT EXISTS override_reason text;
