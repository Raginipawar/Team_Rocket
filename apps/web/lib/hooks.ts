"use client";

import { useEffect, useRef, useState } from "react";
import { post } from "./api";

/** Ticking clock for countdowns and "5 s ago" labels. */
export function useNow(ms = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

export type Geo = { lat: number; lng: number; accuracy: number } | null;
export type GeoState = { pos: Geo; status: "idle" | "asking" | "ok" | "denied" | "unavailable" };

/** Browser location with accuracy (§16.2 location + accuracy indicator). */
export function useGeolocation(watch = true): GeoState & { request: () => void } {
  const [state, setState] = useState<GeoState>({ pos: null, status: "idle" });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setState({ pos: null, status: "unavailable" });
      return;
    }
    setState((s) => ({ ...s, status: s.pos ? "ok" : "asking" }));
    const ok = (p: GeolocationPosition) => setState({ pos: { lat: p.coords.latitude, lng: p.coords.longitude, accuracy: Math.round(p.coords.accuracy) }, status: "ok" });
    const fail = (e: GeolocationPositionError) => setState((s) => ({ pos: s.pos, status: e.code === 1 ? "denied" : "unavailable" }));
    const opts = { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 };
    if (watch) {
      const id = navigator.geolocation.watchPosition(ok, fail, opts);
      return () => navigator.geolocation.clearWatch(id);
    }
    navigator.geolocation.getCurrentPosition(ok, fail, opts);
  }, [watch, tick]);
  return { ...state, request: () => setTick((x) => x + 1) };
}

/** Reports this patient's live location to the backend periodically while
 * the app is open (watchPosition already fires on movement) -- so "call
 * ambulance for them" (family space) can use a family member's own real
 * recent location instead of the caller's, who may not even be with them.
 * Throttled: watchPosition can fire far more often than is useful to send. */
/** Registers this device for push (permission + FCM token) once per
 * session and sends the token to the backend -- "even if the screen is
 * not currently on" requires a registered token to send to at all. */
export function usePushRegistration(enabled: boolean) {
  const done = useRef(false);
  useEffect(() => {
    if (!enabled || done.current) return;
    done.current = true;
    void (async () => {
      const { registerForPush } = await import("./firebase");
      const token = await registerForPush();
      if (token) void post("/me/push-subscriptions", { fcm_token: token }).catch(() => {});
    })();
  }, [enabled]);
}

export function useLocationPing(enabled: boolean, minIntervalMs = 15000) {
  const geo = useGeolocation(enabled);
  const lastSentAt = useRef(0);
  useEffect(() => {
    if (!enabled || !geo.pos) return;
    const now = Date.now();
    if (now - lastSentAt.current < minIntervalMs) return;
    lastSentAt.current = now;
    void post("/me/location", { lat: geo.pos.lat, lng: geo.pos.lng, accuracy_m: geo.pos.accuracy }).catch(() => {
      /* best-effort -- a missed ping just means a slightly staler fallback location later */
    });
  }, [enabled, geo.pos, minIntervalMs]);
}

/** Short haptic feedback (UI rule 5). */
export function buzz(pattern: number | number[] = 40) {
  try {
    navigator.vibrate?.(pattern);
  } catch {
    /* not supported */
  }
}
