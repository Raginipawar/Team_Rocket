// REST routes of the mock core. Paths and bodies follow technical.md §7; where
// the team's real routers already differ (A's offers under /ambulance, B's response
// wrappers like {"requests": [...]} and {"data": ...}), the mock serves both forms so
// the web app works unchanged against either server.

import { C } from "./config";
import { ApiError, badRequest, conflict, forbidden, notFound, num, route, str, type Req } from "./http";
import {
  currentUser, exchangeOpsLink, hashToken, issue, issueOpsLink, refreshCookie, requestOtp, requireOps, requireRole, revoked, verify, verifyOtp,
} from "./auth";
import {
  acceptOffer, acceptRequest, answerFollowup, arrivedHospital, arrivedScene, audit, cancelEmergency, claimEscalation, confirmTriage,
  createEmergency, declineOffer, familyOverride, familyOverrideOptions, markCritical, offerPayload, patchRoom, patientReceived,
  refusedTransport, rejectRequest, releaseReservation, resolveEscalation, selectHospitals, setAmbulance, vehicleIssue,
} from "./domain";
import { computeAnalytics, seedHistory } from "./analytics";
import { listScenarios, runScenario, runs } from "./scenarios";
import { mlStatus } from "./ml";
import {
  activeJob, acuityOf, etaFor, facilityOf, hospitalCard, incomingFor, patientDisplay, patientView, trackView,
} from "./views";
import { db, iso, now, seed, signalOf, uid, type EmergencyRec } from "./world";
import { MOCK } from "./config";
import { publish } from "./bus";
import type { Freshness, RejectReason } from "../../lib/enums";
import type { HospitalDashboard, Staff } from "../../lib/api-types";

const V = "/api/v1";
const secure = (req: Req) => (req.headers["x-forwarded-proto"] ?? "").toString().includes("https");

function publicUser(u: { id: string; role: string; name: string | null; phone: string; language: string; hospital_id: string | null; ambulance_id: string | null }) {
  return { id: u.id, role: u.role, name: u.name, phone: u.phone, language: u.language, hospital_id: u.hospital_id, ambulance_id: u.ambulance_id };
}

function emergencyOr404(id: string) {
  const e = db.emergencies.get(id);
  if (!e) throw notFound("Emergency not found");
  return e;
}

/* ---------- 7.2 auth ---------- */
route("POST", `${V}/auth/otp/request`, (req) => {
  const phone = normalisePhone(str(req.body, "phone"));
  const code = requestOtp(phone);
  // SMS_MODE=fake: the code is logged, and the mock also returns it in a dev header
  console.log(`[fake sms] -> ${phone}: Your GoldenHour OTP is ${code}. Valid for ${C.OTP_TTL_MIN} minutes.`);
  req.setHeader("x-dev-otp", code);
  return undefined;
}, 204);

route("POST", `${V}/auth/otp/verify`, (req) => {
  const phone = normalisePhone(str(req.body, "phone"));
  verifyOtp(phone, str(req.body, "code"));
  let user = [...db.users.values()].find((u) => u.phone === phone);
  if (!user) {
    const id = uid();
    user = { id, role: "patient", name: null, phone, language: "en", password: null, hospital_id: null, ambulance_id: null };
    db.users.set(id, user);
    db.profiles.set(id, { user_id: id, dob: null, sex: null, blood_group: null, allergies: [], conditions: [], medications: [], insurance_provider: null, insurance_policy_no: null, home_address: null, home_location: null, notes: null, version: 1 });
  }
  audit("user", phone, "users", user.id, "otp_login", { phone });
  const { access, refresh } = issue(user);
  req.setCookie(refreshCookie(refresh, secure(req)));
  return { access_token: access, user: publicUser(user) };
});

route("POST", `${V}/auth/login`, (req) => {
  const id = str(req.body, "username_or_phone").trim();
  const pw = str(req.body, "password");
  const phone = normalisePhone(id);
  const user = [...db.users.values()].find((u) => u.phone === phone || u.phone === id || u.name === id);
  if (!user || !user.password || user.password !== pw) throw new ApiError(401, "UNAUTHENTICATED", "Invalid credentials");
  audit("user", user.id, "users", user.id, "password_login", {});
  const { access, refresh } = issue(user);
  req.setCookie(refreshCookie(refresh, secure(req)));
  return { access_token: access, user: publicUser(user) };
});

route("POST", `${V}/auth/refresh`, (req) => {
  const raw = req.cookies.refresh_token;
  if (!raw) throw new ApiError(401, "UNAUTHENTICATED", "No refresh token");
  const claims = verify(raw, "refresh");
  if (revoked.has(claims.jti)) throw new ApiError(401, "UNAUTHENTICATED", "Refresh token revoked");
  const user = db.users.get(claims.sub);
  if (!user) throw new ApiError(401, "UNAUTHENTICATED", "User not found");
  revoked.add(claims.jti); // rotation
  const { access, refresh } = issue(user);
  req.setCookie(refreshCookie(refresh, secure(req)));
  return { access_token: access, user: publicUser(user) };
});

route("POST", `${V}/auth/logout`, (req) => {
  const raw = req.cookies.refresh_token;
  if (raw) {
    try { revoked.add(verify(raw, "refresh").jti); } catch { /* ignore */ }
  }
  req.setCookie("refresh_token=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict");
  return undefined;
}, 204);

function normalisePhone(p: string) {
  const digits = p.replace(/[^\d+]/g, "");
  if (/^\d{10}$/.test(digits)) return `+91${digits}`;
  if (/^91\d{10}$/.test(digits)) return `+${digits}`;
  return digits;
}

/* ---------- 7.3 patient ---------- */
route("GET", `${V}/me/profile`, (req) => {
  const u = requireRole(req, "patient");
  const p = db.profiles.get(u.id)!;
  return { ...p, name: u.user.name, user_id: undefined };
});

route("PUT", `${V}/me/profile`, (req) => {
  const u = requireRole(req, "patient");
  const p = db.profiles.get(u.id)!;
  const version = num(req.body, "version");
  if (version !== p.version) throw conflict("VERSION_CONFLICT", "Your profile was changed somewhere else", { current: { ...p, name: u.user.name } });
  const b = req.body as Record<string, unknown>;
  const list = (k: string) => (Array.isArray(b[k]) ? (b[k] as unknown[]).map(String).filter(Boolean) : (p as unknown as Record<string, string[]>)[k]);
  Object.assign(p, {
    dob: b.dob ?? p.dob, sex: b.sex ?? p.sex, blood_group: b.blood_group ?? p.blood_group,
    allergies: list("allergies"), conditions: list("conditions"), medications: list("medications"),
    insurance_provider: b.insurance_provider ?? p.insurance_provider, insurance_policy_no: b.insurance_policy_no ?? p.insurance_policy_no,
    home_address: b.home_address ?? p.home_address, notes: b.notes ?? p.notes, version: p.version + 1,
  });
  if (typeof b.name === "string") u.user.name = b.name.trim() || u.user.name;
  if (typeof b.language === "string") u.user.language = b.language;
  audit("user", u.id, "health_profiles", u.id, "update", { version: p.version });
  return { ...p, name: u.user.name, user_id: undefined };
});

route("GET", `${V}/me/contacts`, (req) => {
  const u = requireRole(req, "patient");
  return [...db.contacts.values()].filter((c) => c.user_id === u.id).sort((a, b) => a.priority - b.priority).map(({ user_id, ...c }) => (void user_id, c));
});

route("POST", `${V}/me/contacts`, (req) => {
  const u = requireRole(req, "patient");
  const phone = normalisePhone(str(req.body, "phone"));
  if (!/^\+\d{11,13}$/.test(phone)) throw badRequest("Enter a 10 digit mobile number");
  const mine = [...db.contacts.values()].filter((c) => c.user_id === u.id);
  if (mine.length >= 5) throw badRequest("You can add up to 5 contacts");
  const c = { id: uid(), user_id: u.id, name: str(req.body, "name").trim(), phone, relation: (req.body.relation as string) ?? null, language: (req.body.language as string) ?? "en", priority: mine.length + 1 };
  db.contacts.set(c.id, c);
  return (({ user_id, ...rest }) => (void user_id, rest))(c);
}, 201);

route("DELETE", `${V}/me/contacts/{id}`, (req) => {
  const u = requireRole(req, "patient");
  const c = db.contacts.get(req.params.id);
  if (!c || c.user_id !== u.id) throw notFound("Contact not found");
  db.contacts.delete(c.id);
  return undefined;
}, 204);

route("POST", `${V}/me/push-subscriptions`, (req) => {
  const u = currentUser(req);
  db.pushSubs.push({ user_id: u.id, fcm_token: str(req.body, "fcm_token") });
  return undefined;
}, 204);

// extra: the caller's own past emergencies (history screen)
route("GET", `${V}/me/emergencies`, (req) => {
  const u = requireRole(req, "patient");
  return [...db.emergencies.values()].filter((e) => e.caller_user_id === u.id).sort((a, b) => (b.timestamps.received_at ?? 0) - (a.timestamps.received_at ?? 0)).map((e) => ({
    id: e.id, status: e.status, received_at: iso(e.timestamps.received_at), acuity: acuityOf(e), facility: facilityOf(e),
    hospital_name: e.hospital_id ? db.hospitals.get(e.hospital_id)?.name ?? null : null, for_self: e.for_self,
  }));
});

/* ---------- emergencies ---------- */
route("POST", `${V}/emergencies`, async (req) => {
  let user = null;
  try { user = currentUser(req); } catch { /* real core on main accepts caller_phone without a token */ }
  const channel = str(req.body, "channel") as EmergencyRec["channel"];
  if (!["app_button", "app_voice", "app_text", "sms"].includes(channel)) throw badRequest("invalid channel");
  if (channel === "app_voice" && !req.files.audio && !req.body.text) throw badRequest("audio required for app_voice");
  if (req.files.audio && req.files.audio.size > 5 * 1024 * 1024) throw badRequest("audio must be 5 MB or less");
  const text = (req.body.text as string | undefined)?.slice(0, 1000) ?? null;
  if (channel === "app_text" && !text) throw badRequest("text required for app_text");
  // SOS rate limit per phone (§18)
  const phone = user?.user.phone ?? (req.body.caller_phone as string | undefined) ?? null;
  const recent = [...db.emergencies.values()].filter((e) => e.caller_phone === phone && now() - (e.timestamps.received_at ?? 0) < 3600_000);
  if (phone && recent.length >= 5) throw new ApiError(429, "RATE_LIMITED", "Too many emergencies from this phone in the last hour. Call 108.");
  const { emergency, trackRaw } = await createEmergency({
    channel, text, lat: num(req.body, "lat"), lng: num(req.body, "lng"), accuracy_m: num(req.body, "accuracy_m"),
    for_self: req.body.for_self === undefined ? true : String(req.body.for_self) !== "false",
    caller_user_id: user?.role === "patient" ? user.id : null, caller_phone: phone, language: (req.body.language as string) ?? user?.user.language ?? "en",
  });
  return { emergency_id: emergency.id, status: emergency.status, family_track_url: `/track/${trackRaw}`, call_108_fallback: false };
}, 202);

function canSee(u: ReturnType<typeof currentUser>, e: EmergencyRec) {
  if (u.role === "developer") return true;
  if (u.role === "patient") return e.caller_user_id === u.id;
  if (u.role === "paramedic") return e.ambulance_id === u.ambulance_id || [...db.offers.values()].some((o) => o.emergency_id === e.id && o.ambulance_id === u.ambulance_id);
  if (u.role === "hospital_staff") return e.hospital_id === u.hospital_id || [...db.requests.values()].some((r) => r.emergency_id === e.id && r.hospital_id === u.hospital_id);
  return false;
}

route("GET", `${V}/emergencies/{id}`, (req) => {
  const u = currentUser(req);
  const e = emergencyOr404(req.params.id);
  if (!canSee(u, e)) throw forbidden("Not your emergency");
  if (u.role === "hospital_staff") {
    const r = [...db.requests.values()].filter((x) => x.emergency_id === e.id && x.hospital_id === u.hospital_id).at(-1);
    const ho = db.handoffs.get(e.id);
    return {
      id: e.id, status: e.status, version: e.version, card: r ? hospitalCard(r) : null,
      incoming: [...incomingFor(u.hospital_id!, "incoming"), ...incomingFor(u.hospital_id!, "at_door")].find((x) => x.emergency_id === e.id) ?? null,
      handoff: ho ? { arrived_at: iso(ho.arrived_at), offloaded_at: iso(ho.offloaded_at) } : null,
      timeline: patientView(e).timeline, handoff_info: e.handoff_info,
      answers: e.followup_answers.map((a) => ({ question_id: a.question_id, answer: a.answer, at: iso(a.at) })),
      transcript: e.transcript,
    };
  }
  if (u.role === "paramedic" && e.ambulance_id === u.ambulance_id) return { ...patientView(e), job: activeJob(e, db.ambulances.get(e.ambulance_id!)!) };
  return patientView(e);
});

route("GET", `${V}/emergencies/{id}/followup`, (req) => {
  const u = currentUser(req);
  const e = emergencyOr404(req.params.id);
  if (!canSee(u, e)) throw forbidden();
  return { question: e.followup_current, done: e.followup_done, first_aid: e.first_aid };
});

route("POST", `${V}/emergencies/{id}/followup`, async (req) => {
  const u = requireRole(req, "patient");
  const e = emergencyOr404(req.params.id);
  if (e.caller_user_id !== u.id) throw forbidden();
  const answer = (req.body.answer as string | undefined) ?? (req.body.text as string | undefined);
  if (!answer && !req.files.audio) throw badRequest("answer required");
  await answerFollowup(e, str(req.body, "question_id"), answer ?? "(voice answer)");
  return { question: e.followup_current, done: e.followup_done, first_aid: e.first_aid };
});

route("POST", `${V}/emergencies/{id}/cancel`, (req) => {
  const u = currentUser(req);
  const e = emergencyOr404(req.params.id);
  if (!(u.role === "patient" && e.caller_user_id === u.id) && u.role !== "developer") throw forbidden();
  cancelEmergency(e, (req.body.reason as string) ?? "caller cancelled", u.id);
  return patientView(e);
});

function myEmergency(req: Req) {
  const u = requireRole(req, "paramedic");
  const e = emergencyOr404(req.params.id);
  if (e.ambulance_id !== u.ambulance_id) throw forbidden("Not assigned to your ambulance");
  return { u, e };
}

route("POST", `${V}/emergencies/{id}/arrived-scene`, (req) => {
  const { u, e } = myEmergency(req);
  arrivedScene(e, u.id);
  return activeJob(e, db.ambulances.get(e.ambulance_id!)!);
});

route("POST", `${V}/emergencies/{id}/triage-confirm`, async (req) => {
  const { u, e } = myEmergency(req);
  const version = num(req.body, "version");
  if (version === null) throw badRequest("version required");
  await confirmTriage(e, { acuity: str(req.body, "acuity") as never, facility: str(req.body, "facility") as never, patient_count: num(req.body, "patient_count") ?? 1, version }, u.id);
  return { status: "confirmed", triage: { acuity: e.final_acuity, facility: e.final_facility, patient_count: e.patient_count }, job: activeJob(e, db.ambulances.get(e.ambulance_id!)!) };
});

route("POST", `${V}/emergencies/{id}/critical`, async (req) => {
  const { u, e } = myEmergency(req);
  const out = await markCritical(e, u.id);
  return { status: "triggered", ...out };
});

const overrideOptions = async (req: Req) => {
  const { e } = myEmergency(req);
  return { data: await familyOverrideOptions(e) };
};
route("POST", `${V}/emergencies/{id}/family-override/options`, overrideOptions);
route("GET", `${V}/emergencies/{id}/family-override/options`, overrideOptions);

route("POST", `${V}/emergencies/{id}/family-override`, async (req) => {
  const { u, e } = myEmergency(req);
  await familyOverride(e, str(req.body, "hospital_id"), req.body.consent === true || req.body.consent === "true", u.id);
  return { status: "overridden" };
});

route("POST", `${V}/emergencies/{id}/refused-transport`, (req) => {
  const { u, e } = myEmergency(req);
  refusedTransport(e, (req.body.note as string) ?? null, u.id);
  return { status: "recorded" };
});

route("POST", `${V}/emergencies/{id}/arrived-hospital`, (req) => {
  const { u, e } = myEmergency(req);
  arrivedHospital(e, u.id);
  return activeJob(e, db.ambulances.get(e.ambulance_id!)!);
});

/* ---------- 7.4 ambulance ---------- */
function myAmbulance(req: Req) {
  const u = requireRole(req, "paramedic");
  if (!u.ambulance_id) throw forbidden("user has no assigned ambulance");
  return { u, a: db.ambulances.get(u.ambulance_id)! };
}

// extra: own ambulance with its version (needed for POST /ambulance/status)
route("GET", `${V}/ambulance/me`, (req) => {
  const { a } = myAmbulance(req);
  return { id: a.id, registration_no: a.registration_no, type: a.type, status: a.status, version: a.version, location: a.location, kyc_verified: a.kyc_verified, is_simulated: a.is_simulated, base: a.base_name, signal: signalOf(a) };
});

route("POST", `${V}/ambulance/status`, (req) => {
  const { u, a } = myAmbulance(req);
  const status = str(req.body, "status");
  const version = num(req.body, "version");
  if (!["available", "offline", "cleaning_done"].includes(status)) throw badRequest("invalid status");
  if (version !== a.version) throw conflict("VERSION_CONFLICT", "Ambulance was modified", { current: { status: a.status, version: a.version } });
  if (status === "available" && !a.kyc_verified) throw forbidden("Your driver KYC is not verified yet"); // T30
  if (status === "cleaning_done") {
    if (a.status !== "cleaning") throw conflict("INVALID_TRANSITION", "Not cleaning");
    setAmbulance(a, "available", u.id);
  } else if (status === "offline") {
    if (a.active_emergency_id) throw conflict("INVALID_TRANSITION", "Finish the current job before going offline");
    setAmbulance(a, "offline", u.id);
  } else {
    setAmbulance(a, "available", u.id);
    a.last_heartbeat_at = now();
  }
  return { status: a.status, version: a.version };
});

route("POST", `${V}/ambulance/heartbeat`, (req) => {
  const { a } = myAmbulance(req);
  // batch form from the offline queue (§11.12): latest one updates location
  const beats = Array.isArray(req.body.heartbeats) ? (req.body.heartbeats as Record<string, unknown>[]) : [req.body];
  const latest = beats.at(-1) ?? {};
  if (latest.lat === undefined || latest.lng === undefined) throw badRequest("lat and lng required");
  a.last_heartbeat_at = now();
  // simulated ambulances keep their simulated position; a real device's GPS would be used here
  if (!a.is_simulated) a.location = { lat: Number(latest.lat), lng: Number(latest.lng) };
  return undefined;
}, 204);

route("GET", `${V}/ambulance/offers`, (req) => {
  const { a } = myAmbulance(req);
  return [...db.offers.values()].filter((o) => o.ambulance_id === a.id && o.status === "pending" && o.expires_at > now()).map(offerPayload);
});

const accept = async (req: Req) => {
  const { u, a } = myAmbulance(req);
  const out = await acceptOffer(req.params.id, a.id, u.id);
  const e = db.emergencies.get(out.emergency_id)!;
  return { ...out, emergency: patientView(e) };
};
route("POST", `${V}/offers/{id}/accept`, accept);
route("POST", `${V}/ambulance/offers/{id}/accept`, accept);
const decline = (req: Req) => {
  const { u, a } = myAmbulance(req);
  declineOffer(req.params.id, a.id, (req.body.reason as string) ?? null, u.id);
  return { status: "declined" };
};
route("POST", `${V}/offers/{id}/decline`, decline);
route("POST", `${V}/ambulance/offers/{id}/decline`, decline);

route("GET", `${V}/ambulance/active`, (req) => {
  const { a } = myAmbulance(req);
  const e = a.active_emergency_id ? db.emergencies.get(a.active_emergency_id) : null;
  if (!e) return { job: null };
  return { job: activeJob(e, a) };
});

route("POST", `${V}/ambulance/vehicle-issue`, async (req) => {
  const { u, a } = myAmbulance(req);
  await vehicleIssue(a.id, (req.body.note as string) ?? null, u.id);
  return undefined;
}, 204);

// extra: past jobs for the history screen
route("GET", `${V}/ambulance/history`, (req) => {
  const { a } = myAmbulance(req);
  return [...db.emergencies.values()].filter((e) => e.ambulance_id === a.id || db.audit.some((x) => x.entity_id === e.id && x.action === "offer_accepted" && (x.after as { ambulance_id?: string })?.ambulance_id === a.id))
    .sort((x, y) => (y.timestamps.received_at ?? 0) - (x.timestamps.received_at ?? 0)).slice(0, 50).map((e) => ({
      emergency_id: e.id, at: iso(e.timestamps.assigned_at ?? e.timestamps.received_at)!, acuity: e.final_acuity ?? e.ai_acuity, facility: e.final_facility ?? e.ai_facility,
      hospital_name: e.hospital_id ? db.hospitals.get(e.hospital_id)?.name ?? null : null, status: e.status,
      duration_sec: e.timestamps.handed_off_at && e.timestamps.assigned_at ? Math.round((e.timestamps.handed_off_at - e.timestamps.assigned_at) / 1000) : null,
    }));
});

/* ---------- 7.5 hospital ---------- */
function staffUser(req: Req) {
  const u = requireRole(req, "hospital_staff");
  if (!u.hospital_id) throw forbidden("No hospital on this account");
  return u;
}

function freshness(ms: number): Freshness {
  const min = (now() - ms) / 60_000;
  return min <= C.FRESH_MAX_MIN ? "fresh" : min <= C.AGING_MAX_MIN ? "aging" : "stale";
}

function roomsOf(hid: string) {
  return [...db.rooms.values()].filter((r) => r.hospital_id === hid).sort((a, b) => a.priority_order - b.priority_order).map((r) => {
    const res = r.reservation_id ? db.reservations.get(r.reservation_id) : null;
    const e = res ? db.emergencies.get(res.emergency_id) : null;
    const a = e?.ambulance_id ? db.ambulances.get(e.ambulance_id) : null;
    return {
      id: r.id, code: r.code, type: r.type, status: r.status, location_note: r.location_note, version: r.version, status_updated_at: iso(r.status_updated_at),
      reservation: e ? { registration_no: a?.registration_no ?? "", eta_sec: a ? etaFor(a)?.eta ?? null : null, acuity: acuityOf(e), facility: facilityOf(e) } : null,
      occupant: r.occupant,
    };
  });
}

function resourcesOf(hid: string) {
  return [...db.resources.values()].filter((r) => r.hospital_id === hid).map((r) => ({ ...r, hospital_id: undefined, reported_at: iso(r.reported_at)!, freshness: freshness(r.reported_at) }));
}

function staffOf(hid: string, onlyOnDuty = false): Staff[] {
  const t = now();
  return [...db.staff.values()].filter((s) => s.hospital_id === hid).map((s) => {
    const shift = [...db.shifts.values()].find((sh) => sh.staff_id === s.id && sh.start_at <= t && sh.end_at > t) ?? null;
    return { id: s.id, name: s.name, specialty: s.specialty, role: s.specialty, phone: s.phone, is_active: s.is_active, on_duty: !!shift && s.is_active, shift: shift ? { start_at: iso(shift.start_at)!, end_at: iso(shift.end_at)! } : null };
  }).filter((s) => !onlyOnDuty || s.on_duty);
}

route("GET", `${V}/hospital/dashboard`, (req): HospitalDashboard => {
  const u = staffUser(req);
  const h = db.hospitals.get(u.hospital_id!)!;
  const rooms: Record<string, ReturnType<typeof roomsOf>> = {};
  for (const r of roomsOf(h.id)) (rooms[r.type] ??= []).push(r);
  return {
    hospital: { id: h.id, name: h.name, address: h.address, location: h.location, er_entrance_note: h.er_entrance_note, capabilities: h.capabilities, last_confirmed_at: iso(h.last_confirmed_at), is_simulated: h.is_simulated },
    pending_requests: [...db.requests.values()].filter((r) => r.hospital_id === h.id && r.status === "pending").map(hospitalCard),
    rooms, resources: resourcesOf(h.id) as never, staff_on_duty: staffOf(h.id, true), freshness: freshness(h.last_confirmed_at),
    incoming: incomingFor(h.id, "incoming"), at_door: incomingFor(h.id, "at_door"),
  };
});

route("GET", `${V}/hospital/requests`, (req) => {
  const u = staffUser(req);
  const status = req.query.get("status");
  return { requests: [...db.requests.values()].filter((r) => r.hospital_id === u.hospital_id && (!status || r.status === status)).sort((a, b) => b.sent_at - a.sent_at).slice(0, 100).map(hospitalCard) };
});

route("POST", `${V}/hospital/requests/{id}/accept`, async (req) => {
  const u = staffUser(req);
  const staffIds = Array.isArray(req.body.staff_ids) ? (req.body.staff_ids as string[]) : null;
  return acceptRequest(req.params.id, u.hospital_id!, (req.body.room_id as string) ?? null, staffIds, u.id);
});

route("POST", `${V}/hospital/requests/{id}/reject`, async (req) => {
  const u = staffUser(req);
  await rejectRequest(req.params.id, u.hospital_id!, str(req.body, "reason_code") as RejectReason, (req.body.note as string) ?? null, u.id);
  return { status: "rejected" };
});

route("GET", `${V}/hospital/rooms`, (req) => ({ rooms: roomsOf(staffUser(req).hospital_id!) }));

route("PATCH", `${V}/hospital/rooms/{id}`, async (req) => {
  const u = staffUser(req);
  const version = num(req.body, "version");
  if (version === null) throw badRequest("version required");
  const out = await patchRoom(u.hospital_id!, req.params.id, str(req.body, "status"), version, (req.body.override_reason as string) ?? null, u.id);
  const room = "room" in (out as object) ? (out as { room: { id: string } }).room : (out as { id: string });
  return { status: "updated", room: roomsOf(u.hospital_id!).find((r) => r.id === room.id), ...("reallocated_to" in (out as object) ? out : {}) };
});

route("PATCH", `${V}/hospital/resources/{id}`, (req) => {
  const u = staffUser(req);
  const r = db.resources.get(req.params.id);
  if (!r || r.hospital_id !== u.hospital_id) throw notFound("Resource not found");
  const version = num(req.body, "version");
  if (version !== r.version) throw conflict("VERSION_CONFLICT", "Someone else just updated this", { current: { ...r, reported_at: iso(r.reported_at) } });
  const available = num(req.body, "available");
  const total = num(req.body, "total") ?? r.total;
  if (available === null || available < 0) throw badRequest("available must be 0 or more");
  if (available + r.reserved > total) throw badRequest(`available plus reserved (${r.reserved}) cannot be more than total (${total})`);
  r.available = available;
  r.total = total;
  r.version++;
  r.reported_at = now();
  audit("user", u.id, "hospital_resources", r.id, "update", { available, total });
  publish(`hospital:${u.hospital_id}`, "resource.changed", { id: r.id, version: r.version, available: r.available, total: r.total });
  return { status: "updated", resource: { ...r, reported_at: iso(r.reported_at), freshness: "fresh" } };
});

route("POST", `${V}/hospital/availability/confirm`, (req) => {
  const u = staffUser(req);
  const h = db.hospitals.get(u.hospital_id!)!;
  h.last_confirmed_at = now();
  for (const r of db.resources.values()) if (r.hospital_id === h.id) r.reported_at = now();
  audit("user", u.id, "hospitals", h.id, "availability_confirmed", {});
  return { status: "confirmed", last_confirmed_at: iso(h.last_confirmed_at) };
});

route("POST", `${V}/hospital/handoffs/{emergency_id}/received`, (req) => {
  const u = staffUser(req);
  const e = emergencyOr404(req.params.emergency_id);
  patientReceived(e, u.hospital_id!, Array.isArray(req.body.receiving_staff_ids) ? (req.body.receiving_staff_ids as string[]) : [], u.id);
  return { status: "recorded" };
});

// extra: handoffs list (incoming, at the door, recent)
route("GET", `${V}/hospital/handoffs`, (req) => {
  const u = staffUser(req);
  const recent = [...db.handoffs.values()].filter((h) => h.hospital_id === u.hospital_id && h.offloaded_at).sort((a, b) => b.offloaded_at! - a.offloaded_at!).slice(0, 20).map((h) => {
    const e = db.emergencies.get(h.emergency_id)!;
    return { emergency_id: e.id, patient_display: patientDisplay(e), registration_no: db.ambulances.get(e.ambulance_id ?? "")?.registration_no ?? "", arrived_at: iso(h.arrived_at), offloaded_at: iso(h.offloaded_at), offload_delay_sec: h.arrived_at ? Math.round((h.offloaded_at! - h.arrived_at) / 1000) : null };
  });
  return { incoming: incomingFor(u.hospital_id!, "incoming"), at_door: incomingFor(u.hospital_id!, "at_door"), recent };
});

route("GET", `${V}/hospital/staff`, (req) => ({ staff: staffOf(staffUser(req).hospital_id!) }));

route("POST", `${V}/hospital/staff`, (req) => {
  const u = staffUser(req);
  const s = { id: uid(), hospital_id: u.hospital_id!, name: str(req.body, "name"), specialty: (str(req.body, "role", false) || str(req.body, "specialty", false) || "er_nurse") as never, phone: (req.body.phone as string) ?? "", is_active: true };
  db.staff.set(s.id, s);
  audit("user", u.id, "staff", s.id, "create", { name: s.name });
  return { ...s, hospital_id: undefined };
}, 201);

route("GET", `${V}/hospital/staff/{id}/shifts`, (req) => {
  const u = staffUser(req);
  const s = db.staff.get(req.params.id);
  if (!s || s.hospital_id !== u.hospital_id) throw notFound("Staff not found");
  return { shifts: [...db.shifts.values()].filter((x) => x.staff_id === s.id).sort((a, b) => a.start_at - b.start_at).map((x) => ({ id: x.id, staff_id: x.staff_id, start_at: iso(x.start_at), end_at: iso(x.end_at) })) };
});

const saveShifts = (req: Req) => {
  const u = staffUser(req);
  const s = db.staff.get(req.params.id);
  if (!s || s.hospital_id !== u.hospital_id) throw notFound("Staff not found");
  const shifts = Array.isArray(req.body.shifts) ? (req.body.shifts as { start_at: string; end_at: string }[]) : [];
  const parsed = shifts.map((x) => ({ start: Date.parse(x.start_at), end: Date.parse(x.end_at) }));
  if (parsed.some((p) => !Number.isFinite(p.start) || !Number.isFinite(p.end) || p.end <= p.start)) throw badRequest("Each shift needs a start before its end");
  // EXCLUDE constraint (§5.2): no overlapping shifts for one person
  const sorted = [...parsed].sort((a, b) => a.start - b.start);
  for (let i = 1; i < sorted.length; i++) if (sorted[i].start < sorted[i - 1].end) throw conflict("VERSION_CONFLICT", "Two shifts overlap");
  for (const [k, x] of db.shifts) if (x.staff_id === s.id) db.shifts.delete(k);
  for (const p of parsed) {
    const id = uid();
    db.shifts.set(id, { id, staff_id: s.id, start_at: p.start, end_at: p.end });
  }
  if (typeof req.body.is_active === "boolean") s.is_active = req.body.is_active;
  audit("user", u.id, "staff_shifts", s.id, "update", { count: parsed.length });
  return { status: "updated" };
};
route("POST", `${V}/hospital/staff/{id}/shifts`, saveShifts);
route("PATCH", `${V}/hospital/staff/{id}/shifts`, saveShifts);

// extra: unknown patients waiting for identity merge
route("GET", `${V}/hospital/patients`, (req) => {
  const u = staffUser(req);
  return { patients: [...db.emergencies.values()].filter((e) => e.hospital_id === u.hospital_id && e.patient.temp_id).map((e) => ({ temp_id: e.patient.temp_id, emergency_id: e.id, display: patientDisplay(e), status: e.status, merged: !!e.patient.user_id, received_at: iso(e.timestamps.received_at) })) };
});

route("POST", `${V}/hospital/patients/{temp_id}/merge`, (req) => {
  const u = staffUser(req);
  const e = [...db.emergencies.values()].find((x) => x.patient.temp_id === req.params.temp_id && x.hospital_id === u.hospital_id);
  if (!e) throw notFound("Unknown patient not found");
  const phone = normalisePhone(str(req.body, "phone"));
  let user = [...db.users.values()].find((x) => x.phone === phone);
  if (!user) {
    const id = uid();
    user = { id, role: "patient", name: null, phone, language: "en", password: null, hospital_id: null, ambulance_id: null };
    db.users.set(id, user);
    db.profiles.set(id, { user_id: id, dob: null, sex: null, blood_group: null, allergies: [], conditions: [], medications: [], insurance_provider: null, insurance_policy_no: null, home_address: null, home_location: null, notes: null, version: 1 });
  }
  e.patient.user_id = user.id;
  e.patient.is_unknown = false;
  audit("user", u.id, "patients", e.id, "merge", { temp_id: req.params.temp_id, phone });
  return { status: "merged", patient_id: user.id, profile: db.profiles.get(user.id) };
});

route("GET", `${V}/hospital/analytics`, (req) => {
  const u = staffUser(req);
  const from = req.query.get("from");
  const to = req.query.get("to");
  return { data: computeAnalytics(u.hospital_id!, from ? Date.parse(from) : undefined, to ? Date.parse(to) : undefined) };
});

/* ---------- 7.6 family ---------- */
route("GET", `${V}/track/{token}`, (req) => {
  const hash = hashToken(req.params.token);
  const e = [...db.emergencies.values()].find((x) => x.track_token === hash);
  if (!e) throw notFound("This tracking link is not valid");
  if (e.timestamps.closed_at && now() - e.timestamps.closed_at > 6 * 3600_000) throw new ApiError(410, "EXPIRED", "This tracking link has expired");
  return trackView(e);
});

/* ---------- 7.7 ops ---------- */
route("POST", `${V}/ops/session`, (req) => {
  const { session, user, escalation_id } = exchangeOpsLink(str(req.body, "token"));
  req.setCookie(`ops_session=${session}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${C.OPS_SESSION_H * 3600}`);
  return { status: "ok", user: publicUser(user), session_token: session, escalation_id };
});

route("GET", `${V}/ops/overview`, (req) => {
  requireOps(req);
  const t = now();
  return {
    data: {
      emergencies: [...db.emergencies.values()].filter((e) => !["closed", "cancelled", "refused_transport", "merged_duplicate"].includes(e.status) || t - (e.timestamps.received_at ?? 0) < 600_000).map((e) => ({
        id: e.id, status: e.status, acuity: e.ai_acuity ? acuityOf(e) : null, facility: e.ai_facility ? facilityOf(e) : null, location: e.location, received_at: iso(e.timestamps.received_at)!,
        ambulance: e.ambulance_id ? db.ambulances.get(e.ambulance_id)?.registration_no ?? null : null, hospital: e.hospital_id ? db.hospitals.get(e.hospital_id)?.name ?? null : null,
      })),
      ambulances: [...db.ambulances.values()].map((a) => ({ id: a.id, registration_no: a.registration_no, type: a.type, status: a.status, location: a.location, signal: signalOf(a) })),
      hospitals: [...db.hospitals.values()].map((h) => ({ id: h.id, name: h.name, location: h.location, free_rooms: [...db.rooms.values()].filter((r) => r.hospital_id === h.id && r.status === "free").length, freshness: freshness(h.last_confirmed_at) })),
      escalations: [...db.escalations.values()].sort((a, b) => b.created_at - a.created_at).map(escalationView),
    },
  };
});

function escalationView(x: ReturnType<typeof db.escalations.get> & object) {
  const e = x.emergency_id ? db.emergencies.get(x.emergency_id) : null;
  const a = e?.ambulance_id ? db.ambulances.get(e.ambulance_id) : null;
  return {
    id: x.id, type: x.type, status: x.status, emergency_id: x.emergency_id, summary: x.summary,
    options: x.options.map((o) => ({ id: o.id, label: o.label, action: o.action, is_default: o.is_default })),
    default_option_id: x.default_option_id, chosen_option_id: x.chosen_option_id, claimed_by: x.claimed_by, claimed_by_name: x.claimed_by ? db.users.get(x.claimed_by)?.name ?? null : null,
    created_at: iso(x.created_at)!, repeat_at: iso(x.repeat_at), default_at: iso(x.default_at), resolved_at: iso(x.resolved_at),
    map: { pickup: e?.location ?? null, ambulance: a?.location ?? null, hospitals: [...db.hospitals.values()].map((h) => ({ ...h.location, id: h.id, name: h.name, status: e?.tried_hospitals.find((t) => t.hospital_id === h.id)?.outcome })) },
    tried: e?.tried_hospitals.map((t) => ({ hospital: db.hospitals.get(t.hospital_id)?.name ?? "", outcome: t.outcome })) ?? [],
  };
}

route("GET", `${V}/ops/escalations/{id}`, (req) => {
  requireOps(req);
  const x = db.escalations.get(req.params.id);
  if (!x) throw notFound("Escalation not found");
  return { data: escalationView(x) };
});

route("POST", `${V}/ops/escalations/{id}/claim`, (req) => {
  const u = requireOps(req);
  claimEscalation(req.params.id, u.id, u.user.name ?? "developer");
  return { status: "claimed" };
});

route("POST", `${V}/ops/escalations/{id}/resolve`, async (req) => {
  const u = requireOps(req);
  await resolveEscalation(req.params.id, str(req.body, "option_id"), u.id);
  return { status: "resolved" };
});

route("POST", `${V}/ops/emergencies/{id}/override`, async (req) => {
  const u = requireOps(req);
  const e = emergencyOr404(req.params.id);
  const reason = str(req.body, "reason").trim();
  if (reason.length < 3) throw badRequest("A reason is required for a manual override");
  const hid = str(req.body, "hospital_id");
  if (!db.hospitals.has(hid)) throw notFound("Hospital not found");
  if (!["patient_on_board", "hospital_selecting", "hospital_confirmed"].includes(e.status)) throw conflict("INVALID_TRANSITION", `Cannot assign a hospital in ${e.status}`);
  audit("developer", u.id, "emergencies", e.id, "manual_override", { hospital: db.hospitals.get(hid)?.name }, reason);
  for (const r of db.requests.values()) if (r.emergency_id === e.id && r.status === "pending") r.status = "cancelled";
  releaseReservation(e.reservation_id, "released", "ops override");
  e.hospital_id = null;
  e.reservation_id = null;
  await selectHospitals(e, { reason: `ops override: ${reason}`, priority: true, forceHospitalId: hid });
  return { status: "overridden" };
});

route("GET", `${V}/ops/analytics`, (req) => {
  requireOps(req);
  const from = req.query.get("from");
  const to = req.query.get("to");
  return { data: computeAnalytics(null, from ? Date.parse(from) : undefined, to ? Date.parse(to) : undefined) };
});

route("GET", `${V}/ops/audit`, (req) => {
  requireOps(req);
  const id = req.query.get("entity_id");
  const esc = id ? db.escalations.get(id) : null;
  const ids = new Set([id, esc?.emergency_id].filter(Boolean));
  const reqIds = new Set([...db.requests.values()].filter((r) => ids.has(r.emergency_id)).map((r) => r.id));
  return {
    data: db.audit.filter((a) => !id || ids.has(a.entity_id) || reqIds.has(a.entity_id)).slice(-300).reverse().map((a) => ({ id: a.id, at: iso(a.at), actor_type: a.actor_type, actor_id: a.actor_id, entity: a.entity, action: a.action, reason: a.reason, after: a.after })),
  };
});

route("GET", `${V}/ops/scenarios`, (req) => {
  requireOps(req);
  return { data: { scenarios: listScenarios(), runs: [...runs.values()], speed: db.sim.speed } };
});

route("POST", `${V}/ops/scenarios/{name}/run`, async (req) => {
  requireOps(req);
  if (!listScenarios().some((s) => s.name === req.params.name)) throw notFound("Unknown scenario");
  const run = await runScenario(req.params.name);
  return { status: run.status === "not_available" ? "not_available" : "running", run };
});

route("POST", `${V}/ops/sim/reset`, (req) => {
  requireOps(req);
  resetWorld();
  return { status: "reset" };
});

route("POST", `${V}/ops/sim/speed`, (req) => {
  requireOps(req);
  const m = num(req.body, "multiplier");
  if (!m || m < 1 || m > 10) throw badRequest("multiplier must be between 1 and 10");
  db.sim.speed = m;
  return { status: "updated", multiplier: m };
});

// extra: the fake SMS / Telegram / push log (SMS_MODE=fake, TELEGRAM_MODE=fake)
route("GET", `${V}/ops/notifications`, (req) => {
  requireOps(req);
  return { data: db.notifications.slice(-100).reverse().map((n) => ({ ...n, at: iso(n.at) })) };
});

/* ---------- 7.9 health ---------- */
const health = () => ({ status: "ok" });
route("GET", "/healthz", health);
route("GET", `${V}/health`, health);
route("GET", "/readyz", () => ({ status: { db: "ok", redis: "ok", ml: mlStatus(), osrm: "ok" }, mode: "mock" }));

/* ---------- dev helpers (mock only; the real ops link comes from the Telegram bot) ---------- */
route("GET", "/dev/ops-link", () => {
  const token = issueOpsLink();
  return { token, path: `/ops/${token}` };
});
route("GET", "/dev/info", () => ({ mode: "mock", speed: db.sim.speed, web_origin: MOCK.WEB_ORIGIN, ml: mlStatus() }));

export function resetWorld() {
  seed();
  seedHistory();
  runs.clear();
  db.sim.speed = 1;
}
