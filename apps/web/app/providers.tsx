"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { AuthProvider } from "@/lib/auth";
import { WsProvider } from "@/components/realtime/WsProvider";
import { ToastProvider } from "@/components/ui/toast";

/** /readyz watcher (technical.md §7.9).
 *
 * The backend runs on Render's free tier, which spins the service down
 * after ~15 min idle -- the first request after that genuinely takes
 * 30-60s to cold-start, not an outage. The old logic (down after 2 fails,
 * 4s timeout, 5s interval -- so "down" after as little as ~9s) read every
 * cold start as a full-blown server-down banner, which is exactly the
 * "half the time it says server is down" complaint: the backend wasn't
 * actually broken, the check just wasn't patient enough to tell the
 * difference. Now: a single failure is "reconnecting" (quiet, not alarming),
 * and only sustained failure across real elapsed time (not just a fail
 * count, since one slow-but-eventually-ok response shouldn't count the
 * same as a hard connection refusal) escalates to the genuine down state. */
const DOWN_AFTER_MS = 25000; // failing continuously for this long -- past plausible cold-start wake time
const CHECK_INTERVAL_MS = 4000;
const CHECK_TIMEOUT_MS = 10000; // generous: a cold-start response can legitimately take a while

type HealthState = { down: boolean; reconnecting: boolean; online: boolean };
const HealthCtx = createContext<HealthState>({ down: false, reconnecting: false, online: true });
export const useHealth = () => useContext(HealthCtx);

function HealthProvider({ children, onRecover }: { children: ReactNode; onRecover: () => void }) {
  const [state, setState] = useState<HealthState>({ down: false, reconnecting: false, online: true });
  useEffect(() => {
    let stop = false;
    let firstFailAt: number | null = null;
    let wasDown = false;
    const check = async () => {
      try {
        const res = await fetch("/core/readyz", { cache: "no-store", signal: AbortSignal.timeout(CHECK_TIMEOUT_MS) });
        if (stop) return;
        if (res.ok) {
          firstFailAt = null;
          if (wasDown) onRecover(); // "Backend recovers -> restore normal operation and refresh the relevant data"
          wasDown = false;
          setState((s) => ({ ...s, down: false, reconnecting: false }));
        } else {
          throw new Error(`readyz ${res.status}`);
        }
      } catch {
        if (stop) return;
        const now = Date.now();
        if (firstFailAt === null) firstFailAt = now;
        const elapsed = now - firstFailAt;
        const down = elapsed >= DOWN_AFTER_MS;
        wasDown = wasDown || down;
        setState((s) => ({ ...s, down, reconnecting: !down }));
      }
    };
    void check();
    const id = setInterval(check, CHECK_INTERVAL_MS);
    const on = () => setState((s) => ({ ...s, online: true }));
    const off = () => setState((s) => ({ ...s, online: false }));
    setState((s) => ({ ...s, online: navigator.onLine }));
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      stop = true;
      clearInterval(id);
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, [onRecover]);
  return <HealthCtx.Provider value={state}>{children}</HealthCtx.Provider>;
}

export default function Providers({ children }: { children: ReactNode }) {
  const [qc] = useState(() => new QueryClient({
    defaultOptions: {
      queries: { retry: 1, refetchOnWindowFocus: true, staleTime: 2000 },
      mutations: { retry: 0 },
    },
  }));
  useEffect(() => {
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);
  return (
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <WsProvider>
          <HealthProvider onRecover={() => void qc.invalidateQueries()}>
            <ToastProvider>{children}</ToastProvider>
          </HealthProvider>
        </WsProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
