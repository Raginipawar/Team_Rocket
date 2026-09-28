// Types for the core REST + WS contract (technical.md §7, §8 and
// packages/contracts/ws-events.schema.json). Hand-written because
// packages/contracts/openapi.core.yaml does not exist yet; once it lands,
// regenerate with `npx openapi-typescript ../../packages/contracts/openapi.core.yaml -o lib/api-types.gen.ts`
// and point these names at the generated ones.
//
// Fields marked "extra" are sent by the mock core and are optional here, so the
// UI keeps working against the real core, which may not send them yet.

import type {
  Acuity, AmbulanceStatus, AmbulanceType, Capability, Channel, EmergencyStatus, EscalationStatus,
  EscalationType, Facility, Freshness, HospitalRequestStatus, RejectReason, ReservationStatus,
  ResourceType, Role, RoomStatus, RoomType, StaffSpecialty,
} from "./enums";

export type LatLng = { lat: number; lng: number };
export type Signal = "ok" | "weak" | "lost";

/* ---------- 7.1 errors ---------- */
export type ApiErrorBody = { error: { code: string; message: string; details?: Record<string, unknown> } };

/* ---------- 7.2 auth ---------- */
export type User = {
  id: string;
  role: Role;
  name?: string | null;
  phone?: string | null;
  language?: string | null;
  hospital_id?: string | null;
  ambulance_id?: string | null;
};
export type LoginResponse = { access_token: string; user: User };

/* ---------- 7.3 patient ---------- */
export type HealthProfile = {
  name?: string | null; // extra: users.name, edited on the same screen
  dob?: string | null;
  sex?: string | null;
  blood_group?: string | null;
  allergies: string[];
  conditions: string[];
  medications: string[];
  insurance_provider?: string | null;
  insurance_policy_no?: string | null;
  home_address?: string | null;
  notes?: string | null;
  version: number;
};

export type EmergencyContact = {
  id: string;
  name: string;
  phone: string;
  relation?: string | null;
  language?: string | null;
  priority?: number | null;
};

export type CreateEmergencyResponse = {
  emergency_id: string;
  status: EmergencyStatus;
  family_track_url: string;
  call_108_fallback: boolean;
};

export type Triage = {
  acuity: Acuity;
  facility: Facility;
  confidence: number;
  confirmed: boolean;
  needs_review?: boolean;
};

export type AmbulanceView = {
  registration_no: string;
  type: AmbulanceType;
  location: LatLng | null;
  heading?: number | null;
  eta_sec: number | null;
  eta_low_sec: number | null;
  eta_high_sec: number | null;
  crew_phone?: string | null;
  signal?: Signal; // extra
  is_simulated?: boolean; // extra
};

export type HospitalView = {
  id?: string;
  name: string;
  address?: string | null;
  location?: LatLng | null;
  er_entrance_note?: string | null;
  phone?: string | null;
  eta_sec?: number | null;
  is_simulated?: boolean;
};

export type HandoffInfo = {
  room_location_note: string;
  receiving_team: string;
  entrance_note: string;
};

export type FirstAid = {
  protocol_id: string;
  title?: string;
  steps: string[];
  donts?: string[];
};

export type RerouteNotice = { from_hospital: string; to_hospital: string; reason: string; at?: string };

export type Timeline = Partial<Record<
  "received_at" | "triaged_at" | "assigned_at" | "at_scene_at" | "on_board_at" | "hospital_confirmed_at" |
  "arrived_hospital_at" | "handed_off_at" | "closed_at", string | null>>;

/** GET /emergencies/{id} (patient view, §7.3). */
export type EmergencyView = {
  id: string;
  status: EmergencyStatus;
  version: number;
  triage: Triage | null;
  ambulance: AmbulanceView | null;
  hospital: HospitalView | null;
  handoff: HandoffInfo | null;
  first_aid: FirstAid | null;
  // extra
  channel?: Channel;
  for_self?: boolean;
  pickup?: (LatLng & { accuracy_m?: number | null; landmark?: string | null }) | null;
  family_track_url?: string | null;
  timeline?: Timeline;
  reroute?: RerouteNotice | null;
  route?: string | null; // polyline6 of the current leg
  leg?: "to_patient" | "to_hospital" | null;
  call_108_prompt?: boolean;
};

export type FollowupQuestion = {
  id: string;
  text: string;
  answer_type: "yes_no" | "number" | "choice" | "free";
  choices?: string[] | null;
  audio_url?: string | null;
};
export type FollowupState = { question: FollowupQuestion | null; done: boolean; first_aid?: FirstAid | null };

/* ---------- 7.4 ambulance ---------- */
export type OfferSummary = { acuity: Acuity; facility: Facility; age?: number | null; sex?: string | null; patient_count: number };
export type Offer = {
  offer_id: string;
  emergency_id: string;
  expires_at: string;
  pickup: LatLng & { landmark?: string | null; accuracy_m?: number | null };
  eta_to_pickup_sec: number;
  distance_m: number;
  summary: OfferSummary;
};

export type AmbulanceSelf = {
  id: string;
  registration_no: string;
  type: AmbulanceType;
  status: AmbulanceStatus;
  version: number;
  location?: LatLng | null;
  kyc_verified?: boolean;
  is_simulated?: boolean;
};

export type PatientBrief = {
  display: string; // "Male, ~60" or "Unknown male, ~50"
  temp_id?: string | null;
  age?: number | null;
  sex?: string | null;
  patient_count: number;
  profile?: { blood_group?: string | null; allergies: string[]; conditions: string[]; medications: string[] } | null;
};

/** GET /ambulance/active. */
export type ActiveJob = {
  emergency_id: string;
  short_id: string; // for the SMS fallback: GH <short_id> ARRIVED
  status: EmergencyStatus;
  version: number;
  leg: "to_patient" | "to_hospital" | null;
  pickup: LatLng & { landmark?: string | null; accuracy_m?: number | null };
  caller_phone?: string | null;
  patient: PatientBrief;
  triage: Triage & { ai_acuity?: Acuity; ai_facility?: Facility; mlc_flag?: boolean; fragility?: boolean };
  transcript?: string | null;
  route?: string | null; // polyline6
  eta_sec?: number | null;
  distance_m?: number | null;
  turns?: string[];
  destination?: {
    hospital: HospitalView;
    room_code?: string | null;
    room_location_note?: string | null;
    receiving_team?: string | null;
    entrance_note?: string | null;
    reservation_status?: ReservationStatus | null;
    is_family_choice?: boolean;
  } | null;
  hospital_selecting?: { hospital_name: string; expires_at: string } | null;
  arrived_at?: string | null; // at hospital, for the door timer
};

export type FamilyOverrideOption = {
  hospital_id: string;
  name: string;
  eta_sec: number;
  delta_sec: number; // vs current
  notes: string[]; // "no cath lab", "data stale"
  is_current?: boolean;
  capable: boolean;
};

export type AmbulanceHistoryItem = {
  emergency_id: string;
  at: string;
  acuity: Acuity | null;
  facility: Facility | null;
  hospital_name: string | null;
  status: EmergencyStatus;
  duration_sec: number | null;
};

/* ---------- 7.5 hospital ---------- */
export type Room = {
  id: string;
  code: string;
  type: RoomType;
  status: RoomStatus;
  location_note?: string | null;
  version: number;
  status_updated_at?: string | null;
  reservation?: { registration_no: string; eta_sec: number | null; acuity?: Acuity | null; facility?: Facility | null } | null; // extra
  occupant?: string | null; // extra
};

export type Resource = {
  id: string;
  type: ResourceType;
  total: number;
  available: number;
  reserved: number;
  version: number;
  reported_at: string;
  freshness?: Freshness;
};

export type Staff = {
  id: string;
  name: string;
  specialty?: StaffSpecialty | string | null;
  role?: string | null; // B's column name
  phone?: string | null;
  is_active?: boolean;
  on_duty?: boolean; // extra
  shift?: { start_at: string; end_at: string } | null; // extra
};

export type Shift = { id: string; staff_id: string; start_at: string; end_at: string };

export type PrepItem = { item: string; prob: number };
export type Sbar = { situation: string; background: string; assessment: string; recommendation: string };

/** Incoming patient card (§7.5, WS hospital.request.new). */
export type HospitalRequestCard = {
  request_id: string;
  emergency_id: string;
  expires_at: string;
  status?: HospitalRequestStatus;
  patient: {
    display: string;
    temp_id: string | null;
    acuity: Acuity;
    facility: Facility;
    confirmed_by_paramedic: boolean;
    mlc_flag: boolean;
  };
  profile: { blood_group?: string | null; allergies: string[]; conditions: string[]; medications: string[] } | null;
  handover_note: Sbar | null;
  prep_checklist: PrepItem[];
  ambulance: {
    registration_no: string;
    type: AmbulanceType;
    location: LatLng | null;
    eta_sec: number | null;
    eta_low_sec: number | null;
    eta_high_sec: number | null;
    signal: Signal;
  };
  why_you: string[];
  is_family_choice?: boolean;
  is_priority?: boolean;
  suggested_room_id?: string | null; // extra: the held room
  suggested_staff_ids?: string[]; // extra
};

export type IncomingAmbulance = {
  emergency_id: string;
  registration_no: string;
  type: AmbulanceType;
  acuity: Acuity;
  facility: Facility;
  location: LatLng | null;
  eta_sec: number | null;
  eta_low_sec: number | null;
  eta_high_sec: number | null;
  signal: Signal;
  last_seen_at?: string | null;
  room_code?: string | null;
  patient_display: string;
  arrived_at?: string | null; // set once at the door
  temp_id?: string | null;
};

export type HospitalInfo = {
  id: string;
  name: string;
  address?: string | null;
  location?: LatLng | null;
  er_entrance_note?: string | null;
  capabilities?: Capability[];
  last_confirmed_at?: string | null;
  is_simulated?: boolean;
};

/** GET /hospital/dashboard (shape implemented in B's hospital.py, plus extras). */
export type HospitalDashboard = {
  hospital: HospitalInfo;
  pending_requests: HospitalRequestCard[];
  rooms: Record<string, Room[]>; // grouped by room type
  resources: Resource[];
  staff_on_duty: Staff[];
  freshness: Freshness;
  incoming?: IncomingAmbulance[]; // extra: confirmed, on the way
  at_door?: IncomingAmbulance[]; // extra: arrived, not yet received
};

/* ---------- 7.6 family ---------- */
export type TrackView = {
  status: EmergencyStatus;
  patient_first_name?: string | null;
  language?: string | null;
  ambulance: { registration_no: string; location: LatLng | null; eta_sec: number | null; eta_low_sec: number | null; eta_high_sec: number | null; signal?: Signal } | null;
  hospital: { name: string; address?: string | null; location?: LatLng | null; entrance_note?: string | null } | null;
  handoff: { room_location_note?: string | null; receiving_team?: string | null; entrance_note?: string | null } | null;
  pickup?: LatLng | null;
  timeline?: Timeline;
  reroute?: RerouteNotice | null;
  updated_at?: string;
};

/* ---------- 7.7 ops ---------- */
export type EscalationOption = { id: string; label: string; action?: string; is_default: boolean };
export type Escalation = {
  id: string;
  type: EscalationType;
  status: EscalationStatus;
  emergency_id?: string | null;
  summary: string;
  options: EscalationOption[];
  default_option_id: string;
  chosen_option_id?: string | null;
  claimed_by?: string | null;
  claimed_by_name?: string | null;
  created_at: string;
  repeat_at?: string | null;
  default_at?: string | null;
  resolved_at?: string | null;
  map?: { pickup?: LatLng | null; ambulance?: LatLng | null; hospitals?: (LatLng & { id?: string; name: string; status?: string })[] };
  tried?: { hospital: string; outcome: string }[];
};

export type OpsOverview = {
  emergencies: { id: string; status: EmergencyStatus; acuity: Acuity | null; facility: Facility | null; location: LatLng | null; received_at: string; ambulance?: string | null; hospital?: string | null }[];
  ambulances: { id: string; registration_no: string; type: AmbulanceType; status: AmbulanceStatus; location: LatLng | null; signal: Signal }[];
  hospitals: { id: string; name: string; location: LatLng | null; free_rooms: number; freshness: Freshness }[];
  escalations: Escalation[];
};

export type AuditEntry = { id: number | string; at: string; actor_type: string; actor_id: string; entity: string; action: string; reason?: string | null; after?: unknown };

export type Scenario = { name: string; title: string; description?: string; available: boolean };
export type ScenarioRun = {
  name: string;
  status: "running" | "passed" | "failed" | "not_available";
  started_at: string;
  finished_at?: string | null;
  steps: { at: string; text: string; ok?: boolean }[];
  assertions: { text: string; ok: boolean }[];
};

/* ---------- analytics (§11.16) ---------- */
export type Percentiles = { p50: number | null; p90: number | null; n: number };
export type Analytics = {
  synthetic?: boolean; // true when numbers include generated history (labelled in the UI)
  response_times: { call_to_accept: Percentiles; call_to_scene: Percentiles; scene_to_hospital: Percentiles; call_to_handoff: Percentiles };
  offload_delay: { buckets: { label: string; count: number }[]; p50: number | null; p90: number | null };
  request_outcomes: { outcome: string; count: number }[];
  rejections_by_reason: { reason: RejectReason | string; count: number }[];
  triage_confusion?: { ai: Acuity; final: Acuity; count: number }[];
  critical_recall?: number | null;
  stale_data?: { hospital: string; stale_share: number }[];
  escalations?: { type: EscalationType; count: number; auto_default_rate: number; median_claim_sec: number | null }[];
  demand?: { hour: string; actual: number; forecast: number }[];
  hourly_calls?: { hour: number; count: number }[];
  flags?: string[];
};

/* ---------- 8 WebSocket ---------- */
export type WsEnvelope<T = unknown> = { event: string; channel: string; seq: number; ts: string; data: T };

export type WsLocation = {
  lat: number;
  lng: number;
  heading: number;
  speed_kmh: number;
  eta_sec?: number;
  eta_low_sec?: number;
  eta_high_sec?: number;
  signal: Signal;
  emergency_id?: string; // extra, on hospital/ops channels
  ambulance_id?: string; // extra
};
