-- DRAFT (see note in 0001_init.sql). Denormalized room_id on reservations --
-- not in technical.md §5.5's strict table (there the link is only via
-- reservation_items), but db/repos/reservations.py's release_reservation()
-- reads res.room_id after a fresh db.get(), and that was silently always
-- None without this column -- release_reservation never actually freed the
-- room on reject/timeout/refused-transport. Found by running the code
-- against the real database.

ALTER TABLE reservations ADD COLUMN IF NOT EXISTS room_id uuid REFERENCES rooms(id);
