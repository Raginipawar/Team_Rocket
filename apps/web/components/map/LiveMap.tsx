"use client";

// Live map (technical.md §12.4): MapLibre GL with OpenStreetMap-based raster tiles,
// route polylines (polyline6), an animated ambulance marker, pickup and hospitals.
// If tiles cannot load (offline), the markers and route still show on a plain background.

import * as maplibregl from "maplibre-gl";
import type { Map as MLMap, Marker } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { decodePolyline6 } from "@/lib/polyline";
import type { LatLng, Signal } from "@/lib/api-types";
import { cn } from "@/lib/cn";
import Icon from "@/components/ui/icon";

export type MapPoint = LatLng & { id?: string; name?: string; tone?: "grey" | "green" | "red" | "amber"; label?: string };
export type MapAmbulance = LatLng & { id?: string; heading?: number | null; signal?: Signal; label?: string; tone?: "blue" | "dark" | "grey" };

export type LiveMapProps = {
  ambulance?: MapAmbulance | null;
  ambulances?: MapAmbulance[];
  pickup?: (LatLng & { accuracy?: number | null }) | null;
  destination?: MapPoint | null;
  hospitals?: MapPoint[];
  incidents?: MapPoint[];
  route?: string | null;
  routeTone?: "blue" | "red" | "green";
  routeDashed?: boolean;
  dark?: boolean;
  className?: string;
  height?: number | string;
  followDefault?: boolean;
  label?: string;
};

// OSM tiles (technical.md §12.4). Swap for the team's own tile server with NEXT_PUBLIC_MAP_TILES.
const TILES = process.env.NEXT_PUBLIC_MAP_TILES ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTR = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const PUNE: [number, number] = [73.8, 18.6];

// the worker is served from /public (scripts/copy-maplibre-worker.mjs)
maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

function style(dark: boolean): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: { base: { type: "raster", tiles: [TILES], tileSize: 256, attribution: ATTR, maxzoom: 19 } },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": dark ? "#141416" : "#f2f1ee" } },
      // softer colours in the day; inverted for night driving (brightness min/max swapped)
      { id: "base", type: "raster", source: "base", paint: dark
        ? { "raster-brightness-min": 0.92, "raster-brightness-max": 0.08, "raster-saturation": -0.7, "raster-hue-rotate": 180, "raster-contrast": 0.1 }
        : { "raster-saturation": -0.35, "raster-contrast": -0.05 } },
    ],
  };
}

function el(html: string, cls = "") {
  const d = document.createElement("div");
  d.className = cls;
  d.innerHTML = html;
  return d;
}

const ambSvg = (color: string) => `
  <svg width="44" height="44" viewBox="0 0 44 44" aria-hidden="true">
    <circle cx="22" cy="22" r="19" fill="${color}" stroke="#fff" stroke-width="3"/>
    <path d="M22 6 L27 14 L17 14 Z" fill="#fff"/>
    <rect x="14" y="17" width="16" height="11" rx="2.5" fill="#fff"/>
    <path d="M22 19.5v6M19 22.5h6" stroke="#dc2626" stroke-width="2.4" stroke-linecap="round"/>
  </svg>`;

export default function LiveMap(p: LiveMapProps) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const markers = useRef(new Map<string, Marker>());
  const anim = useRef<{ from: LatLng; to: LatLng; start: number } | null>(null);
  const ambMarker = useRef<Marker | null>(null);
  const [follow, setFollow] = useState(p.followDefault ?? false);
  const [auto, setAuto] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const fitted = useRef(false);

  // create
  useEffect(() => {
    if (!box.current) return;
    const m = new maplibregl.Map({
      container: box.current,
      style: style(!!p.dark),
      center: PUNE,
      zoom: 12,
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
    });
    m.touchZoomRotate.disableRotation();
    m.on("load", () => setLoaded(true));
    m.on("dragstart", () => {
      setFollow(false);
      setAuto(false);
    });
    map.current = m;
    const mk = markers.current;
    return () => {
      mk.clear();
      ambMarker.current = null;
      m.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // dark / light switch
  useEffect(() => {
    if (map.current && loaded) map.current.setStyle(style(!!p.dark));
  }, [p.dark, loaded]);

  // route
  useEffect(() => {
    const m = map.current;
    if (!m || !loaded) return;
    const apply = () => {
      const coords = decodePolyline6(p.route).map(([lat, lng]) => [lng, lat]);
      const data: GeoJSON.Feature = { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: coords } };
      const color = p.routeTone === "red" ? "#dc2626" : p.routeTone === "green" ? "#15803d" : "#1d4ed8";
      if (m.getSource("route")) (m.getSource("route") as maplibregl.GeoJSONSource).setData(data);
      else {
        m.addSource("route", { type: "geojson", data });
        m.addLayer({ id: "route-casing", type: "line", source: "route", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#ffffff", "line-width": 9, "line-opacity": 0.9 } });
        m.addLayer({ id: "route", type: "line", source: "route", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": color, "line-width": 5.5 } });
      }
      m.setPaintProperty("route", "line-color", color);
      m.setPaintProperty("route", "line-dasharray", p.routeDashed ? [1.5, 1.5] : [1, 0]);
    };
    if (m.isStyleLoaded()) apply();
    else m.once("styledata", apply);
  }, [p.route, p.routeTone, p.routeDashed, loaded, p.dark]);

  // static markers: pickup, destination, hospitals, incidents, fleet
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const want = new Map<string, { at: LatLng; html: string; cls: string; z: number }>();
    if (p.pickup) {
      want.set("pickup", {
        at: p.pickup,
        cls: "gh-pickup",
        z: 3,
        html: `<div style="position:relative;width:26px;height:26px">
          <span class="gh-pulse" style="position:absolute;inset:0;border-radius:50%;background:#dc2626;opacity:.5"></span>
          <span style="position:absolute;inset:4px;border-radius:50%;background:#dc2626;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.35)"></span></div>`,
      });
    }
    if (p.destination) {
      want.set(`dest`, {
        at: p.destination,
        cls: "gh-dest",
        z: 4,
        html: `<div style="display:flex;flex-direction:column;align-items:center;gap:3px">
          <div style="width:36px;height:36px;border-radius:50%;background:#15803d;border:3px solid #fff;display:grid;place-items:center;box-shadow:0 2px 8px rgba(0,0,0,.35)">
          <svg width="18" height="18" viewBox="0 0 24 24"><path d="M12 4v16M4 12h16" stroke="#fff" stroke-width="4" stroke-linecap="round"/></svg></div>
          ${p.destination.name ? `<span style="background:#fff;color:#111;font:600 12px/1.2 system-ui;padding:3px 7px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.25);white-space:nowrap">${p.destination.name}</span>` : ""}</div>`,
      });
    }
    for (const [i, h] of (p.hospitals ?? []).entries()) {
      const bg = h.tone === "red" ? "#fee2e2" : h.tone === "amber" ? "#fef3c7" : h.tone === "green" ? "#dcfce7" : "#ffffff";
      want.set(`h-${h.id ?? i}`, {
        at: h,
        cls: "gh-h",
        z: 1,
        html: `<div title="${h.name ?? ""}" style="display:flex;align-items:center;gap:4px">
          <div style="width:24px;height:24px;border-radius:7px;background:${bg};border:2px solid #9ca3af;display:grid;place-items:center">
          <svg width="12" height="12" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" stroke="#4b5563" stroke-width="4" stroke-linecap="round"/></svg></div>
          ${h.label ? `<span style="background:rgba(255,255,255,.92);color:#111;font:600 11px/1.2 system-ui;padding:2px 6px;border-radius:6px;white-space:nowrap">${h.label}</span>` : ""}</div>`,
      });
    }
    for (const [i, x] of (p.incidents ?? []).entries()) {
      const c = x.tone === "amber" ? "#d97706" : x.tone === "green" ? "#16a34a" : "#dc2626";
      want.set(`i-${x.id ?? i}`, { at: x, cls: "gh-i", z: 2, html: `<span title="${x.name ?? ""}" style="display:block;width:16px;height:16px;border-radius:50%;background:${c};border:3px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)"></span>` });
    }
    for (const [i, a] of (p.ambulances ?? []).entries()) {
      const c = a.tone === "grey" ? "#9ca3af" : a.tone === "dark" ? "#111111" : "#1d4ed8";
      want.set(`a-${a.id ?? i}`, {
        at: a,
        cls: "gh-a",
        z: 2,
        html: `<div title="${a.label ?? ""}" style="width:22px;height:22px;border-radius:50%;background:${c};border:2.5px solid #fff;display:grid;place-items:center;box-shadow:0 1px 4px rgba(0,0,0,.4);opacity:${a.signal === "lost" ? 0.45 : 1}">
          <svg width="10" height="10" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" stroke="#fff" stroke-width="5" stroke-linecap="round"/></svg></div>`,
      });
    }
    for (const [k, mk] of markers.current) {
      if (!want.has(k)) {
        mk.remove();
        markers.current.delete(k);
      }
    }
    for (const [k, w] of want) {
      const existing = markers.current.get(k);
      if (existing) {
        existing.setLngLat([w.at.lng, w.at.lat]);
        existing.getElement().innerHTML = w.html;
      } else {
        const node = el(w.html, w.cls);
        node.style.zIndex = String(w.z);
        markers.current.set(k, new maplibregl.Marker({ element: node }).setLngLat([w.at.lng, w.at.lat]).addTo(m));
      }
    }
  }, [p.pickup, p.destination, p.hospitals, p.incidents, p.ambulances]);

  // ambulance marker with smooth movement between updates
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const a = p.ambulance;
    if (!a) {
      ambMarker.current?.remove();
      ambMarker.current = null;
      return;
    }
    const color = p.ambulance?.tone === "dark" ? "#111111" : "#1d4ed8";
    if (!ambMarker.current) {
      const node = el(ambSvg(color), "gh-amb");
      node.style.zIndex = "5";
      ambMarker.current = new maplibregl.Marker({ element: node, rotationAlignment: "map" }).setLngLat([a.lng, a.lat]).addTo(m);
    }
    const mk = ambMarker.current!;
    const node = mk.getElement();
    node.style.opacity = a.signal === "lost" ? "0.45" : "1";
    node.setAttribute("aria-label", a.label ?? "Ambulance");
    mk.setRotation(a.heading ?? 0);
    const cur = mk.getLngLat();
    anim.current = { from: { lat: cur.lat, lng: cur.lng }, to: { lat: a.lat, lng: a.lng }, start: performance.now() };
    let raf = 0;
    const step = (t: number) => {
      const an = anim.current;
      if (!an || !ambMarker.current) return;
      const k = Math.min(1, (t - an.start) / 950);
      const lat = an.from.lat + (an.to.lat - an.from.lat) * k;
      const lng = an.from.lng + (an.to.lng - an.from.lng) * k;
      ambMarker.current.setLngLat([lng, lat]);
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [p.ambulance, p.ambulance?.lat, p.ambulance?.lng, p.ambulance?.heading, p.ambulance?.signal, p.ambulance?.tone]);

  // camera: follow the ambulance, or frame everything that matters
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const pts: LatLng[] = [];
    if (p.ambulance) pts.push(p.ambulance);
    if (p.pickup) pts.push(p.pickup);
    if (p.destination) pts.push(p.destination);
    if (!pts.length) {
      for (const h of p.hospitals ?? []) pts.push(h);
      for (const a of p.ambulances ?? []) pts.push(a);
      for (const i of p.incidents ?? []) pts.push(i);
    }
    for (const [lat, lng] of decodePolyline6(p.route)) pts.push({ lat, lng });
    if (!pts.length) return;
    if (follow && p.ambulance && fitted.current) {
      m.easeTo({ center: [p.ambulance.lng, p.ambulance.lat], duration: 900 });
      return;
    }
    if (fitted.current && !auto) return;
    const b = new maplibregl.LngLatBounds();
    pts.forEach((x) => b.extend([x.lng, x.lat]));
    m.fitBounds(b, { padding: 56, maxZoom: 15.5, duration: fitted.current ? 600 : 0 });
    fitted.current = true;
  }, [p.ambulance, p.pickup, p.destination, p.route, p.hospitals, p.ambulances, p.incidents, follow, auto]);

  const recenter = () => {
    fitted.current = false;
    setAuto(true);
    const m = map.current;
    if (!m) return;
    const pts: LatLng[] = [p.ambulance, p.pickup, p.destination].filter(Boolean) as LatLng[];
    if (!pts.length) (p.hospitals ?? []).forEach((h) => pts.push(h));
    if (!pts.length) return;
    const b = new maplibregl.LngLatBounds();
    pts.forEach((x) => b.extend([x.lng, x.lat]));
    m.fitBounds(b, { padding: 56, maxZoom: 15.5, duration: 500 });
    fitted.current = true;
  };

  return (
    <div className={cn("relative overflow-hidden rounded-[24px] border border-line bg-soft", p.className)} style={{ height: p.height ?? 280 }}>
      <div ref={box} className="absolute inset-0 h-full w-full" role="img" aria-label={p.label ?? "Live map"} />
      <div className="absolute right-3 top-3 flex flex-col gap-2">
        <button onClick={recenter} className="grid h-11 w-11 place-items-center rounded-full bg-white text-neutral-900 shadow-md" aria-label="Show everything"><Icon name="target" size={20} /></button>
        {p.ambulance && (
          <button onClick={() => setFollow((f) => !f)} aria-pressed={follow} className={cn("grid h-11 w-11 place-items-center rounded-full shadow-md", follow ? "bg-neutral-900 text-white" : "bg-white text-neutral-900")} aria-label="Follow the ambulance">
            <Icon name="ambulance" size={20} />
          </button>
        )}
      </div>
    </div>
  );
}
