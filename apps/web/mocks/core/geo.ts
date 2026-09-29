// Geometry for the mock core: distances, headings, routes and movement along a route.
// Routes come from OSRM (the team's self-hosted instance per technical.md §22, or the
// public demo server by default). If OSRM is unreachable we fall back to a straight
// line and say so in the route's `source`, never inventing roads.

import { decodePolyline6, encodePolyline6 } from "../../lib/polyline";
import type { LatLng } from "../../lib/api-types";
import { MOCK } from "./config";

const R = 6371000;
const rad = (d: number) => (d * Math.PI) / 180;

export function distanceM(a: LatLng, b: LatLng) {
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export function bearing(a: LatLng, b: LatLng) {
  const y = Math.sin(rad(b.lng - a.lng)) * Math.cos(rad(b.lat));
  const x = Math.cos(rad(a.lat)) * Math.sin(rad(b.lat)) - Math.sin(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.cos(rad(b.lng - a.lng));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

export type Route = {
  coords: [number, number][]; // [lat, lng]
  cum: number[]; // cumulative metres at each vertex
  distance_m: number;
  duration_sec: number; // real-world driving time
  polyline6: string;
  steps: string[];
  source: "osrm" | "straight_line";
};

function build(coords: [number, number][], duration: number, steps: string[], source: Route["source"]): Route {
  const cum = [0];
  for (let i = 1; i < coords.length; i++) {
    cum.push(cum[i - 1] + distanceM({ lat: coords[i - 1][0], lng: coords[i - 1][1] }, { lat: coords[i][0], lng: coords[i][1] }));
  }
  const distance = cum[cum.length - 1] || 1;
  return { coords, cum, distance_m: distance, duration_sec: duration, polyline6: encodePolyline6(coords), steps, source };
}

const cache = new Map<string, Route>();
let osrmDown = 0;

function osrmBase() {
  if (MOCK.OSRM_URL) return MOCK.OSRM_URL;
  return "https://router.project-osrm.org";
}

function describeStep(s: { maneuver?: { type?: string; modifier?: string }; name?: string; distance?: number }) {
  const type = s.maneuver?.type ?? "";
  const mod = s.maneuver?.modifier ?? "";
  const road = s.name ? ` onto ${s.name}` : "";
  const d = Math.round((s.distance ?? 0) / 10) * 10;
  if (type === "depart") return `Head ${mod || "out"}${road}`;
  if (type === "arrive") return "You have arrived";
  if (type === "roundabout" || type === "rotary") return `At the roundabout, take the exit${road}`;
  const verb = mod.includes("left") ? "Turn left" : mod.includes("right") ? "Turn right" : mod === "uturn" ? "Make a U-turn" : "Continue";
  return `${verb}${road}${d ? `, then ${d} m` : ""}`;
}

export async function getRoute(from: LatLng, to: LatLng): Promise<Route> {
  const key = [from.lat, from.lng, to.lat, to.lng].map((v) => v.toFixed(4)).join(",");
  const hit = cache.get(key);
  if (hit) return hit;
  let route: Route | null = null;
  if (Date.now() - osrmDown > 60_000) {
    try {
      const url = `${osrmBase()}/route/v1/driving/${from.lng},${from.lat};${to.lng},${to.lat}?overview=full&geometries=polyline6&steps=true`;
      const res = await fetch(url, { signal: AbortSignal.timeout(3000), headers: { "user-agent": "GoldenHour-mock-core/0.1 (hackathon demo)" } });
      if (res.ok) {
        const j = (await res.json()) as { routes?: { geometry: string; duration: number; legs: { steps: Parameters<typeof describeStep>[0][] }[] }[] };
        const r0 = j.routes?.[0];
        if (r0) {
          const coords = decodePolyline6(r0.geometry);
          const steps = (r0.legs?.[0]?.steps ?? []).map(describeStep).filter(Boolean).slice(0, 12);
          if (coords.length >= 2) route = build(coords, r0.duration, steps, "osrm");
        }
      }
    } catch {
      osrmDown = Date.now();
      console.warn("[mock-core] OSRM unreachable, using straight-line routes for 60 s");
    }
  }
  if (!route) {
    const d = distanceM(from, to);
    route = build([[from.lat, from.lng], [to.lat, to.lng]], (d / 1000 / 28) * 3600, ["Drive to the destination (road route unavailable)"], "straight_line");
  }
  cache.set(key, route);
  return route;
}

/** Point and heading at `m` metres along the route. */
export function pointAt(route: Route, m: number): { pos: LatLng; heading: number } {
  const d = Math.max(0, Math.min(route.distance_m, m));
  let i = 1;
  while (i < route.cum.length - 1 && route.cum[i] < d) i++;
  const a = route.coords[i - 1];
  const b = route.coords[i];
  const seg = route.cum[i] - route.cum[i - 1] || 1;
  const t = (d - route.cum[i - 1]) / seg;
  const pos = { lat: a[0] + (b[0] - a[0]) * t, lng: a[1] + (b[1] - a[1]) * t };
  return { pos, heading: bearing({ lat: a[0], lng: a[1] }, { lat: b[0], lng: b[1] }) };
}

/** Remaining part of the route from `m` metres, as polyline6 (what the map draws). */
export function remainingPolyline(route: Route, m: number) {
  const { pos } = pointAt(route, m);
  let i = 1;
  while (i < route.cum.length - 1 && route.cum[i] < m) i++;
  return encodePolyline6([[pos.lat, pos.lng], ...route.coords.slice(i)]);
}
