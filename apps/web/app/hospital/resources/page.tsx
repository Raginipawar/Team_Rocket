"use client";

import { useState } from "react";
import { ApiError, errorText, patch } from "@/lib/api";
import type { Resource } from "@/lib/api-types";
import { useHosp } from "../context";
import { FreshnessBadge } from "@/components/emergency/badges";
import { Card, ErrorState, Input, LoadingState } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";

const LABEL: Record<string, string> = { ventilator: "Ventilators", cath_lab: "Cath lab", ct_scanner: "CT scanner", mri: "MRI", defibrillator: "Defibrillators", operating_theatre: "Operating theatres", dialysis: "Dialysis", blood_o_neg: "Blood O-negative", blood_o_pos: "Blood O-positive", blood_a_pos: "Blood A-positive", blood_b_pos: "Blood B-positive", blood_ab_pos: "Blood AB-positive" };

function Row({ r }: { r: Resource }) {
  const toast = useToast();
  const [val, setVal] = useState(String(r.available));
  const [busy, setBusy] = useState(false);
  const { refetch } = useHosp();
  const dirty = Number(val) !== r.available;
  const save = async () => {
    const n = Number(val);
    if (!Number.isFinite(n) || n < 0) {
      toast("Enter a number 0 or more", "error");
      return;
    }
    if (n + r.reserved > r.total) {
      toast(`Cannot be more than ${r.total - r.reserved} (total ${r.total} minus ${r.reserved} reserved)`, "error");
      return;
    }
    setBusy(true);
    try {
      await patch(`/hospital/resources/${r.id}`, { available: n, version: r.version });
      refetch();
      toast("Saved", "success");
    } catch (e) {
      if (e instanceof ApiError && e.code === "VERSION_CONFLICT") refetch();
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card className="flex flex-wrap items-center gap-3">
      <div className="min-w-[160px] flex-1">
        <p className="text-[18px] font-bold">{LABEL[r.type] ?? r.type}</p>
        <FreshnessBadge at={r.reported_at} freshness={r.freshness} />
      </div>
      <div className="flex items-center gap-2">
        <Input type="number" min={0} max={r.total} value={val} onChange={(e) => setVal(e.target.value)} className="h-12 w-20 text-center text-[18px]" aria-label={`${LABEL[r.type] ?? r.type} available`} />
        <span className="text-[16px] text-muted">/ {r.total}</span>
      </div>
      {r.reserved > 0 && <span className="rounded-full bg-amber-soft px-2.5 py-1 text-[13px] font-semibold text-amber">{r.reserved} reserved</span>}
      <Button size="sm" disabled={!dirty} loading={busy} onClick={() => void save()}><Icon name="check" size={16} />Save</Button>
    </Card>
  );
}

export default function ResourcesPage() {
  const { dashboard, loading, error, refetch } = useHosp();
  if (loading) return <LoadingState />;
  if (error || !dashboard) return <ErrorState text="Could not load resources" onRetry={refetch} />;
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-[26px] font-extrabold">Resources</h1>
      <p className="text-[16px] text-muted">Numbers older than 30 minutes are shown as stale to ambulances and the ranking model.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        {dashboard.resources.map((r: Resource & { id: string }) => <Row key={r.id} r={r} />)}
      </div>
    </div>
  );
}
