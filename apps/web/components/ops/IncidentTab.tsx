"use client";

// Incident tab (technical.md §16.6): escalation summary, map, options with claim/resolve,
// manual override with a mandatory reason, and the audit trail.

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { errorText, get, post } from "@/lib/api";
import type { AuditEntry, Escalation, OpsOverview } from "@/lib/api-types";
import { ago, dateTime } from "@/lib/format";
import Map from "@/components/map";
import { EmptyState, ErrorState, LoadingState, SectionLabel, Textarea } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { Select } from "@/components/ui/bits";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { useNow } from "@/lib/hooks";
import { cn } from "@/lib/cn";

const TYPE_LABEL: Record<string, string> = { mass_casualty: "Mass casualty", no_ambulance: "No ambulance available", no_hospital: "No hospital accepting", system_anomaly: "System anomaly" };

function EscalationCard({ esc, onChanged }: { esc: Escalation; onChanged: () => void }) {
  const toast = useToast();
  const now = useNow(1000);
  const [busy, setBusy] = useState<string | null>(null);
  const [overriding, setOverriding] = useState(false);
  const [reason, setReason] = useState("");
  const [hospitalId, setHospitalId] = useState("");
  const audit = useQuery({ queryKey: ["ops-audit", esc.id], queryFn: () => get<{ data: AuditEntry[] }>(`/ops/audit?entity_id=${esc.id}`) });

  const claim = async () => {
    setBusy("claim");
    try {
      await post(`/ops/escalations/${esc.id}/claim`);
      onChanged();
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(null);
    }
  };
  const resolve = async (optionId: string) => {
    setBusy(optionId);
    try {
      await post(`/ops/escalations/${esc.id}/resolve`, { option_id: optionId });
      onChanged();
      toast("Resolved", "success");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(null);
    }
  };
  const override = async () => {
    if (!esc.emergency_id || reason.trim().length < 3 || !hospitalId) return;
    setBusy("override");
    try {
      await post(`/ops/emergencies/${esc.emergency_id}/override`, { hospital_id: hospitalId, reason: reason.trim() });
      setOverriding(false);
      onChanged();
      toast("Overridden", "success");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(null);
    }
  };

  const defaultIn = esc.default_at ? Math.max(0, Math.round((new Date(esc.default_at).getTime() - now) / 1000)) : null;
  const claimedByMe = !!esc.claimed_by;

  return (
    <div className="rounded-[24px] border-2 border-red/30 bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-12 w-12 place-items-center rounded-full bg-red text-white"><Icon name="alert" size={24} /></span>
          <div>
            <p className="text-[13px] font-bold uppercase tracking-wide text-red-ink">{TYPE_LABEL[esc.type] ?? esc.type}</p>
            <p className="text-[15px] text-muted">Opened {ago(esc.created_at, now)}</p>
          </div>
        </div>
        <span className={cn("rounded-full px-3 py-1 text-[13px] font-bold", esc.status === "open" ? "bg-red-soft text-red-ink" : esc.status === "claimed" ? "bg-amber-soft text-amber" : "bg-green-soft text-green")}>
          {esc.status.replace(/_/g, " ")}
        </span>
      </div>

      <p className="mt-3 text-[17px] leading-snug">{esc.summary}</p>

      {esc.map && (esc.map.pickup || esc.map.hospitals?.length) && (
        <div className="mt-3">
          <Map
            height={220}
            pickup={esc.map.pickup ?? null}
            ambulance={esc.map.ambulance ? { ...esc.map.ambulance, tone: "dark" } : null}
            hospitals={(esc.map.hospitals ?? []).filter((h) => h.lat).map((h) => ({ lat: h.lat, lng: h.lng, name: h.name, tone: h.status ? "red" : "green" }))}
            followDefault={false}
          />
        </div>
      )}

      {!!esc.tried?.length && (
        <div className="mt-3">
          <SectionLabel>Already tried</SectionLabel>
          <ul className="mt-1 flex flex-col gap-1 text-[15px]">
            {esc.tried.map((t, i) => <li key={i} className="flex items-center gap-2"><Icon name="x" size={14} className="text-red-ink" />{t.hospital}: {t.outcome}</li>)}
          </ul>
        </div>
      )}

      {esc.status !== "resolved" && esc.status !== "auto_defaulted" && (
        <div className="mt-4 flex flex-col gap-2">
          {!claimedByMe && (
            <Button size="lg" onClick={() => void claim()} loading={busy === "claim"}><Icon name="hand" size={20} />I&apos;m handling this</Button>
          )}
          {esc.options.map((o) => (
            <Button key={o.id} size="lg" variant={o.is_default ? "primary" : "outline"} loading={busy === o.id} onClick={() => void resolve(o.id)} className="justify-between">
              <span className="flex items-center gap-2">{o.is_default && <Icon name="check" size={16} />}{o.label}</span>
              {o.is_default && defaultIn != null && <span className="text-[13px] font-normal opacity-80">auto in {defaultIn}s</span>}
            </Button>
          ))}
          {esc.emergency_id && (
            <Button size="lg" variant="ghost" onClick={() => setOverriding(true)}><Icon name="edit" size={18} />Manual override</Button>
          )}
        </div>
      )}

      {audit.data?.data?.length ? (
        <details className="mt-4">
          <summary className="cursor-pointer text-[14px] font-semibold text-muted">Audit trail ({audit.data.data.length})</summary>
          <ul className="mt-2 flex flex-col gap-1.5 border-l-2 border-line pl-3 text-[14px]">
            {audit.data.data.map((a) => <li key={a.id}><span className="text-muted">{dateTime(a.at)}</span> · {a.actor_type} {a.actor_id} · {a.action}{a.reason ? ` (${a.reason})` : ""}</li>)}
          </ul>
        </details>
      ) : null}

      <Sheet open={overriding} onOpenChange={setOverriding} title="Manual override" description="Assign a hospital directly. A reason is required and is written to the audit log."
        footer={<Button size="lg" block variant="danger" loading={busy === "override"} disabled={!hospitalId || reason.trim().length < 3} onClick={() => void override()}>Force assign</Button>}>
        <div className="flex flex-col gap-4">
          <div>
            <p className="mb-1.5 text-[16px] font-semibold">Hospital</p>
            <Select value={hospitalId} onChange={(e) => setHospitalId(e.target.value)}>
              <option value="">Choose a hospital</option>
              {(esc.map?.hospitals ?? []).filter((h) => h.id).map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
            </Select>
          </div>
          <div>
            <p className="mb-1.5 text-[16px] font-semibold">Reason (required)</p>
            <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why is a manual override needed?" />
          </div>
        </div>
      </Sheet>
    </div>
  );
}

export default function IncidentTab({ overview, focusId, onChanged }: { overview: OpsOverview; focusId: string | null; onChanged: () => void }) {
  const open = useMemo(() => overview.escalations.filter((e) => e.status === "open" || e.status === "claimed"), [overview.escalations]);
  const resolved = useMemo(() => overview.escalations.filter((e) => e.status === "resolved" || e.status === "auto_defaulted"), [overview.escalations]);
  const [showResolved, setShowResolved] = useState(false);

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-[20px] border border-line bg-card p-4 text-center"><p className="text-[13px] text-muted">Live emergencies</p><p className="text-[28px] font-extrabold">{overview.emergencies.length}</p></div>
        <div className="rounded-[20px] border border-line bg-card p-4 text-center"><p className="text-[13px] text-muted">Ambulances online</p><p className="text-[28px] font-extrabold">{overview.ambulances.filter((a) => a.status !== "offline").length}</p></div>
        <div className="rounded-[20px] border border-line bg-card p-4 text-center"><p className="text-[13px] text-muted">Open escalations</p><p className={cn("text-[28px] font-extrabold", open.length > 0 && "text-red-ink")}>{open.length}</p></div>
      </div>

      <section>
        <h2 className="mb-3 text-[19px] font-bold">Escalations</h2>
        {open.length === 0 ? <EmptyState icon="shield" title="No open escalations" text="Everything is being handled automatically." /> : (
          <div className="flex flex-col gap-4">
            {[...open].sort((a, b) => (a.id === focusId ? -1 : b.id === focusId ? 1 : 0)).map((e) => <EscalationCard key={e.id} esc={e} onChanged={onChanged} />)}
          </div>
        )}
      </section>

      {resolved.length > 0 && (
        <section>
          <button onClick={() => setShowResolved((s) => !s)} className="flex items-center gap-2 text-[15px] font-semibold text-muted">
            <Icon name={showResolved ? "down" : "chevron"} size={16} />Resolved today ({resolved.length})
          </button>
          {showResolved && (
            <div className="mt-3 flex flex-col gap-2">
              {resolved.map((e) => (
                <div key={e.id} className="flex items-center justify-between rounded-2xl border border-line bg-card px-4 py-3 text-[15px]">
                  <span>{TYPE_LABEL[e.type] ?? e.type}</span>
                  <span className="text-muted">{e.status === "auto_defaulted" ? "auto-defaulted" : `resolved by ${e.claimed_by_name ?? "someone"}`}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
