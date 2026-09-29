"use client";

// Scenarios tab (technical.md §15, §16.6): list, run, speed, reset, results timeline.

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { errorText, get, post } from "@/lib/api";
import type { Scenario, ScenarioRun } from "@/lib/api-types";
import { Banner, Card, ErrorState, LoadingState } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/cn";

type Data = { scenarios: Scenario[]; runs: ScenarioRun[]; speed: number };

function RunResult({ run }: { run: ScenarioRun }) {
  return (
    <div className="mt-3 rounded-2xl bg-soft p-4">
      <div className="flex items-center gap-2">
        {run.status === "running" && <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue border-t-transparent" />}
        {run.status === "passed" && <Icon name="check" size={18} className="text-green" />}
        {run.status === "failed" && <Icon name="x" size={18} className="text-red-ink" />}
        {run.status === "not_available" && <Icon name="info" size={18} className="text-muted" />}
        <span className="text-[15px] font-bold capitalize">{run.status.replace("_", " ")}</span>
      </div>
      <ol className="mt-2 flex flex-col gap-1 text-[14px]">
        {run.steps.map((s, i) => <li key={i} className="text-muted">{s.text}</li>)}
      </ol>
      {!!run.assertions.length && (
        <ul className="mt-2 flex flex-col gap-1 border-t border-line pt-2 text-[14px]">
          {run.assertions.map((a, i) => (
            <li key={i} className={cn("flex items-center gap-2", a.ok ? "text-green" : "text-red-ink")}>
              <Icon name={a.ok ? "check" : "x"} size={14} />{a.text}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ScenariosTab() {
  const toast = useToast();
  const qc = useQueryClient();
  const [running, setRunning] = useState<string | null>(null);
  const [speedBusy, setSpeedBusy] = useState(false);
  const [resetBusy, setResetBusy] = useState(false);
  const q = useQuery<{ data: Data }>({ queryKey: ["ops-scenarios"], queryFn: () => get("/ops/scenarios"), refetchInterval: (query) => (query.state.data?.data.runs.some((r) => r.status === "running") ? 1500 : 5000) });

  if (q.isLoading) return <LoadingState />;
  if (q.isError || !q.data) return <ErrorState text={errorText(q.error)} onRetry={() => q.refetch()} />;
  const { scenarios, runs, speed } = q.data.data;

  const run = async (name: string) => {
    setRunning(name);
    try {
      await post(`/ops/scenarios/${name}/run`);
      void qc.invalidateQueries({ queryKey: ["ops-scenarios"] });
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setRunning(null);
    }
  };
  const setSpeed = async (m: number) => {
    setSpeedBusy(true);
    try {
      await post("/ops/sim/speed", { multiplier: m });
      void qc.invalidateQueries({ queryKey: ["ops-scenarios"] });
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setSpeedBusy(false);
    }
  };
  const reset = async () => {
    setResetBusy(true);
    try {
      await post("/ops/sim/reset");
      void qc.invalidateQueries({ queryKey: [] });
      toast("Simulator reset", "success");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setResetBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <Banner tone="blue" icon="info">Scenarios drive the system through the same public APIs a real user would use, then check the invariants from technical.md §14.</Banner>

      <Card className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-[15px] font-semibold">Simulation speed</span>
          <div className="flex gap-1 rounded-full bg-soft p-1">
            {[1, 2, 5, 10].map((m) => <button key={m} disabled={speedBusy} onClick={() => void setSpeed(m)} aria-pressed={speed === m} className={cn("rounded-full px-3 py-1.5 text-[14px] font-semibold", speed === m ? "bg-card shadow-sm" : "text-muted")}>{m}×</button>)}
          </div>
        </div>
        <Button variant="outline" size="sm" loading={resetBusy} onClick={() => void reset()}><Icon name="refresh" size={16} />Reset simulator</Button>
      </Card>

      <div className="flex flex-col gap-3">
        {scenarios.map((s) => {
          const lastRun = [...runs].reverse().find((r) => r.name === s.name);
          return (
            <Card key={s.name}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[18px] font-bold">{s.title}</p>
                  {s.description && <p className="text-[15px] text-muted">{s.description}</p>}
                </div>
                <Button size="sm" variant={s.available ? "primary" : "soft"} loading={running === s.name} disabled={!s.available} onClick={() => void run(s.name)}>
                  <Icon name="play" size={16} />Run
                </Button>
              </div>
              {lastRun && <RunResult run={lastRun} />}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
