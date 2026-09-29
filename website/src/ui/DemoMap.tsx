import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import Icon from "./Icon";
import { HOSPITALS, PICKUP, ROUTE_TO_HOSPITAL, ROUTE_TO_PATIENT, hospitalById, type Severity } from "../demo/data";
import type { Derived } from "../demo/engine";

type Pt = [number, number];

function length(pts: Pt[]) {
  let L = 0;
  for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  return L;
}

/** Splits a polyline at fraction p; returns the point, heading, and both halves. */
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

const poly = (pts: Pt[]) => pts.map((p) => p.join(",")).join(" ");
const routeFor = (id: string): Pt[] =>
  ROUTE_TO_HOSPITAL[id] ?? [[PICKUP.x, PICKUP.y], [hospitalById(id).x, hospitalById(id).y]];

const SEV_COLOR: Record<Severity, string> = { critical: "#dc2626", urgent: "#d97706", stable: "#16a34a" };

// Background: a schematic road grid of the demo area, not a real map.
const ROADS: Pt[][] = [
  [[0, 130], [180, 140], [420, 150], [760, 170]],
  [[40, 420], [300, 400], [560, 380], [800, 360]],
  [[120, 20], [170, 240], [220, 460], [260, 700]],
  [[430, 0], [440, 250], [470, 460], [520, 700]],
  [[0, 280], [260, 300], [620, 300], [800, 260]],
  [[520, 410], [470, 400], [430, 340], [360, 330], [330, 270], [275, 225], [205, 150], [120, 60]],
  [[600, 0], [640, 200], [700, 520]],
  [[0, 560], [420, 540], [800, 520]],
];
const AREAS: [string, number, number][] = [
  ["Dehu Road", 40, 80], ["Nigdi", 160, 115], ["Akurdi", 250, 265], ["Chinchwad", 470, 215], ["Pimpri", 590, 350],
  ["Bhosari", 690, 145], ["Ravet", 110, 365], ["Wakad", 400, 580],
];

export default function DemoMap({ d, now, severity = "critical", dark, height = 260, variant = "patient", signal = "ok", showHospitals }: {
  d: Derived; now: number; severity?: Severity; dark?: boolean; height?: number | string;
  variant?: "patient" | "ambulance" | "hospital" | "ops"; signal?: "ok" | "weak" | "lost"; showHospitals?: boolean;
}) {
  const [zoom, setZoom] = useState(1);
  const [follow, setFollow] = useState(true);
  const [full, setFull] = useState(false);
  // The box is fitted to the container shape so nothing important is cropped.
  const box = useRef<HTMLDivElement>(null);
  const [ratio, setRatio] = useState(760 / 520);
  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => {
      const { width, height: hh } = e.contentRect;
      if (width > 0 && hh > 0) setRatio(width / hh);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

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

  // Camera: frame whatever matters right now (ambulance + where it is heading, or
  // every hospital on overview maps), then follow the ambulance when zoomed in.
  const pts: Pt[] = [];
  const overview = !d.active && (showHospitals || variant === "hospital" || variant === "ops" || variant === "ambulance");
  if (overview || variant === "ops") HOSPITALS.forEach((hh) => pts.push([hh.x, hh.y]));
  if (d.active) {
    pts.push([PICKUP.x, PICKUP.y]);
    if (showAmbulance) pts.push([pos.x, pos.y]);
    if (hospitalKnown) pts.push([dest.x, dest.y]);
  }
  if (pts.length === 0) pts.push([100, 100], [700, 520]);
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const PAD = 70;
  let bw = Math.max(420, Math.max(...xs) - Math.min(...xs) + PAD * 2);
  let bh = Math.max(290, Math.max(...ys) - Math.min(...ys) + PAD * 2);
  if (bw / bh > ratio) bh = bw / ratio; else bw = bh * ratio;
  const fitCx = (Math.max(...xs) + Math.min(...xs)) / 2;
  const fitCy = (Math.max(...ys) + Math.min(...ys)) / 2;
  const w = bw / zoom;
  const h = bh / zoom;
  const cx = zoom > 1 && follow && showAmbulance ? pos.x : fitCx;
  const cy = zoom > 1 && follow && showAmbulance ? pos.y : fitCy;
  const viewBox = `${cx - w / 2} ${cy - h / 2} ${w} ${h}`;

  const bg = dark ? "#141414" : "#f4f4f2";
  const road = dark ? "#2b2b2b" : "#e4e4e0";
  const label = dark ? "#6b6b6b" : "#9a9a95";
  const toPatientColor = "#2563eb";
  const lost = signal === "lost";

  return (
    <div ref={box} className={`map${dark ? " map-dark" : ""}${full ? " map-full" : ""}`} style={{ height: full ? undefined : height }}>
      <svg viewBox={viewBox} preserveAspectRatio="xMidYMid slice" role="img" aria-label="Schematic map of the emergency">
        <rect x="-500" y="-500" width="2000" height="1700" fill={bg} />
        <path d="M-50 480 C120 440 260 470 380 450 S620 400 850 430" stroke={dark ? "#16263a" : "#dbe8f5"} strokeWidth="16" fill="none" />
        {ROADS.map((r, i) => <polyline key={i} points={poly(r)} fill="none" stroke={road} strokeWidth={i === 5 ? 11 : 8} strokeLinecap="round" strokeLinejoin="round" />)}
        {AREAS.map(([n, x, y]) => <text key={n} x={x} y={y} fontSize="15" fill={label} fontFamily="inherit">{n}</text>)}

        {(showHospitals || variant === "hospital" || variant === "ops" || variant === "ambulance") &&
          HOSPITALS.filter((hh) => hh.id !== d.hospitalId || !hospitalKnown).map((hh) => (
            <g key={hh.id} transform={`translate(${hh.x} ${hh.y})`} opacity={0.75}>
              <rect x="-8" y="-8" width="16" height="16" rx="4" fill={dark ? "#3a3a3a" : "#fff"} stroke={dark ? "#555" : "#bdbdb8"} />
              <path d="M0 -4v8M-4 0h8" stroke={dark ? "#aaa" : "#8a8a85"} strokeWidth="2" />
              {(variant === "ops" || variant === "hospital") && <text x="12" y="5" fontSize={variant === "ops" ? 15 : 11} fill={label}>{hh.name.split(" ")[0]} · {hh.free.split(",")[0]}</text>}
            </g>
          ))}

        {/* Routes */}
        {showPrev && prevRoute && <polyline points={poly(prevRoute)} fill="none" stroke="#9ca3af" strokeWidth="4" strokeDasharray="8 8" />}
        {showAmbulance && onPatientLeg && (
          <>
            <polyline points={poly(pos.done)} fill="none" stroke={dark ? "#444" : "#cfcfcb"} strokeWidth="5" strokeLinecap="round" />
            <polyline points={poly(pos.rest)} fill="none" stroke={toPatientColor} strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
          </>
        )}
        {hospitalKnown && leg === "hospital" && (
          <>
            <polyline points={poly(pos.done)} fill="none" stroke={dark ? "#444" : "#cfcfcb"} strokeWidth="5" strokeLinecap="round" />
            <polyline points={poly(pos.rest)} fill="none" stroke={SEV_COLOR[severity]} strokeWidth="5" strokeLinecap="round" strokeLinejoin="round"
              strokeDasharray={d.hospitalAcceptedAt === null ? "10 8" : undefined} />
          </>
        )}

        {/* Pickup: red pin with pulse and accuracy circle */}
        {d.active && d.stage !== "handedOver" && leg !== "hospital" && (
          <g transform={`translate(${PICKUP.x} ${PICKUP.y})`}>
            <circle r="34" fill="#ef4444" opacity="0.08" stroke="#ef4444" strokeOpacity="0.25" />
            <motion.circle r="12" fill="none" stroke="#ef4444" strokeWidth="2" animate={{ r: [12, 30], opacity: [0.6, 0] }} transition={{ duration: 1.6, repeat: Infinity }} />
            {searching && <motion.circle r="40" fill="none" stroke="#2563eb" strokeWidth="2" animate={{ r: [30, 90], opacity: [0.5, 0] }} transition={{ duration: 2, repeat: Infinity }} />}
            <circle r="9" fill="#ef4444" stroke="#fff" strokeWidth="3" />
          </g>
        )}

        {/* Destination hospital: large green pin */}
        {hospitalKnown && (
          <g transform={`translate(${dest.x} ${dest.y})`}>
            <circle r="16" fill="#16a34a" stroke="#fff" strokeWidth="3" />
            <path d="M0 -7v14M-7 0h14" stroke="#fff" strokeWidth="3" />
          </g>
        )}

        {/* Ambulance */}
        {showAmbulance && (
          <g transform={`translate(${pos.x} ${pos.y})`} opacity={lost ? 0.45 : 1}>
            {lost && <circle r="22" fill="none" stroke="#9ca3af" strokeWidth="2" strokeDasharray="4 4" transform="translate(18 -6)" />}
            <g transform={`rotate(${pos.angle})`}>
              <rect x="-16" y="-10" width="32" height="20" rx="6" fill={variant === "ambulance" ? "#2563eb" : dark ? "#fff" : "#0a0a0a"} />
              <path d="M-4 0h8M0 -4v8" stroke="#ef4444" strokeWidth="3" strokeLinecap="round" />
              <path d="M16 -5l6 5-6 5" fill={variant === "ambulance" ? "#2563eb" : dark ? "#fff" : "#0a0a0a"} />
            </g>
          </g>
        )}
      </svg>

      <span className="map-sim">Simulated</span>
      <span className="map-attr">Schematic demo map</span>
      {searching && <span className="map-note">Finding the nearest ambulance…</span>}

      <div className="map-ctrl">
        <button aria-label="Recenter" onClick={() => { setZoom(1); setFollow(true); }}><Icon name="target" size={16} /></button>
        <button aria-label="Follow ambulance" aria-pressed={follow} className={follow ? "on" : ""} onClick={() => setFollow((f) => !f)}><Icon name="ambulance" size={16} /></button>
        <button aria-label="Zoom in" onClick={() => setZoom((z) => Math.min(3, z + 0.5))}><Icon name="plus" size={16} /></button>
        <button aria-label="Zoom out" onClick={() => setZoom((z) => Math.max(1, z - 0.5))}><Icon name="minus" size={16} /></button>
        <button aria-label="Full screen" onClick={() => setFull((f) => !f)}><Icon name={full ? "x" : "expand"} size={16} /></button>
      </div>
    </div>
  );
}
