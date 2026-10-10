import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { Map as MLMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import Icon from "./Icon";
import { HOSPITALS, PICKUP, ROUTE_TO_HOSPITAL, ROUTE_TO_PATIENT, hospitalById, type Severity } from "../demo/data";
import type { Derived } from "../demo/engine";
import { DEMO_BOUNDS, routeToLngLat, toLngLat } from "./geo";

type Pt = [number, number];

function length(pts: Pt[]) {
  let L = 0;
  for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  return L;
}

/** Splits a polyline at fraction p; returns the point, heading, and both halves (in the abstract demo plane). */
function along(pts: Pt[], p: number) {
  const total = length(pts);
  let target = total * Math.min(1, Math.max(0, p));
  for (let i = 1; i < pts.length; i++) {
    const [ax, ay] = pts[i - 1];
    const [bx, by] = pts[i];
    const seg = Math.hypot(bx - ax, by - ay);
    if (target <= seg || i === pts.length - 1) {
      const t = seg === 0 ? 0 : Math.min(1, target / seg);
      const x = ax + (bx - ax) * t;
      const y = ay + (by - ay) * t;
      const angle = (Math.atan2(by - ay, bx - ax) * 180) / Math.PI;
      return { x, y, angle, done: [...pts.slice(0, i), [x, y] as Pt], rest: [[x, y] as Pt, ...pts.slice(i)] };
    }
    target -= seg;
  }
  const last = pts[pts.length - 1];
  return { x: last[0], y: last[1], angle: 0, done: pts, rest: [last] as Pt[] };
}

const routeFor = (id: string): Pt[] => ROUTE_TO_HOSPITAL[id] ?? [[PICKUP.x, PICKUP.y], [hospitalById(id).x, hospitalById(id).y]];

const SEV_COLOR: Record<Severity, string> = { critical: "#dc2626", urgent: "#d97706", stable: "#16a34a" };

const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTR = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

// the worker is served from /public (scripts/copy-maplibre-worker.mjs)
maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

function style(dark: boolean): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: { base: { type: "raster", tiles: [TILES], tileSize: 256, attribution: ATTR, maxzoom: 19 } },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": dark ? "#141416" : "#f2f1ee" } },
      {
        id: "base", type: "raster", source: "base",
        paint: dark
          ? { "raster-brightness-min": 0.92, "raster-brightness-max": 0.08, "raster-saturation": -0.7, "raster-hue-rotate": 180, "raster-contrast": 0.1 }
          : { "raster-saturation": -0.35, "raster-contrast": -0.05 },
      },
    ],
  };
}

function el(html: string, cls = "") {
  const d = document.createElement("div");
  d.className = cls;
  d.innerHTML = html;
  return d;
}

const hospitalPin = (dark: boolean) => `
  <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
    <rect x="3" y="3" width="22" height="22" rx="7" fill="${dark ? "#3a3a3a" : "#fff"}" stroke="${dark ? "#666" : "#bdbdb8"}" stroke-width="2"/>
    <path d="M14 8v12M8 14h12" stroke="${dark ? "#aaa" : "#8a8a85"}" stroke-width="2.4" stroke-linecap="round"/>
  </svg>`;

const destPin = () => `
  <svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">
    <circle cx="15" cy="15" r="13" fill="#16a34a" stroke="#fff" stroke-width="3"/>
    <path d="M15 8v14M8 15h14" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/>
  </svg>`;

const pickupPin = () => `
  <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
    <circle cx="13" cy="13" r="12" fill="#ef4444" opacity="0.18"/>
    <circle cx="13" cy="13" r="8" fill="#ef4444" stroke="#fff" stroke-width="2.6"/>
  </svg>`;

const ambSvg = (color: string) => `
  <svg width="36" height="36" viewBox="0 0 36 36" aria-hidden="true">
    <g>
      <rect x="4" y="11" width="28" height="18" rx="6" fill="${color}"/>
      <path d="M14 15h8M18 11v8" stroke="#ef4444" stroke-width="3" stroke-linecap="round"/>
    </g>
  </svg>`;

export default function DemoMap({ d, now, severity = "critical", dark, height = 260, variant = "patient", signal = "ok", showHospitals }: {
  d: Derived; now: number; severity?: Severity; dark?: boolean; height?: number | string;
  variant?: "patient" | "ambulance" | "hospital" | "ops"; signal?: "ok" | "weak" | "lost"; showHospitals?: boolean;
}) {
  const box = useRef<HTMLDivElement>(null);
  const mapBox = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const loaded = useRef(false);
  const pickupMarker = useRef<Marker | null>(null);
  const destMarker = useRef<Marker | null>(null);
  const ambMarker = useRef<Marker | null>(null);
  const hospitalMarkers = useRef<Marker[]>([]);
  const [follow, setFollow] = useState(true);
  const [full, setFull] = useState(false);
  const [, forceRerender] = useState(0);

  const toPatient = ROUTE_TO_PATIENT as Pt[];
  const toHospital = routeFor(d.hospitalId);
  const leg = d.leg;
  const onPatientLeg = leg === "patient" || (!leg && d.accepted === null);
  const pos = leg === "hospital" ? along(toHospital, d.progress) : along(toPatient, leg === "patient" ? d.progress : 0);
  const showAmbulance = d.active && d.accepted !== null && d.stage !== "handedOver";
  const searching = d.active && d.accepted === null && d.stage !== "sending";
  const dest = hospitalById(d.hospitalId);
  const hospitalKnown = d.hospitalAcceptedAt !== null || d.stage === "asking";
  const prevRoute = d.reroute ? routeFor(d.reroute.from) : null;
  const showPrev = prevRoute && d.reroute && now - d.reroute.at < 10000;
  const lost = signal === "lost";

  // create the map once
  useEffect(() => {
    if (!mapBox.current || map.current) return;
    const m = new maplibregl.Map({
      container: mapBox.current,
      style: style(!!dark),
      bounds: DEMO_BOUNDS,
      attributionControl: { compact: true },
      interactive: true,
    });
    map.current = m;
    m.on("load", () => {
      loaded.current = true;
      m.resize();
      forceRerender((n) => n + 1);
    });

    // the container may not have its final size yet when the map is created
    // (flex/phone-frame layout settles after mount), so keep the canvas synced.
    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined" && box.current) {
      ro = new ResizeObserver(() => m.resize());
      ro.observe(box.current);
    }

    return () => {
      ro?.disconnect();
      m.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // hospital markers: created once the map is loaded, static positions
  useEffect(() => {
    const m = map.current;
    if (!m || !loaded.current) return;
    hospitalMarkers.current.forEach((mk) => mk.remove());
    hospitalMarkers.current = [];
    const show = showHospitals || variant === "hospital" || variant === "ops" || variant === "ambulance";
    if (!show) return;
    for (const hh of HOSPITALS) {
      if (hh.id === d.hospitalId && hospitalKnown) continue;
      const marker = new maplibregl.Marker({ element: el(hospitalPin(!!dark)) })
        .setLngLat(toLngLat([hh.x, hh.y]))
        .addTo(m);
      hospitalMarkers.current.push(marker);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded.current, showHospitals, variant, dark, d.hospitalId, hospitalKnown]);

  // pickup / destination / ambulance markers + route lines, every tick
  useEffect(() => {
    const m = map.current;
    if (!m || !loaded.current) return;

    const showPickup = d.active && d.stage !== "handedOver" && leg !== "hospital";
    if (showPickup) {
      if (!pickupMarker.current) pickupMarker.current = new maplibregl.Marker({ element: el(pickupPin()) }).setLngLat(toLngLat([PICKUP.x, PICKUP.y])).addTo(m);
      pickupMarker.current.setLngLat(toLngLat([PICKUP.x, PICKUP.y]));
    } else if (pickupMarker.current) {
      pickupMarker.current.remove();
      pickupMarker.current = null;
    }

    if (hospitalKnown) {
      if (!destMarker.current) destMarker.current = new maplibregl.Marker({ element: el(destPin()) }).setLngLat(toLngLat([dest.x, dest.y])).addTo(m);
      destMarker.current.setLngLat(toLngLat([dest.x, dest.y]));
    } else if (destMarker.current) {
      destMarker.current.remove();
      destMarker.current = null;
    }

    if (showAmbulance) {
      const color = variant === "ambulance" ? "#2563eb" : dark ? "#fff" : "#0a0a0a";
      if (!ambMarker.current) {
        ambMarker.current = new maplibregl.Marker({ element: el(ambSvg(color), "amb-marker"), rotationAlignment: "map" }).setLngLat(toLngLat([pos.x, pos.y])).addTo(m);
      }
      ambMarker.current.setLngLat(toLngLat([pos.x, pos.y]));
      ambMarker.current.setRotation(pos.angle + 90);
      const markerEl = ambMarker.current.getElement();
      markerEl.style.opacity = lost ? "0.45" : "1";
      if (follow && showAmbulance) m.panTo(toLngLat([pos.x, pos.y]), { duration: 400 });
    } else if (ambMarker.current) {
      ambMarker.current.remove();
      ambMarker.current = null;
    }

    const setLine = (id: string, coords: Pt[] | null, color: string, width: number, dashed = false) => {
      const src = m.getSource(id) as maplibregl.GeoJSONSource | undefined;
      const data = {
        type: "Feature" as const, properties: {},
        geometry: { type: "LineString" as const, coordinates: coords ?? [] },
      };
      if (src) {
        src.setData(data);
      } else {
        m.addSource(id, { type: "geojson", data });
        m.addLayer({
          id, type: "line", source: id,
          layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": color, "line-width": width, ...(dashed ? { "line-dasharray": [2, 2] } : {}) },
        });
      }
    };

    setLine("demo-prev-route", showPrev && prevRoute ? routeToLngLat(prevRoute) : null, "#9ca3af", 4, true);

    if (showAmbulance && onPatientLeg) {
      setLine("demo-done-route", routeToLngLat(pos.done), dark ? "#444" : "#cfcfcb", 5);
      setLine("demo-rest-route", routeToLngLat(pos.rest), "#2563eb", 5);
    } else if (hospitalKnown && leg === "hospital") {
      setLine("demo-done-route", routeToLngLat(pos.done), dark ? "#444" : "#cfcfcb", 5);
      setLine("demo-rest-route", routeToLngLat(pos.rest), SEV_COLOR[severity], 5, d.hospitalAcceptedAt === null);
    } else {
      setLine("demo-done-route", null, "#000", 0);
      setLine("demo-rest-route", null, "#000", 0);
    }
  });

  // camera fit when not following, or on overview maps
  useEffect(() => {
    const m = map.current;
    if (!m || !loaded.current || full === undefined) return;
    if (!d.active || !showAmbulance || !follow) {
      const pts: Pt[] = [];
      const overview = !d.active && (showHospitals || variant === "hospital" || variant === "ops" || variant === "ambulance");
      if (overview) HOSPITALS.forEach((hh) => pts.push([hh.x, hh.y]));
      if (d.active) {
        pts.push([PICKUP.x, PICKUP.y]);
        if (showAmbulance) pts.push([pos.x, pos.y]);
        if (hospitalKnown) pts.push([dest.x, dest.y]);
      }
      if (pts.length === 0) {
        m.fitBounds(DEMO_BOUNDS, { padding: 40, duration: 0 });
        return;
      }
      const lnglats = pts.map(toLngLat);
      const lngs = lnglats.map((p) => p[0]);
      const lats = lnglats.map((p) => p[1]);
      m.fitBounds(
        [[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]],
        { padding: 60, duration: 400, maxZoom: 15 },
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d.active, d.hospitalId, hospitalKnown, showAmbulance]);

  useEffect(() => {
    const m = map.current;
    if (m) setTimeout(() => m.resize(), full ? 50 : 10);
  }, [full]);

  const recenter = () => {
    setFollow(true);
    const m = map.current;
    if (!m) return;
    if (showAmbulance) m.flyTo({ center: toLngLat([pos.x, pos.y]), zoom: 14, duration: 500 });
    else m.fitBounds(DEMO_BOUNDS, { padding: 40, duration: 500 });
  };

  return (
    <div ref={box} className={`map${dark ? " map-dark" : ""}${full ? " map-full" : ""}`} style={{ height: full ? undefined : height }}>
      <div ref={mapBox} className="map-canvas" />
      <span className="map-sim">Simulated</span>
      {searching && <span className="map-note">Finding the nearest ambulance…</span>}

      <div className="map-ctrl">
        <button aria-label="Recenter" onClick={recenter}><Icon name="target" size={16} /></button>
        <button aria-label="Follow ambulance" aria-pressed={follow} className={follow ? "on" : ""} onClick={() => setFollow((f) => !f)}><Icon name="ambulance" size={16} /></button>
        <button aria-label="Zoom in" onClick={() => map.current?.zoomIn()}><Icon name="plus" size={16} /></button>
        <button aria-label="Zoom out" onClick={() => map.current?.zoomOut()}><Icon name="minus" size={16} /></button>
        <button aria-label="Full screen" onClick={() => setFull((f) => !f)}><Icon name={full ? "x" : "expand"} size={16} /></button>
      </div>
    </div>
  );
}
