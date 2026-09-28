"use client";

import { useNow } from "@/lib/hooks";

/** Countdown ring for offers (20 s) and hospital requests (45 s). */
export default function CountdownRing({ until, total, size = 96, stroke = 9, label }: { until: string; total: number; size?: number; stroke?: number; label?: string }) {
  const now = useNow(250);
  const left = Math.max(0, (new Date(until).getTime() - now) / 1000);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const frac = Math.min(1, left / total);
  const color = left <= 5 ? "var(--red)" : left <= total / 2 ? "var(--amber)" : "var(--green)";
  return (
    <div className="relative grid shrink-0 place-items-center" style={{ width: size, height: size }} role="timer" aria-label={`${Math.ceil(left)} seconds left${label ? ` to ${label}` : ""}`}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--soft-2)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - frac)} />
      </svg>
      <span className="absolute text-center font-extrabold tabular-nums" style={{ fontSize: size * 0.32 }}>{Math.ceil(left)}</span>
    </div>
  );
}
