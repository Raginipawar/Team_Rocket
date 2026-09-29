// WebSocket fan-out for the mock core (technical.md §8): envelope with a monotonic
// per-channel seq, channel authorisation, and per-role projection so patients and
// families never receive scores or clinical fields (T31).

import type { WebSocket } from "ws";

export type WsRole = "patient" | "family" | "paramedic" | "hospital_staff" | "ops";

type Sub = {
  ws: WebSocket;
  role: WsRole;
  userId: string | null;
  hospitalId: string | null;
  ambulanceId: string | null;
  trackEmergencyId: string | null;
  /** internal channel -> the name the client subscribed with (track tokens are stored hashed) */
  channels: Map<string, string>;
};

const subs = new Set<Sub>();
const seqs = new Map<string, number>();

/** Events a family (track token) may receive, per ws-events.schema.json channels. */
const TRACK_EVENTS = new Set(["emergency.status", "ambulance.location", "hospital.selected", "handoff.ready", "reroute"]);

export type { Sub };

export function addSub(s: Omit<Sub, "channels">) {
  const sub: Sub = { ...s, channels: new Map() };
  subs.add(sub);
  return sub;
}

export function removeSub(sub: Sub) {
  subs.delete(sub);
}

export function allowed(sub: Sub, channel: string, canSeeEmergency: (role: WsRole, emergencyId: string, sub: Sub) => boolean) {
  if (channel === "ops") return sub.role === "ops";
  if (channel.startsWith("track:")) return sub.role === "family" || sub.role === "ops";
  if (channel.startsWith("ambulance:")) return sub.role === "paramedic" && channel === `ambulance:${sub.ambulanceId}`;
  if (channel.startsWith("hospital:")) return sub.role === "hospital_staff" && channel === `hospital:${sub.hospitalId}`;
  if (channel.startsWith("emergency:")) {
    if (sub.role === "family") return false;
    return sub.role === "ops" || canSeeEmergency(sub.role, channel.slice("emergency:".length), sub);
  }
  return false;
}

function project(role: WsRole, event: string, data: Record<string, unknown>): Record<string, unknown> | null {
  if (role === "ops" || role === "hospital_staff" || role === "paramedic") return data;
  if (role === "family") {
    if (!TRACK_EVENTS.has(event)) return null;
    if (event === "hospital.selected") {
      const h = data.hospital as Record<string, unknown> | undefined;
      return { hospital: h ? { name: h.name, address: h.address, location: h.location, entrance_note: h.er_entrance_note } : null, eta: data.eta };
    }
    return data;
  }
  // patient
  if (event === "hospital.selected") return { hospital: data.hospital, eta: data.eta, rank_explanation: {} };
  return data;
}

export function publish(channel: string, event: string, data: Record<string, unknown>) {
  const seq = (seqs.get(channel) ?? 0) + 1;
  seqs.set(channel, seq);
  const ts = new Date().toISOString();
  for (const s of subs) {
    if (!s.channels.has(channel) || s.ws.readyState !== 1) continue;
    const d = project(s.role, event, data);
    if (!d) continue;
    s.ws.send(JSON.stringify({ event, channel: s.channels.get(channel) ?? channel, seq, ts, data: d }));
  }
}

/** A real person has this ambulance's app open (so no driver bot acts for it). */
export function ambulanceIsLive(ambulanceId: string) {
  for (const s of subs) if (s.role === "paramedic" && s.ambulanceId === ambulanceId && s.ws.readyState === 1) return true;
  return false;
}

/** A real person has this hospital's dashboard open (so no hospital bot answers). */
export function hospitalIsLive(hospitalId: string) {
  for (const s of subs) if (s.role === "hospital_staff" && s.hospitalId === hospitalId && s.ws.readyState === 1) return true;
  return false;
}

export function liveCounts() {
  let n = 0;
  for (const s of subs) if (s.ws.readyState === 1) n++;
  return n;
}
