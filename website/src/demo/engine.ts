// The shared demo emergency. Explicit actions are stored as timestamps; every other
// state (position, ETA, arrival, hospital timeouts, reroutes) is derived from them, so
// every open tab computes the same picture without needing a coordinator.
import type { Category, Severity } from "./data";

export type ForWhom = string; // a family member id, "rahul" for yourself, or "someone"
export type Channel = "button" | "voice" | "text";
export type Signal = "ok" | "weak" | "lost";

export interface DemoState {
  v: number;
  autoplay: boolean;
  autoplaySince: number;
  online: boolean;
  signal: Signal;
  forWhom: ForWhom;
  channel: Channel;
  text: string;
  sosAt: number | null;
  acceptedAt: number | null;
  confirmedAt: number | null;
  confirm: { category: Category; severity: Severity; patients: number; changed: boolean };
  gfAcceptedAt: number | null;
  gfRejectedAt: number | null;
  gfRejectReason: string;
  room: string;
  familyChoice: { hospital: string; at: number; by: string } | null;
  worsenedAt: number | null;
  receivedAt: number | null;
  readyAt: number | null;
  cancelledAt: number | null;
  cancelReason: string;
  closedAt: number | null;
  answers: { id: string; answer: string; at: number }[];
}

export const initialState = (): DemoState => ({
  v: 0,
  autoplay: true,
  autoplaySince: Date.now(),
  online: true,
  signal: "ok",
  forWhom: "papa",
  channel: "voice",
  text: "",
  sosAt: null,
  acceptedAt: null,
  confirmedAt: null,
  confirm: { category: "cardiac", severity: "critical", patients: 1, changed: false },
  gfAcceptedAt: null,
  gfRejectedAt: null,
  gfRejectReason: "",
  room: "Resus Bay 2",
  familyChoice: null,
  worsenedAt: null,
  receivedAt: null,
  readyAt: null,
  cancelledAt: null,
  cancelReason: "",
  closedAt: null,
  answers: [],
});

// Timings (ms). Driving is compressed so a whole emergency plays out in about two minutes.
export const T = {
  sending: 1500,
  requested: 2500,
  offerRing: 20000,
  driveToPatient: 30000,
  choosing: 1600,
  hospitalTimeout: 45000,
  botHospital: 4000,
  driveToHospital: 30000,
  // autoplay "bot" delays
  autoAccept: 7000,
  autoConfirm: 6000,
  autoHospital: 8000,
  autoReceive: 9000,
  autoReady: 6000,
};

export type Stage =
  | "idle" | "sending" | "requested" | "offered" | "going" | "arrived" | "choosing"
  | "asking" | "transporting" | "atDoor" | "handedOver" | "cancelled";

export interface Derived {
  stage: Stage;
  active: boolean;
  offeredAt: number | null;
  offerSecsLeft: number;
  offerRound: number;
  accepted: number | null;
  arrivedAt: number | null;
  confirmed: number | null;
  askedAt: number | null;
  hospitalId: string;
  hospitalAskedAt: number | null;
  hospitalAcceptedAt: number | null;
  hospitalSecsLeft: number;
  reroute: null | { from: string; to: string; reason: string; at: number };
  progress: number; // 0..1 along the current leg
  leg: "patient" | "hospital" | null;
  etaMin: number;
  doorAt: number | null;
  doorSecs: number;
  received: number | null;
  ready: number | null;
  ambulance: "offline" | "available" | "incoming" | "going" | "atScene" | "transporting" | "atHospital" | "cleaning";
}

const clamp = (n: number, a = 0, b = 1) => Math.min(b, Math.max(a, n));

export function derive(s: DemoState, now: number): Derived {
  const auto = (base: number, delay: number) =>
    s.autoplay ? Math.max(base + delay, s.autoplaySince + 1500) : null;

  const base: Derived = {
    stage: "idle", active: false, offeredAt: null, offerSecsLeft: 0, offerRound: 0, accepted: null,
    arrivedAt: null, confirmed: null, askedAt: null, hospitalId: "greenfield", hospitalAskedAt: null,
    hospitalAcceptedAt: null, hospitalSecsLeft: 0, reroute: null, progress: 0, leg: null, etaMin: 0,
    doorAt: null, doorSecs: 0, received: null, ready: null, ambulance: s.online ? "available" : "offline",
  };

  if (s.sosAt === null || s.closedAt !== null) return base;
  if (s.cancelledAt !== null) return { ...base, stage: "cancelled" };

  const d = { ...base, active: true };
  const offeredAt = s.sosAt + T.sending + T.requested;
  d.offeredAt = offeredAt;

  const accepted = s.acceptedAt ?? auto(offeredAt, T.autoAccept);
  if (now < s.sosAt + T.sending) return { ...d, stage: "sending" };
  if (now < offeredAt) return { ...d, stage: "requested" };
  if (accepted === null || now < accepted) {
    const el = now - offeredAt;
    return {
      ...d, stage: "offered", ambulance: s.online ? "incoming" : "offline",
      offerRound: Math.floor(el / T.offerRing),
      offerSecsLeft: Math.ceil((T.offerRing - (el % T.offerRing)) / 1000),
    };
  }
  d.accepted = accepted;

  const arrivedAt = accepted + T.driveToPatient;
  if (now < arrivedAt) {
    const p = clamp((now - accepted) / T.driveToPatient);
    return { ...d, stage: "going", ambulance: "going", leg: "patient", progress: p, etaMin: Math.max(1, Math.ceil((1 - p) * 9)) };
  }
  d.arrivedAt = arrivedAt;

  const confirmed = s.confirmedAt ?? auto(arrivedAt, T.autoConfirm);
  if (confirmed === null || now < confirmed) return { ...d, stage: "arrived", ambulance: "atScene", leg: "patient", progress: 1 };
  d.confirmed = confirmed;

  const askedAt = confirmed + T.choosing;
  d.askedAt = askedAt;
  if (now < askedAt) return { ...d, stage: "choosing", ambulance: "transporting" };

  // Which hospital, and when did it accept?
  let hospitalId = "greenfield";
  let hAsked = askedAt;
  let hAccepted: number | null = null;
  let reroute: Derived["reroute"] = null;

  const fc = s.familyChoice && s.familyChoice.at >= askedAt ? s.familyChoice : null;
  const gAccept = s.gfAcceptedAt ?? auto(askedAt, T.autoHospital);
  const gFail = s.gfRejectedAt ?? askedAt + T.hospitalTimeout;
  if (gAccept !== null && gAccept < gFail && (!fc || gAccept < fc.at)) {
    hAccepted = gAccept;
  } else if (fc && fc.at < gFail) {
    hospitalId = fc.hospital; hAsked = fc.at; hAccepted = fc.at + T.botHospital;
    reroute = { from: "greenfield", to: fc.hospital, reason: `family choice (${fc.by})`, at: fc.at };
  } else if (now >= gFail) {
    hospitalId = "riverside"; hAsked = gFail; hAccepted = gFail + T.botHospital;
    reroute = {
      from: "greenfield", to: "riverside",
      reason: s.gfRejectedAt ? (s.gfRejectReason || "bed no longer available").toLowerCase() : "no response in 45 s",
      at: gFail,
    };
  }
  // A family choice made after a hospital already accepted switches destination too.
  if (fc && hAccepted !== null && fc.at >= hAccepted && fc.hospital !== hospitalId) {
    reroute = { from: hospitalId, to: fc.hospital, reason: `family choice (${fc.by})`, at: fc.at };
    hospitalId = fc.hospital; hAsked = fc.at; hAccepted = fc.at + T.botHospital;
  }

  d.hospitalId = hospitalId;
  d.hospitalAskedAt = hAsked;
  d.reroute = reroute;

  if (hAccepted === null || now < hAccepted) {
    const secsLeft = hospitalId === "greenfield" ? Math.max(0, Math.ceil((askedAt + T.hospitalTimeout - now) / 1000)) : 0;
    return { ...d, stage: "asking", ambulance: "transporting", hospitalSecsLeft: secsLeft, leg: "hospital", progress: 0, etaMin: 11 };
  }
  d.hospitalAcceptedAt = hAccepted;

  const doorAt = hAccepted + T.driveToHospital;
  if (now < doorAt) {
    const p = clamp((now - hAccepted) / T.driveToHospital);
    return { ...d, stage: "transporting", ambulance: "transporting", leg: "hospital", progress: p, etaMin: Math.max(1, Math.ceil((1 - p) * 11)) };
  }
  d.doorAt = doorAt;

  const received = s.receivedAt ?? auto(doorAt, T.autoReceive);
  // Door time is shown 8x faster so a demo wait reads like minutes.
  if (received === null || now < received) {
    return { ...d, stage: "atDoor", ambulance: "atHospital", leg: "hospital", progress: 1, doorSecs: Math.floor(((now - doorAt) / 1000) * 8) };
  }
  d.received = received;
  d.doorSecs = Math.floor(((received - doorAt) / 1000) * 8);

  const ready = s.readyAt ?? auto(received, T.autoReady);
  d.ready = ready;
  const amb = ready === null || now < ready ? "cleaning" : s.online ? "available" : "offline";
  return { ...d, stage: "handedOver", ambulance: amb, leg: "hospital", progress: 1 };
}
