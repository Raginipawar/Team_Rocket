// Display formats from spec section 2.4 to 2.6. Ranges use "to", never a dash.

export const clock = (ms: number | null | undefined) =>
  ms == null ? "" : new Date(ms).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", hour12: true }).toUpperCase();

export const clockPlus = (ms: number, minutes: number) => clock(ms + minutes * 60000);

export function etaRange(min: number) {
  const low = Math.max(1, min - 2);
  const high = min + 3;
  return { main: `${min} min`, range: `${low} to ${high} min` };
}

export function distance(km: number) {
  if (km < 1) return `${Math.max(50, Math.round((km * 1000) / 50) * 50)} m`;
  return `${km.toFixed(1)} km`;
}

export function mmss(totalSecs: number) {
  const s = Math.max(0, Math.floor(totalSecs));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${String(m).padStart(2, "0")}:${sec}`;
}

export function ago(ms: number, now: number) {
  const s = Math.floor((now - ms) / 1000);
  if (s < 10) return "just now";
  if (s < 60) return `${s} s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ago`;
  return `${Math.floor(m / 60)} h ago`;
}

export const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");

const AVATAR_COLORS = ["#fde2e2", "#dbeafe", "#dcfce7", "#fef3c7", "#ede9fe", "#fce7f3", "#e0f2fe"];
export function avatarColor(name: string) {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}
