"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { IncomingAmbulance, Room } from "@/lib/api-types";
import { errorText, post } from "@/lib/api";
import { useHosp } from "./context";
import RequestCard from "@/components/hospital/RequestCard";
import Map from "@/components/map";
import { FreshnessBadge, SignalBadge } from "@/components/emergency/badges";
import { Banner, EmptyState, ErrorState, LoadingState } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { minutes, mmss, reg } from "@/lib/format";
import { useNow } from "@/lib/hooks";
import { cn } from "@/lib/cn";

function IncomingRow({ a }: { a: IncomingAmbulance }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-line bg-card p-3">
      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-blue-soft text-blue"><Icon name="ambulance" size={20} /></span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[16px] font-bold">{reg(a.registration_no)} <span className="text-[13px] font-normal text-muted">{a.type}</span></p>
        <p className="truncate text-[14px] text-muted">{a.patient_display} · {a.room_code ?? "no room yet"}</p>
      </div>
      <div className="text-right">
        {a.eta_sec != null ? <span className="text-[19px] font-extrabold">{minutes(a.eta_sec)}<span className="text-[12px] font-normal text-muted"> min</span></span> : null}
        <div><SignalBadge signal={a.signal} /></div>
      </div>
    </div>
  );
}

/** At-the-door row: offload timer (§16.4) + the "Patient received" action that closes the handoff. */
function AtDoorRow({ a, onReceived }: { a: IncomingAmbulance; onReceived: () => void }) {
  const toast = useToast();
  const now = useNow(1000);
  const [busy, setBusy] = useState(false);
  const waitSec = a.arrived_at ? (now - new Date(a.arrived_at).getTime()) / 1000 : 0;
  const late = waitSec > 900; // §4 OFFLOAD_DELAY_ALERT_MIN = 15 min
  const receive = async () => {
    setBusy(true);
    try {
      await post(`/hospital/handoffs/${a.emergency_id}/received`, {});
      onReceived();
      toast("Patient received", "success");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className={cn("flex flex-col gap-3 rounded-2xl border p-4", late ? "border-red/40 bg-red-soft" : "border-green/40 bg-green-soft/40")}>
      <div className="flex items-center gap-3">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-card"><Icon name="ambulance" size={20} className={late ? "text-red-ink" : "text-green"} /></span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[16px] font-bold">{reg(a.registration_no)} · {a.patient_display}</p>
          <p className="truncate text-[14px] text-muted">{a.room_code ?? "Room not set"}</p>
        </div>
        <span className={cn("text-[22px] font-extrabold tabular-nums", late && "text-red-ink")}>{mmss(waitSec)}</span>
      </div>
      <Button size="md" variant={late ? "danger" : "success"} block loading={busy} onClick={() => void receive()}><Icon name="check" size={20} stroke={2.6} />Patient received</Button>
    </div>
  );
}

export default function HospitalDashboardPage() {
  const { dashboard, loading, error, refetch } = useHosp();
  const qc = useQueryClient();
  const toast = useToast();
  const [confirming, setConfirming] = useState(false);

  if (loading) return <LoadingState />;
  if (error || !dashboard) return <ErrorState text="Could not load the dashboard" onRetry={refetch} />;

  const rooms: Room[] = Object.values(dashboard.rooms).flat();
  const staff = dashboard.staff_on_duty;
  const confirm = async () => {
    setConfirming(true);
    try {
      await post("/hospital/availability/confirm");
      refetch();
      void qc.invalidateQueries({ queryKey: ["hosp-resources"] });
      toast("Availability confirmed", "success");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setConfirming(false);
    }
  };

  const freeByType = rooms.reduce<Record<string, number>>((acc, r) => {
    if (r.status === "free") acc[r.type] = (acc[r.type] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-[26px] font-extrabold">{dashboard.hospital.name}</h1>
          <p className="mt-1 flex items-center gap-2 text-[14px]"><FreshnessBadge at={dashboard.hospital.last_confirmed_at} freshness={dashboard.freshness} /></p>
        </div>
        <Button size="lg" onClick={() => void confirm()} loading={confirming}><Icon name="check" size={20} stroke={2.6} />Confirm availability</Button>
      </div>

      {dashboard.freshness === "stale" && <Banner tone="amber" icon="clock">Your numbers have not been confirmed in a while. Tap Confirm availability so ambulances trust your beds.</Banner>}

      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <div className="flex flex-col gap-5">
          <section>
            <h2 className="mb-3 text-[19px] font-bold">New requests {dashboard.pending_requests.length > 0 && <span className="ml-1 rounded-full bg-red px-2.5 py-0.5 text-[13px] font-bold text-white">{dashboard.pending_requests.length}</span>}</h2>
            {dashboard.pending_requests.length === 0 ? (
              <EmptyState icon="bell" title="No incoming requests right now" />
            ) : (
              <div className="flex flex-col gap-4">
                {dashboard.pending_requests.map((r) => <RequestCard key={r.request_id} req={r} rooms={rooms} staff={staff} />)}
              </div>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-[19px] font-bold">At the door {(dashboard.at_door ?? []).length > 0 && <span className="ml-1 rounded-full bg-amber-soft px-2.5 py-0.5 text-[13px] font-bold text-amber">{dashboard.at_door!.length}</span>}</h2>
            {(dashboard.at_door ?? []).length === 0 ? <EmptyState icon="door" title="No ambulance waiting" /> : (
              <div className="grid gap-3 sm:grid-cols-2">{dashboard.at_door!.map((a) => <AtDoorRow key={a.emergency_id} a={a} onReceived={refetch} />)}</div>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-[19px] font-bold">Incoming</h2>
            <Map
              height={260}
              ambulances={(dashboard.incoming ?? []).filter((a) => a.location).map((a) => ({ ...a.location!, id: a.emergency_id, tone: "blue", label: reg(a.registration_no) }))}
              hospitals={dashboard.hospital.location ? [{ ...dashboard.hospital.location, name: dashboard.hospital.name, tone: "green" }] : []}
              followDefault={false}
            />
            <div className="mt-3 flex flex-col gap-2">
              {(dashboard.incoming ?? []).length === 0 ? <EmptyState icon="ambulance" title="No confirmed ambulances on the way" /> : dashboard.incoming!.map((a) => <IncomingRow key={a.emergency_id} a={a} />)}
            </div>
          </section>
        </div>

        <aside className="flex flex-col gap-4">
          <div className="rounded-[24px] border border-line bg-card p-5">
            <h3 className="mb-3 text-[15px] font-bold uppercase tracking-wide text-muted">Free rooms</h3>
            <div className="flex flex-col gap-2">
              {Object.entries(freeByType).length === 0 && <p className="text-[15px] text-muted">No free rooms</p>}
              {Object.entries(freeByType).map(([type, n]) => (
                <div key={type} className="flex items-center justify-between text-[16px]"><span className="capitalize">{type.replace(/_/g, " ")}</span><b className={n === 0 ? "text-red-ink" : ""}>{n}</b></div>
              ))}
            </div>
          </div>
          <div className="rounded-[24px] border border-line bg-card p-5">
            <h3 className="mb-3 text-[15px] font-bold uppercase tracking-wide text-muted">Staff on duty</h3>
            <div className="flex flex-col gap-1.5 text-[15px]">
              {staff.length === 0 ? <p className="text-muted">No staff on the current shift</p> : staff.slice(0, 10).map((s) => (
                <div key={s.id} className="flex items-center justify-between"><span>{s.name}</span><span className="text-muted capitalize">{(s.specialty ?? s.role ?? "").replace(/_/g, " ")}</span></div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
