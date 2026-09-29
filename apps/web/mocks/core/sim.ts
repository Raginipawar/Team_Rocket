// Simulator + sweeper for the mock core (technical.md §10.2 timers, §11.4 holds,
// §11.9 geofencing, §11.12 signal, §13 escalation timers, §15 simulated crews and
// hospital bots). Every timer re-checks state before acting, like the real jobs.
// Bots only act for ambulances and hospitals that no real person has open.

import { C } from "./config";
import { ambulanceIsLive, hospitalIsLive, publish } from "./bus";
import { distanceM, pointAt } from "./geo";
import {
  acceptOffer, arrivedHospital, arrivedScene, audit, closeLater, confirmTriage, declineOffer, dispatchRound, extendHold,
  openEscalation, patientReceived, pruneOldEmergencies, rejectRequest, releaseReservation, resolveEscalation, acceptRequest,
  scenarioHooks, setAmbulance, setStatus, timeoutRequest, notify, offerPayload,
} from "./domain";
import { db, now, signalOf } from "./world";
import { acuityOf, etaFor, facilityOf, velocity } from "./views";
import type { RejectReason } from "../../lib/enums";

const TICK_MS = 500;
let last = now();
let lastLocationPush = 0;
const lastSignal = new Map<string, string>();

async function tick() {
  const t = now();
  const dt = (t - last) / 1000;
  last = t;

  /* offers: expiry + simulated crews */
  for (const o of db.offers.values()) {
    if (o.status !== "pending") continue;
    if (t > o.expires_at) {
      o.status = "expired";
      publish(`ambulance:${o.ambulance_id}`, "offer.revoked", { offer_id: o.id, reason: "expired" });
      continue;
    }
    if (o.bot_at && t >= o.bot_at && !ambulanceIsLive(o.ambulance_id)) {
      o.bot_at = null;
      const accept = scenarioHooks.driverAccept?.(o.ambulance_id) ?? o.bot_accept;
      try {
        if (accept) await acceptOffer(o.id, o.ambulance_id, "simulated-crew");
        else declineOffer(o.id, o.ambulance_id, "simulated crew declined", "simulated-crew");
      } catch {
        /* lost the race (409): exactly what the accept transaction is for */
      }
    }
  }

  /* dispatch rounds (§11.1) */
  for (const e of db.emergencies.values()) {
    if (!e.next_round_at || t < e.next_round_at) continue;
    const stillDispatching = e.status === "dispatching" || (!e.ambulance_id && ["patient_on_board", "hospital_selecting", "hospital_confirmed"].includes(e.status));
    if (!stillDispatching) {
      e.next_round_at = null;
      continue;
    }
    e.next_round_at = null;
    if (e.dispatch_round < 3) {
      void dispatchRound(e.id, e.dispatch_round + 1);
    } else if (!e.escalated_no_ambulance) {
      e.escalated_no_ambulance = true;
      openEscalation("no_ambulance", e, `No ambulance accepted after 3 rounds (5, 10 and 20 km) for a ${acuityOf(e)} ${facilityOf(e)} call at ${e.landmark_text ?? "the caller's location"}.`);
    }
  }

  /* movement, heartbeats, geofences, signal */
  for (const a of db.ambulances.values()) {
    const silent = t < a.silent_until;
    if (a.route && a.leg) {
      a.route_m = Math.min(a.route.distance_m, a.route_m + velocity(a) * dt);
      const p = pointAt(a.route, a.route_m);
      a.location = p.pos;
      a.heading = p.heading;
      a.speed_kmh = Math.round((velocity(a) * 3.6) / 5);
    } else if (a.status === "available" || a.status === "offline") {
      a.speed_kmh = 0;
    }
    if (!silent && a.status !== "offline" && a.status !== "out_of_service") {
      a.last_heartbeat_at = t;
      extendHold(a);
    }
    const sig = signalOf(a, t);
    if (lastSignal.get(a.id) !== sig) {
      lastSignal.set(a.id, sig);
      const data = { signal: sig, last_seen_at: new Date(a.last_heartbeat_at).toISOString(), ambulance_id: a.id };
      publish("ops", "ambulance.signal", data);
      if (a.active_emergency_id) {
        const e = db.emergencies.get(a.active_emergency_id);
        publish(`emergency:${a.active_emergency_id}`, "ambulance.signal", data);
        if (e?.hospital_id) publish(`hospital:${e.hospital_id}`, "ambulance.signal", { ...data, emergency_id: e.id });
      }
    }
    // geofence (§11.9)
    const e = a.active_emergency_id ? db.emergencies.get(a.active_emergency_id) : null;
    if (e && a.route && !silent) {
      const remaining = a.route.distance_m - a.route_m;
      if (a.leg === "to_patient" && remaining <= C.GEOFENCE_SCENE_M) {
        try { arrivedScene(e, "geofence"); } catch { /* already there */ }
      } else if (a.leg === "to_hospital" && remaining <= C.GEOFENCE_HOSPITAL_M && e.status === "hospital_confirmed") {
        try { arrivedHospital(e, "geofence"); } catch { /* already there */ }
      } else if (a.leg === "to_hospital" && remaining <= 1 && e.status === "hospital_selecting") {
        a.speed_kmh = 0; // waiting outside while the hospital decides
      }
    }
  }

  /* live location fan-out, once a second */
  if (t - lastLocationPush >= 1000) {
    lastLocationPush = t;
    for (const a of db.ambulances.values()) {
      if (t < a.silent_until) continue;
      const eta = etaFor(a);
      const loc = { lat: a.location.lat, lng: a.location.lng, heading: Math.round(a.heading), speed_kmh: a.speed_kmh, eta_sec: eta?.eta, eta_low_sec: eta?.low, eta_high_sec: eta?.high, signal: signalOf(a, t), ambulance_id: a.id };
      publish("ops", "ambulance.location", loc);
      publish(`ambulance:${a.id}`, "ambulance.location", loc);
      const e = a.active_emergency_id ? db.emergencies.get(a.active_emergency_id) : null;
      if (!e) continue;
      publish(`emergency:${e.id}`, "ambulance.location", loc);
      publish(`track:${e.track_token}`, "ambulance.location", loc);
      if (e.hospital_id && ["hospital_selecting", "hospital_confirmed", "arrived_hospital"].includes(e.status)) publish(`hospital:${e.hospital_id}`, "ambulance.location", { ...loc, emergency_id: e.id });
    }
  }

  /* simulated paramedic confirms triage */
  for (const e of db.emergencies.values()) {
    if (e.status === "at_scene" && e.bot_confirm_at && t >= e.bot_confirm_at && e.ambulance_id && !ambulanceIsLive(e.ambulance_id)) {
      e.bot_confirm_at = null;
      try {
        await confirmTriage(e, { acuity: e.ai_acuity ?? "critical", facility: e.ai_facility ?? "general", patient_count: e.patient_count, version: e.version }, "simulated-crew");
      } catch (err) {
        console.warn("[sim] bot triage confirm failed", (err as Error).message);
      }
    }
    const closeAt = closeLater.get(e.id);
    if (closeAt && t >= closeAt && e.status === "handed_off") {
      closeLater.delete(e.id);
      setStatus(e, "closed");
    }
  }

  /* hospital requests: timeout + bots */
  for (const r of db.requests.values()) {
    if (r.status !== "pending") continue;
    if (t >= r.expires_at) {
      await timeoutRequest(r);
      continue;
    }
    if (r.bot_at && t >= r.bot_at && !hospitalIsLive(r.hospital_id)) {
      r.bot_at = null;
      const decision = scenarioHooks.hospitalDecision?.(r.hospital_id) ?? r.bot_decision;
      try {
        if (decision === "accept") await acceptRequest(r.id, r.hospital_id, null, null, "hospital-bot");
        else if (decision === "reject") {
          const reasons: RejectReason[] = ["NO_BED", "NO_SPECIALIST", "OVER_CAPACITY"];
          await rejectRequest(r.id, r.hospital_id, reasons[Math.floor(Math.random() * reasons.length)], "Simulated hospital", "hospital-bot");
        }
      } catch (err) {
        console.warn("[sim] hospital bot failed", (err as Error).message);
      }
    }
  }

  /* holds: sweeper expiry (T7) */
  for (const res of db.reservations.values()) {
    if (res.status === "held" && t > res.hold_expires_at) {
      const req = db.requests.get(res.hospital_request_id);
      if (req?.status === "pending") continue; // the request timeout handles it
      releaseReservation(res.id, "expired", "hold expired");
    }
    if (res.status === "confirmed" && t > res.hold_expires_at) {
      const e = db.emergencies.get(res.emergency_id);
      const a = e?.ambulance_id ? db.ambulances.get(e.ambulance_id) : null;
      const silentFor = a ? (t - a.last_heartbeat_at) / 1000 : Infinity;
      if (silentFor > C.OFFLINE_HOLD_GRACE_SEC) {
        releaseReservation(res.id, "expired", "ambulance silent beyond grace");
        if (e) openEscalation("system_anomaly", e, `${a?.registration_no ?? "An ambulance"} has been silent beyond the grace period; its hospital hold expired.`);
      }
    }
  }

  /* handoff: offload delay alert (T34) + bot "patient received" */
  for (const ho of db.handoffs.values()) {
    if (ho.offloaded_at || !ho.arrived_at) continue;
    const e = db.emergencies.get(ho.emergency_id);
    if (!e || e.status !== "arrived_hospital") continue;
    if (!ho.delay_alerted && t - ho.arrived_at > C.OFFLOAD_DELAY_ALERT_MIN * 60_000) {
      ho.delay_alerted = true;
      publish(`hospital:${ho.hospital_id}`, "alert", { kind: "offload_delay", message: `Ambulance waiting at the door for over ${C.OFFLOAD_DELAY_ALERT_MIN} minutes` });
      publish("ops", "alert", { kind: "offload_delay", message: `Offload delay at ${db.hospitals.get(ho.hospital_id)?.name}` });
    }
    if (ho.bot_receive_at && t >= ho.bot_receive_at && !hospitalIsLive(ho.hospital_id)) {
      ho.bot_receive_at = null;
      try { patientReceived(e, ho.hospital_id, [], "hospital-bot"); } catch { /* ignore */ }
    }
  }

  /* simulated crews finish cleaning */
  for (const a of db.ambulances.values()) {
    if (a.status === "cleaning" && !ambulanceIsLive(a.id)) {
      const since = db.audit.findLast?.((x) => x.entity_id === a.id && x.action === "status:cleaning")?.at ?? t;
      if (t - since > 20_000 / db.sim.speed) setAmbulance(a, "available", "simulated-crew");
    }
  }

  /* escalations: repeat at 60 s, auto default at 120 s (§13) */
  for (const esc of db.escalations.values()) {
    if (esc.status !== "open" && esc.status !== "claimed") continue;
    if (esc.status === "open" && esc.repeats === 0 && t >= esc.repeat_at) {
      esc.repeats = 1;
      notify("telegram", "team group", `REPEAT: ${esc.type} still unclaimed. ${esc.summary}`);
      notify("sms", "developers", `GoldenHour escalation unclaimed for 60 s: ${esc.type}`);
      publish("ops", "escalation.repeat", { escalation_id: esc.id, status: esc.status });
    }
    if (t >= esc.default_at) {
      try {
        await resolveEscalation(esc.id, esc.default_option_id, null, true);
      } catch (err) {
        console.warn("[sim] auto default failed", (err as Error).message);
      }
    }
  }
}

let running = false;
export function startSim() {
  setInterval(() => {
    if (running) return;
    running = true;
    tick().catch((err) => console.error("[sim] tick failed", err)).finally(() => (running = false));
  }, TICK_MS);
  // keep a long-lived dev process's memory (and tick() cost) bounded; see domain.ts's pruneOldEmergencies
  setInterval(() => pruneOldEmergencies(), 60_000);
}

// used by scenarios
export { distanceM, audit, offerPayload };
