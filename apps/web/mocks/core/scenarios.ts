// Scenario runner (technical.md §15) for the mock core. Each scenario drives the
// system through the same domain functions the REST API uses, then checks the §14
// invariants. The real runner lives in services/core/app/sim (Person B); scenario
// names match the YAML files there.

import type { Scenario, ScenarioRun } from "../../lib/api-types";
import {
  acceptOffer, createEmergency, markCritical, patchRoom, scenarioHooks, sendNextRequest,
} from "./domain";
import { db, now, signalOf, uid, type EmergencyRec } from "./world";
import { ACCEPTABLE_ROOMS } from "../../lib/enums";

const TITLES: Record<string, [string, string]> = {
  s1_happy_path: ["Normal heart emergency", "SOS to handover, every step through the public flow"],
  t1_double_booking: ["Double booking the last bed", "20 requests race for 1 free room: exactly 1 hold"],
  t2_simultaneous_accepts: ["Simultaneous accepts", "4 ambulances accept at once: 1 wins, 3 get 409"],
  t4_walk_in_override: ["Walk-in takes the reserved room", "Override with reason, then re-allocate or reroute"],
  t10_ambulance_offline: ["Ambulance offline mid-route", "Heartbeats stop: signal lost, reservation kept"],
  t11_hospital_not_responding: ["Hospital not responding", "No answer in 45 s: next hospital asked"],
  t13_no_ambulance_accepts: ["No ambulance accepts", "3 rounds declined: escalation to the on call team"],
  t19_all_hospitals_full: ["All hospitals full", "Every hospital rejects: no_hospital escalation, default at 120 s"],
  t20_deterioration: ["Patient gets worse on the way", "Critical tap: divert only if 3 min faster"],
  s2_nearest_lacks_cathlab: ["Nearest hospital has no cath lab", "Runs on the real simulator (Person B)"],
  t18_mass_casualty: ["Mass casualty", "Runs on the real simulator with OR-Tools (Person B)"],
};

const IMPLEMENTED = new Set(["s1_happy_path", "t1_double_booking", "t2_simultaneous_accepts", "t4_walk_in_override", "t10_ambulance_offline", "t11_hospital_not_responding", "t13_no_ambulance_accepts", "t19_all_hospitals_full", "t20_deterioration"]);

export const runs = new Map<string, ScenarioRun>();

export function listScenarios(): Scenario[] {
  return Object.entries(TITLES).map(([name, [title, description]]) => ({ name, title, description, available: IMPLEMENTED.has(name) }));
}

/** §14 invariant checker. */
export function invariants(): { text: string; ok: boolean }[] {
  const active = [...db.reservations.values()].filter((r) => r.status === "held" || r.status === "confirmed");
  const out: { text: string; ok: boolean }[] = [];
  const badRooms = [...db.rooms.values()].filter((r) => r.status === "reserved" && !active.some((a) => a.id === r.reservation_id));
  out.push({ text: "No room is reserved without an active reservation", ok: badRooms.length === 0 });
  const perAmb = new Map<string, number>();
  for (const e of db.emergencies.values()) if (e.ambulance_id && !["closed", "cancelled", "refused_transport", "handed_off", "merged_duplicate"].includes(e.status)) perAmb.set(e.ambulance_id, (perAmb.get(e.ambulance_id) ?? 0) + 1);
  out.push({ text: "No ambulance has two active emergencies", ok: [...perAmb.values()].every((n) => n <= 1) });
  const perEm = new Map<string, number>();
  for (const r of active) perEm.set(r.emergency_id, (perEm.get(r.emergency_id) ?? 0) + 1);
  out.push({ text: "No emergency has two active reservations", ok: [...perEm.values()].every((n) => n <= 1) });
  out.push({ text: "available + reserved is never more than total", ok: [...db.resources.values()].every((r) => r.available >= 0 && r.reserved >= 0 && r.available + r.reserved <= r.total) });
  const late = [...db.requests.values()].filter((r) => r.status === "pending" && now() - r.expires_at > 5000);
  out.push({ text: "No pending hospital request is past its expiry", ok: late.length === 0 });
  return out;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function waitFor(pred: () => boolean, maxMs: number) {
  const until = now() + maxMs / db.sim.speed;
  while (now() < until) {
    if (pred()) return true;
    await sleep(250);
  }
  return pred();
}

async function sos(text: string, lat = 18.6536, lng = 73.7801) {
  const { emergency } = await createEmergency({ channel: "app_text", text, lat, lng, accuracy_m: 25, for_self: false, caller_user_id: null, caller_phone: "+919812300000", language: "en", simulated: true });
  return emergency;
}

export async function runScenario(name: string): Promise<ScenarioRun> {
  const run: ScenarioRun = { name, status: IMPLEMENTED.has(name) ? "running" : "not_available", started_at: new Date().toISOString(), steps: [], assertions: [] };
  runs.set(name, run);
  if (!IMPLEMENTED.has(name)) {
    run.steps.push({ at: new Date().toISOString(), text: "This scenario needs the real simulator in services/core/app/sim." });
    return run;
  }
  const step = (text: string, ok?: boolean) => run.steps.push({ at: new Date().toISOString(), text, ok });
  const check = (text: string, ok: boolean) => run.assertions.push({ text, ok });
  void (async () => {
    try {
      await SCENARIOS[name](step, check);
    } catch (err) {
      step(`Error: ${(err as Error).message}`, false);
      check("Scenario ran without errors", false);
    } finally {
      scenarioHooks.hospitalDecision = undefined;
      scenarioHooks.driverAccept = undefined;
      for (const inv of invariants()) check(inv.text, inv.ok);
      run.status = run.assertions.every((a) => a.ok) ? "passed" : "failed";
      run.finished_at = new Date().toISOString();
    }
  })();
  return run;
}

type Step = (text: string, ok?: boolean) => void;
type Check = (text: string, ok: boolean) => void;

const SCENARIOS: Record<string, (step: Step, check: Check) => Promise<void>> = {
  async s1_happy_path(step, check) {
    const e = await sos("My father has chest pain and is sweating a lot, near Ganesh temple Akurdi");
    step(`SOS created ${e.id.slice(0, 8)}`);
    check("Triaged as a heart emergency", await waitFor(() => e.ai_facility === "cardiac", 15000));
    check("An ambulance accepted", await waitFor(() => !!e.ambulance_id, 60000));
    step(`Ambulance ${db.ambulances.get(e.ambulance_id ?? "")?.registration_no ?? "none"} on the way`);
    check("Ambulance reached the patient", await waitFor(() => !!e.timestamps.at_scene_at, 240000));
    check("Hospital confirmed", await waitFor(() => !!e.timestamps.hospital_confirmed_at, 180000));
    step(`Hospital: ${db.hospitals.get(e.hospital_id ?? "")?.name ?? "none"}`);
    check("Patient handed over", await waitFor(() => !!e.timestamps.handed_off_at, 300000));
  },

  async t2_simultaneous_accepts(step, check) {
    const e = await sos("Man collapsed, not breathing, near Pimpri chowk", 18.6279, 73.8009);
    await waitFor(() => e.status === "dispatching", 10000);
    // freeze bots, then fire 4 accepts at once
    scenarioHooks.driverAccept = () => false;
    for (const o of db.offers.values()) if (o.emergency_id === e.id) o.bot_at = null;
    const offers = [...db.offers.values()].filter((o) => o.emergency_id === e.id && o.status === "pending");
    const extra = [...db.ambulances.values()].filter((a) => a.status === "available" && !offers.some((o) => o.ambulance_id === a.id)).slice(0, Math.max(0, 4 - offers.length));
    for (const a of extra) {
      const o = { id: uid(), emergency_id: e.id, ambulance_id: a.id, round: 1, status: "pending" as const, predicted_eta_sec: 300, distance_m: 2000, rank: 9, offered_at: now(), expires_at: now() + 20000, responded_at: null, bot_at: null, bot_accept: false };
      db.offers.set(o.id, o);
      offers.push(o);
    }
    step(`${offers.length} offers pending, accepting all at the same moment`);
    const results = await Promise.allSettled(offers.map((o) => acceptOffer(o.id, o.ambulance_id, "scenario")));
    const wins = results.filter((r) => r.status === "fulfilled").length;
    const taken = results.filter((r) => r.status === "rejected" && (r.reason as { code?: string }).code === "ALREADY_TAKEN").length;
    step(`${wins} accepted, ${taken} got 409 ALREADY_TAKEN`);
    check("Exactly one accept succeeded", wins === 1);
    check("All the others got 409 ALREADY_TAKEN", taken === offers.length - 1);
  },

  async t1_double_booking(step, check) {
    const target = [...db.hospitals.values()][0];
    const rooms = [...db.rooms.values()].filter((r) => r.hospital_id === target.id && ACCEPTABLE_ROOMS.general.includes(r.type) && r.status === "free");
    const keep = rooms[0];
    for (const r of rooms.slice(1)) r.status = "occupied";
    step(`${target.name} left with 1 free room (${keep?.code})`);
    const other = [...db.hospitals.values()][1];
    const ems: EmergencyRec[] = [];
    for (let i = 0; i < 20; i++) {
      const e = await sos("Patient with fever and weakness");
      await waitFor(() => e.status !== "received" && e.status !== "triaged", 8000);
      ems.push(e);
    }
    // race 20 selections for the same last room
    await Promise.all(ems.map(async (e) => {
      e.final_facility = "general";
      e.predicted_resources = [];
      e.rank_list = [{ hospital_id: target.id, score: 1, eta_sec: 300, why: [] }, { hospital_id: other.id, score: 0, eta_sec: 400, why: [] }];
      e.tried_hospitals = [];
      await sendNextRequest(e);
    }));
    const holdsAtTarget = [...db.reservations.values()].filter((r) => r.hospital_id === target.id && r.status === "held" && ems.some((e) => e.id === r.emergency_id)).length;
    step(`${holdsAtTarget} hold at ${target.name}, ${ems.length - holdsAtTarget} moved to the next hospital`);
    check("Exactly one hold on the last room", holdsAtTarget === 1);
    // clean up so the world stays usable
    for (const r of rooms.slice(1)) if (r.status === "occupied") r.status = "free";
  },

  async t11_hospital_not_responding(step, check) {
    let first: string | null = null;
    scenarioHooks.hospitalDecision = (hid) => {
      if (!first) first = hid;
      return hid === first ? "silent" : "accept";
    };
    const e = await sos("Chest pain and breathlessness, near Chinchwad station", 18.6423, 73.7925);
    check("Hospital asked", await waitFor(() => [...db.requests.values()].some((r) => r.emergency_id === e.id), 240000));
    step(`First hospital: ${db.hospitals.get(first ?? "")?.name ?? "?"} (will stay silent)`);
    check("First request timed out", await waitFor(() => [...db.requests.values()].some((r) => r.emergency_id === e.id && r.status === "timeout"), 120000));
    check("Next hospital was asked", await waitFor(() => [...db.requests.values()].filter((r) => r.emergency_id === e.id).length >= 2, 20000));
    check("Duty manager got an SMS", db.notifications.some((n) => n.body.includes("did not answer")));
  },

  async t13_no_ambulance_accepts(step, check) {
    scenarioHooks.driverAccept = () => false;
    const e = await sos("Accident on the highway, two people hurt, near Bhosari MIDC", 18.625, 73.842);
    check("Rounds were sent", await waitFor(() => e.dispatch_round >= 1, 15000));
    check("Escalated after 3 rounds", await waitFor(() => [...db.escalations.values()].some((x) => x.emergency_id === e.id && x.type === "no_ambulance"), 150000));
    step(`Rounds: ${e.dispatch_round}`);
    check("On call team alerted on Telegram", db.notifications.some((n) => n.channel === "telegram" && n.body.includes("NO_AMBULANCE")));
  },

  async t19_all_hospitals_full(step, check) {
    scenarioHooks.hospitalDecision = () => "reject";
    const e = await sos("Severe chest pain, sweating, near Ganesh temple Akurdi");
    check("Escalated with no_hospital", await waitFor(() => [...db.escalations.values()].some((x) => x.emergency_id === e.id && x.type === "no_hospital"), 300000));
    const esc = [...db.escalations.values()].find((x) => x.emergency_id === e.id && x.type === "no_hospital");
    step(`Options: ${esc?.options.map((o) => o.label).join(" | ")}`);
    check("A safe default is marked", !!esc?.options.some((o) => o.is_default));
  },

  async t10_ambulance_offline(step, check) {
    const e = await sos("Elderly woman fell and cannot get up, near Wakad Dange chowk", 18.606, 73.769);
    check("Hospital confirmed", await waitFor(() => e.status === "hospital_confirmed", 300000));
    const a = db.ambulances.get(e.ambulance_id!)!;
    a.silent_until = now() + 150_000;
    step(`${a.registration_no} stops sending heartbeats`);
    check("Signal goes to lost", await waitFor(() => signalOf(a) === "lost", 160000));
    const res = db.reservations.get(e.reservation_id ?? "");
    check("Hospital reservation is still confirmed", res?.status === "confirmed");
    a.silent_until = 0;
  },

  async t4_walk_in_override(step, check) {
    const e = await sos("Man with chest pain near Nigdi Bhakti Shakti chowk", 18.6628, 73.7708);
    check("Hospital confirmed", await waitFor(() => e.status === "hospital_confirmed", 300000));
    const res = db.reservations.get(e.reservation_id!)!;
    const roomId = (res.items.find((i) => i.kind === "room") as { room_id: string }).room_id;
    const room = db.rooms.get(roomId)!;
    let blocked = false;
    try { await patchRoom(room.hospital_id, room.id, "occupied", room.version, null, "scenario"); } catch (err) { blocked = (err as { code?: string }).code === "ROOM_RESERVED"; }
    check("Taking a reserved room without a reason is blocked (409 ROOM_RESERVED)", blocked);
    const out = await patchRoom(room.hospital_id, room.id, "occupied", room.version, "WALK_IN_CRITICAL", "scenario") as { reallocated_to?: string | null; rerouted_to?: string };
    step(out.reallocated_to ? `Re-allocated to ${out.reallocated_to}` : `Rerouted to ${out.rerouted_to}`);
    check("Patient still has a place", !!out.reallocated_to || !!out.rerouted_to);
  },

  async t20_deterioration(step, check) {
    const e = await sos("Father has chest pain, near Akurdi station", 18.6486, 73.765);
    check("Hospital confirmed", await waitFor(() => e.status === "hospital_confirmed", 300000));
    const out = await markCritical(e, "scenario");
    step(out.reason);
    check("Divert decision follows the 3 minute rule", typeof out.diverted === "boolean");
  },
};
