import type { Freshness } from "./enums";

/** "MH14AB1234" -> "MH14 AB 1234" (easier to read out loud). */
export function reg(r: string | null | undefined) {
  if (!r) return "";
  const m = r.replace(/\s+/g, "").match(/^([A-Z]{2}\d{1,2})([A-Z]{1,3})(\d{1,4})$/i);
  return m ? `${m[1]} ${m[2]} ${m[3]}`.toUpperCase() : r;
}

export function minutes(sec: number | null | undefined) {
  if (sec == null) return null;
  return Math.max(1, Math.round(sec / 60));
}

export function clock(iso: string | number | null | undefined) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
}

export function dateTime(iso: string | null | undefined) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

export function ago(iso: string | number | null | undefined, now = Date.now()) {
  if (!iso) return "";
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s} s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  return `${h} h ago`;
}

export function mmss(sec: number) {
  const s = Math.max(0, Math.floor(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function freshnessOf(iso: string | null | undefined, now = Date.now()): Freshness {
  if (!iso) return "stale";
  const m = (now - new Date(iso).getTime()) / 60000;
  return m <= 10 ? "fresh" : m <= 30 ? "aging" : "stale";
}

export function phone(p: string | null | undefined) {
  if (!p) return "";
  const d = p.replace(/\D/g, "");
  if (d.length === 12 && d.startsWith("91")) return `+91 ${d.slice(2, 7)} ${d.slice(7)}`;
  return p;
}

export function title(s: string) {
  return s.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

export function km(m: number | null | undefined) {
  if (m == null) return "";
  return m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`;
}
