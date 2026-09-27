-- DRAFT migration (see note in 0001_init.sql -- Person B owns this path).
-- technical.md §10.4 mentions the outbox table by name ("outbox(event)") but
-- doesn't give its DDL in §5; this is A's design to make the transactional
-- outbox pattern (§10.4, §8 `seq` monotonic-per-channel) actually work.

CREATE TABLE channel_seq (
  channel text PRIMARY KEY,
  next_seq bigint NOT NULL DEFAULT 1
);

CREATE TABLE outbox (
  id bigserial PRIMARY KEY,
  channel text NOT NULL,
  event text NOT NULL,
  seq bigint NOT NULL,
  data jsonb NOT NULL,
  created_at timestamptz DEFAULT now(),
  sent_at timestamptz NULL
);
CREATE INDEX ON outbox (sent_at) WHERE sent_at IS NULL;
CREATE INDEX ON outbox (channel, seq);
