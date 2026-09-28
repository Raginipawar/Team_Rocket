"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { errorText, get } from "@/lib/api";
import type { Analytics } from "@/lib/api-types";
import { useHosp } from "../context";
import { ChartCard, HBars, Percentiles, StatTile, statusColors } from "@/components/analytics/charts";
import { Banner, ErrorState, LoadingState } from "@/components/ui/bits";
import Icon from "@/components/ui/icon";

const RANGES = [
  { label: "Last 24 hours", days: 1 },
  { label: "Last 7 days", days: 7 },
  { label: "Last 30 days", days: 30 },
];

export default function HospitalAnalyticsPage() {
  const { dashboard } = useHosp();
  const [range, setRange] = useState(1);
  const from = useMemo(() => new Date(Date.now() - range * 86_400_000).toISOString(), [range]);
  const to = useMemo(() => new Date().toISOString(), [range]);
  const q = useQuery({ queryKey: ["hosp-analytics", range], queryFn: () => get<{ data: Analytics }>(`/hospital/analytics?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`) });

  if (q.isLoading) return <LoadingState />;
  if (q.isError || !q.data) return <ErrorState text={errorText(q.error)} onRetry={() => q.refetch()} />;
  const a = q.data.data;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-[26px] font-extrabold">Analytics{dashboard ? ` · ${dashboard.hospital.name}` : ""}</h1>
        <div className="flex gap-1 rounded-full bg-soft p-1">
          {RANGES.map((r) => (
            <button key={r.days} onClick={() => setRange(r.days)} aria-pressed={range === r.days} className={`rounded-full px-3.5 py-2 text-[14px] font-semibold ${range === r.days ? "bg-card shadow-sm" : "text-muted"}`}>{r.label}</button>
          ))}
        </div>
      </div>

      {a.synthetic && <Banner tone="blue" icon="info">These numbers include generated sample history so the charts are not empty on a fresh demo, alongside any real cases from this session.</Banner>}
      {!!a.flags?.length && a.flags.map((f) => <Banner key={f} tone="amber" icon="alert">{f}</Banner>)}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Response time (call to accept)" value={a.response_times.call_to_accept.p50 != null ? `${Math.round(a.response_times.call_to_accept.p50 / 60)} min` : "-"} sub={`p50 of ${a.response_times.call_to_accept.n} calls`} />
        <StatTile label="Offload delay (median)" value={a.offload_delay.p50 != null ? `${Math.round(a.offload_delay.p50 / 60)} min` : "-"} tone={a.offload_delay.p50 != null && a.offload_delay.p50 > 900 ? "warning" : undefined} />
        <StatTile label="Requests accepted" value={a.request_outcomes.find((o) => o.outcome === "accepted")?.count ?? 0} />
        <StatTile label="Requests rejected" value={a.request_outcomes.find((o) => o.outcome === "rejected")?.count ?? 0} tone={(a.request_outcomes.find((o) => o.outcome === "rejected")?.count ?? 0) > 5 ? "warning" : undefined} />
      </div>

      <ChartCard title="Response times" note="Time from the call to each milestone">
        {() => (
          <div className="flex flex-col">
            <Percentiles label="Call to accept" p50={a.response_times.call_to_accept.p50} p90={a.response_times.call_to_accept.p90} />
            <Percentiles label="Call to scene" p50={a.response_times.call_to_scene.p50} p90={a.response_times.call_to_scene.p90} />
            <Percentiles label="Scene to hospital" p50={a.response_times.scene_to_hospital.p50} p90={a.response_times.scene_to_hospital.p90} />
            <Percentiles label="Call to handoff" p50={a.response_times.call_to_handoff.p50} p90={a.response_times.call_to_handoff.p90} />
          </div>
        )}
      </ChartCard>

      <div className="grid gap-5 lg:grid-cols-2">
        <ChartCard title="Accepted vs rejected" note="Share of requests accepted, and why the rest were rejected">
          {(table) => (
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-2 text-[15px] font-semibold">
                <Icon name="check" size={16} className="text-green" />{a.request_outcomes.find((o) => o.outcome === "accepted")?.count ?? 0} accepted
                <span className="text-muted">·</span>
                <Icon name="x" size={16} className="text-red-ink" />{(a.request_outcomes.find((o) => o.outcome === "rejected")?.count ?? 0) + (a.request_outcomes.find((o) => o.outcome === "timeout")?.count ?? 0)} not accepted
              </div>
              <HBars table={table} rows={a.rejections_by_reason.map((r) => ({ label: r.reason.replace(/_/g, " "), value: r.count }))} />
            </div>
          )}
        </ChartCard>

        <ChartCard title="Stale data by hospital" note="Share of the time your numbers were older than 30 minutes">
          {(table) => <HBars table={table} unit="%" rows={(a.stale_data ?? []).slice(0, 8).map((s) => ({ label: s.hospital, value: Math.round(s.stale_share * 100), color: s.stale_share > 0.3 ? statusColors.warning : undefined }))} max={100} />}
        </ChartCard>
      </div>
    </div>
  );
}
