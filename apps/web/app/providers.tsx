"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { AuthProvider } from "@/lib/auth";
import { WsProvider } from "@/components/realtime/WsProvider";
import { ToastProvider } from "@/components/ui/toast";

/** /readyz watcher (technical.md §7.9): down after 2 consecutive failures. */
const HealthCtx = createContext<{ down: boolean; online: boolean }>({ down: false, online: true });
export const useHealth = () => useContext(HealthCtx);

function HealthProvider({ children }: { children: ReactNode }) {
  const [fails, setFails] = useState(0);
  const [online, setOnline] = useState(true);
  useEffect(() => {
    let stop = false;
    const check = async () => {
      try {
        const res = await fetch("/core/readyz", { cache: "no-store", signal: AbortSignal.timeout(4000) });
        if (!stop) setFails(res.ok ? 0 : (f) => f + 1);
      } catch {
        if (!stop) setFails((f) => f + 1);
      }
    };
    void check();
    const id = setInterval(check, 5000);
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    setOnline(navigator.onLine);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      stop = true;
      clearInterval(id);
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return <HealthCtx.Provider value={{ down: fails >= 2, online }}>{children}</HealthCtx.Provider>;
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
          <HealthProvider>
            <ToastProvider>{children}</ToastProvider>
          </HealthProvider>
        </WsProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
