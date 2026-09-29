import { motion } from "framer-motion";
import type { ReactNode } from "react";
import Icon, { CategoryIcon } from "./Icon";
import { CATEGORY_LABEL, SEVERITY_LABEL, type Category, type Severity } from "../demo/data";
import { avatarColor, initials } from "../demo/format";

/* ---------- 2.1 Severity badge ---------- */
export function SeverityBadge({ level, size = "sm", ai, confirmed, needsCheck }: {
  level: Severity; size?: "sm" | "lg"; ai?: boolean; confirmed?: boolean; needsCheck?: boolean;
}) {
  const icon = level === "critical" ? "alert" : level === "urgent" ? "clock" : "check";
  return (
    <span className={`sev sev-${level} sev-${size}${needsCheck ? " sev-check" : ""}`}>
      <Icon name={icon} size={size === "lg" ? 18 : 14} stroke={2.2} />
      {SEVERITY_LABEL[level]}
      {ai && !confirmed && <span className="sev-tag">AI</span>}
      {confirmed && <span className="sev-tag ok"><Icon name="check" size={11} stroke={2.6} />Confirmed by paramedic</span>}
      {needsCheck && <span className="sev-tag warn">Needs check</span>}
    </span>
  );
}

/* ---------- 2.2 Category chip ---------- */
export function CategoryChip({ c }: { c: Category }) {
  return <span className="chip"><CategoryIcon c={c} size={15} />{CATEGORY_LABEL[c]}</span>;
}

/* ---------- 2.3 Confidence ---------- */
export function Confidence({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone = pct >= 80 ? "ok" : pct >= 60 ? "warn" : "bad";
  return (
    <span className={`conf conf-${tone}`} title="How sure the AI is, based on what was said. The paramedic makes the final call.">
      {pct}% sure{pct < 60 && " · Needs check"}
    </span>
  );
}

/* ---------- 2.4 ETA ---------- */
export function Eta({ min, lost, arrived, arrivedAt, big }: { min: number; lost?: boolean; arrived?: boolean; arrivedAt?: string; big?: boolean }) {
  if (arrived) return <span className={`eta${big ? " eta-big" : ""} eta-arrived`}><Icon name="check" size={big ? 22 : 16} stroke={2.4} /><b>Arrived</b>{arrivedAt && ` at ${arrivedAt}`}</span>;
  if (min <= 0) return <span className={`eta${big ? " eta-big" : ""}`}><b>Arriving now</b></span>;
  const low = Math.max(1, min - 2);
  const high = min + 3;
  if (lost) return <span className={`eta${big ? " eta-big" : ""} eta-lost`}>~ {min} min (estimated, no signal)</span>;
  return <span className={`eta${big ? " eta-big" : ""}`}><b>{min} min</b> <span className="eta-range">({low} to {high} min)</span></span>;
}

/* ---------- 2.9 Status stepper ---------- */
export function Stepper({ steps }: { steps: { label: string; time?: string; state: "done" | "current" | "todo" }[] }) {
  return (
    <ol className="stepper">
      {steps.map((s, i) => (
        <li key={i} className={`step-${s.state}`}>
          <span className="stepper-dot">
            {s.state === "done" ? <Icon name="check" size={13} stroke={3} /> : s.state === "current" ? <motion.i animate={{ scale: [1, 1.35, 1] }} transition={{ duration: 1.4, repeat: Infinity }} /> : null}
          </span>
          <span className="stepper-label">{s.label}</span>
          {s.time && <span className="stepper-time">{s.time}</span>}
        </li>
      ))}
    </ol>
  );
}

/* ---------- 2.10 Countdown ring ---------- */
export function CountdownRing({ secs, total, size = 72, dark }: { secs: number; total: number; size?: number; dark?: boolean }) {
  const r = size / 2 - 5;
  const c = 2 * Math.PI * r;
  const frac = Math.max(0, Math.min(1, secs / total));
  const late = secs <= 5;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="ring" aria-label={`${secs} seconds left`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={dark ? "#333" : "#e5e5e5"} strokeWidth="5" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={late ? "#ef4444" : dark ? "#fff" : "#0a0a0a"} strokeWidth="5"
        strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - frac)} transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: "stroke-dashoffset .25s linear, stroke .2s" }} />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" fontSize={size * 0.32} fontWeight="600" fill={late ? "#ef4444" : dark ? "#fff" : "#0a0a0a"}>{secs}</text>
    </svg>
  );
}

/* ---------- 2.11 Freshness dot ---------- */
export function Freshness({ minutes, estimate }: { minutes: number; estimate?: string }) {
  const tone = minutes < 10 ? "ok" : minutes <= 30 ? "warn" : "bad";
  return (
    <span className={`fresh fresh-${tone}`}>
      <i />updated {minutes} min ago{tone === "bad" && ", may be outdated"}
      {tone === "bad" && estimate && <b className="fresh-est">{estimate}</b>}
    </span>
  );
}

/* ---------- 2.12 Signal badge ---------- */
export function SignalBadge({ signal, lostMins = 3 }: { signal: "ok" | "weak" | "lost"; lostMins?: number }) {
  const text = signal === "ok" ? "Live" : signal === "weak" ? "Weak signal" : `Signal lost ${lostMins} min ago`;
  return <span className={`signal signal-${signal}`}><i />{text}</span>;
}

/* ---------- 2.13 Room status chip ---------- */
export type RoomStatus = "free" | "reserved" | "occupied" | "cleaning" | "out";
const ROOM_LABEL: Record<RoomStatus, string> = { free: "Free", reserved: "Reserved", occupied: "Occupied", cleaning: "Cleaning", out: "Out of service" };
export function RoomChip({ status, detail }: { status: RoomStatus; detail?: string }) {
  return <span className={`room-chip room-${status}`}>{ROOM_LABEL[status]}{detail && ` · ${detail}`}</span>;
}

/* ---------- 2.14 Ambulance type ---------- */
export function AmbType({ type }: { type: "ALS" | "BLS" }) {
  return (
    <span className={`amb-type amb-${type.toLowerCase()}`} title={type === "ALS" ? "Advanced Life Support: ventilator, trained paramedic." : "Basic Life Support."}>
      {type}
    </span>
  );
}

/* ---------- 2.15 Why chips ---------- */
export function WhyChips({ items, negative }: { items: { icon: string; text: string }[]; negative?: boolean }) {
  return (
    <div className="why">
      {items.map((w) => (
        <span key={w.text} className={`why-chip${negative ? " neg" : ""}`}><Icon name={negative ? "alert" : w.icon} size={14} />{w.text}</span>
      ))}
    </div>
  );
}

/* ---------- 2.16 Banner ---------- */
export function Banner({ type, children, action }: { type: "info" | "success" | "warning" | "danger" | "offline" | "sim"; children: ReactNode; action?: ReactNode }) {
  const icon = { info: "clock", success: "check", warning: "alert", danger: "alert", offline: "wifiOff", sim: "box" }[type];
  return (
    <motion.div className={`banner banner-${type}`} initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} role={type === "danger" ? "alert" : "status"}>
      <Icon name={icon} size={18} />
      <span className="banner-text">{children}</span>
      {action}
    </motion.div>
  );
}

/* ---------- 2.24 Avatar ---------- */
export function Avatar({ name, size = 40, managed }: { name: string; size?: number; managed?: boolean }) {
  return (
    <span className="avatar-c" style={{ width: size, height: size, background: avatarColor(name), fontSize: size * 0.36 }}>
      {initials(name)}
      {managed && <span className="avatar-managed" title="Managed profile"><Icon name="lock" size={10} stroke={2.4} /></span>}
    </span>
  );
}

/* ---------- Simulated tag ---------- */
export function SimTag() {
  return <span className="sim-tag">Simulated</span>;
}

/* ---------- 2.20 Empty state ---------- */
export function Empty({ icon = "check", text, children }: { icon?: string; text: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <span className="empty-icon"><Icon name={icon} size={26} /></span>
      <p>{text}</p>
      {children}
    </div>
  );
}

/* ---------- 2.21 Skeleton ---------- */
export function Skeleton({ h = 16, w = "100%", r = 10 }: { h?: number; w?: number | string; r?: number }) {
  return <span className="skel" style={{ height: h, width: w, borderRadius: r }} />;
}

/* ---------- Call button (2.8) ---------- */
export function CallButton({ label, number = "108", variant = "light", full }: { label: string; number?: string; variant?: "light" | "dark" | "red" | "ghost"; full?: boolean }) {
  return (
    <a href={`tel:${number}`} className={`btn2 btn2-${variant}${full ? " btn2-full" : ""}`}>
      <Icon name="phone" size={18} />{label}
    </a>
  );
}
