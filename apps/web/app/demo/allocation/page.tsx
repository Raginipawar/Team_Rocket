"use client";

import { useState } from "react";
import { get } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, LoadingState } from "@/components/ui/bits";
import Icon from "@/components/ui/icon";
import { cn } from "@/lib/cn";

type Hospital = { id: string; name: string; capacity: Record<string, number>; free: Record<string, number>; avg_release_min: Record<string, number>; distance_km: number };
type Patient = { id: string; urgency: "critical" | "urgent" | "stable"; required_resource: string; eta_min: number };
type Assigned = { patient_id: string; hospital_id: string; hospital_name: string; resource: string; urgency: string; forecast: { p_available_at_eta: number; basis: string } | null };
type Unserved = { patient_id: string; urgency: string; required_resource: string; reason: string };
type LogEvent = { event: string; patient_id: string; hospital_id?: string; resource?: string; reason?: string; at?: string };
type AllocResult = { assigned: Assigned[]; unserved: Unserved[]; log: LogEvent[]; served_count: number; unserved_count: number };
type Scenario = { name: string; detail: string };
type Result = {
  generated_at: string; objective: string;
  network: { hospitals: Hospital[]; patients: Patient[] };
  baseline_current_capacity_only: AllocResult;
  forecast_aware: AllocResult;
  comparison: { baseline_served: number; forecast_served: number; baseline_unserved: number; forecast_unserved: number };
  scenarios_demonstrated: Scenario[];
};

const URGENCY_STYLE: Record<string, string> = {
  critical: "bg-red text-white", urgent: "bg-amber-soft text-amber", stable: "bg-green-soft text-green",
};

export default function AllocationDemoPage() {
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await get<Result>(`/allocation-demo/run?n_patients=10&seed=${Date.now() % 100000}`, { auth: false });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not run the scenario");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8">
      <div>
        <h1 className="text-[30px] font-extrabold">Multi-Patient Allocation &amp; Forecasting</h1>
        <p className="mt-2 text-[16px] text-muted">
          Batch allocation of simultaneous patients across a hospital network, with replanning on rejection,
          forecast-aware ranking of availability at arrival, and a baseline comparison. Self-contained synthetic
          scenario -- regenerates a fresh patient surge every run.
        </p>
      </div>

      <Button size="lg" onClick={() => void run()} loading={loading}>
        <Icon name="refresh" size={20} />
        Run patient surge scenario
      </Button>

      {error && <Card className="border-red/40 bg-red-soft text-red-ink">{error}</Card>}
      {loading && <LoadingState />}

      {result && !loading && (
        <div className="flex flex-col gap-6">
          <Card>
            <p className="text-[13px] font-bold uppercase tracking-wide text-muted">Allocation objective</p>
            <p className="mt-1.5 text-[16px] leading-relaxed">{result.objective}</p>
          </Card>

          <div>
            <h2 className="mb-3 text-[20px] font-bold">Required scenarios demonstrated this run</h2>
            <div className="flex flex-col gap-3">
              {result.scenarios_demonstrated.map((s) => (
                <Card key={s.name} className="border-blue/30 bg-blue-soft/40">
                  <p className="text-[15px] font-bold text-blue">{s.name}</p>
                  <p className="mt-1 text-[15px] leading-relaxed">{s.detail}</p>
                </Card>
              ))}
            </div>
          </div>

          <div>
            <h2 className="mb-3 text-[20px] font-bold">Forecast-aware vs current-capacity-only baseline</h2>
            <div className="grid grid-cols-2 gap-4">
              <Card className="text-center">
                <p className="text-[13px] font-bold uppercase tracking-wide text-muted">Baseline (capacity only)</p>
                <p className="mt-2 text-[34px] font-extrabold">{result.comparison.baseline_served}<span className="text-[18px] text-muted"> served</span></p>
                <p className="text-[15px] text-red-ink">{result.comparison.baseline_unserved} unserved</p>
              </Card>
              <Card className="text-center border-green/40 bg-green-soft/30">
                <p className="text-[13px] font-bold uppercase tracking-wide text-muted">Forecast-aware</p>
                <p className="mt-2 text-[34px] font-extrabold">{result.comparison.forecast_served}<span className="text-[18px] text-muted"> served</span></p>
                <p className="text-[15px] text-green">{result.comparison.forecast_unserved} unserved</p>
              </Card>
            </div>
          </div>

          <div>
            <h2 className="mb-3 text-[20px] font-bold">Assigned patients (forecast-aware)</h2>
            <div className="flex flex-col gap-2">
              {result.forecast_aware.assigned.map((a) => (
                <div key={a.patient_id} className="flex items-center gap-3 rounded-2xl border border-line bg-card p-3">
                  <span className={cn("rounded-full px-2.5 py-1 text-[12px] font-bold uppercase", URGENCY_STYLE[a.urgency])}>{a.urgency}</span>
                  <span className="font-semibold">{a.patient_id}</span>
                  <Icon name="chevron" size={16} className="text-muted" />
                  <span className="flex-1 truncate">{a.hospital_name} &middot; {a.resource.replace(/_/g, " ")}</span>
                  {a.forecast && <span className="text-[13px] text-muted">p={a.forecast.p_available_at_eta}</span>}
                </div>
              ))}
            </div>
          </div>

          {result.forecast_aware.unserved.length > 0 && (
            <div>
              <h2 className="mb-3 text-[20px] font-bold">Unserved patients &amp; reasons</h2>
              <div className="flex flex-col gap-2">
                {result.forecast_aware.unserved.map((u) => (
                  <div key={u.patient_id} className="flex items-start gap-3 rounded-2xl border border-red/30 bg-red-soft/40 p-3">
                    <span className={cn("rounded-full px-2.5 py-1 text-[12px] font-bold uppercase", URGENCY_STYLE[u.urgency])}>{u.urgency}</span>
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold">{u.patient_id} &middot; {u.required_resource.replace(/_/g, " ")}</p>
                      <p className="text-[14px] text-muted">{u.reason}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <h2 className="mb-3 text-[20px] font-bold">Hospital network state</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {result.network.hospitals.map((h) => (
                <Card key={h.id}>
                  <p className="font-bold">{h.name} <span className="font-normal text-muted">&middot; {h.distance_km}km</span></p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {Object.entries(h.capacity).map(([rt, total]) => (
                      <span key={rt} className="rounded-full bg-soft px-2.5 py-1 text-[12px] font-semibold">{rt.replace(/_/g, " ")}: {h.free[rt]}/{total}</span>
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          </div>

          <details className="rounded-2xl border border-line bg-card p-4">
            <summary className="cursor-pointer text-[15px] font-bold">Full reservation transition log (evidence)</summary>
            <pre className="mt-3 overflow-x-auto text-[12px] leading-relaxed">{JSON.stringify(result.forecast_aware.log, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  );
}
