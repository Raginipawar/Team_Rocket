// In-memory "database" of the mock core: the same entities as technical.md §5,
// seeded with a Pune + Pimpri Chinchwad world (§15: fictional hospital names at
// plausible locations, 15 ambulances, staff with shifts). Logins match
// data/seed/CREDENTIALS.md so the same phone + password work on the real core.

import { randomUUID } from "node:crypto";
import type {
  Acuity, AmbulanceStatus, AmbulanceType, Capability, Channel, EmergencyStatus, EscalationStatus, EscalationType,
  Facility, HospitalRequestStatus, RejectReason, ReservationStatus, ResourceType, Role, RoomStatus, RoomType, StaffSpecialty,
} from "../../lib/enums";
import type { FirstAid, LatLng, PrepItem, RerouteNotice, Sbar, Signal } from "../../lib/api-types";
import type { Route } from "./geo";

export const uid = () => randomUUID();
export const now = () => Date.now();
export const iso = (ms: number | null | undefined) => (ms ? new Date(ms).toISOString() : null);

/* ---------- records (mirror §5 tables) ---------- */
export type UserRec = {
  id: string; role: Role; name: string | null; phone: string; language: string;
  password: string | null; hospital_id: string | null; ambulance_id: string | null;
};
export type ProfileRec = {
  user_id: string; dob: string | null; sex: string | null; blood_group: string | null;
  allergies: string[]; conditions: string[]; medications: string[];
  insurance_provider: string | null; insurance_policy_no: string | null;
  home_address: string | null; home_location: LatLng | null; notes: string | null; version: number;
};
export type ContactRec = { id: string; user_id: string; name: string; phone: string; relation: string | null; language: string | null; priority: number };

export type HospitalRec = {
  id: string; name: string; address: string; location: LatLng; er_entrance_note: string; duty_manager_phone: string;
  capabilities: Capability[]; stabilization_capable: boolean; last_confirmed_at: number; is_simulated: boolean; phone: string;
};
export type RoomRec = {
  id: string; hospital_id: string; code: string; type: RoomType; status: RoomStatus; location_note: string;
  priority_order: number; reservation_id: string | null; version: number; status_updated_at: number; occupant: string | null;
};
export type ResourceRec = {
  id: string; hospital_id: string; type: ResourceType; total: number; available: number; reserved: number; version: number; reported_at: number;
};
export type StaffRec = { id: string; hospital_id: string; name: string; specialty: StaffSpecialty; phone: string; is_active: boolean };
export type ShiftRec = { id: string; staff_id: string; start_at: number; end_at: number };

export type AmbulanceRec = {
  id: string; registration_no: string; type: AmbulanceType; equipment: string[]; status: AmbulanceStatus;
  location: LatLng; heading: number; speed_kmh: number; last_heartbeat_at: number; active_emergency_id: string | null;
  kyc_verified: boolean; version: number; is_simulated: boolean; crew_phone: string; base_name: string;
  // movement (mock simulator)
  route: Route | null; route_m: number; leg: "to_patient" | "to_hospital" | "to_base" | null;
  silent_until: number; // heartbeats suppressed until (T10 scenario)
  idle_since: number | null;
};

export type ExtractedFacts = {
  age?: number | null; sex?: string | null; patient_count?: number; conscious?: boolean | null; breathing?: string | null;
  bleeding?: string | null; symptoms?: string[]; mechanism?: string; pregnant?: boolean; landmark?: string | null;
  for_whom?: string | null; coherence?: number;
};

export type EmergencyRec = {
  id: string; incident_id: string; caller_user_id: string | null; caller_phone: string | null; channel: Channel;
  raw_text: string | null; transcript: string | null; language: string; extracted: ExtractedFacts;
  location: LatLng | null; accuracy_m: number | null; landmark_text: string | null; location_source: string;
  ai_acuity: Acuity | null; ai_facility: Facility | null; ai_confidence: number | null; needs_review: boolean;
  final_acuity: Acuity | null; final_facility: Facility | null; required_ambulance_type: AmbulanceType;
  fragility: boolean; mlc_flag: boolean; prank_score: number | null; duplicate_of: string | null;
  predicted_resources: PrepItem[]; handover_note: Sbar | null; status: EmergencyStatus;
  ambulance_id: string | null; hospital_id: string | null; reservation_id: string | null;
  track_token: string; version: number; for_self: boolean; patient_count: number;
  patient: { user_id: string | null; temp_id: string | null; is_unknown: boolean; est_age: number | null; sex: string | null; name: string | null };
  followup_answers: { question_id: string; answer: string; at: number }[];
  followup_current: { id: string; text: string; answer_type: string; choices?: string[] | null; audio_url?: string | null } | null;
  followup_done: boolean;
  first_aid: FirstAid | null;
  model_versions: Record<string, string>;
  dispatch_round: number; next_round_at: number | null; escalated_no_ambulance: boolean;
  rank_list: { hospital_id: string; score: number; eta_sec: number; why: string[] }[];
  tried_hospitals: { hospital_id: string; outcome: string }[];
  reroute: RerouteNotice | null; handoff_info: { room_location_note: string; receiving_team: string; entrance_note: string } | null;
  family_choice_hospital_id: string | null;
  timestamps: Partial<Record<"received_at" | "triaged_at" | "assigned_at" | "at_scene_at" | "on_board_at" | "hospital_confirmed_at" | "arrived_hospital_at" | "handed_off_at" | "closed_at", number>>;
  is_simulated: boolean;
  bot_confirm_at: number | null; // simulated paramedic confirms triage
  call_108_prompt: boolean;
};

export type OfferRec = {
  id: string; emergency_id: string; ambulance_id: string; round: number; status: "pending" | "accepted" | "declined" | "expired" | "superseded";
  predicted_eta_sec: number; distance_m: number; rank: number; offered_at: number; expires_at: number; responded_at: number | null;
  bot_at: number | null; bot_accept: boolean;
};

export type HospitalRequestRec = {
  id: string; emergency_id: string; hospital_id: string; rank: number; score: number; explanation: string[];
  status: HospitalRequestStatus; reason_code: RejectReason | null; reason_note: string | null;
  is_family_choice: boolean; is_priority: boolean; sent_at: number; expires_at: number; responded_at: number | null; responded_by: string | null;
  bot_at: number | null; bot_decision: "accept" | "reject" | "silent";
};

export type ReservationItem = { kind: "room"; room_id: string } | { kind: "resource"; resource_type: ResourceType; quantity: number } | { kind: "staff"; staff_id: string };
export type ReservationRec = {
  id: string; emergency_id: string; hospital_id: string; hospital_request_id: string; status: ReservationStatus;
  hold_expires_at: number; version: number; items: ReservationItem[];
};

export type HandoffRec = {
  emergency_id: string; hospital_id: string; room_id: string | null; receiving_staff_ids: string[];
  arrived_at: number | null; offloaded_at: number | null; delay_alerted: boolean; bot_receive_at: number | null;
};

export type EscalationOptionRec = { id: string; label: string; action: string; params: Record<string, unknown>; is_default: boolean };
export type EscalationRec = {
  id: string; type: EscalationType; emergency_id: string | null; status: EscalationStatus; summary: string;
  options: EscalationOptionRec[]; default_option_id: string; chosen_option_id: string | null;
  claimed_by: string | null; claimed_at: number | null; created_at: number; repeat_at: number; default_at: number;
  resolved_at: number | null; version: number; repeats: number;
};

export type AuditRec = {
  id: number; at: number; actor_type: "system" | "ai" | "user" | "developer" | "simulator"; actor_id: string;
  entity: string; entity_id: string; action: string; before?: unknown; after?: unknown; reason?: string | null; model_version?: string | null;
};

export type NotificationRec = { id: string; at: number; channel: "sms" | "telegram" | "push"; to: string; body: string };

export type HistoryRec = {
  at: number; hospital_id: string; acuity: Acuity; ai_acuity: Acuity; facility: Facility;
  call_to_accept: number; call_to_scene: number; scene_to_hospital: number; call_to_handoff: number; offload_delay: number;
  outcome: "accepted" | "rejected" | "timeout"; reject_reason: RejectReason | null; escalation: EscalationType | null; claim_sec: number | null; auto_default: boolean;
  stale: boolean;
};

/* ---------- the store ---------- */
export const db = {
  users: new Map<string, UserRec>(),
  profiles: new Map<string, ProfileRec>(),
  contacts: new Map<string, ContactRec>(),
  hospitals: new Map<string, HospitalRec>(),
  rooms: new Map<string, RoomRec>(),
  resources: new Map<string, ResourceRec>(),
  staff: new Map<string, StaffRec>(),
  shifts: new Map<string, ShiftRec>(),
  ambulances: new Map<string, AmbulanceRec>(),
  emergencies: new Map<string, EmergencyRec>(),
  offers: new Map<string, OfferRec>(),
  requests: new Map<string, HospitalRequestRec>(),
  reservations: new Map<string, ReservationRec>(),
  handoffs: new Map<string, HandoffRec>(),
  escalations: new Map<string, EscalationRec>(),
  audit: [] as AuditRec[],
  notifications: [] as NotificationRec[],
  history: [] as HistoryRec[],
  pushSubs: [] as { user_id: string; fcm_token: string }[],
  sim: { speed: 1 },
};

export function signalOf(a: AmbulanceRec, t = now()): Signal {
  const s = (t - a.last_heartbeat_at) / 1000;
  if (s > 120) return "lost";
  if (s > 30) return "weak";
  return "ok";
}

/* ---------- seed ---------- */
type SeedHospital = { name: string; area: string; address: string; lat: number; lng: number; caps: Capability[]; entrance: string; stab?: boolean };

export const SEED_HOSPITALS: SeedHospital[] = [
  { name: "Greenfield Heart Centre", area: "Nigdi", address: "Plot 12, Sector 24, Nigdi, Pimpri Chinchwad 411044", lat: 18.6566, lng: 73.7742, caps: ["cardiac_cathlab", "icu", "general_er"], entrance: "Emergency Gate 2, ground floor" },
  { name: "Riverside Multispeciality Hospital", area: "Chinchwad", address: "Old Mumbai Pune Highway, Chinchwad, Pimpri Chinchwad 411019", lat: 18.6309, lng: 73.7866, caps: ["cardiac_cathlab", "trauma_center", "stroke_thrombolysis", "neurosurgery", "icu", "general_er"], entrance: "Main Gate 1, emergency on the left" },
  { name: "Metro Neuro and Trauma Institute", area: "Pimpri", address: "Near PCMC Building, Pimpri, Pimpri Chinchwad 411018", lat: 18.6252, lng: 73.8061, caps: ["stroke_thrombolysis", "neurosurgery", "trauma_center", "icu", "general_er"], entrance: "Trauma entrance, back side" },
  { name: "Lotus Mother and Child Hospital", area: "Ravet", address: "Ravet Pul Road, Ravet, Pimpri Chinchwad 412101", lat: 18.6451, lng: 73.7468, caps: ["obstetrics", "pediatrics", "general_er"], entrance: "Gate A, labour ward first floor" },
  { name: "Northgate Burns and Trauma Centre", area: "Bhosari", address: "MIDC Road, Bhosari, Pimpri Chinchwad 411026", lat: 18.6216, lng: 73.8468, caps: ["burns_unit", "trauma_center", "icu", "general_er"], entrance: "Emergency ramp, MIDC Road side" },
  { name: "Unity Community Hospital", area: "Akurdi", address: "Station Road, Akurdi, Pimpri Chinchwad 411035", lat: 18.6482, lng: 73.7693, caps: ["general_er"], entrance: "Front gate, casualty on the right", stab: true },
  { name: "Hillview General Hospital", area: "Wakad", address: "Dange Chowk Road, Wakad, Pune 411057", lat: 18.5986, lng: 73.7651, caps: ["general_er", "icu", "toxicology", "pediatrics"], entrance: "Casualty entrance, Gate 3" },
  { name: "Sunrise Care Hospital", area: "Aundh", address: "ITI Road, Aundh, Pune 411007", lat: 18.5603, lng: 73.8092, caps: ["cardiac_cathlab", "stroke_thrombolysis", "obstetrics", "toxicology", "icu", "general_er"], entrance: "Emergency, ground floor, Gate 1" },
];

const SEED_AMBULANCES: { reg: string; type: AmbulanceType; base: string; lat: number; lng: number }[] = [
  { reg: "MH14AB1234", type: "ALS", base: "Akurdi", lat: 18.6448, lng: 73.7612 },
  { reg: "MH14CD5678", type: "ALS", base: "Pimpri", lat: 18.6268, lng: 73.8003 },
  { reg: "MH14EF2211", type: "ALS", base: "Wakad", lat: 18.5992, lng: 73.7618 },
  { reg: "MH12GH4410", type: "ALS", base: "Shivajinagar", lat: 18.5308, lng: 73.8475 },
  { reg: "MH12JK7788", type: "ALS", base: "Kothrud", lat: 18.5074, lng: 73.8077 },
  { reg: "MH14LM3030", type: "ALS", base: "Bhosari", lat: 18.6190, lng: 73.8480 },
  { reg: "MH14NP1001", type: "BLS", base: "Nigdi", lat: 18.6601, lng: 73.7702 },
  { reg: "MH14QR2020", type: "BLS", base: "Chinchwad", lat: 18.6391, lng: 73.7902 },
  { reg: "MH14ST3131", type: "BLS", base: "Ravet", lat: 18.6480, lng: 73.7430 },
  { reg: "MH12UV4242", type: "BLS", base: "Aundh", lat: 18.5590, lng: 73.8070 },
  { reg: "MH12WX5353", type: "BLS", base: "Baner", lat: 18.5590, lng: 73.7868 },
  { reg: "MH12YZ6464", type: "BLS", base: "Hadapsar", lat: 18.5089, lng: 73.9260 },
  { reg: "MH12AB7575", type: "BLS", base: "Swargate", lat: 18.5018, lng: 73.8636 },
  { reg: "MH14CD8686", type: "BLS", base: "Moshi", lat: 18.6720, lng: 73.8490 },
  { reg: "MH12EF9797", type: "BLS", base: "Viman Nagar", lat: 18.5679, lng: 73.9143 },
];

/** Offline gazetteer (subset of the OSM landmarks table, §5.6). */
export const LANDMARKS: { name: string; alt: string[]; lat: number; lng: number }[] = [
  { name: "Ganesh Temple, Sector 26, Akurdi", alt: ["ganesh temple", "ganesh mandir", "sector 26", "pradhikaran"], lat: 18.6536, lng: 73.7801 },
  { name: "Bhakti Shakti Chowk, Nigdi", alt: ["bhakti shakti", "nigdi chowk"], lat: 18.6628, lng: 73.7708 },
  { name: "Akurdi Railway Station", alt: ["akurdi station", "akurdi"], lat: 18.6486, lng: 73.7650 },
  { name: "PCMC Building, Pimpri", alt: ["pcmc", "pimpri chowk", "pimpri"], lat: 18.6279, lng: 73.8009 },
  { name: "Chinchwad Station", alt: ["chinchwad station", "chinchwad", "chaphekar chowk"], lat: 18.6423, lng: 73.7925 },
  { name: "Dange Chowk, Wakad", alt: ["dange chowk", "wakad"], lat: 18.6060, lng: 73.7690 },
  { name: "Hinjewadi Phase 1", alt: ["hinjewadi", "phase 1"], lat: 18.5913, lng: 73.7389 },
  { name: "Bhosari MIDC", alt: ["bhosari", "midc"], lat: 18.6250, lng: 73.8420 },
  { name: "Ravet Pul", alt: ["ravet"], lat: 18.6470, lng: 73.7450 },
  { name: "Aundh ITI Road", alt: ["aundh", "iti road"], lat: 18.5585, lng: 73.8075 },
  { name: "Shivajinagar Bus Stand", alt: ["shivajinagar"], lat: 18.5308, lng: 73.8475 },
  { name: "Pune Railway Station", alt: ["pune station"], lat: 18.5289, lng: 73.8744 },
  { name: "Swargate", alt: ["swargate"], lat: 18.5018, lng: 73.8636 },
  { name: "Kothrud Depot", alt: ["kothrud"], lat: 18.5074, lng: 73.8077 },
];

const NAMES = {
  emergency_physician: ["Dr. R. Shah", "Dr. P. Iyer"],
  er_nurse: ["Nurse P. Joshi", "Nurse S. Pawar"],
  anesthetist: ["Dr. M. Deshpande", "Dr. K. Rao"],
  cardiologist: ["Dr. A. Kulkarni", "Dr. V. Menon"],
  neurologist: ["Dr. S. Gokhale", "Dr. N. Bhat"],
  trauma_surgeon: ["Dr. H. Patil", "Dr. Y. Khan"],
  burns_surgeon: ["Dr. T. Sawant", "Dr. L. Dsouza"],
  obstetrician: ["Dr. M. Jadhav", "Dr. F. Sheikh"],
  pediatrician: ["Dr. G. Nair", "Dr. A. Wagh"],
  pulmonologist: ["Dr. C. Apte", "Dr. D. Sinha"],
} as Record<StaffSpecialty, string[]>;

/** Start of today at hh:00 India time, in ms. */
function istToday(hour: number) {
  const d = new Date();
  const utc = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), hour, 0, 0) - 330 * 60_000;
  return utc;
}

export function seed() {
  for (const m of Object.values(db)) if (m instanceof Map) m.clear();
  db.audit.length = 0;
  db.notifications.length = 0;
  db.pushSubs.length = 0;

  const t = now();
  const hospitalIds: string[] = [];
  SEED_HOSPITALS.forEach((h, hi) => {
    const id = uid();
    hospitalIds.push(id);
    db.hospitals.set(id, {
      id, name: h.name, address: h.address, location: { lat: h.lat, lng: h.lng }, er_entrance_note: h.entrance,
      duty_manager_phone: `+9190000001${String(hi + 1).padStart(2, "0")}`, phone: `+9120${String(27100000 + hi * 1111)}`,
      capabilities: h.caps, stabilization_capable: h.stab ?? true,
      // one hospital starts with stale data so the freshness badges have something to show (T32)
      last_confirmed_at: t - (hi === 6 ? 47 : 3 + hi * 2) * 60_000, is_simulated: true,
    });

    const rooms: [RoomType, string, string][] = [
      ["resus_bay", "RESUS-1", "Ground floor, Resus Bay 1"],
      ["resus_bay", "RESUS-2", "Ground floor, Resus Bay 2"],
      ["er_bed", "ER-1", "Ground floor, ER Bay 1"],
      ["er_bed", "ER-2", "Ground floor, ER Bay 2"],
      ["er_bed", "ER-3", "Ground floor, ER Bay 3"],
      ["er_bed", "ER-4", "Ground floor, ER Bay 4"],
      ["icu_bed", "ICU-1", "Second floor, ICU Bed 1"],
      ["icu_bed", "ICU-2", "Second floor, ICU Bed 2"],
    ];
    if (h.caps.includes("trauma_center")) rooms.push(["trauma_bay", "TRAUMA-1", "Ground floor, Trauma Bay 1"], ["trauma_bay", "TRAUMA-2", "Ground floor, Trauma Bay 2"]);
    if (h.caps.includes("burns_unit")) rooms.push(["burns_unit", "BURNS-1", "First floor, Burns Unit"]);
    if (h.caps.includes("obstetrics")) rooms.push(["labour_room", "LR-1", "First floor, Labour Room 1"], ["labour_room", "LR-2", "First floor, Labour Room 2"]);
    if (h.caps.includes("pediatrics")) rooms.push(["pediatric_er", "PEDS-1", "Ground floor, Children's ER"]);
    rooms.forEach(([type, code, note], i) => {
      // realistic occupancy: some rooms busy already
      const busy = (hi + i) % 3 === 0;
      const id = uid();
      db.rooms.set(id, {
        id, hospital_id: hospitalIds[hi], code, type, status: busy ? "occupied" : i % 7 === 5 ? "cleaning" : "free",
        location_note: note, priority_order: i, reservation_id: null, version: 1, status_updated_at: t - ((i * 7) % 40) * 60_000,
        occupant: busy ? "Admitted patient" : null,
      });
    });

    const res: [ResourceType, number, number][] = [["defibrillator", 3, 3], ["ventilator", 6, 2 + (hi % 3)]];
    if (h.caps.includes("cardiac_cathlab")) res.push(["cath_lab", 2, hi === 0 ? 1 : 2]);
    if (h.caps.includes("stroke_thrombolysis")) res.push(["ct_scanner", 1, 1], ["mri", 1, 1]);
    if (h.caps.includes("trauma_center") || h.caps.includes("burns_unit")) res.push(["operating_theatre", 3, 2]);
    res.push(["blood_o_neg", 10, 4 + hi], ["blood_o_pos", 12, 8], ["blood_b_pos", 10, 6], ["blood_a_pos", 10, 7]);
    res.forEach(([type, total, available], i) => {
      const id = uid();
      db.resources.set(id, {
        id, hospital_id: hospitalIds[hi], type, total, available, reserved: 0, version: 1,
        reported_at: t - (hi === 6 ? 47 : (i * 4 + hi) % 25) * 60_000,
      });
    });

    const staff: [StaffSpecialty, number][] = [["emergency_physician", 2], ["er_nurse", 2], ["anesthetist", 1]];
    if (h.caps.includes("cardiac_cathlab")) staff.push(["cardiologist", 2]);
    if (h.caps.includes("stroke_thrombolysis")) staff.push(["neurologist", 2]);
    if (h.caps.includes("trauma_center")) staff.push(["trauma_surgeon", 2]);
    if (h.caps.includes("burns_unit")) staff.push(["burns_surgeon", 2]);
    if (h.caps.includes("obstetrics")) staff.push(["obstetrician", 2]);
    if (h.caps.includes("pediatrics")) staff.push(["pediatrician", 2]);
    if (h.caps.includes("toxicology")) staff.push(["pulmonologist", 1]);
    for (const [specialty, count] of staff) {
      for (let k = 0; k < count; k++) {
        const id = uid();
        db.staff.set(id, { id, hospital_id: hospitalIds[hi], name: NAMES[specialty][k] ?? `${specialty} ${k + 1}`, specialty, phone: `+91980000${hi}${k}${specialty.length}`, is_active: true });
        // 12 hour shifts so one of each specialty is always on duty: 08:00 to 20:00 and 20:00 to 08:00 IST
        for (const dayOffset of [-1, 0, 1]) {
          const start = istToday(k === 0 ? 8 : 20) + dayOffset * 86_400_000;
          const sid = uid();
          db.shifts.set(sid, { id: sid, staff_id: id, start_at: start, end_at: start + 12 * 3600_000 });
        }
      }
    }
  });

  SEED_AMBULANCES.forEach((a, i) => {
    const id = uid();
    db.ambulances.set(id, {
      id, registration_no: a.reg, type: a.type, equipment: a.type === "ALS" ? ["als_kit", "ventilator", "defibrillator"] : ["bls_kit", "oxygen"],
      status: i === 11 || i === 14 ? "offline" : "available", location: { lat: a.lat, lng: a.lng }, heading: 0, speed_kmh: 0,
      last_heartbeat_at: t, active_emergency_id: null, kyc_verified: true, version: 1, is_simulated: true,
      crew_phone: `+9191000000${String(i + 1).padStart(2, "0")}`, base_name: a.base, route: null, route_m: 0, leg: null, silent_until: 0, idle_since: null,
    });
  });

  // Users (data/seed/CREDENTIALS.md)
  const addUser = (u: Omit<UserRec, "id" | "language"> & { language?: string }) => {
    const id = uid();
    db.users.set(id, { id, language: u.language ?? "en", ...u });
    return id;
  };
  addUser({ role: "developer", name: "On call developer", phone: "+911234567890", password: "demo1234", hospital_id: null, ambulance_id: null });
  hospitalIds.forEach((hid, i) => addUser({ role: "hospital_staff", name: ["Nurse P. Joshi", "Dr. R. Shah", "Nurse K. More", "Dr. S. Kale", "Nurse A. Gaikwad", "Dr. V. Pillai", "Nurse R. Dias", "Dr. N. Rane"][i], phone: `+91900000000${i + 1}`, password: "demo1234", hospital_id: hid, ambulance_id: null }));
  [...db.ambulances.values()].forEach((a, i) => addUser({ role: "paramedic", name: ["S. Patil", "R. Jagtap", "M. Shinde", "A. Kamble", "P. Salunkhe", "V. Mane", "D. Pawar", "K. Chavan", "G. Bhosale", "H. Kadam", "J. More", "L. Gaikwad", "N. Thorat", "O. Deshmukh", "T. Kale"][i], phone: `+9191000000${String(i + 1).padStart(2, "0")}`, password: "demo1234", hospital_id: null, ambulance_id: a.id }));
  const p1 = addUser({ role: "patient", name: "Rahul Kulkarni", phone: "+919200000001", password: "demo1234", hospital_id: null, ambulance_id: null, language: "en" });
  const p2 = addUser({ role: "patient", name: "Anita Deshmukh", phone: "+919200000002", password: "demo1234", hospital_id: null, ambulance_id: null, language: "mr" });
  db.profiles.set(p1, { user_id: p1, dob: "1981-03-14", sex: "male", blood_group: "O+", allergies: [], conditions: ["Diabetes"], medications: ["Metformin 500 mg twice daily"], insurance_provider: null, insurance_policy_no: null, home_address: "Sector 26, Pradhikaran, Akurdi", home_location: { lat: 18.6536, lng: 73.7801 }, notes: null, version: 1 });
  db.profiles.set(p2, { user_id: p2, dob: "1996-07-02", sex: "female", blood_group: "A-", allergies: [], conditions: ["Hypertension"], medications: [], insurance_provider: null, insurance_policy_no: null, home_address: "Dange Chowk, Wakad", home_location: { lat: 18.606, lng: 73.769 }, notes: null, version: 1 });
  const c1 = uid();
  db.contacts.set(c1, { id: c1, user_id: p1, name: "Sunita Kulkarni", phone: "+919999999999", relation: "Wife", language: "mr", priority: 1 });
  const c2 = uid();
  db.contacts.set(c2, { id: c2, user_id: p2, name: "Emergency Contact", phone: "+919999999998", relation: "Family", language: "mr", priority: 1 });
}
