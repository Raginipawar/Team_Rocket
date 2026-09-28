// Domain logic of the mock core, following technical.md §6 (state machines),
// §10 (intake pipeline) and §11 (dispatch, hospital selection, reservations,
// walk-in override, deterioration, family override, breakdown, handoff) and §13
// (escalations). JavaScript is single threaded, so each function below runs as one
// atomic unit: that stands in for the SQL transactions of the real core, and the
// same guards (status + version checks) produce the same 409s.

import type { Acuity, AmbulanceStatus, EmergencyStatus, Facility, RejectReason, ResourceType } from "../../lib/enums";
import { ACCEPTABLE_ROOMS, ENUMS, FACILITY_SPECIALIST, REQUIRED_CAPABILITY } from "../../lib/enums";
import { C, MOCK } from "./config";
import { publish, ambulanceIsLive, hospitalIsLive } from "./bus";
import { conflict, badRequest, ApiError } from "./http";
import { getRoute, distanceM, pointAt } from "./geo";
import * as ml from "./ml";
import { issueOpsLink, newToken, hashToken } from "./auth";
import {
  db, uid, now, iso, signalOf,
  type AmbulanceRec, type EmergencyRec, type EscalationOptionRec, type EscalationRec, type ExtractedFacts,
  type HospitalRequestRec, type OfferRec, type ReservationRec, type RoomRec, LANDMARKS,
} from "./world";
import { acuityOf, etaFor, facilityOf, hospitalCard, patientDisplay, patientView, suggestStaff, whyYou, specialistOnDutyAt } from "./views";

const S = () => db.sim.speed;
const sec = (n: number) => (n * 1000) / S(); // timers scale with the sim speed (§15)
const rand = (a: number, b: number) => a + Math.random() * (b - a);

/* ---------- audit + fake notifications ---------- */
// A dev process that stays up for hours of testing must not let these grow forever —
// unbounded growth here was traced to a real, reproducible multi-second stall under
// load (long test session, many emergencies) even though a fresh process was always
// fast. Keep the array bounded rather than only capping what a route slices off it.
const AUDIT_CAP = 4000;
let auditSeq = 0;
export function audit(actor_type: "system" | "ai" | "user" | "developer" | "simulator", actor_id: string, entity: string, entity_id: string, action: string, after?: unknown, reason?: string | null, model_version?: string | null, before?: unknown) {
  db.audit.push({ id: ++auditSeq, at: now(), actor_type, actor_id, entity, entity_id, action, before, after, reason: reason ?? null, model_version: model_version ?? null });
  if (db.audit.length > AUDIT_CAP) db.audit.splice(0, db.audit.length - AUDIT_CAP);
}

const TERMINAL: EmergencyStatus[] = ["closed", "cancelled", "refused_transport", "merged_duplicate"];
/** Drops finished emergencies (and their offers/requests/reservations/handoffs) once
 * they're old enough that nothing valid still needs them: past the family track
 * token's own validity window (§7.6: closed + 6h). Run periodically by sim.ts so a
 * long-lived dev process doesn't accumulate years of test runs in memory and slow
 * every tick()/dashboard fetch down as the collections grow without bound. */
export function pruneOldEmergencies(maxAgeMs = 6 * 3600_000) {
  const cutoff = now() - maxAgeMs;
  let removed = 0;
  for (const [id, e] of db.emergencies) {
    if (!TERMINAL.includes(e.status)) continue;
    const endedAt = e.timestamps.closed_at ?? e.timestamps.handed_off_at ?? e.timestamps.received_at ?? 0;
    if (endedAt > cutoff) continue;
    for (const [k, o] of db.offers) if (o.emergency_id === id) db.offers.delete(k);
    for (const [k, r] of db.requests) if (r.emergency_id === id) db.requests.delete(k);
    for (const [k, r] of db.reservations) if (r.emergency_id === id) db.reservations.delete(k);
    db.handoffs.delete(id);
    db.emergencies.delete(id);
    removed++;
  }
  if (removed) console.log(`[mock-core] pruned ${removed} emergency(ies) older than ${Math.round(maxAgeMs / 3600_000)}h`);
  return removed;
}

/** SMS_MODE=fake / TELEGRAM_MODE=fake (§17): logged, never sent. */
export function notify(channel: "sms" | "telegram" | "push", to: string, body: string) {
  db.notifications.push({ id: uid(), at: now(), channel, to, body });
  if (db.notifications.length > 500) db.notifications.shift();
  console.log(`[fake ${channel}] -> ${to}: ${body}`);
}

/* ---------- state machines (§6) ---------- */
const EM_FSM: Record<EmergencyStatus, EmergencyStatus[]> = {
  received: ["triaged", "cancelled", "merged_duplicate"],
  triaged: ["dispatching", "cancelled", "merged_duplicate"],
  dispatching: ["ambulance_assigned", "cancelled"],
  ambulance_assigned: ["at_scene", "dispatching", "cancelled"],
  at_scene: ["patient_on_board", "refused_transport", "cancelled", "dispatching"],
  patient_on_board: ["hospital_selecting", "refused_transport"],
  hospital_selecting: ["hospital_selecting", "hospital_confirmed", "refused_transport"],
  hospital_confirmed: ["arrived_hospital", "hospital_selecting"],
  arrived_hospital: ["handed_off"],
  handed_off: ["closed"],
  closed: [],
  cancelled: [],
  refused_transport: [],
  merged_duplicate: [],
};

const AMB_FSM: Record<AmbulanceStatus, AmbulanceStatus[]> = {
  offline: ["available", "out_of_service"],
  available: ["offline", "dispatched", "out_of_service"],
  dispatched: ["at_scene", "available", "out_of_service"],
  at_scene: ["transporting", "available", "out_of_service"],
  transporting: ["at_hospital", "out_of_service"],
  at_hospital: ["cleaning", "out_of_service"],
  cleaning: ["available", "out_of_service"],
  out_of_service: ["offline", "available"],
};

const STAMP: Partial<Record<EmergencyStatus, keyof EmergencyRec["timestamps"]>> = {
  triaged: "triaged_at", ambulance_assigned: "assigned_at", at_scene: "at_scene_at", patient_on_board: "on_board_at",
  hospital_confirmed: "hospital_confirmed_at", arrived_hospital: "arrived_hospital_at", handed_off: "handed_off_at", closed: "closed_at",
};

function trackChannel(e: EmergencyRec) {
  return `track:${e.track_token}`;
}

export function setStatus(e: EmergencyRec, to: EmergencyStatus, actor = "system", reason?: string) {
  if (e.status !== to && !EM_FSM[e.status].includes(to)) throw conflict("INVALID_TRANSITION", `Cannot go from ${e.status} to ${to}`, { current: patientView(e) });
  const from = e.status;
  e.status = to;
  e.version++;
  const stamp = STAMP[to];
  if (stamp && !e.timestamps[stamp]) e.timestamps[stamp] = now();
  audit(actor === "system" ? "system" : "user", actor, "emergencies", e.id, `status:${to}`, { from, to }, reason);
  const data = { status: to, version: e.version };
  publish(`emergency:${e.id}`, "emergency.status", data);
  publish(trackChannel(e), "emergency.status", data);
  publish("ops", "emergency.status", { ...data, emergency_id: e.id });
  if (e.hospital_id) publish(`hospital:${e.hospital_id}`, "emergency.status", { ...data, emergency_id: e.id });
  if (e.ambulance_id) publish(`ambulance:${e.ambulance_id}`, "emergency.status", { ...data, emergency_id: e.id });
}

export function setAmbulance(a: AmbulanceRec, to: AmbulanceStatus, actor = "system") {
  if (a.status !== to && !AMB_FSM[a.status].includes(to)) throw conflict("INVALID_TRANSITION", `Ambulance cannot go from ${a.status} to ${to}`);
  const from = a.status;
  a.status = to;
  a.version++;
  audit(actor === "system" ? "system" : "user", actor, "ambulances", a.id, `status:${to}`, { from, to });
  publish(`ambulance:${a.id}`, "ambulance.status", { status: to, version: a.version });
  publish("ops", "ambulance.status", { ambulance_id: a.id, status: to });
}

/* ---------- location helpers ---------- */
function matchLandmark(text: string | null | undefined) {
  if (!text) return null;
  const t = text.toLowerCase();
  let best: (typeof LANDMARKS)[number] | null = null;
  let bestLen = 0;
  for (const l of LANDMARKS) {
    for (const alt of [l.name.toLowerCase(), ...l.alt]) {
      if (t.includes(alt) && alt.length > bestLen) {
        best = l;
        bestLen = alt.length;
      }
    }
  }
  return best;
}

/* ---------- 10.1 SOS intake ---------- */
export async function createEmergency(input: {
  channel: EmergencyRec["channel"]; text: string | null; lat: number | null; lng: number | null; accuracy_m: number | null;
  for_self: boolean; caller_user_id: string | null; caller_phone: string | null; language: string; simulated?: boolean;
}) {
  const t = now();
  const { raw, hash } = newToken();
  const caller = input.caller_user_id ? db.users.get(input.caller_user_id) : null;
  const e: EmergencyRec = {
    id: uid(), incident_id: uid(), caller_user_id: input.caller_user_id, caller_phone: input.caller_phone ?? caller?.phone ?? null,
    channel: input.channel, raw_text: input.text, transcript: input.text, language: input.language || caller?.language || "en", extracted: {},
    location: input.lat != null && input.lng != null ? { lat: input.lat, lng: input.lng } : null, accuracy_m: input.accuracy_m,
    landmark_text: null, location_source: "gps",
    ai_acuity: null, ai_facility: null, ai_confidence: null, needs_review: false, final_acuity: null, final_facility: null,
    required_ambulance_type: "ALS", fragility: false, mlc_flag: false, prank_score: null, duplicate_of: null,
    predicted_resources: [], handover_note: null, status: "received", ambulance_id: null, hospital_id: null, reservation_id: null,
    track_token: hash, version: 1, for_self: input.for_self, patient_count: 1,
    patient: { user_id: input.for_self ? input.caller_user_id : null, temp_id: null, is_unknown: !input.for_self && !input.caller_user_id, est_age: null, sex: null, name: input.for_self ? caller?.name ?? null : null },
    followup_answers: [], followup_current: null, followup_done: false, first_aid: null, model_versions: {},
    dispatch_round: 0, next_round_at: null, escalated_no_ambulance: false, rank_list: [], tried_hospitals: [], reroute: null,
    handoff_info: null, family_choice_hospital_id: null, timestamps: { received_at: t }, is_simulated: !!input.simulated,
    bot_confirm_at: null, call_108_prompt: false,
  };
  if (input.for_self && caller) {
    const p = db.profiles.get(caller.id);
    if (p?.dob) e.patient.est_age = Math.floor((t - Date.parse(p.dob)) / (365.25 * 86_400_000));
    if (p?.sex) e.patient.sex = p.sex;
  }
  db.emergencies.set(e.id, e);
  audit("user", e.caller_phone ?? "anonymous", "emergencies", e.id, "create", { channel: e.channel, status: "received" });
  // family notification (§12.1): the tracking link goes to emergency contacts by SMS
  if (caller) {
    for (const c of db.contacts.values()) {
      if (c.user_id === caller.id) notify("sms", c.phone, `GoldenHour: ${caller.name?.split(" ")[0] ?? "Your family member"} asked for an ambulance. Follow live: ${MOCK.WEB_ORIGIN}/track/${raw}`);
    }
  }
  void processEmergency(e.id).catch((err) => console.error("[mock-core] process_emergency failed", err));
  return { emergency: e, trackRaw: raw };
}

async function processEmergency(id: string) {
  const e = db.emergencies.get(id);
  if (!e || e.status !== "received") return;
  const text = e.transcript ?? "";
  // 2. extraction
  let facts: ExtractedFacts = {};
  if (text) {
    const out = await ml.extract(text, e.language);
    facts = out.facts;
    e.model_versions.extract = out.model_version;
  }
  e.extracted = facts;
  e.patient_count = Math.max(1, facts.patient_count ?? 1);
  if (!e.patient.sex && facts.sex) e.patient.sex = facts.sex;
  if (!e.patient.est_age && facts.age) e.patient.est_age = facts.age;
  // 3. location resolution
  const lm = matchLandmark(facts.landmark ?? text);
  if (!e.location || (e.accuracy_m ?? 0) > 100) {
    if (lm) {
      e.location = { lat: lm.lat, lng: lm.lng };
      e.location_source = "landmark_geocode";
      e.landmark_text = lm.name;
    } else if (e.caller_user_id && db.profiles.get(e.caller_user_id)?.home_location) {
      e.location = db.profiles.get(e.caller_user_id)!.home_location;
      e.location_source = "profile_home";
      e.landmark_text = db.profiles.get(e.caller_user_id)!.home_address;
    }
  } else if (lm && distanceM(lm, e.location) < 1500) {
    e.landmark_text = lm.name;
  }
  if (!e.location) {
    // no fix at all: fall back to the demo area centre and ask for a landmark first
    e.location = { lat: 18.6298, lng: 73.7997 };
    e.location_source = "unresolved";
  }
  // unknown patient (§11.14)
  if (!e.for_self && !e.patient.user_id && facts.conscious === false) {
    const d = new Date();
    e.patient.temp_id = `UNK-${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}-${String(Math.floor(rand(1, 9999))).padStart(4, "0")}`;
    e.patient.is_unknown = true;
  }
  // 4. triage + resources in parallel
  const prof = e.patient.user_id ? db.profiles.get(e.patient.user_id) : null;
  const profileSummary = prof ? [prof.conditions.join(", "), prof.medications.join(", ")].filter(Boolean).join("; ") : null;
  let tri: ml.TriageOut;
  if (!text) {
    // app_button with no text (§10.1 step 3): default critical/general, needs review, ALS
    tri = { acuity: "critical", facility: "general", confidence: 0.3, needs_review: true, fragility: false, mlc_flag: false, model_version: "rule:no-text" };
  } else {
    tri = await ml.triage(text, facts, profileSummary);
  }
  e.ai_acuity = tri.acuity;
  e.ai_facility = tri.facility;
  e.ai_confidence = tri.confidence;
  e.needs_review = tri.needs_review || tri.confidence < C.TRIAGE_REVIEW_CONFIDENCE;
  e.fragility = tri.fragility;
  e.mlc_flag = tri.mlc_flag;
  e.model_versions.triage = tri.model_version;
  e.required_ambulance_type = tri.acuity === "critical" || e.needs_review ? "ALS" : "BLS";
  const res = await ml.resources(tri.acuity, tri.facility, facts, prof?.blood_group ?? null);
  e.predicted_resources = res.items;
  audit("ai", "triage", "emergencies", e.id, "triage_complete", tri, null, tri.model_version);
  if (e.status !== "received") return; // cancelled meanwhile
  setStatus(e, "triaged");
  const triData = { acuity: tri.acuity, facility: tri.facility, confidence: tri.confidence, needs_review: e.needs_review, confirmed: false };
  publish(`emergency:${e.id}`, "emergency.triage", triData);
  publish("ops", "emergency.triage", { ...triData, emergency_id: e.id });
  // 7. MCI
  if (e.patient_count >= C.MCI_PATIENT_THRESHOLD) {
    openEscalation("mass_casualty", e, `${e.patient_count} patients reported at one location (${e.landmark_text ?? "unknown landmark"}).`);
  }
  // 8. dispatch
  setStatus(e, "dispatching");
  void dispatchRound(e.id, 1);
  // 9. follow-up + first aid + initial handover note
  await refreshFollowup(e);
  const aid = await ml.firstAid(tri.facility, tri.acuity, facts, e.language);
  e.first_aid = { protocol_id: aid.protocol_id, title: aid.title, steps: aid.steps, donts: aid.donts };
  publish(`emergency:${e.id}`, "emergency.first_aid", { protocol_id: aid.protocol_id, steps: aid.steps, title: aid.title, donts: aid.donts });
  await refreshHandover(e);
}

export async function refreshFollowup(e: EmergencyRec) {
  if (e.followup_done) return;
  const out = await ml.nextQuestion(facilityOf(e), acuityOf(e), e.extracted, e.followup_answers.map((a) => ({ question_id: a.question_id, answer: a.answer })), e.language);
  e.model_versions.followup = out.model_version;
  if (!out.question || out.done || e.followup_answers.length >= C.FOLLOWUP_MAX_QUESTIONS) {
    e.followup_current = null;
    e.followup_done = true;
    publish(`emergency:${e.id}`, "emergency.followup", { done: true });
    return;
  }
  e.followup_current = out.question;
  if (!out.question.audio_url) out.question.audio_url = await ml.tts(out.question.text, e.language);
  publish(`emergency:${e.id}`, "emergency.followup", { question: out.question.text, question_obj: out.question });
}

export async function answerFollowup(e: EmergencyRec, questionId: string, answer: string) {
  if (!e.followup_current || e.followup_current.id !== questionId) throw conflict("VERSION_CONFLICT", "That question was already answered", { current: { question: e.followup_current } });
  e.followup_answers.push({ question_id: questionId, answer, at: now() });
  const field = ml.questionField(facilityOf(e), questionId);
  const yes = /^(yes|y|haan|ha|hoy|होय|हाँ|हां|true)$/i.test(answer.trim());
  const no = /^(no|n|nahi|nahin|nako|नाही|नहीं|false)$/i.test(answer.trim());
  if (field === "conscious") e.extracted.conscious = yes ? true : no ? false : e.extracted.conscious;
  if (field === "breathing") e.extracted.breathing = answer === "absent" || no ? "absent" : answer;
  audit("user", e.caller_phone ?? "caller", "emergencies", e.id, "followup_answer", { question_id: questionId, answer });
  // breathing absent => CPR always (§4.2 priority override)
  if (e.extracted.breathing === "absent" || e.extracted.conscious === false) {
    const aid = await ml.firstAid(facilityOf(e), acuityOf(e), e.extracted, e.language);
    if (aid.protocol_id !== e.first_aid?.protocol_id) {
      e.first_aid = { protocol_id: aid.protocol_id, title: aid.title, steps: aid.steps, donts: aid.donts };
      publish(`emergency:${e.id}`, "emergency.first_aid", { protocol_id: aid.protocol_id, steps: aid.steps, title: aid.title, donts: aid.donts });
    }
  }
  await refreshFollowup(e);
  await refreshHandover(e);
}

async function refreshHandover(e: EmergencyRec) {
  const prof = e.patient.user_id ? db.profiles.get(e.patient.user_id) : null;
  const answers = e.followup_answers.map((a) => `${ml.questionText(a.question_id)} ${a.answer}.`);
  const note = await ml.handover({
    transcript: e.transcript ?? e.raw_text ?? "", facts: e.extracted, answers,
    profile: prof ? { conditions: prof.conditions, medications: prof.medications, allergies: prof.allergies, blood_group: prof.blood_group } : {},
    acuity: acuityOf(e), facility: facilityOf(e), display: patientDisplay(e),
  });
  e.handover_note = { situation: note.situation, background: note.background, assessment: note.assessment, recommendation: note.recommendation };
  e.model_versions.handover = note.model_version;
}

/* ---------- 11.1 dispatch ---------- */
export async function dispatchRound(emergencyId: string, round: number, opts: { radiusKm?: number; includeBls?: boolean } = {}) {
  const e = db.emergencies.get(emergencyId);
  if (!e || (e.status !== "dispatching" && !isBreakdownRedispatch(e))) return;
  e.dispatch_round = round;
  const radius = opts.radiusKm ?? C.DISPATCH_RADII_KM[Math.min(round, 3) - 1];
  const offered = new Set([...db.offers.values()].filter((o) => o.emergency_id === e.id).map((o) => o.ambulance_id));
  const pickup = e.location!;
  const cands = [...db.ambulances.values()].filter((a) =>
    a.status === "available" && a.kyc_verified && !offered.has(a.id) &&
    now() - a.last_heartbeat_at < 30_000 && distanceM(a.location, pickup) <= radius * 1000 &&
    (e.required_ambulance_type === "BLS" || a.type === "ALS" || opts.includeBls),
  );
  const withEta = await Promise.all(cands.map(async (a) => {
    const r = await getRoute(a.location, pickup);
    return { a, r, eta: Math.round(r.duration_sec / (MOCK.DRIVE_FACTOR * S())) };
  }));
  // dispatch-rank (§9.6): ETA first, then how reliably the crew accepts
  withEta.sort((x, y) => x.eta - y.eta);
  const chosen = withEta.slice(0, C.OFFERS_PER_ROUND);
  const t = now();
  const liveAmong = chosen.some((c) => ambulanceIsLive(c.a.id));
  chosen.forEach((c, i) => {
    const live = ambulanceIsLive(c.a.id);
    const o: OfferRec = {
      id: uid(), emergency_id: e.id, ambulance_id: c.a.id, round, status: "pending", predicted_eta_sec: c.eta, distance_m: Math.round(c.r.distance_m),
      rank: i + 1, offered_at: t, expires_at: t + sec(C.OFFER_EXPIRY_SEC), responded_at: null,
      // simulated crews (§15) take a few seconds; if a real paramedic got this offer too, bots give them a fair head start
      bot_at: live ? null : t + sec(liveAmong ? rand(13, 18) : rand(3, 10)), bot_accept: Math.random() < MOCK.BOT_DRIVER_ACCEPT,
    };
    db.offers.set(o.id, o);
    publish(`ambulance:${c.a.id}`, "offer.new", offerPayload(o));
    notify("push", c.a.registration_no, `New emergency ${Math.round(o.distance_m / 100) / 10} km away`);
  });
  audit("system", "dispatch", "emergencies", e.id, "dispatch_round", { round, radius_km: radius, offers: chosen.map((c) => c.a.registration_no) });
  publish("ops", "dispatch.round", { emergency_id: e.id, round, offers: chosen.length });
  // no candidates: nothing to wait for, widen quickly; otherwise wait the full interval
  e.next_round_at = now() + (chosen.length ? sec(C.DISPATCH_ROUND_INTERVAL_SEC) : sec(3));
}

function isBreakdownRedispatch(e: EmergencyRec) {
  return !e.ambulance_id && ["patient_on_board", "hospital_selecting", "hospital_confirmed"].includes(e.status);
}

export function offerPayload(o: OfferRec) {
  const e = db.emergencies.get(o.emergency_id)!;
  return {
    offer_id: o.id, emergency_id: e.id, expires_at: iso(o.expires_at)!,
    pickup: { lat: e.location!.lat, lng: e.location!.lng, landmark: e.landmark_text, accuracy_m: e.accuracy_m },
    eta_to_pickup_sec: o.predicted_eta_sec, distance_m: o.distance_m,
    summary: { acuity: acuityOf(e), facility: facilityOf(e), age: e.patient.est_age ?? e.extracted.age ?? null, sex: e.patient.sex ?? e.extracted.sex ?? null, patient_count: e.patient_count },
    // flat fields from ws-events.schema.json offer.new
    acuity: acuityOf(e), pickup_lat: e.location!.lat, pickup_lng: e.location!.lng, eta_sec: o.predicted_eta_sec,
  };
}

/** Accept transaction (§11.1). */
export async function acceptOffer(offerId: string, ambulanceId: string, actor: string) {
  const o = db.offers.get(offerId);
  if (!o || o.ambulance_id !== ambulanceId) throw new ApiError(404, "NOT_FOUND", "Offer not found");
  if (o.status !== "pending") throw conflict("ALREADY_TAKEN", "Offer no longer available");
  if (now() > o.expires_at) throw conflict("OFFER_EXPIRED", "This offer has expired");
  const e = db.emergencies.get(o.emergency_id)!;
  if (e.ambulance_id || (e.status !== "dispatching" && !isBreakdownRedispatch(e))) throw conflict("ALREADY_TAKEN", "Emergency already assigned");
  const a = db.ambulances.get(ambulanceId)!;
  if (a.status !== "available") throw conflict("ALREADY_TAKEN", "Ambulance no longer available");
  // commit
  const breakdown = isBreakdownRedispatch(e);
  e.ambulance_id = a.id;
  if (!breakdown) setStatus(e, "ambulance_assigned", actor);
  else { e.version++; audit("user", actor, "emergencies", e.id, "breakdown_replacement_assigned", { ambulance: a.registration_no }); }
  setAmbulance(a, "dispatched", actor);
  a.active_emergency_id = e.id;
  o.status = "accepted";
  o.responded_at = now();
  for (const x of db.offers.values()) {
    if (x.id === o.id || x.status !== "pending") continue;
    if (x.emergency_id === e.id) {
      x.status = "superseded";
      publish(`ambulance:${x.ambulance_id}`, "offer.revoked", { offer_id: x.id, reason: "taken" });
    } else if (x.ambulance_id === a.id) {
      x.status = "superseded";
      publish(`ambulance:${a.id}`, "offer.revoked", { offer_id: x.id, reason: "cancelled" });
    }
  }
  e.next_round_at = null;
  audit("user", actor, "emergencies", e.id, "offer_accepted", { ambulance_id: a.id, registration_no: a.registration_no });
  // resolve an open no_ambulance escalation: an ambulance was found after all
  for (const esc of db.escalations.values()) {
    if (esc.emergency_id === e.id && esc.type === "no_ambulance" && (esc.status === "open" || esc.status === "claimed")) {
      esc.status = "resolved";
      esc.resolved_at = now();
      esc.chosen_option_id = null;
      publish("ops", "escalation.resolved", { escalation_id: esc.id, status: esc.status, note: "An ambulance accepted" });
    }
  }
  await startLeg(a, "to_patient", e.location!);
  if (e.caller_phone) notify("sms", e.caller_phone, `GoldenHour: Ambulance ${a.registration_no} is on the way. Arriving in about ${Math.max(1, Math.round((etaFor(a)?.eta ?? 300) / 60))} min.`);
  return { emergency_id: e.id, ambulance_id: a.id };
}

export function declineOffer(offerId: string, ambulanceId: string, reason: string | null, actor: string) {
  const o = db.offers.get(offerId);
  if (!o || o.ambulance_id !== ambulanceId) throw new ApiError(404, "NOT_FOUND", "Offer not found");
  if (o.status !== "pending") throw conflict("ALREADY_TAKEN", "Offer no longer available");
  o.status = "declined";
  o.responded_at = now();
  audit("user", actor, "dispatch_offers", o.id, "declined", { reason });
  publish(`ambulance:${ambulanceId}`, "offer.revoked", { offer_id: o.id, reason: "cancelled" });
  const e = db.emergencies.get(o.emergency_id);
  // everyone in this round said no: go to the next round now instead of waiting
  if (e && e.status === "dispatching" && ![...db.offers.values()].some((x) => x.emergency_id === e.id && x.status === "pending")) {
    e.next_round_at = now() + sec(2);
  }
}

async function startLeg(a: AmbulanceRec, leg: "to_patient" | "to_hospital", to: { lat: number; lng: number }) {
  a.route = await getRoute(a.location, to);
  a.route_m = 0;
  a.leg = leg;
  a.idle_since = null;
}

/* ---------- lifecycle (§11.9) ---------- */
export function arrivedScene(e: EmergencyRec, actor = "geofence") {
  const a = e.ambulance_id ? db.ambulances.get(e.ambulance_id) : null;
  if (!a) throw conflict("INVALID_TRANSITION", "No ambulance assigned");
  if (isBreakdownRedispatch(e)) {
    // replacement ambulance reached the broken-down one: patient transfers, go on to hospital
    a.route = null;
    a.leg = null;
    setAmbulance(a, "at_scene", actor);
    setAmbulance(a, "transporting", actor);
    if (e.hospital_id) void startLeg(a, "to_hospital", db.hospitals.get(e.hospital_id)!.location);
    audit("system", actor, "emergencies", e.id, "breakdown_transfer_done", { ambulance: a.registration_no });
    return;
  }
  if (e.status !== "ambulance_assigned") throw conflict("INVALID_TRANSITION", `Cannot mark arrived from ${e.status}`, { current: patientView(e) });
  a.route = null;
  a.leg = null;
  a.speed_kmh = 0;
  setStatus(e, "at_scene", actor);
  setAmbulance(a, "at_scene", actor);
  // simulated crew confirms after a short assessment; a real paramedic does it in the app
  e.bot_confirm_at = ambulanceIsLive(a.id) ? null : now() + sec(rand(6, 10));
}

/** Paramedic triage confirmation (§7.4) -> patient on board -> hospital selection (§11.2). */
export async function confirmTriage(e: EmergencyRec, input: { acuity: Acuity; facility: Facility; patient_count: number; version: number }, actor: string) {
  if (!ENUMS.Acuity.includes(input.acuity) || !ENUMS.Facility.includes(input.facility)) throw badRequest("acuity and facility must be valid enum values");
  if (input.version !== e.version) throw conflict("VERSION_CONFLICT", "The emergency was updated. Check the latest details.", { current: patientView(e) });
  if (e.status !== "at_scene") throw conflict("INVALID_TRANSITION", `Cannot confirm triage in ${e.status}`, { current: patientView(e) });
  const changed = input.acuity !== e.ai_acuity || input.facility !== e.ai_facility;
  e.final_acuity = input.acuity;
  e.final_facility = input.facility;
  e.patient_count = Math.max(1, input.patient_count || 1);
  // learning loop row (§5.4 triage_confirmations)
  audit("user", actor, "triage_confirmations", e.id, "confirm", { ai_acuity: e.ai_acuity, ai_facility: e.ai_facility, ai_confidence: e.ai_confidence, final_acuity: input.acuity, final_facility: input.facility, changed, model_version: e.model_versions.triage });
  const tri = { acuity: input.acuity, facility: input.facility, confidence: e.ai_confidence ?? 0, needs_review: false, confirmed: true };
  setStatus(e, "patient_on_board", actor);
  publish(`emergency:${e.id}`, "emergency.triage", tri);
  publish("ops", "emergency.triage", { ...tri, emergency_id: e.id });
  const a = db.ambulances.get(e.ambulance_id!)!;
  setAmbulance(a, "transporting", actor);
  if (e.patient_count >= C.MCI_PATIENT_THRESHOLD) openEscalation("mass_casualty", e, `${e.patient_count} patients confirmed by the paramedic at ${e.landmark_text ?? "the scene"}.`);
  if (changed) {
    const res = await ml.resources(input.acuity, input.facility, e.extracted, null);
    e.predicted_resources = res.items;
  }
  await refreshHandover(e);
  await selectHospitals(e, { reason: "triage_confirmed" });
}

/* ---------- 11.2 hospital selection ---------- */
function freeRooms(hospitalId: string, facility: Facility) {
  return [...db.rooms.values()].filter((r) => r.hospital_id === hospitalId && r.status === "free" && ACCEPTABLE_ROOMS[facility].includes(r.type)).sort((x, y) => x.priority_order - y.priority_order);
}

function rejectionRate24h(hospitalId: string) {
  const since = now() - 86_400_000;
  const mine = [...db.requests.values()].filter((r) => r.hospital_id === hospitalId && r.sent_at > since && r.status !== "pending");
  const hist = db.history.filter((h) => h.hospital_id === hospitalId && h.at > since);
  const total = mine.length + hist.length;
  if (!total) return 0;
  const rej = mine.filter((r) => r.status === "rejected" || r.status === "timeout").length + hist.filter((h) => h.outcome !== "accepted").length;
  return rej / total;
}

export async function rankHospitals(e: EmergencyRec, radiusKm: number = C.HOSPITAL_SEARCH_KM) {
  const a = e.ambulance_id ? db.ambulances.get(e.ambulance_id)! : null;
  const from = a?.location ?? e.location!;
  const f = facilityOf(e);
  const need = REQUIRED_CAPABILITY[f];
  const out: EmergencyRec["rank_list"] = [];
  for (const h of db.hospitals.values()) {
    if (distanceM(from, h.location) > radiusKm * 1000) continue;
    if (!h.capabilities.includes(need)) continue; // hard constraint (§9.13)
    const r = await getRoute(from, h.location);
    const eta = Math.round(r.duration_sec / (MOCK.DRIVE_FACTOR * S()));
    const rooms = freeRooms(h.id, f).length;
    const staleMin = (now() - h.last_confirmed_at) / 60_000;
    const spec = specialistOnDutyAt(h.id, FACILITY_SPECIALIST[f], now() + eta * 1000);
    // hospital-rank (§9.13) stand-in: time to definitive care, penalised by missing room, missing specialist, stale data, rejections
    const pAvail = staleMin > C.AGING_MAX_MIN ? 0.55 : staleMin > C.FRESH_MAX_MIN ? 0.8 : 0.95;
    const score = -(r.duration_sec / 60) - (rooms ? 0 : 25) - (spec ? 0 : 12) - (1 - pAvail) * 10 - rejectionRate24h(h.id) * 8;
    out.push({ hospital_id: h.id, score, eta_sec: eta, why: whyYou(e, h.id, eta) });
  }
  out.sort((x, y) => y.score - x.score);
  return out;
}

export async function selectHospitals(e: EmergencyRec, opts: { reason: string; radiusKm?: number; priority?: boolean; forceHospitalId?: string }) {
  e.rank_list = await rankHospitals(e, opts.radiusKm);
  if (opts.forceHospitalId) {
    const forced = e.rank_list.find((x) => x.hospital_id === opts.forceHospitalId);
    e.rank_list = [forced ?? { hospital_id: opts.forceHospitalId, score: 0, eta_sec: 600, why: ["Assigned by the on call team"] }, ...e.rank_list.filter((x) => x.hospital_id !== opts.forceHospitalId)];
  } else if (e.family_choice_hospital_id) {
    const fam = e.rank_list.find((x) => x.hospital_id === e.family_choice_hospital_id);
    if (fam) e.rank_list = [fam, ...e.rank_list.filter((x) => x !== fam)];
  }
  e.tried_hospitals = [];
  audit("ai", "hospital-rank", "emergencies", e.id, "rank_snapshot", { reason: opts.reason, ranked: e.rank_list.map((r) => ({ hospital: db.hospitals.get(r.hospital_id)?.name, score: Math.round(r.score * 10) / 10, eta_sec: r.eta_sec })) });
  await sendNextRequest(e, { priority: opts.priority, forced: !!opts.forceHospitalId });
}

/** Request + soft hold (§11.3): one room + countable resources, all or nothing. */
export async function sendNextRequest(e: EmergencyRec, opts: { priority?: boolean; forced?: boolean } = {}) {
  const f = facilityOf(e);
  const tried = new Set(e.tried_hospitals.map((t) => t.hospital_id));
  for (const cand of e.rank_list) {
    if (tried.has(cand.hospital_id)) continue;
    const h = db.hospitals.get(cand.hospital_id)!;
    const room = freeRooms(h.id, f)[0];
    if (!room) {
      e.tried_hospitals.push({ hospital_id: h.id, outcome: "no free room" });
      continue;
    }
    const need = e.predicted_resources.filter((p) => p.prob >= 0.7 && (ENUMS.ResourceType as readonly string[]).includes(p.item));
    const resRows = need.map((n) => [...db.resources.values()].find((r) => r.hospital_id === h.id && r.type === n.item));
    if (resRows.some((r) => !r || r.available < 1)) {
      e.tried_hospitals.push({ hospital_id: h.id, outcome: "equipment not available" });
      continue; // bundle not fully available: nothing is held (T5)
    }
    const timeout = opts.priority ? C.PRIORITY_REQUEST_TIMEOUT_SEC : acuityOf(e) === "critical" ? C.HOSPITAL_TIMEOUT_CRITICAL_SEC : C.HOSPITAL_TIMEOUT_OTHER_SEC;
    const t = now();
    const reqId = uid();
    const res: ReservationRec = {
      id: uid(), emergency_id: e.id, hospital_id: h.id, hospital_request_id: reqId, status: "held",
      hold_expires_at: t + sec(timeout + C.HOLD_PENDING_EXTRA_SEC), version: 1,
      items: [{ kind: "room", room_id: room.id }, ...resRows.map((r) => ({ kind: "resource" as const, resource_type: r!.type, quantity: 1 }))],
    };
    room.status = "reserved";
    room.reservation_id = res.id;
    room.version++;
    room.status_updated_at = t;
    for (const r of resRows) {
      r!.available -= 1;
      r!.reserved += 1;
      r!.version++;
      publish(`hospital:${h.id}`, "resource.changed", { id: r!.id, version: r!.version, available: r!.available, reserved: r!.reserved });
    }
    db.reservations.set(res.id, res);
    e.reservation_id = res.id;
    e.hospital_id = h.id;
    const live = hospitalIsLive(h.id);
    const decision: HospitalRequestRec["bot_decision"] = scenarioHooks.hospitalDecision?.(h.id) ?? (opts.priority || opts.forced ? "accept" : Math.random() < MOCK.BOT_HOSPITAL_ACCEPT ? "accept" : "reject");
    const req: HospitalRequestRec = {
      id: reqId, emergency_id: e.id, hospital_id: h.id, rank: e.rank_list.indexOf(cand) + 1, score: cand.score, explanation: cand.why,
      status: "pending", reason_code: null, reason_note: null, is_family_choice: e.family_choice_hospital_id === h.id, is_priority: !!opts.priority,
      sent_at: t, expires_at: t + sec(timeout), responded_at: null, responded_by: null,
      bot_at: live ? null : t + sec(rand(5, 14)), bot_decision: live ? "silent" : decision,
    };
    db.requests.set(req.id, req);
    if (e.status !== "hospital_selecting") setStatus(e, "hospital_selecting");
    else { e.version++; }
    publish(`hospital:${h.id}`, "room.changed", { id: room.id, status: room.status, version: room.version, code: room.code });
    publish(`hospital:${h.id}`, "hospital.request.new", hospitalCard(req) as unknown as Record<string, unknown>);
    publish(`emergency:${e.id}`, "reservation.changed", { reservation_id: res.id, status: res.status });
    publish("ops", "reservation.changed", { reservation_id: res.id, status: res.status, emergency_id: e.id });
    notify("push", h.name, `New incoming patient request, respond within ${timeout} s`);
    audit("system", "selection", "hospital_requests", req.id, "sent", { hospital: h.name, rank: req.rank, room: room.code, priority: req.is_priority });
    // drive toward the hospital being asked; reroute if it says no
    const a = e.ambulance_id ? db.ambulances.get(e.ambulance_id) : null;
    if (a && a.status === "transporting") await startLeg(a, "to_hospital", h.location);
    return req;
  }
  // list exhausted (§11.2 step 4)
  e.hospital_id = null;
  e.reservation_id = null;
  if (![...db.escalations.values()].some((x) => x.emergency_id === e.id && x.type === "no_hospital" && (x.status === "open" || x.status === "claimed"))) {
    openEscalation("no_hospital", e, `${acuityOf(e)} ${facilityOf(e)} patient in ${db.ambulances.get(e.ambulance_id ?? "")?.registration_no ?? "ambulance"}. ${e.tried_hospitals.map((t) => `${db.hospitals.get(t.hospital_id)?.name}: ${t.outcome}`).join(", ") || "No capable hospital in range"}.`);
  }
  return null;
}

export function releaseReservation(resId: string | null, status: "released" | "expired" | "overridden", why: string) {
  if (!resId) return;
  const res = db.reservations.get(resId);
  if (!res || (res.status !== "held" && res.status !== "confirmed")) return;
  res.status = status;
  res.version++;
  for (const it of res.items) {
    if (it.kind === "room") {
      const room = db.rooms.get(it.room_id);
      if (room && room.reservation_id === res.id) {
        room.status = "free";
        room.reservation_id = null;
        room.version++;
        room.status_updated_at = now();
        publish(`hospital:${res.hospital_id}`, "room.changed", { id: room.id, status: room.status, version: room.version, code: room.code });
      }
    } else if (it.kind === "resource") {
      const r = [...db.resources.values()].find((x) => x.hospital_id === res.hospital_id && x.type === it.resource_type);
      if (r) {
        r.available += it.quantity;
        r.reserved = Math.max(0, r.reserved - it.quantity);
        r.version++;
        publish(`hospital:${res.hospital_id}`, "resource.changed", { id: r.id, version: r.version, available: r.available, reserved: r.reserved });
      }
    }
  }
  audit("system", "reservations", "reservations", res.id, status, { why });
  publish(`hospital:${res.hospital_id}`, "reservation.changed", { reservation_id: res.id, status: res.status });
  publish(`emergency:${res.emergency_id}`, "reservation.changed", { reservation_id: res.id, status: res.status });
  publish("ops", "reservation.changed", { reservation_id: res.id, status: res.status, emergency_id: res.emergency_id });
}

function receivingTeam(hospitalId: string, e: EmergencyRec, staffIds?: string[]) {
  const team = staffIds?.length ? staffIds.map((id) => db.staff.get(id)).filter(Boolean) : suggestStaff(e, hospitalId);
  const lead = team[0];
  const f = facilityOf(e);
  const unit = { cardiac: "cardiology", stroke: "stroke", trauma: "trauma", burns: "burns", respiratory: "emergency", obstetric: "obstetrics", pediatric: "children's", poisoning: "emergency", general: "emergency" }[f];
  return { label: lead ? `${lead.name}'s ${unit} team` : `Duty ${unit} team`, staff: team as NonNullable<(typeof team)[number]>[] };
}

/** Hospital accepts (§11.3 accept + §11.6 allocation). */
export async function acceptRequest(requestId: string, hospitalId: string, roomId: string | null, staffIds: string[] | null, actor: string) {
  const req = db.requests.get(requestId);
  if (!req || req.hospital_id !== hospitalId) throw new ApiError(404, "NOT_FOUND", "Request not found");
  if (req.status !== "pending") throw conflict("INVALID_TRANSITION", req.status === "timeout" ? "This request timed out and went to the next hospital" : `This request is already ${req.status}`);
  const e = db.emergencies.get(req.emergency_id)!;
  let res = [...db.reservations.values()].find((r) => r.hospital_request_id === req.id);
  if (!res || res.status !== "held") {
    // hold expired in a race with the sweeper: try to re-reserve here
    const room = freeRooms(hospitalId, facilityOf(e))[0];
    if (!room) throw conflict("RESOURCE_UNAVAILABLE", "No free room is left for this patient");
    res = { id: uid(), emergency_id: e.id, hospital_id: hospitalId, hospital_request_id: req.id, status: "held", hold_expires_at: now(), version: 1, items: [{ kind: "room", room_id: room.id }] };
    room.status = "reserved";
    room.reservation_id = res.id;
    room.version++;
    db.reservations.set(res.id, res);
  }
  // staff picked another free room: swap in one step
  if (roomId) {
    const cur = res.items.find((i) => i.kind === "room") as { kind: "room"; room_id: string };
    if (roomId !== cur.room_id) {
      const next = db.rooms.get(roomId);
      if (!next || next.hospital_id !== hospitalId || next.status !== "free") throw conflict("ROOM_RESERVED", "That room is not free any more");
      const old = db.rooms.get(cur.room_id)!;
      old.status = "free";
      old.reservation_id = null;
      old.version++;
      next.status = "reserved";
      next.reservation_id = res.id;
      next.version++;
      cur.room_id = next.id;
      publish(`hospital:${hospitalId}`, "room.changed", { id: old.id, status: old.status, version: old.version, code: old.code });
    }
  }
  const a = db.ambulances.get(e.ambulance_id!)!;
  const eta = etaFor(a)?.eta ?? 600;
  req.status = "accepted";
  req.responded_at = now();
  req.responded_by = actor;
  res.status = "confirmed";
  res.version++;
  res.hold_expires_at = now() + Math.max(C.HOLD_CONFIRMED_MIN_SEC, 1.5 * eta) * 1000;
  const team = receivingTeam(hospitalId, e, staffIds ?? undefined);
  for (const s of team.staff) res.items.push({ kind: "staff", staff_id: s.id });
  const h = db.hospitals.get(hospitalId)!;
  const room = db.rooms.get((res.items.find((i) => i.kind === "room") as { room_id: string }).room_id)!;
  e.hospital_id = hospitalId;
  e.reservation_id = res.id;
  e.handoff_info = { room_location_note: `${room.location_note} (${room.code})`, receiving_team: team.label, entrance_note: h.er_entrance_note };
  setStatus(e, "hospital_confirmed", actor);
  audit("user", actor, "hospital_requests", req.id, "accepted", { room: room.code, staff: team.staff.map((s) => s.name) });
  const hv = { id: h.id, name: h.name, address: h.address, location: h.location, er_entrance_note: h.er_entrance_note };
  const cand = e.rank_list.find((r) => r.hospital_id === h.id);
  const sel = { hospital: hv, rank_explanation: { why: cand?.why ?? [], score: cand?.score ?? null }, eta };
  publish(`emergency:${e.id}`, "hospital.selected", sel);
  publish(trackChannel(e), "hospital.selected", sel);
  publish("ops", "hospital.selected", { ...sel, emergency_id: e.id });
  publish(`emergency:${e.id}`, "handoff.ready", e.handoff_info);
  publish(trackChannel(e), "handoff.ready", e.handoff_info);
  publish(`emergency:${e.id}`, "reservation.changed", { reservation_id: res.id, status: res.status });
  publish(`hospital:${hospitalId}`, "reservation.changed", { reservation_id: res.id, status: res.status });
  publish(`hospital:${hospitalId}`, "hospital.request.revoked", { request_id: req.id, reason: "accepted" });
  publish(`ambulance:${a.id}`, "handoff.ready", { ...e.handoff_info, hospital: h.name, room: room.code });
  if (a.leg !== "to_hospital" || distanceM(a.route?.coords.length ? { lat: a.route.coords.at(-1)![0], lng: a.route.coords.at(-1)![1] } : a.location, h.location) > 200) {
    if (a.status === "transporting") await startLeg(a, "to_hospital", h.location);
  }
  for (const c of db.contacts.values()) if (c.user_id === e.caller_user_id) notify("sms", c.phone, `GoldenHour: going to ${h.name}, ${h.er_entrance_note}.`);
  return { status: "accepted", reservation: { id: res.id, status: res.status, room_id: room.id, room_code: room.code, staff_ids: team.staff.map((s) => s.id), hold_expires_at: iso(res.hold_expires_at) } };
}

export async function rejectRequest(requestId: string, hospitalId: string, reason: RejectReason, note: string | null, actor: string) {
  const req = db.requests.get(requestId);
  if (!req || req.hospital_id !== hospitalId) throw new ApiError(404, "NOT_FOUND", "Request not found");
  if (!ENUMS.RejectReason.includes(reason)) throw badRequest("reason_code is required", { allowed: ENUMS.RejectReason });
  if (req.status !== "pending") throw conflict("INVALID_TRANSITION", `This request is already ${req.status}`);
  req.status = "rejected";
  req.reason_code = reason;
  req.reason_note = note;
  req.responded_at = now();
  req.responded_by = actor;
  const res = [...db.reservations.values()].find((r) => r.hospital_request_id === req.id);
  releaseReservation(res?.id ?? null, "released", `rejected ${reason}`);
  audit("user", actor, "hospital_requests", req.id, "rejected", { reason, note });
  publish(`hospital:${hospitalId}`, "hospital.request.revoked", { request_id: req.id, reason: "rejected" });
  await moveOn(req, `said no (${reason.replace(/_/g, " ").toLowerCase()})`);
}

async function moveOn(req: HospitalRequestRec, outcome: string) {
  const e = db.emergencies.get(req.emergency_id)!;
  const h = db.hospitals.get(req.hospital_id)!;
  e.tried_hospitals.push({ hospital_id: h.id, outcome });
  if (e.family_choice_hospital_id === h.id) {
    // family's choice declined: back to AI ranking, tell the family (§11.8)
    e.family_choice_hospital_id = null;
    for (const c of db.contacts.values()) if (c.user_id === e.caller_user_id) notify("sms", c.phone, `GoldenHour: ${h.name} could not take the patient. Going to the next best hospital.`);
  }
  e.hospital_id = null;
  e.reservation_id = null;
  const next = await sendNextRequest(e);
  if (next) {
    const nh = db.hospitals.get(next.hospital_id)!;
    const rr = { from_hospital: h.name, to_hospital: nh.name, reason: outcome };
    if (e.status === "hospital_selecting") {
      publish(`ambulance:${e.ambulance_id}`, "reroute", rr);
    }
  }
}

export async function timeoutRequest(req: HospitalRequestRec) {
  if (req.status !== "pending") return;
  req.status = "timeout";
  req.responded_at = now();
  const res = [...db.reservations.values()].find((r) => r.hospital_request_id === req.id);
  releaseReservation(res?.id ?? null, "released", "hospital timeout");
  const h = db.hospitals.get(req.hospital_id)!;
  notify("sms", h.duty_manager_phone, `GoldenHour: ${h.name} did not answer an incoming emergency request in time. It went to the next hospital.`);
  audit("system", "sweeper", "hospital_requests", req.id, "timeout", {});
  publish(`hospital:${h.id}`, "hospital.request.revoked", { request_id: req.id, reason: "timeout" });
  await moveOn(req, "did not answer in time");
}

/* ---------- arrival, handoff (§11.9) ---------- */
export function arrivedHospital(e: EmergencyRec, actor = "geofence") {
  if (e.status !== "hospital_confirmed") throw conflict("INVALID_TRANSITION", `Cannot mark arrived at hospital from ${e.status}`, { current: patientView(e) });
  const a = db.ambulances.get(e.ambulance_id!)!;
  a.route = null;
  a.leg = null;
  a.speed_kmh = 0;
  setStatus(e, "arrived_hospital", actor);
  setAmbulance(a, "at_hospital", actor);
  const res = e.reservation_id ? db.reservations.get(e.reservation_id) : null;
  const roomItem = res?.items.find((i) => i.kind === "room") as { room_id: string } | undefined;
  db.handoffs.set(e.id, {
    emergency_id: e.id, hospital_id: e.hospital_id!, room_id: roomItem?.room_id ?? null, receiving_staff_ids: [], arrived_at: now(), offloaded_at: null, delay_alerted: false,
    bot_receive_at: hospitalIsLive(e.hospital_id!) ? null : now() + sec(rand(12, 25)),
  });
  publish(`hospital:${e.hospital_id}`, "handoff.arrived", { emergency_id: e.id, registration_no: a.registration_no });
}

export function patientReceived(e: EmergencyRec, hospitalId: string, staffIds: string[], actor: string) {
  if (e.hospital_id !== hospitalId) throw new ApiError(403, "FORBIDDEN", "Not your patient");
  if (e.status !== "arrived_hospital") throw conflict("INVALID_TRANSITION", e.status === "hospital_confirmed" ? "The ambulance has not reached the door yet" : `Already ${e.status.replace(/_/g, " ")}`);
  const ho = db.handoffs.get(e.id)!;
  ho.offloaded_at = now();
  ho.receiving_staff_ids = staffIds;
  const res = e.reservation_id ? db.reservations.get(e.reservation_id) : null;
  if (res) {
    res.status = "consumed";
    res.version++;
    for (const it of res.items) {
      if (it.kind === "room") {
        const room = db.rooms.get(it.room_id)!;
        room.status = "occupied";
        room.reservation_id = null;
        room.occupant = patientDisplay(e);
        room.version++;
        publish(`hospital:${hospitalId}`, "room.changed", { id: room.id, status: room.status, version: room.version, code: room.code });
      } else if (it.kind === "resource") {
        const r = [...db.resources.values()].find((x) => x.hospital_id === hospitalId && x.type === it.resource_type);
        if (r) {
          r.reserved = Math.max(0, r.reserved - it.quantity);
          r.total = Math.max(r.total, r.available + r.reserved);
          r.version++;
        }
      }
    }
    publish(`hospital:${hospitalId}`, "reservation.changed", { reservation_id: res.id, status: res.status });
  }
  setStatus(e, "handed_off", actor);
  const a = db.ambulances.get(e.ambulance_id!)!;
  setAmbulance(a, "cleaning", actor);
  a.active_emergency_id = null;
  audit("user", actor, "handoffs", e.id, "received", { offload_delay_sec: Math.round((ho.offloaded_at - (ho.arrived_at ?? ho.offloaded_at)) / 1000) });
  closeLater.set(e.id, now() + 8000);
}
export const closeLater = new Map<string, number>();

/* ---------- side exits ---------- */
function releaseAmbulance(e: EmergencyRec, actor: string) {
  if (!e.ambulance_id) return;
  const a = db.ambulances.get(e.ambulance_id)!;
  a.route = null;
  a.leg = null;
  a.active_emergency_id = null;
  if (a.status !== "available" && a.status !== "out_of_service") setAmbulance(a, "available", actor);
  publish(`ambulance:${a.id}`, "job.ended", { emergency_id: e.id, status: e.status });
}

function supersedeOffers(e: EmergencyRec) {
  for (const o of db.offers.values()) {
    if (o.emergency_id === e.id && o.status === "pending") {
      o.status = "superseded";
      publish(`ambulance:${o.ambulance_id}`, "offer.revoked", { offer_id: o.id, reason: "cancelled" });
    }
  }
}

function cancelRequests(e: EmergencyRec) {
  for (const r of db.requests.values()) {
    if (r.emergency_id === e.id && r.status === "pending") {
      r.status = "cancelled";
      publish(`hospital:${r.hospital_id}`, "hospital.request.revoked", { request_id: r.id, reason: "cancelled" });
    }
  }
}

export function cancelEmergency(e: EmergencyRec, reason: string, actor: string) {
  if (!EM_FSM[e.status].includes("cancelled")) throw conflict("INVALID_TRANSITION", "The ambulance crew already has the patient. Talk to the crew to cancel.", { current: patientView(e) });
  supersedeOffers(e);
  cancelRequests(e);
  releaseReservation(e.reservation_id, "released", "cancelled");
  setStatus(e, "cancelled", actor, reason);
  releaseAmbulance(e, actor);
}

export function refusedTransport(e: EmergencyRec, note: string | null, actor: string) {
  if (!EM_FSM[e.status].includes("refused_transport")) throw conflict("INVALID_TRANSITION", `Cannot record refusal in ${e.status}`);
  cancelRequests(e);
  releaseReservation(e.reservation_id, "released", "refused transport");
  setStatus(e, "refused_transport", actor, note ?? undefined);
  releaseAmbulance(e, actor);
}

/** §11.11 vehicle breakdown. */
export async function vehicleIssue(ambulanceId: string, note: string | null, actor: string) {
  const a = db.ambulances.get(ambulanceId)!;
  const e = a.active_emergency_id ? db.emergencies.get(a.active_emergency_id) : null;
  a.route = null;
  a.leg = null;
  a.speed_kmh = 0;
  setAmbulance(a, "out_of_service", actor);
  a.active_emergency_id = null;
  audit("user", actor, "ambulances", a.id, "vehicle_issue", { note });
  if (!e) return;
  e.ambulance_id = null;
  if (e.status === "ambulance_assigned" || e.status === "at_scene") {
    // patient not on board: back to dispatching, priority
    setStatus(e, "dispatching", actor, "vehicle issue");
    for (const o of db.offers.values()) if (o.emergency_id === e.id && o.ambulance_id === a.id) o.status = "superseded";
    void dispatchRound(e.id, 1);
  } else {
    // patient on board: new ambulance to the breakdown point, keep and extend the hospital hold
    e.location = { ...a.location };
    e.landmark_text = `Breakdown point of ${a.registration_no}`;
    const res = e.reservation_id ? db.reservations.get(e.reservation_id) : null;
    if (res) res.hold_expires_at = Math.max(res.hold_expires_at, now() + 30 * 60_000);
    if (e.hospital_id) publish(`hospital:${e.hospital_id}`, "alert", { kind: "breakdown", message: `${a.registration_no} broke down. A replacement ambulance is being sent. Your room stays reserved.` });
    publish(`emergency:${e.id}`, "alert", { kind: "breakdown", message: "The ambulance had a problem. Another ambulance is coming." });
    e.version++;
    void dispatchRound(e.id, 1);
  }
}

/* ---------- 11.8 deterioration + family override ---------- */
export async function markCritical(e: EmergencyRec, actor: string) {
  if (!["patient_on_board", "hospital_selecting", "hospital_confirmed", "at_scene", "ambulance_assigned"].includes(e.status)) throw conflict("INVALID_TRANSITION", `Cannot mark critical in ${e.status}`);
  const was = acuityOf(e);
  e.final_acuity = "critical";
  e.required_ambulance_type = "ALS";
  e.version++;
  audit("user", actor, "emergencies", e.id, "deterioration", { from: was, to: "critical" });
  const tri = { acuity: "critical", facility: facilityOf(e), confidence: e.ai_confidence ?? 0, needs_review: false, confirmed: !!e.final_facility };
  publish(`emergency:${e.id}`, "emergency.triage", tri);
  publish("ops", "emergency.triage", { ...tri, emergency_id: e.id });
  if (e.hospital_id) publish(`hospital:${e.hospital_id}`, "alert", { kind: "deterioration", message: `Patient in ${db.ambulances.get(e.ambulance_id ?? "")?.registration_no} got worse: now CRITICAL.` });
  if (e.status !== "hospital_confirmed") return { diverted: false, reason: "No hospital confirmed yet. The request now says critical." };
  // divert only if the new best is at least 3 minutes faster to definitive care (§11.8)
  const ranked = await rankHospitals(e);
  const cur = ranked.find((r) => r.hospital_id === e.hospital_id);
  const best = ranked[0];
  if (best && cur && best.hospital_id !== cur.hospital_id && cur.eta_sec - best.eta_sec >= C.DETERIORATION_DIVERT_GAIN_SEC) {
    await divertTo(e, best.hospital_id, "Patient got worse; a closer suitable hospital is available", actor);
    return { diverted: true, reason: `Diverted to ${db.hospitals.get(best.hospital_id)?.name}` };
  }
  return { diverted: false, reason: "Current hospital is still the fastest suitable one. It has been told the patient is now critical." };
}

async function divertTo(e: EmergencyRec, hospitalId: string, reason: string, actor: string, family = false) {
  const from = e.hospital_id ? db.hospitals.get(e.hospital_id)?.name ?? "" : "";
  cancelRequests(e);
  releaseReservation(e.reservation_id, "released", "divert");
  if (e.status === "hospital_confirmed") setStatus(e, "hospital_selecting", actor, reason);
  e.hospital_id = null;
  e.reservation_id = null;
  e.handoff_info = null;
  if (family) e.family_choice_hospital_id = hospitalId;
  await selectHospitals(e, { reason, forceHospitalId: hospitalId });
  const to = db.hospitals.get(hospitalId)?.name ?? "";
  e.reroute = { from_hospital: from, to_hospital: to, reason, at: new Date().toISOString() };
  const rr = { from_hospital: from, to_hospital: to, reason };
  publish(`emergency:${e.id}`, "reroute", rr);
  publish(trackChannel(e), "reroute", rr);
  publish(`ambulance:${e.ambulance_id}`, "reroute", rr);
  publish("ops", "reroute", { ...rr, emergency_id: e.id });
}

export async function familyOverrideOptions(e: EmergencyRec) {
  const ranked = await rankHospitals(e);
  const cur = ranked.find((r) => r.hospital_id === e.hospital_id) ?? ranked[0];
  const f = facilityOf(e);
  const a = e.ambulance_id ? db.ambulances.get(e.ambulance_id)! : null;
  const out = [];
  for (const h of db.hospitals.values()) {
    const r = await getRoute(a?.location ?? e.location!, h.location);
    const eta = Math.round(r.duration_sec / (MOCK.DRIVE_FACTOR * S()));
    const notes: string[] = [];
    const capable = h.capabilities.includes(REQUIRED_CAPABILITY[f]);
    if (!capable) notes.push(({ cardiac: "no cath lab", stroke: "no stroke team", trauma: "no trauma centre", burns: "no burns unit", respiratory: "no ICU", obstetric: "no labour ward", pediatric: "no children's ER", poisoning: "no toxicology", general: "no emergency room" } as Record<Facility, string>)[f]);
    if (!freeRooms(h.id, f).length) notes.push("no free room right now");
    if (now() - h.last_confirmed_at > C.AGING_MAX_MIN * 60_000) notes.push("data stale");
    out.push({ hospital_id: h.id, name: h.name, eta_sec: eta, delta_sec: eta - (cur?.eta_sec ?? eta), notes, is_current: h.id === e.hospital_id, capable });
  }
  out.sort((x, y) => Number(y.capable) - Number(x.capable) || x.eta_sec - y.eta_sec);
  return out;
}

export async function familyOverride(e: EmergencyRec, hospitalId: string, consent: boolean, actor: string) {
  if (!consent) throw new ApiError(400, "CONSENT_REQUIRED", "The family must agree to the trade-offs first");
  if (!db.hospitals.has(hospitalId)) throw new ApiError(404, "NOT_FOUND", "Hospital not found");
  if (!["patient_on_board", "hospital_selecting", "hospital_confirmed"].includes(e.status)) throw conflict("INVALID_TRANSITION", `Cannot change hospital in ${e.status}`);
  audit("user", actor, "emergencies", e.id, "family_override", { hospital: db.hospitals.get(hospitalId)?.name, consent });
  await divertTo(e, hospitalId, "Family chose this hospital", actor, true);
  const req = [...db.requests.values()].find((r) => r.emergency_id === e.id && r.status === "pending");
  if (req) req.is_family_choice = true;
}

/* ---------- rooms, walk-in override (§11.7) ---------- */
export async function patchRoom(hospitalId: string, roomId: string, status: string, version: number, overrideReason: string | null, actor: string) {
  const room = db.rooms.get(roomId);
  if (!room || room.hospital_id !== hospitalId) throw new ApiError(404, "NOT_FOUND", "Room not found");
  if (!(ENUMS.RoomStatus as readonly string[]).includes(status)) throw badRequest("invalid room status");
  if (version !== room.version) throw conflict("VERSION_CONFLICT", "Someone else just changed this room", { current: room });
  if (status === "reserved") throw badRequest("Rooms are reserved by the system, not by hand");
  if (room.status === "reserved") {
    if (!overrideReason) throw conflict("ROOM_RESERVED", "This room is held for an incoming ambulance", { current: room });
    if (!(ENUMS.OverrideReason as readonly string[]).includes(overrideReason)) throw badRequest("invalid override_reason");
    return walkInOverride(room, status, overrideReason, actor);
  }
  const before = room.status;
  room.status = status as typeof room.status;
  room.occupant = status === "occupied" ? room.occupant ?? "Walk-in patient" : null;
  room.version++;
  room.status_updated_at = now();
  audit("user", actor, "rooms", room.id, "status", { from: before, to: status });
  publish(`hospital:${hospitalId}`, "room.changed", { id: room.id, status: room.status, version: room.version, code: room.code });
  return room;
}

async function walkInOverride(room: RoomRec, status: string, reason: string, actor: string) {
  const res = db.reservations.get(room.reservation_id!)!;
  const e = db.emergencies.get(res.emergency_id)!;
  room.status = status as typeof room.status;
  room.occupant = "Walk-in patient";
  room.reservation_id = null;
  room.version++;
  room.status_updated_at = now();
  res.items = res.items.filter((i) => !(i.kind === "room" && i.room_id === room.id));
  audit("user", actor, "reservations", res.id, "overridden", { room: room.code, reason }, reason);
  publish(`hospital:${room.hospital_id}`, "room.changed", { id: room.id, status: room.status, version: room.version, code: room.code });
  // same hospital first
  const other = freeRooms(room.hospital_id, facilityOf(e))[0];
  if (other) {
    other.status = "reserved";
    other.reservation_id = res.id;
    other.version++;
    res.items.push({ kind: "room", room_id: other.id });
    res.version++;
    if (e.handoff_info) e.handoff_info.room_location_note = `${other.location_note} (${other.code})`;
    publish(`hospital:${room.hospital_id}`, "room.changed", { id: other.id, status: other.status, version: other.version, code: other.code });
    publish(`emergency:${e.id}`, "reservation.changed", { reservation_id: res.id, status: res.status });
    if (e.handoff_info) publish(`emergency:${e.id}`, "handoff.ready", e.handoff_info);
    publish(`ambulance:${e.ambulance_id}`, "alert", { kind: "room_changed", message: `Room changed to ${other.code}` });
    return { room, reallocated_to: other.code };
  }
  // nothing free here: priority reroute
  releaseReservation(res.id, "overridden", "walk-in took the last room");
  const from = db.hospitals.get(room.hospital_id)!.name;
  if (e.status === "hospital_confirmed") setStatus(e, "hospital_selecting", actor, "walk-in override");
  e.hospital_id = null;
  e.reservation_id = null;
  e.handoff_info = null;
  e.tried_hospitals.push({ hospital_id: room.hospital_id, outcome: "room taken by a walk-in" });
  await sendNextRequest(e, { priority: true });
  const to = e.hospital_id ? db.hospitals.get(e.hospital_id)!.name : "the next hospital";
  e.reroute = { from_hospital: from, to_hospital: to, reason: "The reserved room was needed for a walk-in patient", at: new Date().toISOString() };
  const rr = { from_hospital: from, to_hospital: to, reason: e.reroute.reason };
  publish(`emergency:${e.id}`, "reroute", rr);
  publish(trackChannel(e), "reroute", rr);
  publish(`ambulance:${e.ambulance_id}`, "reroute", rr);
  return { room, reallocated_to: null, rerouted_to: to };
}

/* ---------- 13 escalations ---------- */
function nearestStabilising(e: EmergencyRec) {
  const from = e.ambulance_id ? db.ambulances.get(e.ambulance_id)!.location : e.location!;
  return [...db.hospitals.values()].filter((h) => h.stabilization_capable && h.capabilities.includes("general_er")).sort((x, y) => distanceM(from, x.location) - distanceM(from, y.location))[0];
}

export function openEscalation(type: EscalationRec["type"], e: EmergencyRec | null, summary: string) {
  const t = now();
  let options: EscalationOptionRec[] = [];
  if (type === "no_hospital" && e) {
    const stab = nearestStabilising(e);
    const partial = [...db.hospitals.values()].filter((h) => freeRooms(h.id, "general").length).sort((x, y) => distanceM(e.location!, x.location) - distanceM(e.location!, y.location))[0];
    const greenfield = [...db.hospitals.values()][0];
    options = [
      { id: "stabilise", label: `Stabilise at ${stab?.name ?? "nearest hospital"}, transfer later`, action: "stabilise", params: { hospital_id: stab?.id }, is_default: true },
      { id: "partial", label: `Best partial match: ${partial?.name ?? "none"}`, action: "force_hospital", params: { hospital_id: partial?.id }, is_default: false },
      { id: "force", label: `Force ${greenfield.name}`, action: "force_hospital", params: { hospital_id: greenfield.id }, is_default: false },
      { id: "widen", label: "Search up to 40 km", action: "widen_hospital", params: { radius_km: 40 }, is_default: false },
    ];
  } else if (type === "no_ambulance") {
    options = [
      { id: "widen", label: "Search up to 40 km, include BLS with ALS follow-up", action: "widen_ambulance", params: { radius_km: 40 }, is_default: true },
      { id: "force", label: "Force-assign the nearest free ambulance", action: "force_ambulance", params: {}, is_default: false },
      { id: "notify108", label: "Tell the caller to call 108", action: "notify_108", params: {}, is_default: false },
    ];
  } else if (type === "mass_casualty") {
    options = [
      { id: "plan", label: "Use the allocation plan (spread patients across hospitals)", action: "mci_plan", params: {}, is_default: true },
      { id: "widen", label: "Widen ambulance search to 40 km", action: "widen_ambulance", params: { radius_km: 40 }, is_default: false },
      { id: "manual", label: "I'll plan it manually on this page", action: "manual", params: {}, is_default: false },
    ];
  } else {
    options = [
      { id: "safe", label: "Take the safe action (re-reserve and notify)", action: "safe", params: {}, is_default: true },
      { id: "prompt108", label: "Show callers the 108 prompt", action: "notify_108", params: {}, is_default: false },
    ];
  }
  const esc: EscalationRec = {
    id: uid(), type, emergency_id: e?.id ?? null, status: "open", summary, options, default_option_id: options.find((o) => o.is_default)!.id,
    chosen_option_id: null, claimed_by: null, claimed_at: null, created_at: t, repeat_at: t + sec(C.ESCALATION_REPEAT_SEC),
    default_at: t + sec(C.ESCALATION_DEFAULT_SEC), resolved_at: null, version: 1, repeats: 0,
  };
  db.escalations.set(esc.id, esc);
  if (e) e.version++;
  audit("system", "escalation", "escalations", esc.id, "open", { type, summary });
  publish("ops", "escalation.open", { escalation_id: esc.id, type, status: esc.status, summary });
  if (e) publish(`emergency:${e.id}`, "escalation.open", { escalation_id: esc.id, type, status: esc.status });
  const link = `${MOCK.WEB_ORIGIN}/ops/${issueOpsLink(esc.id)}`;
  notify("telegram", "team group", `ESCALATION ${type.toUpperCase()}: ${summary} Options: ${options.map((o) => (o.is_default ? "*" : "") + o.label).join(" | ")}. Open live map: ${link}`);
  return esc;
}

export function claimEscalation(id: string, userId: string, name: string) {
  const esc = db.escalations.get(id);
  if (!esc) throw new ApiError(404, "NOT_FOUND", "Escalation not found");
  if (esc.status !== "open") throw conflict("ALREADY_TAKEN", esc.claimed_by ? `Already claimed by ${db.users.get(esc.claimed_by)?.name ?? "someone"}` : `Escalation is ${esc.status}`);
  esc.status = "claimed";
  esc.claimed_by = userId;
  esc.claimed_at = now();
  esc.default_at = now() + sec(C.ESCALATION_DEFAULT_SEC); // claimed but no choice within 120 s -> auto default
  esc.version++;
  audit("developer", userId, "escalations", esc.id, "claimed", { by: name });
  publish("ops", "escalation.claimed", { escalation_id: esc.id, status: esc.status, claimed_by: name });
  notify("telegram", "team group", `Escalation claimed by ${name}`);
  return esc;
}

export async function resolveEscalation(id: string, optionId: string, userId: string | null, system = false) {
  const esc = db.escalations.get(id);
  if (!esc) throw new ApiError(404, "NOT_FOUND", "Escalation not found");
  if (esc.status === "resolved" || esc.status === "auto_defaulted") throw conflict("ALREADY_TAKEN", `Escalation already ${esc.status.replace("_", " ")}`);
  if (!system) {
    if (esc.status === "open") claimEscalation(id, userId!, db.users.get(userId!)?.name ?? "developer"); // option press without claim implicitly claims (§12.2)
    else if (esc.claimed_by !== userId) throw new ApiError(403, "FORBIDDEN", "Only the person who claimed this can choose");
  }
  const opt = esc.options.find((o) => o.id === optionId);
  if (!opt) throw badRequest("unknown option");
  esc.status = system ? "auto_defaulted" : "resolved";
  esc.chosen_option_id = opt.id;
  esc.resolved_at = now();
  esc.version++;
  audit(system ? "system" : "developer", userId ?? "system", "escalations", esc.id, esc.status, { option: opt.label });
  publish("ops", `escalation.${esc.status}`, { escalation_id: esc.id, status: esc.status, option: opt.label });
  if (system) notify("telegram", "team group", `Auto-executed default: ${opt.label}`);
  await executeOption(esc, opt);
  return esc;
}

async function executeOption(esc: EscalationRec, opt: EscalationOptionRec) {
  const e = esc.emergency_id ? db.emergencies.get(esc.emergency_id) : null;
  if (!e) return;
  switch (opt.action) {
    case "stabilise":
    case "force_hospital":
      if (opt.params.hospital_id) await selectHospitals(e, { reason: `ops: ${opt.label}`, priority: true, forceHospitalId: String(opt.params.hospital_id) });
      break;
    case "widen_hospital":
      await selectHospitals(e, { reason: "ops: widen to 40 km", radiusKm: 40 });
      break;
    case "widen_ambulance":
      if (e.status === "dispatching") await dispatchRound(e.id, 3, { radiusKm: 40, includeBls: true });
      break;
    case "force_ambulance": {
      if (e.status !== "dispatching") break;
      const a = [...db.ambulances.values()].filter((x) => x.status === "available").sort((x, y) => distanceM(x.location, e.location!) - distanceM(y.location, e.location!))[0];
      if (!a) break;
      const o: OfferRec = { id: uid(), emergency_id: e.id, ambulance_id: a.id, round: 99, status: "pending", predicted_eta_sec: 0, distance_m: Math.round(distanceM(a.location, e.location!)), rank: 1, offered_at: now(), expires_at: now() + 60_000, responded_at: null, bot_at: null, bot_accept: true };
      db.offers.set(o.id, o);
      publish(`ambulance:${a.id}`, "alert", { kind: "mandatory_assignment", message: "The on call team assigned you to an emergency. This is mandatory." });
      await acceptOffer(o.id, a.id, "ops-force");
      break;
    }
    case "notify_108":
      e.call_108_prompt = true;
      e.version++;
      publish(`emergency:${e.id}`, "alert", { kind: "call_108", message: "Please call 108 now as well." });
      if (e.caller_phone) notify("sms", e.caller_phone, "GoldenHour: we are still finding an ambulance. Please also call 108 now.");
      break;
    case "mci_plan": {
      const caps = [...db.hospitals.values()].map((h) => ({ h, free: [...db.rooms.values()].filter((r) => r.hospital_id === h.id && r.status === "free").length })).filter((x) => x.free);
      audit("system", "mci-allocate", "escalations", esc.id, "plan", { plan: caps.map((c) => ({ hospital: c.h.name, patients: Math.min(c.free, Math.ceil(e.patient_count / caps.length)) })) });
      break;
    }
    default:
      break;
  }
}

/* ---------- helpers used by the sim ---------- */
export const scenarioHooks: { hospitalDecision?: (hospitalId: string) => HospitalRequestRec["bot_decision"] | undefined; driverAccept?: (ambulanceId: string) => boolean | undefined } = {};

export function extendHold(a: AmbulanceRec) {
  // §11.4: each heartbeat keeps a confirmed hold alive for the remaining trip
  if (!a.active_emergency_id) return;
  const e = db.emergencies.get(a.active_emergency_id);
  const res = e?.reservation_id ? db.reservations.get(e.reservation_id) : null;
  if (res?.status !== "confirmed") return;
  const eta = etaFor(a)?.eta ?? 0;
  res.hold_expires_at = Math.max(res.hold_expires_at, now() + (eta * 1.5 + 120) * 1000);
}

export function pointOnRoute(a: AmbulanceRec) {
  return a.route ? pointAt(a.route, a.route_m) : null;
}

export { signalOf, hashToken };
export type { ResourceType };
