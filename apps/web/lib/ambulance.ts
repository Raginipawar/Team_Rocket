"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, get, post } from "./api";
import type { ActiveJob, AmbulanceSelf, Offer } from "./api-types";
import { flush, onQueueChange } from "./offline-queue";

/** GET /ambulance/me (not in §7.4 yet; see docs/FRONTEND_GAPS.md). Falls back to the last known state. */
export async function fetchSelf(): Promise<AmbulanceSelf | null> {
  try {
    const me = await get<AmbulanceSelf>("/ambulance/me");
    try {
      localStorage.setItem("gh-amb-self", JSON.stringify(me));
    } catch {
      /* ignore */
    }
    return me;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      try {
        return JSON.parse(localStorage.getItem("gh-amb-self") ?? "null");
      } catch {
        return null;
      }
    }
    throw e;
  }
}

/** Offers come as the §7.4 payload; the flat ws-events.schema.json fields are mapped too. */
export function normalizeOffer(raw: Record<string, unknown>): Offer {
  const r = raw as Record<string, never>;
  if (r.pickup && r.summary) return raw as unknown as Offer;
  return {
    offer_id: r.offer_id, emergency_id: r.emergency_id, expires_at: r.expires_at,
    pickup: { lat: r.pickup_lat ?? 0, lng: r.pickup_lng ?? 0, landmark: null },
    eta_to_pickup_sec: r.eta_sec ?? 0, distance_m: r.distance_m ?? 0,
    summary: { acuity: r.acuity ?? "critical", facility: r.facility ?? "general", patient_count: 1 },
  };
}

export async function fetchOffers(): Promise<Offer[]> {
  try {
    const list = await get<Record<string, unknown>[]>("/ambulance/offers");
    return list.map(normalizeOffer);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return []; // router not live yet: offers still arrive over WS
    throw e;
  }
}

export async function fetchActive(): Promise<ActiveJob | null> {
  try {
    const r = await get<{ job: ActiveJob | null } | ActiveJob | null>("/ambulance/active");
    if (!r) return null;
    return "job" in r ? r.job : (r as ActiveJob);
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 204)) return null;
    throw e;
  }
}

/** Accept: A's router serves /ambulance/offers/{id}/accept; the spec says /offers/{id}/accept. */
export async function acceptOffer(id: string) {
  try {
    return await post<{ emergency_id: string }>(`/ambulance/offers/${id}/accept`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404 && e.code === "NOT_FOUND" && !e.message.toLowerCase().includes("offer")) {
      return post<{ emergency_id: string }>(`/offers/${id}/accept`);
    }
    throw e;
  }
}

export async function declineOffer(id: string, reason?: string) {
  try {
    return await post(`/ambulance/offers/${id}/decline`, { reason });
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return post(`/offers/${id}/decline`, { reason });
    throw e;
  }
}

/** Heartbeat every 5 s while on duty (§4 HEARTBEAT_INTERVAL_SEC), with the phone's GPS. Queued when offline. */
export function useHeartbeat(active: boolean, onBeat?: (d: { lat: number; lng: number; heading?: number; speed_kmh?: number }) => void) {
  const last = useRef<GeolocationPosition | null>(null);
  useEffect(() => {
    if (!active || !navigator.geolocation) return;
    const id = navigator.geolocation.watchPosition((p) => (last.current = p), () => {}, { enableHighAccuracy: true, maximumAge: 5000 });
    return () => navigator.geolocation.clearWatch(id);
  }, [active]);
  useEffect(() => {
    if (!active) return;
    const beat = () => {
      const p = last.current;
      if (!p) return;
      const d = {
        lat: p.coords.latitude, lng: p.coords.longitude, heading: p.coords.heading ?? undefined,
        speed_kmh: p.coords.speed != null ? p.coords.speed * 3.6 : undefined, accuracy_m: p.coords.accuracy, client_ts: new Date().toISOString(),
      };
      onBeat?.(d);
      // latest wins by client_ts on the server, so a missed beat is simply replaced by the next one
      void post("/ambulance/heartbeat", d).catch(() => {});
    };
    const id = setInterval(beat, 5000);
    return () => clearInterval(id);
  }, [active, onBeat]);
}

/** Offline queue size + replay on reconnect (§11.12). */
export function useOfflineQueue(token: () => string | null) {
  const [queued, setQueued] = useState(0);
  const [online, setOnline] = useState(true);
  useEffect(() => {
    setOnline(navigator.onLine);
    const off = onQueueChange(setQueued);
    const up = () => {
      setOnline(true);
      void flush(token);
    };
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    const id = setInterval(() => navigator.onLine && void flush(token), 10_000);
    return () => {
      off();
      clearInterval(id);
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, [token]);
  return { queued, online };
}

/** Loud repeating alert for a new offer: sound + vibration (§16.3). */
export function useOfferAlert(ringing: boolean, enabled = true) {
  useEffect(() => {
    if (!ringing || !enabled) return;
    let ctx: AudioContext | null = null;
    try {
      ctx = new AudioContext();
    } catch {
      return;
    }
    const ring = () => {
      if (!ctx) return;
      [0, 0.18, 0.36].forEach((t, i) => {
        const o = ctx!.createOscillator();
        const g = ctx!.createGain();
        o.type = "square";
        o.frequency.value = i % 2 ? 988 : 784;
        g.gain.setValueAtTime(0.18, ctx!.currentTime + t);
        g.gain.exponentialRampToValueAtTime(0.001, ctx!.currentTime + t + 0.16);
        o.connect(g).connect(ctx!.destination);
        o.start(ctx!.currentTime + t);
        o.stop(ctx!.currentTime + t + 0.17);
      });
      try {
        navigator.vibrate?.([300, 150, 300]);
      } catch {
        /* ignore */
      }
    };
    ring();
    const id = setInterval(ring, 1500);
    return () => {
      clearInterval(id);
      void ctx?.close();
    };
  }, [ringing, enabled]);
}

export type DarkPref = "auto" | "on" | "off";
export function useNightMode(): [boolean, DarkPref, (p: DarkPref) => void] {
  const [pref, setPref] = useState<DarkPref>("auto");
  const [hour, setHour] = useState(12);
  useEffect(() => {
    try {
      setPref((localStorage.getItem("gh-amb-dark") as DarkPref) ?? "auto");
    } catch {
      /* ignore */
    }
    setHour(new Date().getHours());
    const id = setInterval(() => setHour(new Date().getHours()), 60_000);
    return () => clearInterval(id);
  }, []);
  const set = (p: DarkPref) => {
    setPref(p);
    try {
      localStorage.setItem("gh-amb-dark", p);
    } catch {
      /* ignore */
    }
  };
  const dark = pref === "on" || (pref === "auto" && (hour >= 19 || hour < 6));
  return [dark, pref, set];
}
