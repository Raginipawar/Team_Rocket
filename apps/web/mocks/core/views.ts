// Role-based response projections (technical.md §18). Each audience gets its own
// serializer; the family view carries no clinical fields at all (T31).

import type {
  ActiveJob, AmbulanceView, EmergencyView, HospitalRequestCard, HospitalView, IncomingAmbulance, TrackView, Timeline,
} from "../../lib/api-types";
import { FACILITY_SPECIALIST } from "../../lib/enums";
import { MOCK } from "./config";
import { distanceM, remainingPolyline } from "./geo";
import { db, iso, now, signalOf, type AmbulanceRec, type EmergencyRec, type HospitalRequestRec } from "./world";

export function velocity(a: AmbulanceRec) {
  // metres per real second for a simulated ambulance on its current route
  if (!a.route) return 0;
  return (a.route.distance_m / Math.max(60, a.route.duration_sec)) * MOCK.DRIVE_FACTOR * db.sim.speed;
}

export function etaFor(a: AmbulanceRec): { eta: number; low: number; high: number } | null {
  if (!a.route) return null;
  const v = velocity(a) || 1;
  const remaining = Math.max(0, a.route.distance_m - a.route_m);
  const eta = Math.round(remaining / v);
  // uncertainty band (§9.11): wider when the signal is poor
  const sig = signalOf(a);
  const spread = sig === "lost" ? 0.6 : sig === "weak" ? 0.35 : 0.2;
  return { eta, low: Math.max(0, Math.round(eta * (1 - spread * 0.6))), high: Math.round(eta * (1 + spread) + 30) };
}

export function acuityOf(e: EmergencyRec) {
  return e.final_acuity ?? e.ai_acuity ?? "critical";
}
export function facilityOf(e: EmergencyRec) {
  return e.final_facility ?? e.ai_facility ?? "general";
}

export function patientDisplay(e: EmergencyRec) {
  const sex = e.patient.sex ?? e.extracted.sex ?? null;
  const age = e.patient.est_age ?? e.extracted.age ?? null;
  const s = sex === "male" || sex === "M" ? "Male" : sex === "female" || sex === "F" ? "Female" : "Patient";
  const base = e.patient.is_unknown && !e.patient.user_id ? `Unknown ${s.toLowerCase()}` : s;
  return age ? `${base}, ~${Math.round(age / 5) * 5 || age}` : base;
}

function profileFor(e: EmergencyRec) {
  if (!e.patient.user_id) return null;
  const p = db.profiles.get(e.patient.user_id);
  if (!p) return null;
  return { blood_group: p.blood_group, allergies: p.allergies, conditions: p.conditions, medications: p.medications };
}

export function timeline(e: EmergencyRec): Timeline {
  const t: Timeline = {};
  for (const [k, v] of Object.entries(e.timestamps)) (t as Record<string, string | null>)[k] = iso(v);
  return t;
}

function hospitalView(hid: string | null, a: AmbulanceRec | null): HospitalView | null {
  if (!hid) return null;
  const h = db.hospitals.get(hid);
  if (!h) return null;
  const eta = a && a.leg === "to_hospital" ? etaFor(a)?.eta ?? null : null;
  return { id: h.id, name: h.name, address: h.address, location: h.location, er_entrance_note: h.er_entrance_note, phone: h.phone, eta_sec: eta, is_simulated: h.is_simulated };
}

function ambulanceView(a: AmbulanceRec | null): AmbulanceView | null {
  if (!a) return null;
  const eta = etaFor(a);
  return {
    registration_no: a.registration_no, type: a.type, location: a.location, heading: a.heading,
    eta_sec: eta?.eta ?? null, eta_low_sec: eta?.low ?? null, eta_high_sec: eta?.high ?? null,
    crew_phone: a.crew_phone, signal: signalOf(a), is_simulated: a.is_simulated,
  };
}

/** GET /emergencies/{id} for the caller (§7.3). */
export function patientView(e: EmergencyRec): EmergencyView {
  const a = e.ambulance_id ? db.ambulances.get(e.ambulance_id) ?? null : null;
  const confirmedHospital = ["hospital_confirmed", "arrived_hospital", "handed_off", "closed"].includes(e.status) ? e.hospital_id : null;
  return {
    id: e.id, status: e.status, version: e.version,
    triage: e.ai_acuity ? { acuity: acuityOf(e), facility: facilityOf(e), confidence: e.ai_confidence ?? 0, confirmed: !!e.final_acuity, needs_review: e.needs_review } : null,
    ambulance: ["ambulance_assigned", "at_scene", "patient_on_board", "hospital_selecting", "hospital_confirmed", "arrived_hospital"].includes(e.status) ? ambulanceView(a) : null,
    hospital: hospitalView(confirmedHospital, a),
    handoff: confirmedHospital ? e.handoff_info : null,
    first_aid: e.first_aid,
    channel: e.channel, for_self: e.for_self,
    pickup: e.location ? { ...e.location, accuracy_m: e.accuracy_m, landmark: e.landmark_text } : null,
    timeline: timeline(e), reroute: e.reroute,
    route: a?.route ? remainingPolyline(a.route, a.route_m) : null,
    leg: a?.leg === "to_patient" || a?.leg === "to_hospital" ? a.leg : null,
    call_108_prompt: e.call_108_prompt,
  };
}

/** GET /track/{token} (§7.6): non-clinical only. */
export function trackView(e: EmergencyRec): TrackView {
  const a = e.ambulance_id ? db.ambulances.get(e.ambulance_id) ?? null : null;
  const eta = a ? etaFor(a) : null;
  const confirmed = ["hospital_confirmed", "arrived_hospital", "handed_off", "closed"].includes(e.status);
  const h = confirmed && e.hospital_id ? db.hospitals.get(e.hospital_id) : null;
  const caller = e.caller_user_id ? db.users.get(e.caller_user_id) : null;
  const contact = caller ? [...db.contacts.values()].find((c) => c.user_id === caller.id) : null;
  return {
    status: e.status,
    patient_first_name: e.for_self && caller?.name ? caller.name.split(" ")[0] : null,
    language: contact?.language ?? "en",
    ambulance: a && ["ambulance_assigned", "at_scene", "patient_on_board", "hospital_selecting", "hospital_confirmed", "arrived_hospital"].includes(e.status)
      ? { registration_no: a.registration_no, location: a.location, eta_sec: eta?.eta ?? null, eta_low_sec: eta?.low ?? null, eta_high_sec: eta?.high ?? null, signal: signalOf(a) }
      : null,
    hospital: h ? { name: h.name, address: h.address, location: h.location, entrance_note: h.er_entrance_note } : null,
    handoff: confirmed && e.handoff_info ? { room_location_note: e.handoff_info.room_location_note, receiving_team: e.handoff_info.receiving_team, entrance_note: e.handoff_info.entrance_note } : null,
    pickup: e.location,
    timeline: timeline(e),
    reroute: e.reroute ? { from_hospital: e.reroute.from_hospital, to_hospital: e.reroute.to_hospital, reason: "The hospital changed to one that can take the patient sooner.", at: e.reroute.at } : null,
    updated_at: new Date().toISOString(),
  };
}

/** GET /ambulance/active (§7.4). */
export function activeJob(e: EmergencyRec, a: AmbulanceRec): ActiveJob {
  const eta = etaFor(a);
  const req = [...db.requests.values()].find((r) => r.emergency_id === e.id && r.status === "pending");
  const res = e.reservation_id ? db.reservations.get(e.reservation_id) : null;
  const roomItem = res?.items.find((i) => i.kind === "room") as { kind: "room"; room_id: string } | undefined;
  const room = roomItem ? db.rooms.get(roomItem.room_id) : null;
  const confirmed = res?.status === "confirmed";
  const h = e.hospital_id ? db.hospitals.get(e.hospital_id) : null;
  const handoff = db.handoffs.get(e.id);
  return {
    emergency_id: e.id,
    short_id: e.id.slice(0, 6).toUpperCase(),
    status: e.status, version: e.version,
    leg: a.leg === "to_patient" || a.leg === "to_hospital" ? a.leg : null,
    pickup: { ...(e.location ?? a.location), landmark: e.landmark_text, accuracy_m: e.accuracy_m },
    caller_phone: e.caller_phone,
    patient: { display: patientDisplay(e), temp_id: e.patient.temp_id, age: e.patient.est_age ?? e.extracted.age ?? null, sex: e.patient.sex ?? e.extracted.sex ?? null, patient_count: e.patient_count, profile: profileFor(e) },
    triage: {
      acuity: acuityOf(e), facility: facilityOf(e), confidence: e.ai_confidence ?? 0, confirmed: !!e.final_acuity, needs_review: e.needs_review,
      ai_acuity: e.ai_acuity ?? undefined, ai_facility: e.ai_facility ?? undefined, mlc_flag: e.mlc_flag, fragility: e.fragility,
    },
    transcript: e.transcript ?? e.raw_text,
    route: a.route ? remainingPolyline(a.route, a.route_m) : null,
    eta_sec: eta?.eta ?? null,
    distance_m: a.route ? Math.max(0, Math.round(a.route.distance_m - a.route_m)) : null,
    turns: a.route?.steps ?? [],
    destination: h && (confirmed || e.status === "arrived_hospital") ? {
      hospital: { id: h.id, name: h.name, address: h.address, location: h.location, er_entrance_note: h.er_entrance_note, phone: h.phone },
      room_code: room?.code ?? null, room_location_note: e.handoff_info?.room_location_note ?? room?.location_note ?? null,
      receiving_team: e.handoff_info?.receiving_team ?? null, entrance_note: h.er_entrance_note, reservation_status: res?.status ?? null,
      is_family_choice: !!e.family_choice_hospital_id && e.family_choice_hospital_id === h.id,
    } : null,
    hospital_selecting: req ? { hospital_name: db.hospitals.get(req.hospital_id)?.name ?? "", expires_at: iso(req.expires_at)! } : null,
    arrived_at: iso(handoff?.arrived_at ?? null),
  };
}

export function whyYou(e: EmergencyRec, hospitalId: string, etaSec: number): string[] {
  const h = db.hospitals.get(hospitalId)!;
  const f = facilityOf(e);
  const why: string[] = [];
  const capLabel: Record<string, string> = { cardiac: "Cath lab available", stroke: "Stroke team and CT available", trauma: "Trauma centre", burns: "Burns unit", obstetric: "Labour room available", pediatric: "Children's ER", poisoning: "Toxicology support", respiratory: "ICU and ventilators", general: "Emergency room" };
  why.push(capLabel[f]);
  const spec = FACILITY_SPECIALIST[f];
  if (specialistOnDutyAt(hospitalId, spec, now() + etaSec * 1000)) why.push(`${spec.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())} on duty at arrival`);
  why.push(`${Math.max(1, Math.round(etaSec / 60))} min ETA`);
  if (now() - h.last_confirmed_at > 30 * 60_000) why.push("Beds last confirmed over 30 min ago");
  return why;
}

export function specialistOnDutyAt(hospitalId: string, specialty: string, at: number) {
  for (const s of db.staff.values()) {
    if (s.hospital_id !== hospitalId || s.specialty !== specialty || !s.is_active) continue;
    for (const sh of db.shifts.values()) if (sh.staff_id === s.id && sh.start_at <= at && sh.end_at > at) return s;
  }
  return null;
}

/** Incoming patient card (§7.5). */
export function hospitalCard(r: HospitalRequestRec): HospitalRequestCard {
  const e = db.emergencies.get(r.emergency_id)!;
  const a = e.ambulance_id ? db.ambulances.get(e.ambulance_id)! : null;
  const eta = a ? etaFor(a) : null;
  const res = [...db.reservations.values()].find((x) => x.hospital_request_id === r.id);
  const roomItem = res?.items.find((i) => i.kind === "room") as { kind: "room"; room_id: string } | undefined;
  return {
    request_id: r.id, emergency_id: e.id, expires_at: iso(r.expires_at)!, status: r.status,
    patient: { display: patientDisplay(e), temp_id: e.patient.temp_id, acuity: acuityOf(e), facility: facilityOf(e), confirmed_by_paramedic: !!e.final_acuity, mlc_flag: e.mlc_flag },
    profile: profileFor(e),
    handover_note: e.handover_note,
    prep_checklist: e.predicted_resources,
    ambulance: {
      registration_no: a?.registration_no ?? "", type: a?.type ?? "ALS", location: a?.location ?? null,
      eta_sec: eta?.eta ?? null, eta_low_sec: eta?.low ?? null, eta_high_sec: eta?.high ?? null, signal: a ? signalOf(a) : "ok",
    },
    why_you: r.explanation,
    is_family_choice: r.is_family_choice, is_priority: r.is_priority,
    suggested_room_id: roomItem?.room_id ?? null,
    suggested_staff_ids: suggestStaff(e, r.hospital_id).map((s) => s.id),
  };
}

export function suggestStaff(e: EmergencyRec, hospitalId: string) {
  const a = e.ambulance_id ? db.ambulances.get(e.ambulance_id) : null;
  const at = now() + (a ? etaFor(a)?.eta ?? 600 : 600) * 1000;
  const picks = [FACILITY_SPECIALIST[facilityOf(e)], "emergency_physician", "er_nurse"];
  const out: NonNullable<ReturnType<typeof specialistOnDutyAt>>[] = [];
  for (const sp of picks) {
    const s = specialistOnDutyAt(hospitalId, sp, at);
    if (s && !out.includes(s)) out.push(s);
  }
  return out;
}

export function incomingFor(hospitalId: string, which: "incoming" | "at_door"): IncomingAmbulance[] {
  const out: IncomingAmbulance[] = [];
  for (const e of db.emergencies.values()) {
    if (e.hospital_id !== hospitalId) continue;
    const want = which === "incoming" ? e.status === "hospital_confirmed" : e.status === "arrived_hospital";
    if (!want) continue;
    const a = e.ambulance_id ? db.ambulances.get(e.ambulance_id) : null;
    const eta = a ? etaFor(a) : null;
    const res = e.reservation_id ? db.reservations.get(e.reservation_id) : null;
    const roomItem = res?.items.find((i) => i.kind === "room") as { kind: "room"; room_id: string } | undefined;
    out.push({
      emergency_id: e.id, registration_no: a?.registration_no ?? "", type: a?.type ?? "ALS", acuity: acuityOf(e), facility: facilityOf(e),
      location: a?.location ?? null, eta_sec: eta?.eta ?? null, eta_low_sec: eta?.low ?? null, eta_high_sec: eta?.high ?? null,
      signal: a ? signalOf(a) : "ok", last_seen_at: a ? iso(a.last_heartbeat_at) : null,
      room_code: roomItem ? db.rooms.get(roomItem.room_id)?.code ?? null : null,
      patient_display: patientDisplay(e), arrived_at: iso(db.handoffs.get(e.id)?.arrived_at ?? null), temp_id: e.patient.temp_id,
    });
  }
  return out;
}

export function distanceTo(a: AmbulanceRec, e: EmergencyRec) {
  return e.location ? distanceM(a.location, e.location) : Infinity;
}
