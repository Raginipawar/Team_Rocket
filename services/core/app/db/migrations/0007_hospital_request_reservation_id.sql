-- DRAFT (see note in 0001_init.sql). Denormalized back-reference:
-- domain/reservations.py reads req.reservation_id (hospital_requests ->
-- reservations), while the spec's own direction is the reverse
-- (reservations.hospital_request_id). Both nullable, both queryable --
-- true 1:1, no real correctness risk from the redundancy.

ALTER TABLE hospital_requests ADD COLUMN IF NOT EXISTS reservation_id uuid REFERENCES reservations(id);
