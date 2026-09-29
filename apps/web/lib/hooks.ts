"use client";

import { useEffect, useState } from "react";

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

/** Short haptic feedback (UI rule 5). */
export function buzz(pattern: number | number[] = 40) {
  try {
    navigator.vibrate?.(pattern);
  } catch {
    /* not supported */
  }
}
