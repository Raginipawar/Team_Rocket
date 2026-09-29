import { useState, type ReactNode } from "react";

/* Small chart kit for the hospital and ops analytics.
   Rules followed: one series = one hue (sequential blue); thin marks with rounded
   data ends on the baseline; recessive grid; text never wears the series color;
   hover tooltip on every mark; a table view for every chart. */

export const SERIES = "#2a78d6"; // sequential blue, step 450
const SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"];

export function StatTile({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "good" | "warn" | "bad" }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <b className="stat-value">{value}</b>
      {sub && <span className={`stat-sub${tone ? ` tone-${tone}` : ""}`}>{sub}</span>}
    </div>
  );
}

export function ChartCard({ title, note, children, table }: { title: string; note?: string; children: ReactNode; table: { head: string[]; rows: (string | number)[][] } }) {
  const [asTable, setAsTable] = useState(false);
  return (
    <section className="chart-card">
      <header>
        <div><h3>{title}</h3>{note && <p>{note}</p>}</div>
        <button className="link-btn" onClick={() => setAsTable((v) => !v)} aria-pressed={asTable}>{asTable ? "Show chart" : "Show table"}</button>
      </header>
      {asTable ? (
        <table className="viz-table">
          <thead><tr>{table.head.map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>{table.rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
        </table>
      ) : children}
    </section>
  );
}

/** Vertical columns, one series. Optional reference line (e.g. a limit). */
export function Columns({ data, unit, refLine, refLabel, height = 200 }: {
  data: { label: string; value: number }[]; unit: string; refLine?: number; refLabel?: string; height?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(...data.map((d) => d.value), refLine ?? 0) * 1.15 || 1;
  const W = 600;
  const H = height;
  const padB = 24;
  const padL = 30;
  const innerH = H - padB - 8;
  const bw = (W - padL) / data.length;
  const y = (v: number) => 8 + innerH - (v / max) * innerH;
  const ticks = [0, max / 2, max].map((t) => Math.round(t));
  return (
    <div className="viz" style={{ position: "relative" }}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Column chart">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W} y1={y(t)} y2={y(t)} stroke="#ececea" />
            <text x={padL - 6} y={y(t) + 4} textAnchor="end" fontSize="10" fill="#8a8a8a">{t}</text>
          </g>
        ))}
        {data.map((d, i) => {
          const x = padL + i * bw + bw * 0.22;
          const w = bw * 0.56;
          const top = y(d.value);
          const h = Math.max(0, 8 + innerH - top);
          const r = Math.min(4, w / 2, h);
          return (
            <g key={d.label} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={padL + i * bw} y={0} width={bw} height={H - padB} fill="transparent" />
              <path
                d={`M${x},${8 + innerH} V${top + r} Q${x},${top} ${x + r},${top} H${x + w - r} Q${x + w},${top} ${x + w},${top + r} V${8 + innerH} Z`}
                fill={SERIES} opacity={hover === null || hover === i ? 1 : 0.45}
              />
              {i % Math.ceil(data.length / 12) === 0 && <text x={x + w / 2} y={H - 8} textAnchor="middle" fontSize="10" fill="#8a8a8a">{d.label}</text>}
            </g>
          );
        })}
        {refLine !== undefined && (
          <g>
            <line x1={padL} x2={W} y1={y(refLine)} y2={y(refLine)} stroke="#0a0a0a" strokeDasharray="4 4" strokeWidth="1" />
            <text x={W - 4} y={y(refLine) - 5} textAnchor="end" fontSize="10" fill="#525252">{refLabel}</text>
          </g>
        )}
      </svg>
      {hover !== null && (
        <div className="viz-tip" style={{ left: `${((padL + hover * bw + bw / 2) / W) * 100}%` }}>
          <b>{data[hover].value} {unit}</b><span>{data[hover].label}</span>
        </div>
      )}
    </div>
  );
}

/** Horizontal bars with direct value labels, one series, sorted by the caller. */
export function HBars({ data, unit = "" }: { data: { label: string; value: number }[]; unit?: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(...data.map((d) => d.value)) || 1;
  return (
    <div className="hbars">
      {data.map((d, i) => (
        <div key={d.label} className="hbar" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} title={`${d.label}: ${d.value}${unit}`}>
          <span className="hbar-label">{d.label}</span>
          <span className="hbar-track">
            <span className="hbar-fill" style={{ width: `${(d.value / max) * 100}%`, background: SERIES, opacity: hover === null || hover === i ? 1 : 0.45 }} />
          </span>
          <span className="hbar-val">{d.value}{unit}</span>
        </div>
      ))}
    </div>
  );
}

/** A single ratio against a limit (same-hue track). */
export function Meter({ value, label }: { value: number; label: string }) {
  return (
    <div className="meter2" role="meter" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <div className="meter2-top"><b>{value}%</b><span>{label}</span></div>
      <div className="meter2-track"><span style={{ width: `${value}%`, background: SERIES }} /></div>
    </div>
  );
}

/** Grid heatmap, sequential blue ramp. */
export function Heatmap({ rows, cols, values, unit }: { rows: string[]; cols: string[]; values: number[][]; unit: string }) {
  const [hover, setHover] = useState<[number, number] | null>(null);
  const max = Math.max(...values.flat()) || 1;
  return (
    <div className="heat" style={{ gridTemplateColumns: `110px repeat(${cols.length}, 1fr)` }}>
      <span />
      {cols.map((c) => <span key={c} className="heat-col">{c}</span>)}
      {rows.map((r, i) => (
        <div key={r} className="heat-row" style={{ display: "contents" }}>
          <span className="heat-rowlabel">{r}</span>
          {cols.map((c, j) => {
            const v = values[i][j];
            const step = Math.min(SEQ.length - 1, Math.round((v / max) * (SEQ.length - 1)));
            const on = hover && hover[0] === i && hover[1] === j;
            return (
              <span key={c} className={`heat-cell${on ? " on" : ""}`} style={{ background: SEQ[step] }}
                onMouseEnter={() => setHover([i, j])} onMouseLeave={() => setHover(null)} title={`${r}, ${c}: ${v} ${unit}`}>
                {on && <em>{v}</em>}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}
