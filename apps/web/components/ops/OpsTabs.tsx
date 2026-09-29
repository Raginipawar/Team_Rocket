"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get } from "@/lib/api";
import type { OpsOverview, WsEnvelope } from "@/lib/api-types";
import { WsClient } from "@/lib/ws";
import { wsUrl } from "@/lib/config";
import { Brand, LanguageSwitcher, MockRibbon } from "@/components/shell";
import { ErrorState, LoadingState } from "@/components/ui/bits";
import Icon, { type IconName } from "@/components/ui/icon";
import { buzz } from "@/lib/hooks";
import { cn } from "@/lib/cn";
import IncidentTab from "./IncidentTab";
import AnalyticsTab from "./AnalyticsTab";
import ScenariosTab from "./ScenariosTab";

const TABS: { key: "incident" | "analytics" | "scenarios"; label: string; icon: IconName }[] = [
  { key: "incident", label: "Incident", icon: "alert" },
  { key: "analytics", label: "Analytics", icon: "chart" },
  { key: "scenarios", label: "Scenarios", icon: "play" },
];

export default function OpsTabs({ userName, focusEscalationId, sessionToken }: { userName: string | null; focusEscalationId: string | null; sessionToken: string | null }) {
  const [tab, setTab] = useState<"incident" | "analytics" | "scenarios">(focusEscalationId ? "incident" : "incident");
  const qc = useQueryClient();
  const [ws, setWs] = useState<WsClient | null>(null);

  const token = sessionToken ?? (typeof window !== "undefined" ? sessionStorage.getItem("gh-ops-session") : null);

  useEffect(() => {
    if (!token) return;
    const client = new WsClient(wsUrl("OPS"), token);
    setWs(client);
    return () => client.close();
  }, [token]);

  const q = useQuery({ queryKey: ["ops-overview"], queryFn: () => get<{ data: OpsOverview }>("/ops/overview"), refetchInterval: 10000 });
  const openCount = useMemo(() => (q.data?.data.escalations ?? []).filter((e) => e.status === "open" || e.status === "claimed").length, [q.data]);

  useEffect(() => {
    if (!ws) return;
    return ws.subscribe("ops", (ev: WsEnvelope) => {
      if (ev.event.startsWith("escalation")) buzz([200, 100, 200]);
      void qc.invalidateQueries({ queryKey: ["ops-overview"] });
      void qc.invalidateQueries({ queryKey: ["ops-analytics"] });
    }, () => void qc.invalidateQueries({ queryKey: ["ops-overview"] }));
  }, [ws, qc]);

  return (
    <div className="desk min-h-dvh bg-page text-ink">
      <MockRibbon />
      <header className="flex items-center justify-between gap-3 border-b border-line bg-card px-4 py-3">
        <div className="flex items-center gap-3">
          <Brand small />
          {userName && <span className="hidden text-[14px] text-muted sm:inline">· {userName}</span>}
        </div>
        <LanguageSwitcher compact />
      </header>
      <nav className="flex gap-1 border-b border-line bg-card px-3 py-2 sm:px-6">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} aria-pressed={tab === t.key} className={cn("flex items-center gap-2 rounded-full px-4 py-2.5 text-[15px] font-semibold", tab === t.key ? "bg-ink text-bg" : "text-muted hover:bg-soft")}>
            <Icon name={t.icon} size={17} />
            {t.label}
            {t.key === "incident" && openCount > 0 && <span className="rounded-full bg-red px-2 py-0.5 text-[12px] font-bold text-white">{openCount}</span>}
          </button>
        ))}
      </nav>
      <main className="px-4 py-5 sm:px-6">
        {q.isLoading ? <LoadingState /> : q.isError ? <ErrorState text="Could not load the ops overview" onRetry={() => q.refetch()} /> : (
          <>
            {tab === "incident" && <IncidentTab overview={q.data!.data} focusId={focusEscalationId} onChanged={() => void qc.invalidateQueries({ queryKey: ["ops-overview"] })} />}
            {tab === "analytics" && <AnalyticsTab />}
            {tab === "scenarios" && <ScenariosTab />}
          </>
        )}
      </main>
    </div>
  );
}
