-- DRAFT migration, written by Person A to unblock intake-pipeline testing.
-- Owner per work-distribution.md §2.2 is Person B (app/db/models/**,
-- app/db/migrations/**) -- B should review/replace this, not silently keep it.
-- Transcribed verbatim from technical.md §5 (all tables, §5.1-5.6).

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS btree_gist; -- uuid equality operator class inside GiST exclusion constraints

-- ============================================================
-- 5.1 Identity
-- ============================================================

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz,
  role text NOT NULL CHECK (role IN ('patient','paramedic','hospital_staff','developer')),
  name text, phone text UNIQUE, language text DEFAULT 'en',
  password_hash text,
  hospital_id uuid NULL,
  ambulance_id uuid NULL,
  telegram_user_id bigint NULL,
  is_active bool DEFAULT true
);

CREATE TABLE health_profiles (
  user_id uuid PRIMARY KEY REFERENCES users(id),
  dob date, sex text, blood_group text,
  allergies text[], conditions text[], medications text[],
  insurance_provider text, insurance_policy_no text,
  home_address text, home_location geography(Point,4326),
  notes text, version int DEFAULT 1
);

CREATE TABLE emergency_contacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  user_id uuid REFERENCES users(id),
  name text, phone text, relation text, language text, priority int
);

CREATE TABLE otp_codes (
  phone text, code_hash text, expires_at timestamptz, attempts int DEFAULT 0
);

-- ============================================================
-- 5.2 Hospitals
-- ============================================================

CREATE TABLE hospitals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  name text, address text, location geography(Point,4326),
  er_entrance_note text,
  duty_manager_phone text,
  capabilities text[] NOT NULL,
  stabilization_capable bool DEFAULT true,
  is_active bool DEFAULT true,
  last_confirmed_at timestamptz,
  is_simulated bool DEFAULT true
);

ALTER TABLE users ADD CONSTRAINT fk_users_hospital FOREIGN KEY (hospital_id) REFERENCES hospitals(id);

CREATE TABLE rooms (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  hospital_id uuid REFERENCES hospitals(id),
  code text,
  type text CHECK (type IN ('er_bed','resus_bay','trauma_bay','icu_bed','labour_room','burns_unit','pediatric_er')),
  status text CHECK (status IN ('free','reserved','occupied','cleaning','out_of_service')) DEFAULT 'free',
  location_note text,
  priority_order int,
  reservation_id uuid NULL,
  version int NOT NULL DEFAULT 1,
  status_updated_at timestamptz DEFAULT now(),
  UNIQUE (hospital_id, code)
);
CREATE INDEX ON rooms (hospital_id, type, status);

CREATE TABLE hospital_resources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  hospital_id uuid REFERENCES hospitals(id),
  type text CHECK (type IN ('ventilator','cath_lab','ct_scanner','mri','defibrillator','blood_o_neg',
                            'blood_o_pos','blood_a_pos','blood_b_pos','blood_ab_pos','dialysis','operating_theatre')),
  total int, available int CHECK (available >= 0), reserved int DEFAULT 0 CHECK (reserved >= 0),
  CHECK (available + reserved <= total),
  version int NOT NULL DEFAULT 1,
  reported_at timestamptz NOT NULL,
  UNIQUE (hospital_id, type)
);

CREATE TABLE staff (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  hospital_id uuid REFERENCES hospitals(id),
  name text, specialty text, phone text, is_active bool DEFAULT true
);

CREATE TABLE staff_shifts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  staff_id uuid REFERENCES staff(id),
  start_at timestamptz, end_at timestamptz,
  EXCLUDE USING gist (staff_id WITH =, tstzrange(start_at,end_at) WITH &&)
);

CREATE TABLE hospital_occupancy_history (
  hospital_id uuid, room_type text, ts timestamptz,
  free int, occupied int, reserved int,
  PRIMARY KEY (hospital_id, room_type, ts)
);

-- ============================================================
-- 5.3 Ambulances
-- ============================================================

CREATE TABLE ambulances (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  registration_no text UNIQUE, type text CHECK (type IN ('BLS','ALS')),
  equipment text[],
  status text CHECK (status IN ('offline','available','dispatched','at_scene','transporting',
                                'at_hospital','cleaning','out_of_service')) DEFAULT 'offline',
  current_location geography(Point,4326), heading real, speed_kmh real,
  last_heartbeat_at timestamptz,
  active_emergency_id uuid NULL,
  kyc_verified bool DEFAULT false, driver_license_no text, kyc_verified_at timestamptz,
  version int NOT NULL DEFAULT 1,
  is_simulated bool DEFAULT true
);
CREATE INDEX ON ambulances USING gist (current_location);
CREATE INDEX ON ambulances (status, type);

ALTER TABLE users ADD CONSTRAINT fk_users_ambulance FOREIGN KEY (ambulance_id) REFERENCES ambulances(id);

CREATE TABLE ambulance_status_log (
  ambulance_id uuid, from_status text, to_status text, at timestamptz, emergency_id uuid
);

-- ============================================================
-- 5.4 Emergencies
-- ============================================================

CREATE TABLE incidents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  location geography(Point,4326),
  patient_count int DEFAULT 1, is_mass_casualty bool DEFAULT false,
  status text DEFAULT 'active'
);

CREATE TABLE emergencies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  incident_id uuid REFERENCES incidents(id),
  caller_user_id uuid NULL REFERENCES users(id), caller_phone text,
  channel text CHECK (channel IN ('app_button','app_voice','app_text','sms')),
  raw_text text, audio_object_key text, transcript text, language text,
  stt_confidence real,
  extracted jsonb,
  location geography(Point,4326), location_accuracy_m real, landmark_text text,
  location_source text,
  ai_acuity text, ai_facility text, ai_confidence real, ai_probs jsonb, needs_review bool,
  final_acuity text, final_facility text,
  required_ambulance_type text,
  fragility bool DEFAULT false,
  mlc_flag bool DEFAULT false,
  prank_score real, prank_verified bool NULL,
  duplicate_of uuid NULL,
  predicted_resources jsonb,
  handover_note jsonb,
  status text CHECK (status IN ('received','triaged','dispatching','ambulance_assigned','at_scene',
                                'patient_on_board','hospital_selecting','hospital_confirmed',
                                'arrived_hospital','handed_off','closed','cancelled',
                                'refused_transport','merged_duplicate')),
  ambulance_id uuid NULL REFERENCES ambulances(id),
  hospital_id uuid NULL REFERENCES hospitals(id),
  reservation_id uuid NULL,
  eta_to_patient_sec int, eta_to_hospital_sec int, eta_low_sec int, eta_high_sec int,
  family_track_token_hash text,
  escalated bool DEFAULT false,
  version int NOT NULL DEFAULT 1,
  received_at timestamptz, triaged_at timestamptz, assigned_at timestamptz, at_scene_at timestamptz,
  on_board_at timestamptz, hospital_confirmed_at timestamptz, arrived_hospital_at timestamptz,
  handed_off_at timestamptz, closed_at timestamptz
);
CREATE INDEX ON emergencies USING gist (location);
CREATE INDEX ON emergencies (status);
CREATE INDEX ON emergencies (received_at);

CREATE TABLE patients (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  emergency_id uuid REFERENCES emergencies(id),
  user_id uuid NULL REFERENCES users(id),
  temp_id text UNIQUE,
  is_unknown bool, est_age int, sex text,
  merged_into_user_id uuid NULL
);

CREATE TABLE followup_answers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  emergency_id uuid, question_id text, answer_raw text, answer_parsed jsonb, language text
);

CREATE TABLE triage_confirmations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  emergency_id uuid, paramedic_id uuid,
  ai_acuity text, ai_facility text, ai_confidence real,
  final_acuity text, final_facility text, changed bool,
  input_text text, model_version text, used_for_training bool DEFAULT false
);

-- ============================================================
-- 5.5 Dispatch, hospital requests, reservations
-- ============================================================

CREATE TABLE dispatch_offers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  emergency_id uuid, ambulance_id uuid, round int,
  status text CHECK (status IN ('pending','accepted','declined','expired','superseded')) DEFAULT 'pending',
  predicted_accept_prob real, predicted_eta_sec int, rank int,
  offered_at timestamptz, expires_at timestamptz, responded_at timestamptz,
  UNIQUE (emergency_id, ambulance_id)
);
CREATE INDEX ON dispatch_offers (ambulance_id, status);

CREATE TABLE hospital_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  emergency_id uuid, hospital_id uuid, rank int,
  score real, explanation jsonb,
  features jsonb,
  status text CHECK (status IN ('pending','accepted','rejected','timeout','cancelled','superseded')) DEFAULT 'pending',
  reason_code text NULL, reason_note text NULL,
  is_family_choice bool DEFAULT false, is_priority bool DEFAULT false,
  sent_at timestamptz, expires_at timestamptz, responded_at timestamptz, responded_by uuid
);
CREATE UNIQUE INDEX one_pending_request_per_emergency
  ON hospital_requests (emergency_id) WHERE status = 'pending';

CREATE TABLE reservations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  emergency_id uuid, hospital_id uuid, hospital_request_id uuid,
  status text CHECK (status IN ('held','confirmed','consumed','released','expired','overridden')),
  hold_expires_at timestamptz NOT NULL,
  version int NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX one_active_reservation_per_emergency
  ON reservations (emergency_id) WHERE status IN ('held','confirmed');

CREATE TABLE reservation_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  reservation_id uuid,
  kind text CHECK (kind IN ('room','resource','staff')),
  room_id uuid NULL, resource_type text NULL, quantity int DEFAULT 1, staff_id uuid NULL
);

CREATE TABLE handoffs (
  emergency_id uuid PRIMARY KEY, hospital_id uuid, room_id uuid,
  receiving_staff_ids uuid[],
  arrived_at timestamptz, offloaded_at timestamptz,
  offload_delay_sec int GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (offloaded_at - arrived_at))::int) STORED
);

-- ============================================================
-- 5.6 Escalation, notifications, security, audit
-- ============================================================

CREATE TABLE escalations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  type text, emergency_id uuid NULL, incident_id uuid NULL,
  status text CHECK (status IN ('open','claimed','resolved','auto_defaulted')) DEFAULT 'open',
  summary text, options jsonb,
  default_option_id text,
  chosen_option_id text NULL, claimed_by uuid NULL, claimed_at timestamptz,
  resolved_at timestamptz, telegram_message_ids jsonb,
  repeat_at timestamptz, default_at timestamptz,
  version int NOT NULL DEFAULT 1
);

CREATE TABLE one_time_tokens (
  token_hash text PRIMARY KEY, purpose text CHECK (purpose IN ('ops','family_track')),
  escalation_id uuid NULL, emergency_id uuid NULL, issued_to uuid NULL,
  expires_at timestamptz, used_at timestamptz NULL
);

CREATE TABLE notifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  recipient_kind text, recipient_ref text,
  channel text CHECK (channel IN ('ws','push','sms','telegram')),
  template text, payload jsonb, status text, error text, sent_at timestamptz
);

CREATE TABLE sms_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now(), updated_at timestamptz,
  direction text CHECK (direction IN ('in','out')), phone text, body text,
  emergency_id uuid NULL, gateway_message_id text, status text
);

CREATE TABLE caller_reputation (
  phone text PRIMARY KEY, total_calls int, prank_flags int, last_prank_at timestamptz,
  requires_verification bool DEFAULT false
);

CREATE TABLE idempotency_keys (
  key text, user_id uuid, endpoint text, request_hash text,
  status_code int, response jsonb, created_at timestamptz,
  PRIMARY KEY (key, user_id)
);

CREATE TABLE push_subscriptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid, fcm_token text, created_at timestamptz DEFAULT now()
);

CREATE TABLE audit_log (
  id bigserial PRIMARY KEY, at timestamptz DEFAULT now(),
  actor_type text CHECK (actor_type IN ('system','ai','user','developer','simulator')),
  actor_id text, entity text, entity_id uuid, action text,
  before jsonb, after jsonb, reason text, model_version text, correlation_id uuid
);
CREATE RULE audit_no_update AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
CREATE RULE audit_no_delete AS ON DELETE TO audit_log DO INSTEAD NOTHING;

CREATE TABLE landmarks (
  id bigserial PRIMARY KEY, name text, name_normalized text, alt_names text[],
  kind text, location geography(Point,4326)
);
CREATE INDEX ON landmarks USING gin (name_normalized gin_trgm_ops);

CREATE TABLE demand_forecasts (
  h3_cell text, window_start timestamptz, predicted_calls real, model_version text,
  PRIMARY KEY (h3_cell, window_start)
);

CREATE TABLE ml_predictions (
  id bigserial PRIMARY KEY, at timestamptz, capability text, emergency_id uuid, input jsonb,
  output jsonb, model_version text, latency_ms int
);
