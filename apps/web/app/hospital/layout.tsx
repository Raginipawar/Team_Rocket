"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { get } from "@/lib/api";
import type { HospitalDashboard, WsEnvelope } from "@/lib/api-types";
import { useChannel, useWsClient } from "@/components/realtime/WsProvider";
import { Brand, ConnectionBanners, LanguageSwitcher, MockRibbon, RequireRole } from "@/components/shell";
import Icon, { type IconName } from "@/components/ui/icon";
import { buzz } from "@/lib/hooks";
import { cn } from "@/lib/cn";
import { HospitalContext } from "./context";

const NAV: { href: string; icon: IconName; label: string }[] = [
  { href: "/hospital", icon: "grid", label: "Dashboard" },
  { href: "/hospital/rooms", icon: "bed", label: "Rooms" },
  { href: "/hospital/resources", icon: "box", label: "Resources" },
  { href: "/hospital/staff", icon: "users", label: "Staff" },
  { href: "/hospital/patients", icon: "user", label: "Patients" },
  { href: "/hospital/analytics", icon: "chart", label: "Analytics" },
  { href: "/hospital/settings", icon: "settings", label: "Settings" },
];

function Shell({ children }: { children: ReactNode }) {
  const { session, signOut } = useAuth();
  const qc = useQueryClient();
  const path = usePathname();
  const ws = useWsClient("HOSPITAL", session?.token);
  const [alertOn, setAlertOn] = useState(true);
  const [open, setOpen] = useState(false);

  const q = useQuery({ queryKey: ["hosp-dashboard"], queryFn: () => get<HospitalDashboard>("/hospital/dashboard"), refetchInterval: 15000 });
  const hospitalId = q.data?.hospital.id ?? session?.user.hospital_id ?? null;
  const refresh = () => void qc.invalidateQueries({ queryKey: ["hosp-dashboard"] });

  useChannel(ws, hospitalId ? `hospital:${hospitalId}` : null, (ev: WsEnvelope) => {
    if (ev.event === "hospital.request.new") buzz([250, 100, 250]);
    if (ev.event.startsWith("alert")) buzz(150);
    refresh();
  }, refresh);

  useEffect(() => {
    try {
      setAlertOn(localStorage.getItem("gh-hosp-sound") !== "off");
    } catch {
      /* ignore */
    }
  }, []);

  const pendingCount = q.data?.pending_requests.length ?? 0;

  return (
    <HospitalContext.Provider value={{ dashboard: q.data ?? null, loading: q.isLoading, error: q.isError, refetch: refresh, ws, alertOn, setAlertOn: (v) => { setAlertOn(v); try { localStorage.setItem("gh-hosp-sound", v ? "on" : "off"); } catch { /* ignore */ } } }}>
      <div className="desk min-h-dvh bg-page text-ink lg:flex">
        <MockRibbon />
        <aside className="hidden shrink-0 flex-col gap-1 border-r border-line bg-card px-4 py-5 lg:flex lg:w-64">
          <div className="mb-4 flex items-center justify-between px-1"><Brand small /></div>
          {NAV.map((n) => {
            const active = n.href === "/hospital" ? path === "/hospital" : path.startsWith(n.href);
            return (
              <Link key={n.href} href={n.href} className={cn("flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] font-semibold", active ? "bg-ink text-bg" : "text-ink hover:bg-soft")}>
                <Icon name={n.icon} size={19} />
                {n.label}
                {n.href === "/hospital" && pendingCount > 0 && <span className="ml-auto rounded-full bg-red px-2 py-0.5 text-[12px] font-bold text-white">{pendingCount}</span>}
              </Link>
            );
          })}
          <div className="mt-auto flex flex-col gap-2 pt-4">
            <LanguageSwitcher />
            <button onClick={() => void signOut()} className="flex items-center gap-2 rounded-xl px-3 py-2 text-[14px] font-semibold text-muted hover:bg-soft"><Icon name="logout" size={16} />Sign out</button>
          </div>
        </aside>

        {/* mobile top bar */}
        <div className="flex items-center justify-between border-b border-line bg-card px-4 py-3 lg:hidden">
          <button onClick={() => setOpen(true)} className="grid h-10 w-10 place-items-center rounded-lg" aria-label="Menu"><Icon name="list" size={22} /></button>
          <Brand small />
          <span className="relative w-10">{pendingCount > 0 && <span className="absolute right-1 top-0 grid h-5 w-5 place-items-center rounded-full bg-red text-[11px] font-bold text-white">{pendingCount}</span>}</span>
        </div>
        {open && (
          <div className="fixed inset-0 z-[90] bg-black/40 lg:hidden" onClick={() => setOpen(false)}>
            <nav className="flex h-full w-72 flex-col gap-1 bg-card p-4" onClick={(e) => e.stopPropagation()}>
              {NAV.map((n) => (
                <Link key={n.href} href={n.href} onClick={() => setOpen(false)} className={cn("flex items-center gap-3 rounded-xl px-3 py-3 text-[16px] font-semibold", path.startsWith(n.href) && n.href !== "/hospital" || path === n.href ? "bg-ink text-bg" : "")}>
                  <Icon name={n.icon} size={20} />{n.label}
                </Link>
              ))}
              <LanguageSwitcher />
              <button onClick={() => void signOut()} className="mt-2 flex items-center gap-2 rounded-xl px-3 py-2 text-[15px] font-semibold text-muted"><Icon name="logout" size={16} />Sign out</button>
            </nav>
          </div>
        )}

        <main className="min-w-0 flex-1 px-4 py-5 lg:px-8 lg:py-6">
          <div className="mb-4"><ConnectionBanners /></div>
          {children}
        </main>
      </div>
    </HospitalContext.Provider>
  );
}

export default function HospitalLayout({ children }: { children: ReactNode }) {
  return (
    <RequireRole role="hospital_staff">
      <Shell>{children}</Shell>
    </RequireRole>
  );
}
