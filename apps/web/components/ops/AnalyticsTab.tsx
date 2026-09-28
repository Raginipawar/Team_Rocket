"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { errorText, get } from "@/lib/api";
import type { Analytics } from "@/lib/api-types";
import { ChartCard, HBars, Heatmap, Percentiles, StatTile } from "@/components/analytics/charts";
import { Banner, ErrorState, LoadingState } from "@/components/ui/bits";
import Icon from "@/components/ui/icon";

const RANGES = [{ label: "24 hours", days: 1 }, { label: "7 days", days: 7 }, { label: "30 days", days: 30 }];

export default function AnalyticsTab() {
  const [range, setRange] = useState(1);
  const from = useMemo(() => new Date(Date.now() - range * 86_400_000).toISOString(), [range]);
  const to = useMemo(() => new Date().toISOString(), [range]);
  const q = useQuery({ queryKey: ["ops-analytics", range], queryFn: () => get<{ data: Analytics }>(`/ops/analytics?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`) });

  if (q.isLoading) return <LoadingState />;
  if (q.isError || !q.data) return <ErrorState text={errorText(q.error)} onRetry={() => q.refetch()} />;
  const a = q.data.data;
  const demand = a.demand ?? [];
  const maxDemand = Math.max(1, ...demand.flatMap((d) => [d.actual, d.forecast]));

  return (
    <div className="flex flex-col gap-5">
      <div className="flex justify-end">
        <div className="flex gap-1 rounded-full bg-soft p-1">
          {RANGES.map((r) => <button key={r.days} onClick={() => setRange(r.days)} aria-pressed={range === r.days} className={`rounded-full px-3.5 py-2 text-[14px] font-semibold ${range === r.days ? "bg-card shadow-sm" : "text-muted"}`}>{r.label}</button>)}
        </div>
      </div>
      {a.synthetic && <Banner tone="blue" icon="info">Includes generated sample history alongside real cases from this session, so the dashboard is never empty.</Banner>}
      {!!a.flags?.length && a.flags.map((f) => <Banner key={f} tone="amber" icon="alert">{f}</Banner>)}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Critical recall" value={a.critical_recall != null ? `${Math.round(a.critical_recall * 100)}%` : "-"} sub="AI flagged truly critical cases" tone={a.critical_recall != null && a.critical_recall < 0.85 ? "warning" : "good"} />
        <StatTile label="Call to accept (p50)" value={a.response_times.call_to_accept.p50 != null ? `${Math.round(a.response_times.call_to_accept.p50)}s` : "-"} />
        <StatTile label="Escalations" value={(a.escalations ?? []).reduce((s, e) => s + e.count, 0)} />
        <StatTile label="Auto-defaulted" value={`${Math.round(((a.escalations ?? []).reduce((s, e) => s + e.count * e.auto_default_rate, 0) / Math.max(1, (a.escalations ?? []).reduce((s, e) => s + e.count, 0))) * 100)}%`} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <ChartCard title="Response times, system-wide">
          {() => (
            <div className="flex flex-col">
              <Percentiles label="Call to accept" p50={a.response_times.call_to_accept.p50} p90={a.response_times.call_to_accept.p90} />
              <Percentiles label="Call to scene" p50={a.response_times.call_to_scene.p50} p90={a.response_times.call_to_scene.p90} />
              <Percentiles label="Scene to hospital" p50={a.response_times.scene_to_hospital.p50} p90={a.response_times.scene_to_hospital.p90} />
              <Percentiles label="Call to handoff" p50={a.response_times.call_to_handoff.p50} p90={a.response_times.call_to_handoff.p90} />
            </div>
          )}
        </ChartCard>

        <ChartCard title="Escalations by type" note="Count and how often the default option had to auto-execute">
          {(table) => (
            <div className="flex flex-col gap-3">
              <HBars table={table} rows={(a.escalations ?? []).map((e) => ({ label: e.type.replace(/_/g, " "), value: e.count }))} />
              {!table && (a.escalations ?? []).some((e) => e.auto_default_rate > 0) && (
                <p className="flex items-center gap-1.5 text-[13px] text-amber"><Icon name="clock" size={14} />{(a.escalations ?? []).filter((e) => e.auto_default_rate > 0).map((e) => `${e.type.replace(/_/g, " ")}: ${Math.round(e.auto_default_rate * 100)}% auto`).join(" · ")}</p>
              )}
            </div>
          )}
        </ChartCard>
      </div>

      <ChartCard title="Triage: AI vs paramedic-confirmed" note="Confusion matrix, most recent cases" tableToggle={false}>
        {() => {
          const rows = ["critical", "urgent", "stable"] as const;
          return (
            <table className="w-full text-[14px]">
              <thead><tr><th className="p-1 text-left text-muted">AI \ Final</th>{rows.map((r) => <th key={r} className="p-1 text-center capitalize text-muted">{r}</th>)}</tr></thead>
              <tbody>
                {rows.map((ai) => (
                  <tr key={ai}>
                    <td className="p-1 font-semibold capitalize">{ai}</td>
                    {rows.map((fin) => {
                      const cell = a.triage_confusion?.find((c) => c.ai === ai && c.final === fin);
                      const n = cell?.count ?? 0;
                      return <td key={fin} className={`p-1 text-center font-semibold tabular-nums ${ai === fin ? "text-green" : n > 0 ? "text-amber" : "text-muted"}`}>{n}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          );
        }}
      </ChartCard>

      <ChartCard title="Demand: actual vs forecast" note="Calls per hour, last 24 hours" tableToggle={false}>
        {() => (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-4 text-[13px]"><span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: "#2a78d6" }} />Actual</span><span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full border-2 border-current opacity-50" />Forecast</span></div>
            <div className="flex h-32 items-end gap-1">
              {demand.map((d) => (
                <div key={d.hour} className="group relative flex-1" title={`${d.hour}: ${d.actual} actual, ${d.forecast} forecast`}>
                  <div className="absolute bottom-0 w-full rounded-t border-t-2 border-dashed border-ink/30" style={{ height: `${(d.forecast / maxDemand) * 100}%` }} />
                  <div className="absolute bottom-0 w-full rounded-t bg-blue" style={{ height: `${(d.actual / maxDemand) * 100}%`, opacity: 0.85 }} />
                </div>
              ))}
            </div>
            <div className="flex justify-between text-[11px] text-muted"><span>{demand[0]?.hour}</span><span>{demand[demand.length - 1]?.hour}</span></div>
          </div>
        )}
      </ChartCard>

      {!!(a.hourly_calls ?? []).length && (
        <ChartCard title="Calls by hour of day" tableToggle={false}>
          {() => <Heatmap cols={12} cells={(a.hourly_calls ?? []).map((h) => ({ x: `${h.hour}:00`, v: h.count }))} />}
        </ChartCard>
      )}
    </div>
  );
}
