# GoldenHour — Technical Specification

> **HackMatrix 5.0 · HLTH-02 Real-Time Emergency Resource Allocator**
> This is the technical backbone. Every module, contract, table, state machine, model and edge case is defined here. The three work-distribution files will be derived from this document; **the contracts in this file are the source of truth**.

---

## 0. Non-negotiable engineering principles

1. **No feature reduction.** Every feature listed in `project-description.md` (features 1–39 and all tough scenarios) is in scope for the MVP. Nothing is dropped, stubbed, faked, or replaced with a hard-coded demo path.
2. **No simplification, no quality degradation.** Features are built to their full specification in this document. "It works for the happy path" is not done. A feature is done only when its edge cases in §14 pass their tests.
3. **Real code paths in the demo.** The simulator drives the system through the *same public APIs* real users would use. No demo-only shortcuts, no bypassed locks, no pre-computed results.
4. **Honest ML.** Every model is trained, evaluated on a held-out set the model never saw, and reported with real metrics. Synthetic data is labelled synthetic. Uncertainty is always shown.
5. **Contracts first.** API, WebSocket and ML-service contracts (§7–§9) are frozen before implementation. Any change goes through a contract change note in `packages/contracts/CHANGELOG.md` and is announced to the team.
6. **Every module is independently runnable** against mocks (§17), so no teammate is blocked on another.
7. **Correctness under concurrency** is enforced by the database, not by the UI.
8. **Fail safe.** When anything fails, the system degrades toward a safe, explicit behaviour (fallback, escalation, *Call 108*), never toward silence.
9. **Everything auditable.** Every automated decision, human override, and model output that affects routing is written to the append-only audit log.
10. **Web only.** No native app development. All clients are Next.js web apps, responsive for phones, installable as a PWA (a manifest + service worker — no native code).

---

## 1. System architecture

```
                         ┌─────────────────────────────────────────┐
  Patient web app ──────►│                                         │◄──── Ambulance web app
  (/patient)       REST  │          CORE SERVICE (FastAPI)          │ REST+WS (/ambulance)
                   + WS  │  auth · emergencies · dispatch ·        │
  Family page ◄──────────│  hospital selection · reservations ·    │────► Hospital dashboard
  (/track/[t])      WS   │  rule engine · escalation · sim ·       │ REST+WS (/hospital)
                         │  scenario runner · analytics · audit     │
  Ops page ◄────────────►│                                         │
  (/ops/[token])  REST+WS└───┬──────────┬──────────┬───────────┬──┘
                             │          │          │           │
                    HTTP     │          │          │           │ HTTPS webhooks
                             ▼          ▼          ▼           ▼
                   ┌──────────────┐ ┌────────┐ ┌──────┐ ┌──────────────────────┐
                   │  ML SERVICE  │ │Postgres│ │Redis │ │ SMS gateway (Android)│
                   │  (FastAPI)   │ │+PostGIS│ │      │ │ Telegram Bot API     │
                   │ STT·LLM·     │ └────────┘ └──────┘ └──────────────────────┘
                   │ triage·rank· │
                   │ ETA·nowcast· │──► OSRM (self-hosted) · Mapbox Directions (traffic)
                   │ forecast·OR  │──► Ollama (local LLM)
                   └──────────────┘
```

### 1.1 Services

| Service | Tech | Port | Responsibility |
|---|---|---|---|
| `apps/web` | Next.js (App Router) + TypeScript | 3000 | All UIs: patient, ambulance, hospital, family tracking, ops page |
| `services/core` | FastAPI (Python 3.11+) | 8000 | Business logic, state machines, concurrency, rule engine, escalation, WebSockets, webhooks, simulator, scenario runner, analytics |
| `services/ml` | FastAPI (Python 3.11+) | 8001 | Every AI/ML model and geo-computation behind a stable HTTP contract |
| `postgres` | PostgreSQL 16 + PostGIS 3 | 5432 | Source of truth |
| `redis` | Redis 7 | 6379 | Live GPS, pub/sub fan-out, job queue, rate limits, leader lock |
| `osrm` | OSRM backend (Pune extract, car profile) | 5000 | Routes, route geometry, distance/duration tables |
| `ollama` | Ollama | 11434 | Local LLM (Qwen2.5-7B-Instruct) |
| `sms-gateway` | Android phone + textbee or httpSMS app | — | Inbound/outbound SMS via webhook/API |
| `telegram` | Telegram Bot API | — | Crisis escalation |
| `tunnel` | Cloudflare Tunnel (or ngrok) | — | Public HTTPS for SMS + Telegram webhooks |

### 1.2 Why this split

- **Core ↔ ML over HTTP** means the ML owner can iterate on models without touching business logic, and core can run with `ML_MODE=mock` (§17).
- **Postgres is the single source of truth** for all state that matters for correctness (reservations, assignments, statuses). Redis holds only derived/ephemeral data; losing Redis never corrupts state.
- **WebSockets for everything live**; REST for every mutation (mutations are idempotent and versioned).

---

## 2. Repository layout (monorepo)

```
goldenhour/
├── apps/
│   └── web/                         # Next.js app
│       ├── app/
│       │   ├── (patient)/patient/...          # SOS, profile, live emergency view
│       │   ├── (ambulance)/ambulance/...      # offers, active job, status
│       │   ├── (hospital)/hospital/...        # dashboard, rooms, staff, analytics
│       │   ├── track/[token]/page.tsx         # family tracking (public, token)
│       │   ├── ops/[token]/page.tsx           # one-time link → incident / analytics / scenarios
│       │   └── login/...
│       ├── components/  (map/, ui/, realtime/)
│       ├── lib/  (api-client (generated), ws-client, offline-queue, auth)
│       ├── public/manifest.webmanifest
│       └── service-worker.ts
├── services/
│   ├── core/
│   │   ├── app/
│   │   │   ├── api/v1/        # routers: auth, patient, emergencies, ambulance, hospital, ops, webhooks, track
│   │   │   ├── domain/        # state machines, dispatch, selection, reservations, rules, escalation
│   │   │   ├── db/            # SQLAlchemy models, repositories, migrations (Alembic)
│   │   │   ├── realtime/      # WS manager, channels, Redis pub/sub
│   │   │   ├── jobs/          # arq workers: timers, sweepers, forecasts
│   │   │   ├── integrations/  # ml_client, sms_client, telegram_client
│   │   │   ├── sim/           # simulator + scenario runner
│   │   │   └── analytics/
│   │   └── tests/             # unit, concurrency, scenario
│   └── ml/
│       ├── app/
│       │   ├── api/v1/        # one router per capability
│       │   ├── models/        # model wrappers (load, predict, version)
│       │   ├── geo/           # osrm, mapbox, road comfort, gazetteer
│       │   ├── protocols/     # follow-up question trees, first-aid scripts (JSON)
│       │   └── mock/          # deterministic schema-valid mock responses
│       ├── training/          # notebooks + scripts per model, eval reports
│       ├── data/              # synthetic generators, raw pulls (OSM), processed datasets
│       └── artifacts/         # trained model files (git-lfs or downloaded at startup)
├── packages/
│   └── contracts/
│       ├── openapi.core.yaml      # SOURCE OF TRUTH for core REST
│       ├── openapi.ml.yaml        # SOURCE OF TRUTH for ML service
│       ├── ws-events.schema.json  # SOURCE OF TRUTH for WS events
│       ├── enums.json             # shared enums (single definition)
│       └── CHANGELOG.md
├── data/seed/                     # hospitals, rooms, staff, ambulances, users, landmarks
├── infra/
│   ├── docker-compose.yml
│   ├── osrm/ (prepare script for Pune extract)
│   └── env/.env.example
└── docs/  (project-description.md, technical.md, work-distribution-*.md)
```

Type generation: `openapi-typescript` generates `apps/web/lib/api-types.ts` from `openapi.core.yaml`. Pydantic models in core/ml are validated against the OpenAPI files in CI (`schemathesis` contract tests).

---

## 3. Shared enums (`packages/contracts/enums.json`)

Defined once; imported by all three codebases.

```jsonc
{
  "Role": ["patient", "paramedic", "hospital_staff", "developer"],
  "Acuity": ["critical", "urgent", "stable"],
  "Facility": ["cardiac", "stroke", "trauma", "burns", "respiratory", "obstetric", "pediatric", "poisoning", "general"],
  "AmbulanceType": ["BLS", "ALS"],
  "AmbulanceStatus": ["offline", "available", "dispatched", "at_scene", "transporting", "at_hospital", "cleaning", "out_of_service"],
  "EmergencyStatus": ["received", "triaged", "dispatching", "ambulance_assigned", "at_scene", "patient_on_board",
                      "hospital_selecting", "hospital_confirmed", "arrived_hospital", "handed_off", "closed",
                      "cancelled", "refused_transport", "merged_duplicate"],
  "Channel": ["app_button", "app_voice", "app_text", "sms"],
  "OfferStatus": ["pending", "accepted", "declined", "expired", "superseded"],
  "HospitalRequestStatus": ["pending", "accepted", "rejected", "timeout", "cancelled", "superseded"],
  "ReservationStatus": ["held", "confirmed", "consumed", "released", "expired", "overridden"],
  "RoomType": ["er_bed", "resus_bay", "trauma_bay", "icu_bed", "labour_room", "burns_unit", "pediatric_er"],
  "RoomStatus": ["free", "reserved", "occupied", "cleaning", "out_of_service"],
  "ResourceType": ["ventilator", "cath_lab", "ct_scanner", "mri", "defibrillator", "blood_o_neg", "blood_o_pos",
                   "blood_a_pos", "blood_b_pos", "blood_ab_pos", "dialysis", "operating_theatre"],
  "Capability": ["cardiac_cathlab", "stroke_thrombolysis", "trauma_center", "burns_unit", "obstetrics",
                 "pediatrics", "toxicology", "icu", "neurosurgery", "general_er"],
  "StaffSpecialty": ["emergency_physician", "cardiologist", "neurologist", "trauma_surgeon", "burns_surgeon",
                     "obstetrician", "pediatrician", "pulmonologist", "anesthetist", "er_nurse"],
  "RejectReason": ["NO_BED", "NO_SPECIALIST", "EQUIPMENT_DOWN", "OVER_CAPACITY", "NOT_EQUIPPED_FOR_CASE", "OTHER"],
  "OverrideReason": ["WALK_IN_CRITICAL", "BED_UNUSABLE", "INTERNAL_TRANSFER", "OTHER"],
  "EscalationType": ["mass_casualty", "no_ambulance", "no_hospital", "system_anomaly"],
  "EscalationStatus": ["open", "claimed", "resolved", "auto_defaulted"],
  "Freshness": ["fresh", "aging", "stale"],
  "Language": ["hi", "mr", "en", "hi-en", "mr-en"]
}
```

---

## 4. System constants (`services/core/app/config.py`, overridable via env)

| Constant | Value | Meaning |
|---|---|---|
| `DISPATCH_RADII_KM` | `[5, 10, 20]` | Search radius per dispatch round |
| `OFFERS_PER_ROUND` | `4` | Ambulances offered simultaneously per round |
| `OFFER_EXPIRY_SEC` | `20` | An offer expires if not answered |
| `DISPATCH_ROUND_INTERVAL_SEC` | `30` | Time before the next (wider) round |
| `NO_AMBULANCE_ESCALATE_AFTER_ROUND` | `3` | After round 3 fails (~90 s) → escalation |
| `HOSPITAL_TIMEOUT_SEC` | `45` critical / `60` other | Hospital must answer within this |
| `HOLD_PENDING_TTL_SEC` | `HOSPITAL_TIMEOUT_SEC + 10` | Soft hold while hospital decides |
| `HOLD_CONFIRMED_MIN_SEC` | `600` | Confirmed hold = `max(600, 1.5 × ETA)` |
| `HEARTBEAT_INTERVAL_SEC` | `5` | Ambulance location heartbeat |
| `SIGNAL_WEAK_SEC` / `SIGNAL_LOST_SEC` | `30` / `120` | Connectivity states |
| `OFFLINE_HOLD_GRACE_SEC` | `ETA_remaining + 900` | Keep reservation while ambulance silent |
| `ESCALATION_REPEAT_SEC` | `60` | Re-alert + SMS |
| `ESCALATION_DEFAULT_SEC` | `120` | Auto-execute safe default |
| `FRESH_MAX_MIN` / `AGING_MAX_MIN` | `10` / `30` | Freshness buckets (> 30 = stale) |
| `DUPLICATE_RADIUS_M` / `DUPLICATE_WINDOW_MIN` / `DUPLICATE_SIM` | `500` / `15` / `0.80` | Duplicate detection |
| `MCI_PATIENT_THRESHOLD` | `5` | Mass-casualty trigger |
| `MCI_CLUSTER` | `≥3 calls within 300 m in 10 min` | Mass-casualty trigger |
| `TRIAGE_REVIEW_CONFIDENCE` | `0.60` | Below → `needs_review`, ALS dispatched regardless |
| `PRANK_VERIFY_WAIT_SEC` | `30` | Non-critical suspicious calls only |
| `GEOFENCE_SCENE_M` / `GEOFENCE_HOSPITAL_M` | `75` / `150` | Auto-arrival detection |
| `IDLE_ALERT_SEC` / `IDLE_REASSIGN_SEC` | `90` / `150` | Driver not progressing |
| `OFFLOAD_DELAY_ALERT_MIN` | `15` | Offload delay alert |
| `DETERIORATION_DIVERT_GAIN_SEC` | `180` | Divert only if new target is ≥ 3 min faster to definitive care |
| `IDEMPOTENCY_TTL_H` | `24` | Stored idempotent responses |
| `OPS_LINK_TTL_MIN` / `OPS_SESSION_H` | `15` / `2` | One-time link / session |

---

## 5. Database schema (PostgreSQL + PostGIS)

All tables: `id UUID PK DEFAULT gen_random_uuid()`, `created_at timestamptz DEFAULT now()`, `updated_at timestamptz` (trigger-maintained) unless stated. All times are server time (UTC). Migrations via Alembic.

### 5.1 Identity

```sql
users (
  id uuid PK, role text NOT NULL CHECK (role IN (...Role)),
  name text, phone text UNIQUE, language text DEFAULT 'en',
  password_hash text,                -- staff/paramedic/developer (argon2id)
  hospital_id uuid NULL REFERENCES hospitals,   -- hospital_staff
  ambulance_id uuid NULL REFERENCES ambulances, -- paramedic
  telegram_user_id bigint NULL,      -- developer
  is_active bool DEFAULT true
)

health_profiles (
  user_id uuid PK REFERENCES users,
  dob date, sex text, blood_group text,
  allergies text[], conditions text[], medications text[],
  insurance_provider text, insurance_policy_no text,
  home_address text, home_location geography(Point,4326),
  notes text, version int DEFAULT 1
)

emergency_contacts (
  id uuid PK, user_id uuid REFERENCES users,
  name text, phone text, relation text, language text, priority int
)

otp_codes (phone text, code_hash text, expires_at timestamptz, attempts int DEFAULT 0)
```

### 5.2 Hospitals

```sql
hospitals (
  id uuid PK, name text, address text, location geography(Point,4326),
  er_entrance_note text,                 -- e.g. "Gate 2, ground floor"
  duty_manager_phone text,
  capabilities text[] NOT NULL,          -- Capability enum
  stabilization_capable bool DEFAULT true,
  is_active bool DEFAULT true,
  last_confirmed_at timestamptz,         -- staff "Confirm availability" ping
  is_simulated bool DEFAULT true
)

rooms (
  id uuid PK, hospital_id uuid REFERENCES hospitals,
  code text,                             -- "ER-3"
  type text CHECK (type IN (...RoomType)),
  status text CHECK (status IN (...RoomStatus)) DEFAULT 'free',
  location_note text,                    -- "Ground floor, ER Bay 3"
  priority_order int,                    -- allocation preference (lower first)
  reservation_id uuid NULL,
  version int NOT NULL DEFAULT 1,
  status_updated_at timestamptz DEFAULT now(),
  UNIQUE (hospital_id, code)
)
CREATE INDEX ON rooms (hospital_id, type, status);

hospital_resources (
  id uuid PK, hospital_id uuid REFERENCES hospitals,
  type text CHECK (type IN (...ResourceType)),
  total int, available int CHECK (available >= 0), reserved int DEFAULT 0 CHECK (reserved >= 0),
  CHECK (available + reserved <= total),
  version int NOT NULL DEFAULT 1,
  reported_at timestamptz NOT NULL,      -- when staff last reported this number
  UNIQUE (hospital_id, type)
)

staff (
  id uuid PK, hospital_id uuid REFERENCES hospitals,
  name text, specialty text, phone text, is_active bool DEFAULT true
)

staff_shifts (
  id uuid PK, staff_id uuid REFERENCES staff,
  start_at timestamptz, end_at timestamptz,
  EXCLUDE USING gist (staff_id WITH =, tstzrange(start_at,end_at) WITH &&)
)

hospital_occupancy_history (             -- feeds bed nowcasting + analytics
  hospital_id uuid, room_type text, ts timestamptz,
  free int, occupied int, reserved int,
  PRIMARY KEY (hospital_id, room_type, ts)
)
```

### 5.3 Ambulances

```sql
ambulances (
  id uuid PK, registration_no text UNIQUE, type text CHECK (type IN ('BLS','ALS')),
  equipment text[],
  status text CHECK (status IN (...AmbulanceStatus)) DEFAULT 'offline',
  current_location geography(Point,4326), heading real, speed_kmh real,
  last_heartbeat_at timestamptz,
  active_emergency_id uuid NULL,
  kyc_verified bool DEFAULT false, driver_license_no text, kyc_verified_at timestamptz,
  version int NOT NULL DEFAULT 1,
  is_simulated bool DEFAULT true
)
CREATE INDEX ON ambulances USING gist (current_location);
CREATE INDEX ON ambulances (status, type);

ambulance_status_log (ambulance_id uuid, from_status text, to_status text, at timestamptz, emergency_id uuid)
```

### 5.4 Emergencies

```sql
incidents (                              -- groups duplicate calls / MCI
  id uuid PK, location geography(Point,4326),
  patient_count int DEFAULT 1, is_mass_casualty bool DEFAULT false,
  status text DEFAULT 'active'
)

emergencies (
  id uuid PK, incident_id uuid REFERENCES incidents,
  caller_user_id uuid NULL REFERENCES users, caller_phone text,
  channel text CHECK (channel IN (...Channel)),
  raw_text text, audio_object_key text, transcript text, language text,
  stt_confidence real,
  extracted jsonb,                       -- ExtractedFacts (§9.2)
  location geography(Point,4326), location_accuracy_m real, landmark_text text,
  location_source text,                  -- gps | landmark_geocode | profile_home
  ai_acuity text, ai_facility text, ai_confidence real, ai_probs jsonb, needs_review bool,
  final_acuity text, final_facility text,   -- after paramedic confirmation
  required_ambulance_type text,
  fragility bool DEFAULT false,          -- spinal/fracture/pregnancy/pediatric → comfort weight
  mlc_flag bool DEFAULT false,
  prank_score real, prank_verified bool NULL,
  duplicate_of uuid NULL,
  predicted_resources jsonb,
  handover_note jsonb,                   -- SBAR (§9.9)
  status text CHECK (status IN (...EmergencyStatus)),
  ambulance_id uuid NULL, hospital_id uuid NULL, reservation_id uuid NULL,
  eta_to_patient_sec int, eta_to_hospital_sec int, eta_low_sec int, eta_high_sec int,
  family_track_token_hash text,
  escalated bool DEFAULT false,
  version int NOT NULL DEFAULT 1,
  -- timestamps for analytics:
  received_at timestamptz, triaged_at timestamptz, assigned_at timestamptz, at_scene_at timestamptz,
  on_board_at timestamptz, hospital_confirmed_at timestamptz, arrived_hospital_at timestamptz,
  handed_off_at timestamptz, closed_at timestamptz
)
CREATE INDEX ON emergencies USING gist (location);
CREATE INDEX ON emergencies (status);
CREATE INDEX ON emergencies (received_at);

patients (
  id uuid PK, emergency_id uuid REFERENCES emergencies,
  user_id uuid NULL REFERENCES users,
  temp_id text UNIQUE,                   -- "UNK-20260927-0042" for unknown patients
  is_unknown bool, est_age int, sex text,
  merged_into_user_id uuid NULL
)

followup_answers (
  id uuid PK, emergency_id uuid, question_id text, answer_raw text, answer_parsed jsonb, language text
)

triage_confirmations (                   -- learning loop
  id uuid PK, emergency_id uuid, paramedic_id uuid,
  ai_acuity text, ai_facility text, ai_confidence real,
  final_acuity text, final_facility text, changed bool,
  input_text text, model_version text, used_for_training bool DEFAULT false
)
```

### 5.5 Dispatch, hospital requests, reservations

```sql
dispatch_offers (
  id uuid PK, emergency_id uuid, ambulance_id uuid, round int,
  status text CHECK (status IN (...OfferStatus)) DEFAULT 'pending',
  predicted_accept_prob real, predicted_eta_sec int, rank int,
  offered_at timestamptz, expires_at timestamptz, responded_at timestamptz,
  UNIQUE (emergency_id, ambulance_id)
)
CREATE INDEX ON dispatch_offers (ambulance_id, status);

hospital_requests (
  id uuid PK, emergency_id uuid, hospital_id uuid, rank int,
  score real, explanation jsonb,          -- top factors (§9.13)
  features jsonb,                         -- snapshot of ranking features (audit/training)
  status text CHECK (status IN (...HospitalRequestStatus)) DEFAULT 'pending',
  reason_code text NULL, reason_note text NULL,
  is_family_choice bool DEFAULT false, is_priority bool DEFAULT false,
  sent_at timestamptz, expires_at timestamptz, responded_at timestamptz, responded_by uuid
)
CREATE UNIQUE INDEX one_pending_request_per_emergency
  ON hospital_requests (emergency_id) WHERE status = 'pending';

reservations (
  id uuid PK, emergency_id uuid, hospital_id uuid, hospital_request_id uuid,
  status text CHECK (status IN (...ReservationStatus)),
  hold_expires_at timestamptz NOT NULL,
  version int NOT NULL DEFAULT 1
)
CREATE UNIQUE INDEX one_active_reservation_per_emergency
  ON reservations (emergency_id) WHERE status IN ('held','confirmed');

reservation_items (
  id uuid PK, reservation_id uuid,
  kind text CHECK (kind IN ('room','resource','staff')),
  room_id uuid NULL, resource_type text NULL, quantity int DEFAULT 1, staff_id uuid NULL
)

handoffs (
  emergency_id uuid PK, hospital_id uuid, room_id uuid,
  receiving_staff_ids uuid[],
  arrived_at timestamptz, offloaded_at timestamptz, offload_delay_sec int GENERATED ALWAYS AS
    (EXTRACT(EPOCH FROM (offloaded_at - arrived_at))::int) STORED
)
```

### 5.6 Escalation, notifications, security, audit

```sql
escalations (
  id uuid PK, type text, emergency_id uuid NULL, incident_id uuid NULL,
  status text CHECK (status IN (...EscalationStatus)) DEFAULT 'open',
  summary text, options jsonb,           -- [{id, label, action, params, is_default}]
  default_option_id text,
  chosen_option_id text NULL, claimed_by uuid NULL, claimed_at timestamptz,
  resolved_at timestamptz, telegram_message_ids jsonb,
  repeat_at timestamptz, default_at timestamptz,
  version int NOT NULL DEFAULT 1
)

one_time_tokens (
  token_hash text PK, purpose text CHECK (purpose IN ('ops','family_track')),
  escalation_id uuid NULL, emergency_id uuid NULL, issued_to uuid NULL,
  expires_at timestamptz, used_at timestamptz NULL
)

notifications (
  id uuid PK, recipient_kind text, recipient_ref text,
  channel text CHECK (channel IN ('ws','push','sms','telegram')),
  template text, payload jsonb, status text, error text, sent_at timestamptz
)

sms_messages (
  id uuid PK, direction text CHECK (direction IN ('in','out')), phone text, body text,
  emergency_id uuid NULL, gateway_message_id text, status text
)

caller_reputation (
  phone text PK, total_calls int, prank_flags int, last_prank_at timestamptz,
  requires_verification bool DEFAULT false
)

idempotency_keys (
  key text, user_id uuid, endpoint text, request_hash text,
  status_code int, response jsonb, created_at timestamptz,
  PRIMARY KEY (key, user_id)
)

push_subscriptions (id uuid PK, user_id uuid, fcm_token text, created_at timestamptz)

audit_log (
  id bigserial PK, at timestamptz DEFAULT now(),
  actor_type text CHECK (actor_type IN ('system','ai','user','developer','simulator')),
  actor_id text, entity text, entity_id uuid, action text,
  before jsonb, after jsonb, reason text, model_version text, correlation_id uuid
)
-- append-only: trigger raises on UPDATE/DELETE
CREATE RULE audit_no_update AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
CREATE RULE audit_no_delete AS ON DELETE TO audit_log DO INSTEAD NOTHING;

landmarks (                              -- offline gazetteer from OSM
  id bigserial PK, name text, name_normalized text, alt_names text[],
  kind text, location geography(Point,4326)
)
CREATE INDEX ON landmarks USING gin (name_normalized gin_trgm_ops);

demand_forecasts (h3_cell text, window_start timestamptz, predicted_calls real, model_version text,
                  PRIMARY KEY (h3_cell, window_start))
ml_predictions (id bigserial PK, at timestamptz, capability text, emergency_id uuid, input jsonb,
                output jsonb, model_version text, latency_ms int)
```

---

## 6. State machines

Every transition is a single SQL `UPDATE ... WHERE status = <expected> AND version = <expected>`; zero rows updated ⇒ `409 CONFLICT`. Every transition writes `audit_log` and publishes a WS event in the same unit of work (outbox pattern, §10.4).

### 6.1 Emergency

```
received ──AI done──► triaged ──► dispatching ──accept──► ambulance_assigned
                                     ▲   │                     │ geofence/tap
                                     │   └─ no accept → escalation(no_ambulance)
      breakdown/idle reassign ───────┘                         ▼
                                                            at_scene
                                                               │ triage confirm
                                                               ▼
                                                        patient_on_board
                                                               │ (auto)
                                                               ▼
       reject/timeout/override → next hospital ──► hospital_selecting ──accept──► hospital_confirmed
                                                     │ none left → escalation(no_hospital)   │ geofence/tap
                                                     ▼                                        ▼
                                                                                    arrived_hospital
                                                                                              │ "patient received"
                                                                                              ▼
                                                                                         handed_off → closed
Side exits: cancelled (caller/ops), refused_transport (paramedic), merged_duplicate (AI duplicate).
Deterioration/family override/wrong triage: hospital_confirmed → hospital_selecting (old reservation released).
```

Allowed transitions are encoded in `domain/emergency_fsm.py` as a dict; any other transition raises.

### 6.2 Ambulance

```
offline ⇄ available ─accept─► dispatched ─geofence─► at_scene ─confirm─► transporting
   ▲          ▲                    │                                        │ geofence
   │          └──── "Ready" ── cleaning ◄── offloaded ── at_hospital ◄──────┘
   └─ out_of_service ◄─ vehicle issue (from any active state)
```

Go-online requires `kyc_verified = true`.

### 6.3 Reservation

```
held ──hospital accepts──► confirmed ──handoff──► consumed
 │                             │
 ├─ reject / timeout ──► released
 ├─ hold_expires_at passed ──► expired
                               ├─ staff override ──► overridden
                               ├─ divert / cancel / refused ──► released
                               └─ silent ambulance beyond grace ──► expired (+ escalation)
```

Invariant (DB-enforced): at most one `held|confirmed` reservation per emergency; a room's `reservation_id` is set iff its status is `reserved`.

### 6.4 Escalation

```
open ──first claim──► claimed ──option chosen──► resolved
  │ 60 s: repeat + SMS
  └ 120 s unclaimed ──► auto_defaulted (default option executed)
claimed but no choice within 120 s of claim ──► auto_defaulted
```

---

## 7. Core REST API (`/api/v1`) — contract

### 7.1 Conventions

- JSON; `snake_case`; timestamps ISO-8601 UTC.
- Auth: `Authorization: Bearer <access_jwt>` (15 min) + refresh token (httpOnly cookie, 7 days). JWT claims: `sub, role, hospital_id?, ambulance_id?`.
- **Every mutating request** (POST/PATCH/DELETE) **must** send `Idempotency-Key: <uuid v4>`. Same key + same body ⇒ stored response replayed. Same key + different body ⇒ `422 IDEMPOTENCY_MISMATCH`.
- **Versioned updates** send `"version": <int>`; mismatch ⇒ `409 VERSION_CONFLICT` with `current` object in the body.
- `X-Correlation-Id` returned on every response and propagated to ML calls and audit.
- Error envelope:

```json
{ "error": { "code": "VERSION_CONFLICT", "message": "Room was modified", "details": { "current": { } } } }
```

| HTTP | code | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Bad body |
| 401 | `UNAUTHENTICATED` | Missing/expired token |
| 403 | `FORBIDDEN` | Role/ownership check failed (enforced server-side on every route) |
| 404 | `NOT_FOUND` | |
| 409 | `VERSION_CONFLICT`, `ALREADY_TAKEN`, `INVALID_TRANSITION`, `RESOURCE_UNAVAILABLE`, `ROOM_RESERVED` | Concurrency / state conflicts |
| 422 | `IDEMPOTENCY_MISMATCH` | |
| 429 | `RATE_LIMITED` | Per-phone / per-user limits |
| 503 | `DEPENDENCY_UNAVAILABLE` | Only when no fallback exists (core then shows *Call 108*) |

### 7.2 Auth

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/otp/request` | `{phone}` | `204` — OTP sent via SMS gateway (6 digits, 5 min, 5 attempts, rate-limited 3/10 min) |
| POST | `/auth/otp/verify` | `{phone, code}` | `{access_token, user}` + refresh cookie. Creates patient user on first login |
| POST | `/auth/login` | `{username_or_phone, password}` | Staff/paramedic/developer login |
| POST | `/auth/refresh` | — | `{access_token}` |
| POST | `/auth/logout` | — | `204` |

### 7.3 Patient

| Method | Path | Notes |
|---|---|---|
| GET/PUT | `/me/profile` | Health profile; PUT requires `version` |
| GET/POST | `/me/contacts` · DELETE `/me/contacts/{id}` | Emergency contacts |
| POST | `/me/push-subscriptions` | `{fcm_token}` |
| POST | `/emergencies` | Create SOS (below) |
| GET | `/emergencies/{id}` | Role-filtered view |
| GET | `/emergencies/{id}/followup` | Current follow-up question + first-aid steps |
| POST | `/emergencies/{id}/followup` | Answer (text or audio) |
| POST | `/emergencies/{id}/cancel` | `{reason}` |

**`POST /emergencies`** — `multipart/form-data`

| Field | Type | Required |
|---|---|---|
| `channel` | `app_button` \| `app_voice` \| `app_text` | yes |
| `audio` | file (webm/ogg/wav, ≤ 60 s, ≤ 5 MB) | if `app_voice` |
| `text` | string ≤ 1000 | if `app_text` |
| `lat`, `lng`, `accuracy_m` | number | yes if browser gives them |
| `for_self` | bool | default true (attach own health profile) |

Response `202`:

```json
{ "emergency_id": "7b0c…", "status": "received", "family_track_url": "https://…/track/…",
  "call_108_fallback": false }
```

Processing continues asynchronously (§10.1); the client subscribes to `emergency:{id}` on WS.

**`GET /emergencies/{id}`** (patient view) — excludes internal scores:

```json
{
  "id": "…", "status": "ambulance_assigned",
  "triage": { "acuity": "critical", "facility": "cardiac", "confidence": 0.91, "confirmed": false },
  "ambulance": { "registration_no": "MH12AB1234", "type": "ALS", "location": {"lat":18.64,"lng":73.77},
                 "eta_sec": 540, "eta_low_sec": 480, "eta_high_sec": 720, "crew_phone": "+91…" },
  "hospital": null,
  "handoff": null,
  "first_aid": { "protocol_id": "cardiac_chest_pain_v1", "steps": ["…"] },
  "version": 7
}
```

### 7.4 Ambulance (role `paramedic`)

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/ambulance/status` | `{status: "available"\|"offline"\|"cleaning_done", version}` | `cleaning_done` → `available` |
| POST | `/ambulance/heartbeat` | `{lat, lng, heading, speed_kmh, accuracy_m, client_ts}` | Also accepted over WS; no idempotency key (latest wins by `client_ts`) |
| GET | `/ambulance/offers` | — | Pending offers with patient summary, pickup ETA, expiry |
| POST | `/offers/{id}/accept` | — | `200 {emergency}` or `409 ALREADY_TAKEN` / `409 OFFER_EXPIRED` |
| POST | `/offers/{id}/decline` | `{reason?}` | |
| GET | `/ambulance/active` | — | Active emergency: patient, route, hospital, handover target |
| POST | `/emergencies/{id}/arrived-scene` | — | Manual fallback; normally geofence |
| POST | `/emergencies/{id}/triage-confirm` | `{acuity, facility, patient_count, version}` | Triggers hospital selection |
| POST | `/emergencies/{id}/critical` | — | Deterioration one-tap |
| POST | `/emergencies/{id}/family-override/options` | — | Returns hospitals with trade-off deltas |
| POST | `/emergencies/{id}/family-override` | `{hospital_id, consent: true}` | |
| POST | `/emergencies/{id}/refused-transport` | `{note?}` | Releases everything |
| POST | `/ambulance/vehicle-issue` | `{note?}` | Out of service + re-dispatch |
| POST | `/emergencies/{id}/arrived-hospital` | — | Manual fallback; normally geofence |

**Offer payload (in list and WS `offer.new`)**

```json
{ "offer_id": "…", "emergency_id": "…", "expires_at": "…",
  "pickup": { "lat": 18.65, "lng": 73.78, "landmark": "Near Ganesh temple, Akurdi", "accuracy_m": 40 },
  "eta_to_pickup_sec": 310, "distance_m": 2400,
  "summary": { "acuity": "critical", "facility": "cardiac", "age": 60, "sex": "M", "patient_count": 1 } }
```

### 7.5 Hospital (role `hospital_staff`, scoped to own `hospital_id`)

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/hospital/dashboard` | — | Incoming, pending requests, rooms, resources, staff on duty, freshness |
| GET | `/hospital/requests?status=pending` | — | |
| POST | `/hospital/requests/{id}/accept` | `{room_id?, staff_ids?}` | Auto-allocates if omitted (§11.6); `409 RESOURCE_UNAVAILABLE` if bundle can't be confirmed |
| POST | `/hospital/requests/{id}/reject` | `{reason_code, note?}` | `reason_code` required |
| PATCH | `/hospital/rooms/{id}` | `{status, version, override_reason?}` | Setting a `reserved` room to `occupied` without `override_reason` ⇒ `409 ROOM_RESERVED` |
| PATCH | `/hospital/resources/{id}` | `{available, total?, version}` | Updates `reported_at` |
| POST | `/hospital/availability/confirm` | — | Freshness ping: stamps `last_confirmed_at` and all `reported_at` |
| POST | `/hospital/handoffs/{emergency_id}/received` | `{receiving_staff_ids?}` | Sets `offloaded_at`, consumes reservation, room → `occupied` |
| GET/POST/PATCH | `/hospital/staff`, `/hospital/staff/{id}/shifts` | | Duty roster |
| POST | `/hospital/patients/{temp_id}/merge` | `{phone}` | Unknown-patient identity merge |
| GET | `/hospital/analytics?from&to` | | Hospital-scoped metrics |

**Incoming patient card (dashboard + WS `hospital.request.new`)**

```json
{
  "request_id": "…", "emergency_id": "…", "expires_at": "…",
  "patient": { "display": "Male, ~60", "temp_id": null, "acuity": "critical", "facility": "cardiac",
               "confirmed_by_paramedic": true, "mlc_flag": false },
  "profile": { "blood_group": "B+", "allergies": ["aspirin"], "conditions": ["type 2 diabetes"],
               "medications": ["metformin"] },
  "handover_note": { "situation": "…", "background": "…", "assessment": "…", "recommendation": "…" },
  "prep_checklist": [ {"item": "cardiologist", "prob": 0.94}, {"item": "cath_lab", "prob": 0.88},
                      {"item": "defibrillator", "prob": 0.81} ],
  "ambulance": { "registration_no": "MH12AB1234", "type": "ALS", "location": {"lat":…,"lng":…},
                 "eta_sec": 660, "eta_low_sec": 600, "eta_high_sec": 840, "signal": "ok" },
  "why_you": [ "Cath lab available", "Cardiologist on duty at arrival", "11 min ETA" ]
}
```

### 7.6 Family tracking (public, token)

| Method | Path | Notes |
|---|---|---|
| GET | `/track/{token}` | Non-clinical view only: ambulance position, ETA range, hospital name/address/entrance, room location note, receiving team name, status. Token = 32-byte random, stored hashed, valid until emergency `closed` + 6 h |

### 7.7 Ops (developer, one-time link)

| Method | Path | Notes |
|---|---|---|
| POST | `/ops/session` | `{token}` → single-use exchange → httpOnly session cookie (2 h) |
| GET | `/ops/overview` | All live emergencies, ambulances, hospitals, open escalations |
| GET | `/ops/escalations/{id}` | Summary, options, map data |
| POST | `/ops/escalations/{id}/claim` | CAS on `status='open'`; `409 ALREADY_TAKEN` |
| POST | `/ops/escalations/{id}/resolve` | `{option_id}`; only the claimer |
| POST | `/ops/emergencies/{id}/override` | Manual assignment with mandatory `reason` |
| GET | `/ops/analytics?from&to` | System-wide metrics |
| GET | `/ops/audit?entity_id=` | Audit trail |
| GET | `/ops/scenarios` · POST `/ops/scenarios/{name}/run` · POST `/ops/sim/reset` · POST `/ops/sim/speed {multiplier}` | Scenario runner (§15) |

### 7.8 Webhooks

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/webhooks/sms` | Shared secret header / HMAC (per gateway app) | Inbound SMS → §12.1. Always `200` fast; processing is async |
| POST | `/webhooks/telegram` | `X-Telegram-Bot-Api-Secret-Token` | Commands and button callbacks → §13 |

### 7.9 Health

`GET /healthz` (liveness), `GET /readyz` (DB, Redis, ML, OSRM status). Frontend polls `/readyz` and shows *Call 108* banner after 2 consecutive failures or any failed SOS submission after retries.

---

## 8. WebSocket contract

**Endpoint:** `GET /ws?token=<access_jwt | track_token | ops_session>`
**Envelope (server → client):**

```json
{ "event": "ambulance.location", "channel": "emergency:7b0c…", "seq": 1842, "ts": "…", "data": { } }
```

`seq` is monotonic per channel; clients ignore out-of-order `seq` and call the REST GET to resync on a gap.

**Client → server:** `{"op":"subscribe","channel":"…"}`, `{"op":"unsubscribe",…}`, `{"op":"heartbeat","data":{…}}` (paramedic only), `{"op":"ping"}`.

**Channel authorisation**

| Channel | Who may subscribe |
|---|---|
| `emergency:{id}` | Caller (patient view), assigned paramedic, requested/confirmed hospital (hospital view), ops |
| `track:{token}` | Family (non-clinical view) |
| `ambulance:{id}` | That ambulance's paramedic |
| `hospital:{id}` | That hospital's staff |
| `ops` | Ops session |

The server projects each event to the subscriber's role (patient/family never receive scores, internal features, or other patients' data).

**Events**

| Event | Channels | Data |
|---|---|---|
| `emergency.status` | emergency, track, ops | `{status, version}` |
| `emergency.triage` | emergency, ops | `{acuity, facility, confidence, needs_review, confirmed}` |
| `emergency.followup` | emergency | `{question}` or `{done:true}` |
| `emergency.first_aid` | emergency | `{protocol_id, steps}` |
| `offer.new` / `offer.revoked` | ambulance | offer payload / `{offer_id, reason: "taken"\|"expired"\|"cancelled"}` |
| `ambulance.location` | emergency, track, hospital (incoming only), ops | `{lat,lng,heading,speed_kmh,eta_sec,eta_low_sec,eta_high_sec,signal}` |
| `ambulance.signal` | emergency, hospital, ops | `{signal: "ok"\|"weak"\|"lost", last_seen_at}` |
| `hospital.request.new` / `hospital.request.revoked` | hospital | card / `{request_id, reason}` |
| `hospital.selected` | emergency, track, ops | `{hospital, rank_explanation, eta}` |
| `handoff.ready` | emergency, track | `{room_location_note, receiving_team, entrance_note}` |
| `reservation.changed` | hospital, emergency, ops | `{reservation_id, status}` |
| `room.changed` / `resource.changed` | hospital, ops | row + version |
| `reroute` | emergency, track, ambulance | `{from_hospital, to_hospital, reason}` |
| `alert` | hospital, ambulance, ops | `{kind: "offload_delay"\|"idle"\|"stale_data"\|…, message}` |
| `escalation.*` | ops | open/claimed/resolved/auto_defaulted |

Fan-out: core publishes to Redis channel `ws:{channel}`; every core worker subscribed pushes to its local sockets. Reconnect: exponential backoff (1 s → 15 s), re-subscribe, then REST resync.

---

## 9. ML service contract (`/ml/v1`) and models

Every endpoint returns `model_version` and `latency_ms`. Every endpoint has a **mock mode** (`ML_MODE=mock`) returning deterministic, schema-valid outputs derived from the input hash — so core and frontend develop independently. Core calls ML with timeouts; timeout/failure behaviour for each capability is listed (these are resilience fallbacks, **not** substitutes — the real model is always the primary path and must be built).

### 9.1 Speech-to-text — `POST /ml/v1/stt`

- **Input:** multipart `audio`, `lang_hint?`
- **Output:** `{transcript, language, confidence, segments:[{start,end,text}], model_version}`
- **Models:** AI4Bharat **IndicConformer** (Hindi, Marathi) and **Whisper large-v3 via faster-whisper** (English + code-mixed). Language ID first (Whisper's detector); route to the best model; if both run, pick the higher average log-prob.
- **Pre-processing:** resample 16 kHz mono, loudness normalise, VAD trim (Silero VAD).
- **Evaluation:** WER/CER on a team-recorded test set (≥ 60 clips across hi / mr / en / code-mixed, noisy + clean). Report per language.
- **Timeout:** 8 s. **On failure:** emergency is still created; dispatch proceeds as `app_button` (location + profile) with ALS; transcript retried in background.

### 9.2 Structured extraction — `POST /ml/v1/extract`

- **Input:** `{text, language}`
- **Output (`ExtractedFacts`):**

```json
{ "age": 60, "age_confidence": "stated|estimated|unknown", "sex": "M",
  "patient_count": 1, "conscious": true, "breathing": "difficult", "bleeding": "none",
  "symptoms": ["chest_pain","sweating","breathlessness"], "mechanism": "none|road_accident|fall|assault|burn|poisoning|drowning|other",
  "pregnant": false, "landmark": "near Ganesh temple, Akurdi", "for_whom": "father",
  "coherence": 0.92 }
```

- **Model:** Qwen2.5-7B-Instruct via Ollama, constrained decoding with the JSON schema (Ollama `format`), temperature 0, Pydantic validation, one repair retry.
- **Evaluation:** field-level accuracy on 200 hand-labelled transcripts.
- **Timeout:** 6 s. **On failure:** triage runs on raw text only.

### 9.3 Triage — `POST /ml/v1/triage`

- **Input:** `{text, extracted, profile_summary?, followup_answers?}`
- **Output:** `{acuity, acuity_probs, facility, facility_probs, confidence, needs_review, fragility, mlc_flag, model_version}`
- **Model:** **MuRIL** (`google/muril-base-cased`) fine-tuned, two heads (acuity: 3 classes; facility: 9 classes), input = transcript + serialized extracted facts + profile conditions. Train an **IndicBERT v2** variant too; ship the one with better macro-F1 on the human holdout.
- **Calibration:** temperature scaling on validation; `confidence = min(max acuity prob, max facility prob)`; `needs_review = confidence < 0.60`.
- **Rules layered on top (safety, auditable):** `fragility = pregnant ∨ age<14 ∨ mechanism∈{fall, road_accident} with spinal/fracture symptoms`; `mlc_flag = mechanism ∈ {road_accident, assault, burn, poisoning}`.
- **Data:**
  - Synthetic: ~8–10k utterances generated with an LLM from a scenario grid (facility × acuity × language × speaker × noise), in hi / mr / en / code-mixed, colloquial.
  - ASR-noise augmentation: sample text → TTS → STT round-trip to inject realistic transcription errors.
  - **Human holdout:** ≥ 300 utterances written and labelled by the team without LLM help — never used in training. All reported metrics are on this set.
- **Metrics (reported honestly):** macro-F1 per head, per-language F1, confusion matrix, ECE, and **critical-recall** (critical cases predicted non-critical is the worst error — tracked separately).
- **Timeout:** 3 s. **On failure:** acuity `critical`, facility `general`, `needs_review=true` → ALS dispatch (safe side).

### 9.4 Prank score — `POST /ml/v1/prank-score`

- **Input:** `{phone, channel, hour, calls_24h, calls_7d, prior_prank_flags, transcript_len, coherence, location_jump_km, text_repeat_ratio}`
- **Output:** `{score, suspicious, reasons[]}`
- **Model:** Isolation Forest on caller-behaviour features + rule-based reasons for explainability; trained on simulated legitimate + prank call logs.
- **Policy (in core):** suspicious ∧ acuity ≠ critical ⇒ SMS/app verification ("Reply YES"), dispatch waits ≤ 30 s, then proceeds anyway. Suspicious ∧ critical ⇒ dispatch immediately. **Never block.**

### 9.5 Duplicate check — `POST /ml/v1/duplicate-check`

- **Input:** `{emergency: {text, location, time, extracted}, candidates: [same, within 500 m & 15 min]}`
- **Output:** `{duplicate_of, similarity, same_incident, additional_patients}`
- **Model:** `intfloat/multilingual-e5-base` (or LaBSE) embeddings, cosine similarity ≥ 0.80 + spatial/temporal gate; DBSCAN over recent emergencies for incident clustering (feeds MCI trigger).
- **Policy:** duplicate with no additional patients ⇒ `merged_duplicate`, caller told "help is already on the way" and subscribed to the original. If more patients reported ⇒ same incident, extra ambulances dispatched.

### 9.6 Dispatch ranking — `POST /ml/v1/dispatch-rank`

- **Input:** `{emergency: {location, acuity, required_type}, candidates: [{ambulance_id, type, eta_sec, distance_m, hours_on_shift, mins_since_last_job, accept_rate_7d, avg_accept_latency_s, declines_today}]}`
- **Output:** `[{ambulance_id, accept_prob, expected_accept_latency_s, expected_arrival_sec, score}]` sorted.
- **Model:** LightGBM classifier (accept within 20 s) + LightGBM regressor (accept latency). `score = P(accept) / (eta_sec + E[latency])`, with an ALS-preservation penalty when sending ALS to stable cases while BLS is available.
- **Data:** simulated driver-behaviour logs (per-driver propensity, fatigue, distance aversion).
- **Metrics:** AUC, Brier, latency MAE; plus simulation A/B: mean time-to-accept vs nearest-first baseline.
- **Timeout:** 2 s. **On failure:** order by ETA.

### 9.7 Follow-up questions — `POST /ml/v1/followup/next`

- **Input:** `{facility, acuity, extracted, answers:[{question_id, answer}], language}`
- **Output:** `{question: {id, text, answer_type: "yes_no"|"number"|"choice"|"free", choices?, audio_url}}` or `{done: true}`
- **Design:** protocol trees in `services/ml/app/protocols/followup/*.json` (per facility), each question has fixed translations (hi/mr/en), the field it resolves, and a priority. The LLM **only selects** the next question ID (the one with most expected triage information given current uncertainty) and **parses** free answers into the field; it cannot author question text. Max 5 questions.
- **After each answer:** core re-runs triage; if acuity/facility changes before pickup, the change is propagated (dispatch type upgraded if needed).
- `POST /ml/v1/followup/parse` → `{question_id, raw_answer, language}` → `{parsed}`.

### 9.8 First aid — `POST /ml/v1/first-aid`

- **Input:** `{facility, acuity, extracted}` → **Output:** `{protocol_id, title, steps:[text], donts:[text], audio_urls:[]}`
- Fixed, versioned scripts in `protocols/first_aid/*.json`, written from established lay first-aid guidance (Indian Red Cross / standard BLS lay-rescuer guidance), in hi / mr / en, pre-rendered to audio with TTS. Selection is deterministic by rules on facility + extracted facts (e.g., not breathing ⇒ hands-only CPR script). **No generated medical text.**

### 9.9 Handover note — `POST /ml/v1/handover`

- **Input:** `{transcript, extracted, followup_answers, profile, triage}`
- **Output:** `{situation, background, assessment, recommendation, source_spans:[{field, quote}]}` in English (hospital language).
- **Model:** LLM with SBAR JSON schema; every clinical statement must cite a source span from transcript/answers/profile; a validator drops any statement without a source. Regenerated when follow-up answers arrive or triage is confirmed.

### 9.10 Resource prediction — `POST /ml/v1/resources`

- **Input:** `{acuity, facility, extracted, profile_summary}` → **Output:** `{resources:[{item, prob}]}` (specialists, equipment, blood types).
- **Model:** LightGBM one-vs-rest multi-label, trained on a clinician-style mapping table + noise; metrics: per-label AUC, micro-F1. Items with `prob ≥ 0.5` go to the prep checklist; the top required ones become the reservation bundle (§11.5).

### 9.11 Routing, ETA, uncertainty — `POST /ml/v1/eta`

- **Input:** `{origin, destination, depart_at, alternatives: true}`
- **Output:** `{routes:[{route_id, geometry (polyline6), distance_m, eta_sec, eta_low_sec, eta_high_sec, source: "mapbox_traffic"|"model", road_comfort}]}`
- **Pipeline:** OSRM route + alternatives (geometry, free-flow duration, edge list) → traffic ETA from **Mapbox Directions `driving-traffic`** for the same route → **LightGBM quantile/point model** (features: free-flow duration, distance, road-class mix, hour, weekday, turn count) → **conformal prediction (MAPIE)** for 90 % intervals.
- **ETA model data:** sampled route pairs across the Pune demo area queried against Mapbox traffic at different hours (collected during build), labelled with traffic durations; conformal calibration on a held-out split. Coverage of the 90 % interval is reported.
- **Batch:** `POST /ml/v1/eta/matrix` → `{origins[], destinations[]}` via OSRM table (used for dispatch candidate pre-filter and hospital candidates).
- **On Mapbox failure:** model ETA from OSRM free-flow + learned correction.

### 9.12 Road comfort — (inside `/eta`, also `POST /ml/v1/road-comfort {geometry}`)

- **Data:** OSM via **OSMnx + Overpass** for the demo area, pre-processed into an edge table: `surface`, `smoothness`, `highway`, `traffic_calming` nodes.
- **Score (0–100, higher = smoother):** length-weighted edge penalties (surface: paved 0 … unpaved 40; smoothness: excellent 0 … very_bad 50; road class: primary 0 … track 30) + speed-breaker penalty per count/km + **turn penalty** from geometry (Shapely: count of heading changes > 60° per km and total curvature).
- **Coverage:** `{score, components:{surface, smoothness, class, breakers, turns}, data_coverage: 0.0–1.0, estimated: bool}`. Where `smoothness` is missing, a road-class default is used and `estimated=true` is surfaced to UI.

### 9.13 Hospital ranking — `POST /ml/v1/hospital-rank`

- **Input:** `{emergency: {acuity, facility, fragility, required_resources[]}, candidates:[{hospital_id, features}]}`
- **Candidate features (computed by core + ML):** `facility_match` (0/1/partial), `required_resources_available_prob` (from nowcast), `p_bed_available_at_eta`, `eta_sec`, `eta_high_sec`, `road_comfort`, `specialist_on_duty_at_eta` (0/1), `staleness_min`, `occupancy_ratio`, `rejection_rate_24h`, `incoming_reserved_count`, `stabilization_capable`, acuity one-hot, fragility.
- **Output:** `[{hospital_id, score, rank, explanation:[{factor, value, contribution, text}], eligible: bool, ineligible_reason?}]`
- **Hard constraints (core, before ML):** active; has a capability matching facility (or `stabilization_capable` for fallback list); not already rejected for this emergency.
- **Model:** **LightGBM LambdaRank**. Acuity and fragility are features, so the model learns that critical cases weight time and fragile ones weight comfort.
- **Labels:** generated from simulated episodes scored by a documented clinical utility — expected *time to definitive care* = ETA + P(no bed) × expected reroute delay + P(no specialist) × delay, plus a comfort term scaled by fragility. The utility definition is in `training/hospital_rank/UTILITY.md` for judges to inspect.
- **Explanations:** SHAP TreeExplainer; top 3 contributions templated to text ("Cath lab available", "Data 3 min old", "11 min ETA").
- **Metrics:** NDCG@3 vs utility ground truth; simulation: mean time-to-definitive-care and reroute rate vs nearest-hospital baseline.
- **Timeout:** 2 s. **On failure:** core sorts eligible candidates by the utility function directly.

### 9.14 Bed nowcasting — `POST /ml/v1/bed-nowcast`

- **Input:** `{hospital_id, room_type, last_reported_free, minutes_since_report, eta_min, hour, weekday, arrival_rate_1h, discharge_rate_1h, incoming_reserved}`
- **Output:** `{p_available_at_eta, expected_free_at_eta, interval:[lo,hi]}`
- **Models:** LightGBM (calibrated with isotonic regression) **and** a **Temporal Fusion Transformer** (pytorch-forecasting) on occupancy series; both trained and evaluated; the better one on held-out Brier score is served (both kept, selectable by config).
- **Data:** simulated occupancy traces per hospital (non-homogeneous Poisson arrivals/discharges with hour-of-day profiles, surges), plus the live `hospital_occupancy_history` table.
- **Freshness tie-in:** `staleness` directly lowers certainty; UI shows both the reported number and the predicted probability.

### 9.15 Demand forecast — `GET /ml/v1/demand-forecast?horizon_min=60`

- **Output:** `[{h3_cell, predicted_calls, lo, hi}]` at H3 resolution 8.
- **Model:** LightGBM Poisson regression; features: lagged counts, neighbour-cell counts, hour, weekday, event calendar flag, POI density (from OSM: highways, markets). Data: synthetic historical calls with realistic spatio-temporal patterns. Metrics: MAE / Poisson deviance vs historical-average baseline.

### 9.16 Pre-positioning — `POST /ml/v1/preposition`

- **Input:** `{idle_ambulances:[{id, location, type}], forecast:[…]}`
- **Output:** `[{ambulance_id, target:{lat,lng}, h3_cell, expected_coverage_gain}]`
- **Solver:** Google OR-Tools (MIP): maximise forecast demand covered within 8 min, penalise relocation distance, keep ≥ 1 ALS per high-demand zone. Runs every 15 min; suggestions pushed to ambulances (declinable).

### 9.17 Mass-casualty allocation — `POST /ml/v1/mci-allocate`

- **Input:** `{patients:[{id, acuity, facility}], hospitals:[{id, capacities_by_type, eta_sec}], ambulances:[{id, type, eta_to_scene}]}`
- **Output:** `{assignments:[{patient_id, ambulance_id, hospital_id}], unassigned:[…], objective}`
- **Solver:** OR-Tools CP-SAT: critical first, capacity limits per hospital, max share per hospital (avoid overload), minimise weighted time-to-definitive-care. Becomes the **default option** of the MCI escalation.

### 9.18 Translation and speech — `POST /ml/v1/translate`, `POST /ml/v1/tts`

- **IndicTrans2** (AI4Bharat) for family SMS / caller messages; **Indic Parler-TTS** (AI4Bharat) for spoken follow-up questions and first-aid. Fixed texts are pre-translated and pre-rendered at build time and cached by hash.

### 9.19 Learning loop — `POST /ml/v1/feedback/triage`, `POST /ml/v1/retrain/triage`

- Core forwards each `triage_confirmations` row. Retraining job (manual trigger or nightly): merges confirmed real cases (weighted ×3) with the synthetic set, fine-tunes, evaluates on the **fixed human holdout**, and **promotes only if** macro-F1 and critical-recall do not drop. Versions tracked in **MLflow**; `GET /ml/v1/models` lists active versions.

### 9.20 Health

`GET /ml/v1/health` → per-model loaded status, device (cpu/cuda), version.

**Hardware plan:** training on Kaggle/Colab GPUs; inference on the team's GPU laptop (STT, LLM) — the ML service loads models once at startup and keeps them warm.

---

## 10. Core processing pipelines

### 10.1 SOS intake (async job `process_emergency`)

1. `POST /emergencies` → insert `emergencies(status='received')`, patient row, audit, family track token → `202` immediately.
2. Job:
   1. `stt` (voice) → `transcript`.
   2. `extract` → `ExtractedFacts`.
   3. Location resolution: GPS if `accuracy_m ≤ 100`; else landmark → gazetteer match (pg_trgm similarity + proximity to coarse GPS or profile home) → `location_source`; still weak ⇒ first follow-up question asks for a landmark.
   4. In parallel: `triage`, `prank-score`, `duplicate-check`, `resources`.
   5. Duplicate ⇒ merge path (§9.5). Suspicious ⇒ policy (§9.4).
   6. Set `required_ambulance_type` = ALS if critical or `needs_review`; else BLS-preferred.
   7. Patient count ≥ `MCI_PATIENT_THRESHOLD` or cluster rule ⇒ MCI escalation (§13) **and** dispatch starts for the most critical immediately.
   8. `status → triaged` → `status → dispatching`, start dispatch (§11.1).
   9. Start follow-up loop and first aid; generate initial handover note.
3. `app_button` with no text: skip 1–2; triage from profile + default `critical/general needs_review` (ALS), follow-up questions start immediately to gather facts.

### 10.2 Timers

All time-based behaviour is implemented as **arq deferred jobs** keyed by entity, and **every job re-checks state** before acting (idempotent). A **sweeper** runs every 5 s as a safety net for missed timers: expired offers, hospital request timeouts, hold expiries, signal-lost detection, escalation repeat/default, offload delay.

### 10.3 Leader election

Only one core worker runs the sweeper/forecast schedulers: Redis `SET leader:core <id> NX PX 10000`, renewed every 3 s.

### 10.4 Transactional outbox

State change + audit row + `outbox(event)` are written in one DB transaction. An outbox relay publishes to Redis pub/sub and marks rows sent. Guarantees no WS event for a rolled-back change and no lost event for a committed one.

---

## 11. Core domain logic

### 11.1 Dispatch (Uber-style)

```
round r ∈ {1,2,3}, radius = DISPATCH_RADII_KM[r-1]
candidates = ambulances WHERE status='available' AND kyc_verified
             AND ST_DWithin(current_location, emergency.location, radius)
             AND type satisfies required_ambulance_type          -- ALS required ⇒ ALS only
             AND last_heartbeat_at > now() - 30s
             AND id NOT IN (already offered for this emergency)
eta = /ml/v1/eta/matrix(candidates → pickup)
ranked = /ml/v1/dispatch-rank
create OFFERS_PER_ROUND offers (expires_at = now()+20s), push offer.new + FCM push
schedule next round at +30s  (cancelled if accepted)
after round 3 without acceptance → escalation(no_ambulance) while round 3 offers stay open
```

**Accept (single transaction):**

```sql
BEGIN;
SELECT * FROM dispatch_offers WHERE id=:offer FOR UPDATE;                -- must be pending, not expired
UPDATE emergencies SET status='ambulance_assigned', ambulance_id=:amb, assigned_at=now(), version=version+1
  WHERE id=:em AND status='dispatching' AND ambulance_id IS NULL;        -- 0 rows ⇒ ALREADY_TAKEN
UPDATE ambulances SET status='dispatched', active_emergency_id=:em, version=version+1
  WHERE id=:amb AND status='available';                                  -- 0 rows ⇒ ambulance busy ⇒ rollback
UPDATE dispatch_offers SET status='accepted', responded_at=now() WHERE id=:offer;
UPDATE dispatch_offers SET status='superseded' WHERE emergency_id=:em AND id<>:offer AND status='pending';
UPDATE dispatch_offers SET status='superseded' WHERE ambulance_id=:amb AND id<>:offer AND status='pending';
INSERT audit_log…, outbox…;
COMMIT;
```

### 11.2 Hospital selection

Triggered by `triage-confirm`, deterioration, family override, rejection/timeout/override of the current request, or divert.

1. Candidate hospitals within 25 km (PostGIS), hard constraints (§9.13).
2. For each: `eta` (with alternatives; best route chosen by `eta` for critical, by `eta − λ·comfort` for fragile), `road_comfort`, nowcast per required room/resource type, specialist-on-duty-at-ETA from `staff_shifts`, staleness, occupancy, rejection rate.
3. `/ml/v1/hospital-rank` → ranked list stored in `emergency_rank_snapshot` (jsonb on the emergency) for audit.
4. Send request to rank 1 (§11.3). On reject/timeout → next rank. List exhausted → `escalation(no_hospital)` with options: *stabilise at nearest stabilisation-capable* (default), *best partial match*, *force-assign to X (ops)*, *widen radius to 40 km*.

### 11.3 Hospital request + soft hold (double-booking prevention)

**Create (single transaction):**

```sql
BEGIN;
-- 1. choose a room for the soft hold
SELECT id FROM rooms
 WHERE hospital_id=:h AND type = ANY(:acceptable_types) AND status='free'
 ORDER BY priority_order
 FOR UPDATE SKIP LOCKED LIMIT 1;                      -- none ⇒ skip this hospital, next rank
UPDATE rooms SET status='reserved', reservation_id=:res, version=version+1 WHERE id=:room AND status='free';
-- 2. countable resources in the bundle (all-or-nothing)
UPDATE hospital_resources SET available=available-:q, reserved=reserved+:q, version=version+1
 WHERE hospital_id=:h AND type=:t AND available >= :q;  -- any 0-row ⇒ ROLLBACK ⇒ next hospital
-- 3.
INSERT reservations(status='held', hold_expires_at=now()+HOLD_PENDING_TTL) …;
INSERT reservation_items …;
INSERT hospital_requests(status='pending', expires_at=now()+HOSPITAL_TIMEOUT) …;
UPDATE emergencies SET status='hospital_selecting', version=version+1 …;
COMMIT;
```

`SKIP LOCKED` means two concurrent requests for the last room: one gets it, the other sees no free room and moves to its next hospital **immediately** — that is the double-booking guarantee.

**Accept:** CAS `hospital_requests.status pending→accepted`; reservation `held→confirmed`, `hold_expires_at = now() + max(600, 1.5·ETA)`; allocate staff (§11.6); emergency → `hospital_confirmed`; `handoff.ready` to paramedic + family. If the hold already expired (race with sweeper) ⇒ re-attempt reservation in same hospital; if impossible ⇒ `409 RESOURCE_UNAVAILABLE` to staff and move on.

**Reject/timeout:** release all items (room → `free`, resources `available += q, reserved -= q`), reservation `released`, request `rejected|timeout`, SMS duty manager on timeout, next rank.

### 11.4 Hold extension

Each heartbeat from an ambulance with a `confirmed` reservation: `hold_expires_at = GREATEST(hold_expires_at, now() + remaining_eta*1.5 + 120s)`. If heartbeats stop: hold is kept until `last_seen + remaining_eta_estimate + 900s`; then `expired` + `escalation(system_anomaly)` with option to re-reserve.

### 11.5 Reservation bundle

`acceptable_room_types` by facility (e.g., cardiac → `resus_bay, er_bed`; trauma → `trauma_bay, resus_bay`; obstetric → `labour_room`; pediatric → `pediatric_er, er_bed`; burns → `burns_unit`). Countable resources = predicted resources with `prob ≥ 0.7` that are `ResourceType` (e.g., cath_lab, ventilator, matching blood units). Staff = on-duty specialist for the facility at ETA (reserved as a soft assignment, not exclusive, but shown as "assigned").

### 11.6 Room and doctor allocation on accept

Room = the held room unless staff pick another free room (swap in one transaction). Staff = on-duty specialists matching facility at ETA + one emergency physician + one ER nurse, least-loaded first (count of active assignments). Staff can edit; changes versioned.

### 11.7 Walk-in override

`PATCH /hospital/rooms/{id}` on a `reserved` room with `override_reason`:
1. Room → `occupied`, reservation item removed, reservation → `overridden` (audit with reason).
2. Same transaction: try another free acceptable room in the same hospital (`SKIP LOCKED`) → if found, reservation re-created as `confirmed`, `reservation.changed` to ambulance ("room changed to ER-5").
3. Else: new selection with `is_priority=true` (hospital requests created with shortened timeout 30 s), `reroute` event to ambulance and family.

### 11.8 Deterioration, wrong triage, family override

- **Critical tap / triage change:** re-run selection with new acuity/facility including the current hospital; divert only if new best improves expected time-to-definitive-care by ≥ `DETERIORATION_DIVERT_GAIN_SEC` or current hospital no longer matches facility. Divert = release old reservation, new request, `reroute` event.
- **Family override:** `/family-override/options` returns all eligible hospitals with deltas vs current (`+14 min`, `no cath lab`, `data stale`). Confirm (consent=true) ⇒ request with `is_family_choice=true`; if that hospital rejects, fall back to AI ranking and notify family.

### 11.9 Geofencing and lifecycle automation

On each heartbeat: distance to pickup ≤ 75 m ⇒ `at_scene`; distance to confirmed hospital ≤ 150 m ⇒ `arrived_hospital` + handoff row `arrived_at`. `received` tap by hospital ⇒ `handed_off`, reservation `consumed`, room `occupied`, ambulance → `cleaning`. Paramedic taps *Ready* ⇒ `available`.

### 11.10 Driver idle / wrong way

While `dispatched`: if remaining route distance has not decreased for 90 s (and speed < 5 km/h or heading away) ⇒ `alert` to paramedic; at 150 s ⇒ start a new dispatch round in parallel; first new acceptance ⇒ original ambulance released (`superseded`), audit.

### 11.11 Vehicle breakdown

`/ambulance/vehicle-issue` ⇒ ambulance `out_of_service`. If patient not on board ⇒ emergency back to `dispatching` (priority). If on board ⇒ new dispatch to the ambulance's current location, hospital reservation kept and extended; hospital sees delay.

### 11.12 Connectivity

Paramedic web app keeps an **IndexedDB offline queue** of mutations (each with its Idempotency-Key) and replays on reconnect; heartbeats buffered and sent as a batch (latest one updates location). Hospital sees `signal: weak/lost`. One-tap SMS fallback: `sms:` link pre-filled `GH <emergency_short_id> ARRIVED|CRITICAL|ONBOARD` to the gateway number; the SMS webhook parses and applies the same transition (idempotent).

### 11.13 Rejection patterns

`rejection_rate_24h` per hospital feeds ranking. Analytics flags hospitals whose rejections with `NO_BED` contradict their own reported free beds at that time, and hospitals with rejection rate > 40 % in 24 h.

### 11.14 Unknown patient

No caller profile + extraction indicates unconscious/unknown ⇒ `temp_id = UNK-YYYYMMDD-####`, display "Unknown male, ~50". Hospital can merge later by phone (audit).

### 11.15 Pre-positioning job

Every 15 min (leader): demand forecast → preposition → suggestions to idle ambulances as declinable `alert{kind:"reposition"}`; acceptance tracked.

### 11.16 Analytics (computed by SQL views + materialised views refreshed each minute)

- Response times: call→accept, call→scene, scene→hospital, call→handoff (p50/p90).
- Offload delay distribution per hospital.
- Hospital acceptance/rejection by reason; timeouts.
- Triage accuracy: AI vs paramedic-confirmed confusion matrix, critical-recall.
- Stale-data frequency per hospital.
- Escalations: count by type, time to claim, auto-default rate.
- Demand heatmap (actual vs forecast), MCI events, prank/duplicate counts.

Hospital portal shows its own; ops page shows system-wide.

---

## 12. Integrations

### 12.1 SMS (feature phones) — textbee or httpSMS on an Android phone

- **Inbound:** gateway app → `POST /webhooks/sms {from, body, received_at, message_id}` (auth by shared secret). Dedupe by `message_id`.
- **Parsing:** any inbound from an unknown context = new emergency (`channel='sms'`); keyword `GH <id> …` = paramedic fallback command; `YES` = prank verification; replies to a follow-up question are matched to the open emergency for that phone (latest, < 60 min).
- **Location:** landmark from extraction → gazetteer; if the phone has a registered profile, `home_location` is a prior; no location ⇒ SMS asks "Reply with nearest landmark / area".
- **Outbound:** core → gateway API: confirmation, ambulance reg + ETA, hospital name/address, family tracking link, up to 2 follow-up questions, OTPs, duty-manager alerts, escalation SMS. Messages translated to caller language, ≤ 160 chars per part where possible.
- **Rate limits:** 5 inbound emergencies / phone / hour; outbound throttle to respect carrier limits (e.g., ≤ 1 SMS / 2 s); queue with retries.
- **Health:** gateway heartbeat (app's ping feature) → missing for 2 min ⇒ `escalation(system_anomaly)`.

### 12.2 Telegram escalation

- Bot created via BotFather; webhook set with secret token; allow-listed `telegram_user_id`s (team) in `users(role='developer')`; alerts posted to the team group.
- **Alert message:** summary (patient, triage, what was tried, why escalated) + inline keyboard: one button per option (`callback_data = esc:{id}:opt:{option_id}`), plus `I'm handling this` (`esc:{id}:claim`) and `Open live map` (URL button with a fresh one-time ops link).
- **Claim:** `UPDATE escalations SET status='claimed', claimed_by=:u, version=version+1 WHERE id=:e AND status='open'` → edit the group message to "Claimed by Rahul"; others' option presses are rejected with an alert popup unless they are the claimer.
- **Option press without claim:** implicitly claims (same CAS) then resolves.
- **Timers:** repeat at 60 s (new message + SMS to developers), default at 120 s (execute default option as `actor_type='system'`, message edited to "Auto-executed default: …").
- **Command** `/ops` (allow-listed users only) ⇒ reply with a fresh one-time ops link.

### 12.3 Push notifications

Firebase Cloud Messaging web push (service worker) for: new offers (ambulance), new hospital requests (hospital), status updates (patient/family who have the page open). WS is primary; push wakes a backgrounded tab.

### 12.4 Maps

Frontend: MapLibre GL with OSM tiles (or Leaflet), route polylines from `/eta`, live markers from WS, H3 hexagons (h3-js) for the demand heatmap.

---

## 13. Escalation engine (crises only)

| Type | Trigger | Options (default marked ★) |
|---|---|---|
| `mass_casualty` | patient_count ≥ 5 or cluster rule | ★ OR-Tools allocation plan · widen ambulance radius to 40 km · manual plan on ops page |
| `no_ambulance` | 3 rounds without accept | ★ widen to 40 km + include BLS for critical with ALS follow-up · force-assign nearest available (paramedic notified as mandatory) · notify 108 (caller shown 108 prompt) |
| `no_hospital` | ranked list exhausted | ★ stabilise at nearest stabilisation-capable hospital (priority request, transfer planned) · best partial match · force-assign hospital X · widen to 40 km |
| `system_anomaly` | call surge (> 3× forecast in 10 min), SMS gateway down, hospital dashboard offline > 5 min, silent ambulance beyond grace | context-specific; ★ always the conservative action (re-reserve / notify / fall back to 108 prompt) |

Every option is pre-computed and validated before the alert is sent; executing an option calls the same domain functions as the automated path. Everything is audited.

---

## 14. Tough scenarios — technical handling and required tests

Each row is a **mandatory automated test** (`services/core/tests/scenarios/`) and, where marked 🎬, a scripted demo scenario.

| # | Scenario | Mechanism | Test |
|---|---|---|---|
| T1 🎬 | Double booking last bed | `FOR UPDATE SKIP LOCKED` room hold + resource `available >= q` guard (§11.3) | 50 concurrent selections for 1 free room ⇒ exactly 1 hold, 49 move to next hospital, 0 invariant violations |
| T2 🎬 | Simultaneous accepts | Accept transaction CAS (§11.1) | 4 parallel accepts ⇒ 1 × 200, 3 × `409 ALREADY_TAKEN` |
| T3 | Ambulance accepts two calls | `ambulances.status='available'` guard + supersede other offers | Accept A and B concurrently ⇒ one succeeds |
| T4 🎬 | Walk-in takes reserved room | `409 ROOM_RESERVED` unless override reason; auto re-allocation (§11.7) | Override ⇒ same-hospital room if free, else priority reroute |
| T5 | Bundle partially available | All-or-nothing transaction | Room free, cath lab 0 ⇒ nothing held at that hospital |
| T6 | Hold expires in traffic | Heartbeat-driven extension (§11.4) | Slow ETA, heartbeats ⇒ hold never expires |
| T7 | Ghost reservation | Release on cancel/refused/died; sweeper expiry | Cancel ⇒ room free within 1 s; no heartbeat & no cancel ⇒ expired after grace |
| T8 | Duplicate request (retry) | Idempotency keys | Same key ×5 ⇒ one emergency |
| T9 | Out-of-order update | `version` CAS + WS `seq` | Stale version PATCH ⇒ 409 with current |
| T10 🎬 | Ambulance offline mid-route | Signal states, dead-reckoned ETA, hold kept, offline queue replay, SMS fallback | Drop heartbeats 3 min ⇒ hospital shows `lost`, reservation intact; replayed actions applied once |
| T11 🎬 | Hospital not responding | Timeout → next rank + duty-manager SMS | No response 45 s ⇒ next hospital requested |
| T12 | Server down | `/readyz` failure ⇒ *Call 108* UI; SMS gateway retries | Kill core ⇒ UI banner within 10 s |
| T13 🎬 | No ambulance accepts | Radius rounds → escalation | 3 rounds declined ⇒ Telegram alert |
| T14 🎬 | Driver idle / wrong way | §11.10 | Stationary 150 s ⇒ parallel re-dispatch, original superseded on new accept |
| T15 🎬 | Breakdown | §11.11 | Patient on board ⇒ new ambulance to breakdown point, reservation extended |
| T16 | Bad GPS | Landmark gazetteer + follow-up question | accuracy 800 m + landmark ⇒ location_source=`landmark_geocode` |
| T17 | Multiple patients one call | `patient_count` ⇒ multiple dispatch; ≥ 5 ⇒ MCI | "3 people hurt" ⇒ 3 dispatches |
| T18 🎬 | Mass casualty | MCI escalation + OR-Tools plan | 8 patients ⇒ plan respects capacities & per-hospital share |
| T19 🎬 | All hospitals full | `no_hospital` escalation + default | All reject ⇒ default executed at 120 s if unclaimed |
| T20 🎬 | Deterioration | §11.8 divert rule | Critical tap ⇒ divert only if ≥ 3 min gain |
| T21 🎬 | Wrong triage | Confirm with change ⇒ re-rank + learning loop row | Facility change ⇒ new hospital request, confirmation stored |
| T22 | Rejection patterns | Reason codes, ranking feature, analytics flags | Contradictory `NO_BED` flagged |
| T23 | Specialist shift ends | Shift check at ETA | Shift ends before ETA ⇒ `specialist_on_duty_at_eta=0` |
| T24 🎬 | Family override | Options with deltas + consent | Chosen hospital rejects ⇒ AI ranking resumes, family notified |
| T25 🎬 | Unknown patient | temp_id + merge | Merge links records, audited |
| T26 | Medico-legal | `mlc_flag` from mechanism | Road accident ⇒ flag on hospital card |
| T27 | Pregnant / child | Facility routing + fragility comfort weight | Pregnant ⇒ obstetric-capable only; smoother route preferred when ETA delta small |
| T28 🎬 | Prank caller | Score + verification, never blocked; critical bypass | Flagged number + critical text ⇒ immediate dispatch |
| T29 🎬 | Duplicate calls | Embedding + geo/time gate | 5 calls same crash ⇒ 1 incident, correct ambulance count |
| T30 | Fake driver | `kyc_verified` required to go online | Unverified ⇒ 403 |
| T31 | Privacy | Role projection on REST + WS | Family token never receives clinical fields (test on serializer output) |
| T32 🎬 | Stale data | Freshness buckets + nowcast in ranking | 45-min-old "2 ICU beds" ⇒ lower p_available, UI stale badge |
| T33 🎬 | SMS from basic phone | Full SMS flow | Inbound SMS ⇒ dispatch + confirmation SMS |
| T34 | Offload delay | Geofence arrival + received tap | 16 min wait ⇒ alert + analytics |

**Invariant checker:** a test utility (also runnable in the sim every 10 s) asserts: no room `reserved` without an active reservation; no ambulance with two active emergencies; no emergency with two active reservations; `available + reserved ≤ total`; no pending hospital request past expiry for > sweeper interval.

---

## 15. Simulator and scenario runner (`services/core/app/sim`)

- **World:** seeded Pune demo area; 8 hospitals (fictional names at plausible locations, labelled *Simulated*), rooms per type, resources, staff with shifts; 15 ambulances (6 ALS, 9 BLS) with simulated drivers (behaviour profiles matching the dispatch-model training generator); landmarks gazetteer.
- **Movement:** simulated ambulances follow OSRM geometry at speeds from the time-of-day traffic profile, sending **real heartbeats through the public API**.
- **Hospitals:** non-live hospitals are driven by bots (accept/reject with configurable probabilities, occupancy churn, confirmation pings or deliberate staleness). One hospital is operated live by a person in the demo.
- **Callers:** scripted SOS through the public API (text, pre-recorded voice files, SMS via the webhook).
- **Speed:** multiplier 1×–10× (timers scale).
- **Scenarios:** YAML files in `sim/scenarios/` (one per 🎬 row in §14 plus S1 happy path and S2 nearest-lacks-cath-lab), each: setup state → timed actions → assertions. Run from the ops page or CLI; results shown with pass/fail.
- **Labelling:** every simulated entity has `is_simulated=true` and the UI shows a *Simulated* badge.

---

## 16. Frontend specification (`apps/web`)

### 16.1 General

- Next.js App Router, TypeScript strict, Tailwind + shadcn/ui, TanStack Query for REST, a single WS client with channel subscriptions and resync, generated API types, i18n (en/hi/mr) with `next-intl`.
- Mobile-first layouts for patient and ambulance; desktop-first for hospital and ops.
- PWA: `manifest.webmanifest`, service worker (offline shell + FCM + IndexedDB queue for paramedic).
- Accessibility: large tap targets (≥ 48 px) for SOS/Accept/Confirm, high contrast, screen-reader labels.
- Every mutating call generates an Idempotency-Key; retries reuse it.
- Every data point from hospitals shows freshness; every AI output shows confidence; every ranking shows its explanation.

### 16.2 Patient (`/patient`)

- Login (phone OTP) · Health profile form · Emergency contacts.
- **SOS screen:** giant SOS button (press-and-hold 1 s to avoid accidental taps), *Record voice* (MediaRecorder, max 60 s, waveform), *Type* box, location permission + accuracy indicator, *Call 108* always visible.
- **Live emergency screen:** status stepper, map with ambulance + route + ETA range, triage label, follow-up question card (voice playback + answer buttons / mic), first-aid steps (with audio), hospital + room + receiving team + entrance when ready, reroute notices.

### 16.3 Ambulance (`/ambulance`)

- Login · Go online/offline · Status chip.
- **Offer card:** pickup, ETA, patient summary, countdown ring (20 s), Accept / Decline; sound + vibration.
- **Active job:** map + turn list, pickup details, caller call button, **Confirm triage** sheet (AI suggestion preselected, 9 facility buttons, 3 acuity buttons, patient count), **Critical** button, family-override sheet with deltas, vehicle issue, refused transport, destination card (hospital, room, entrance, team). Offline banner + queued actions count + SMS fallback button.
- After handoff: *Cleaning* → *Ready*. Reposition suggestion card (accept/decline).

### 16.4 Hospital (`/hospital`)

- **Incoming panel:** request cards (§7.5) with countdown, Accept (with room/staff pickers prefilled) / Reject (reason required); confirmed incoming list with live ambulance map and signal state.
- **Rooms board:** grid by type, status colours, `Reserved for MH12AB1234 (ETA 6 min)`, override flow with reason.
- **Resources:** editable counts with versions and freshness; big *Confirm availability* button with last-confirmed timer.
- **Staff & shifts** roster. **Handoffs:** *Patient received* button, offload timer. **Analytics** tab. **Unknown patients** merge.

### 16.5 Family (`/track/[token]`)

Read-only: status, map, ETA range, hospital, entrance, room location note, receiving team; language auto from contact language.

### 16.6 Ops (`/ops/[token]`)

One page, three tabs: **Incident** (escalation summary, map, options, claim/resolve, manual override with reason, audit trail), **Analytics** (system-wide §11.16), **Scenarios** (list, run, speed, reset, results).

---

## 17. Mocks and independent development

| Consumer | Mock | How |
|---|---|---|
| Frontend → core | **Prism** mock server from `openapi.core.yaml` + a small WS mock (`packages/contracts/ws-mock.ts`) replaying recorded event streams per scenario | `pnpm mock:core` |
| Core → ML | `ML_MODE=mock` in ML service (deterministic schema-valid outputs), or `ML_BASE_URL` pointed at ML's mock router | per-capability toggle `ML_MOCK_CAPABILITIES=stt,triage,…` |
| Core → SMS / Telegram | Fake gateway + fake Telegram adapters writing to `notifications` table and a local log UI | `SMS_MODE=fake`, `TELEGRAM_MODE=fake` |
| ML → OSRM/Mapbox | Recorded fixtures for demo-area routes | `GEO_MODE=fixtures` |

Contract tests (Schemathesis) run core and ML against their OpenAPI files; the frontend type-checks against generated types. A contract change breaks CI until all three sides update.

---

## 18. Security and privacy

- RBAC enforced in FastAPI dependencies on every route + object ownership checks (hospital_id / ambulance_id / caller) — never UI-only.
- Role-based response projection (patient/family/hospital/paramedic/ops serializers); WS uses the same projections.
- Passwords argon2id; JWT HS256 with rotation-ready key id; refresh tokens rotated and revocable.
- One-time tokens: 32 random bytes, stored SHA-256 hashed, single use, short TTL.
- Webhook secrets verified; Telegram allow-list.
- Rate limiting (Redis): OTP, SOS per phone, SMS inbound, login.
- Audio stored with object keys, served only to authorised roles, deleted 30 days after closure (configurable).
- Minimal data to family; ops access audited; designed in the spirit of India's DPDP Act (purpose limitation, minimisation, access logging).
- CORS locked to the web origin; HTTPS via tunnel.

---

## 19. Observability

- Structured JSON logs with `correlation_id`; request timing middleware.
- `ml_predictions` table logs inputs/outputs/latency for every model call affecting a decision.
- Metrics endpoint (Prometheus format) for request latency, job lag, WS connections, ML latency per capability.
- Audit trail viewable per emergency on the ops page.

---

## 20. Performance targets

| Path | Target |
|---|---|
| SOS (text) → first offers sent | ≤ 5 s p90 |
| SOS (voice, ≤ 20 s audio) → first offers sent | ≤ 10 s p90 (GPU STT) |
| Triage confirm → hospital request sent | ≤ 3 s p90 |
| Heartbeat → WS location on hospital screen | ≤ 1 s |
| Offer accept response | ≤ 300 ms |
| 50-way concurrent reservation test | correct, ≤ 2 s total |

Measured in CI/sim and reported in the demo.

---

## 21. Testing strategy

- **Unit:** FSMs (all allowed/forbidden transitions), scoring utilities, parsers.
- **Concurrency:** `pytest-asyncio` + real Postgres (testcontainers), parallel requests via `asyncio.gather` for T1–T3, T8, T9.
- **Scenario tests:** every row of §14 via the scenario runner in headless mode.
- **Contract tests:** Schemathesis for core + ML.
- **E2E:** Playwright — patient SOS → ambulance accept → confirm → hospital accept → handoff, across three browser contexts.
- **ML evaluation reports** (`services/ml/training/*/REPORT.md`): dataset description, splits, metrics on holdout, calibration, failure analysis. Generated by script, not hand-written.
- **Invariant checker** runs during all tests and sim.

---

## 22. Environment and running

`infra/env/.env.example`:

```
DATABASE_URL=postgresql+asyncpg://gh:gh@postgres:5432/goldenhour
REDIS_URL=redis://redis:6379/0
JWT_SECRET=… JWT_KID=k1
ML_BASE_URL=http://ml:8001   ML_MODE=real|mock   ML_MOCK_CAPABILITIES=
OSRM_URL=http://osrm:5000    MAPBOX_TOKEN=…      GEO_MODE=live|fixtures
OLLAMA_URL=http://ollama:11434  LLM_MODEL=qwen2.5:7b-instruct
SMS_MODE=real|fake  SMS_PROVIDER=textbee|httpsms  SMS_API_KEY=…  SMS_WEBHOOK_SECRET=…  SMS_GATEWAY_NUMBER=+91…
TELEGRAM_MODE=real|fake  TELEGRAM_BOT_TOKEN=…  TELEGRAM_WEBHOOK_SECRET=…  TELEGRAM_GROUP_CHAT_ID=…
FCM_PROJECT_ID=…  FCM_SERVICE_ACCOUNT_JSON=…
PUBLIC_BASE_URL=https://<tunnel-domain>
SIM_ENABLED=true  SIM_SPEED=1
```

Bring-up: `docker compose up` (postgres, redis, osrm, ollama, core, ml, worker) → `alembic upgrade head` → `python -m app.seed` → `pnpm dev` in `apps/web` → `cloudflared tunnel` → register SMS + Telegram webhooks (`python -m app.integrations.register_webhooks`).

OSRM prep: download Maharashtra/Western-India OSM extract → clip to Pune demo bbox → `osrm-extract/partition/customize` (MLD) → mount in container. OSM edge attributes for road comfort and the landmark gazetteer are pulled once via Overpass/OSMnx and committed as processed files.

---

## 23. Definition of Done (applies to every feature)

A feature is done only when:

1. It follows the contract in this document exactly (or a contract change was agreed and recorded).
2. Its happy path **and** every related tough scenario in §14 pass automated tests.
3. It is reachable in the UI with loading, empty, error, conflict (409) and offline states handled.
4. Its decisions are audited and its real-time events are emitted.
5. For ML: trained model served, holdout metrics reported in `REPORT.md`, confidence/uncertainty exposed, fallback verified.
6. It works inside the simulator through public APIs.
7. It has been demoed to one other teammate end to end.

**Reminder: this is the MVP. No feature in `project-description.md` may be removed, simplified, faked, or reduced in quality. If something is at risk, raise it to the team immediately — the answer is to reallocate effort, not to cut scope silently.**
