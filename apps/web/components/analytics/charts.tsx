"use client";

// Small hand-built chart primitives (dataviz skill: plain HTML/SVG, one hue for
// magnitude, status colors reserved and always paired with an icon + label, a
// legend for 2+ series, a table view so nothing is gated behind the chart).

import { useState, type ReactNode } from "react";
import Icon from "@/components/ui/icon";

const SERIES = "#2a78d6"; // categorical slot 1 / sequential hue (palette.md)
const STATUS = { good: "#0ca30c", warning: "#fab219", serious: "#ec835a", critical: "#d03b3b" };

function compact(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return Math.round(n).toLocaleString("en-IN");
}

export function ChartCard({ title, note, action, tableToggle = true, children }: { title: string; note?: string; action?: ReactNode; tableToggle?: boolean; children: (table: boolean) => ReactNode }) {
  const [table, setTable] = useState(false);
  return (
    <div className="rounded-[24px] border border-line bg-card p-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-[17px] font-bold">{title}</h3>
          {note && <p className="text-[14px] text-muted">{note}</p>}
        </div>
        <div className="flex items-center gap-2">
          {action}
          {tableToggle && (
            <button onClick={() => setTable((t) => !t)} className="grid h-9 w-9 place-items-center rounded-full bg-soft" aria-pressed={table} aria-label="Toggle table view">
              <Icon name={table ? "chart" : "list"} size={16} />
            </button>
          )}
        </div>
      </div>
      {children(table)}
    </div>
  );
}

/** Stat tile: label, value (auto-compact), optional delta. */
export function StatTile({ label, value, sub, tone }: { label: string; value: number | string; sub?: string; tone?: "good" | "warning" | "critical" }) {
  const color = tone ? STATUS[tone === "warning" ? "warning" : tone] : undefined;
  return (
    <div className="rounded-[20px] border border-line bg-card p-4">
      <p className="text-[13px] font-semibold text-muted">{label}</p>
      <p className="mt-1 text-[30px] font-bold leading-none" style={color ? { color } : undefined}>{typeof value === "number" ? compact(value) : value}</p>
      {sub && <p className="mt-1 text-[13px] text-muted">{sub}</p>}
    </div>
  );
}

/** Horizontal bars: one hue, labels at the tip, table view via ChartCard. */
export function HBars({ rows, unit = "", max, table }: { rows: { label: string; value: number; color?: string }[]; unit?: string; max?: number; table?: boolean }) {
  const top = max ?? Math.max(1, ...rows.map((r) => r.value));
  if (table) {
    return (
      <table className="w-full text-[15px]">
        <thead><tr className="text-left text-muted"><th className="pb-2 font-semibold">Label</th><th className="pb-2 text-right font-semibold">Value</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={r.label} className="border-t border-line"><td className="py-1.5">{r.label}</td><td className="py-1.5 text-right font-semibold tabular-nums">{r.value}{unit}</td></tr>)}</tbody>
      </table>
    );
  }
  return (
    <div className="flex flex-col gap-2.5">
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-3">
          <span className="w-32 shrink-0 truncate text-[14px] text-ink/75">{r.label}</span>
          <div className="h-6 flex-1 overflow-hidden rounded-full bg-soft" role="img" aria-label={`${r.label}: ${r.value}${unit}`}>
            <div className="h-full rounded-full" style={{ width: `${Math.max(3, (r.value / top) * 100)}%`, background: r.color ?? SERIES }} />
          </div>
          <span className="w-14 shrink-0 text-right text-[15px] font-bold tabular-nums">{r.value}{unit}</span>
        </div>
      ))}
      {!rows.length && <p className="py-4 text-center text-[15px] text-muted">No data yet</p>}
    </div>
  );
}

/** Meter: fill = value, track = lighter step of the same hue. */
export function Meter({ value, label, tone = "good" }: { value: number; label: string; tone?: "good" | "warning" | "critical" }) {
  const color = STATUS[tone];
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-[14px]">
        <span className="flex items-center gap-1.5 font-semibold"><span style={{ color }}><Icon name={tone === "good" ? "check" : tone === "warning" ? "clock" : "alert"} size={14} /></span>{label}</span>
        <span className="font-bold tabular-nums">{Math.round(value * 100)}%</span>
      </div>
      <div className="h-3 overflow-hidden rounded-full" style={{ background: `color-mix(in srgb, ${color} 18%, var(--soft))` }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${Math.round(value * 100)}%`, background: color }} />
      </div>
    </div>
  );
}

/** Simple percentile row: p50 / p90 as two stat numbers with a unit. */
export function Percentiles({ label, p50, p90, unit = "min" }: { label: string; p50: number | null; p90: number | null; unit?: string }) {
  return (
    <div className="flex items-center justify-between border-t border-line py-2.5 text-[15px]">
      <span className="text-ink/75">{label}</span>
      <span className="flex gap-4 font-semibold tabular-nums">
        <span>p50 <b>{p50 != null ? Math.round(p50 / (unit === "min" ? 60 : 1)) : "-"}</b> {unit}</span>
        <span>p90 <b>{p90 != null ? Math.round(p90 / (unit === "min" ? 60 : 1)) : "-"}</b> {unit}</span>
      </span>
    </div>
  );
}

/** Heatmap: one-hue sequential ramp, hour x day (or hour x value), with a legend. */
export function Heatmap({ cells, cols }: { cells: { x: string; v: number }[]; cols: number }) {
  const max = Math.max(1, ...cells.map((c) => c.v));
  return (
    <div>
      <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
        {cells.map((c, i) => {
          const t = c.v / max;
          return <div key={i} title={`${c.x}: ${c.v}`} className="aspect-square rounded" style={{ background: `color-mix(in srgb, ${SERIES} ${Math.round(10 + t * 80)}%, var(--soft))` }} />;
        })}
      </div>
      <div className="mt-2 flex items-center gap-2 text-[12px] text-muted">
        <span>Fewer</span>
        <div className="flex h-3 flex-1 overflow-hidden rounded-full">
          {[10, 30, 50, 70, 90].map((t) => <div key={t} className="flex-1" style={{ background: `color-mix(in srgb, ${SERIES} ${t}%, var(--soft))` }} />)}
        </div>
        <span>More</span>
      </div>
    </div>
  );
}

export { STATUS as statusColors };
