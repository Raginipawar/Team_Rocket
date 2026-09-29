"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { errorText, get, post } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { Card, EmptyState, ErrorState, Field, Input, LoadingState } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";

type UnknownPatient = { temp_id: string; emergency_id: string; display: string; status: string; merged: boolean; received_at: string | null };

export default function PatientsPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["hosp-patients"], queryFn: () => get<{ patients: UnknownPatient[] }>("/hospital/patients") });
  const [merging, setMerging] = useState<UnknownPatient | null>(null);
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);

  const merge = async () => {
    if (!merging) return;
    setBusy(true);
    try {
      await post(`/hospital/patients/${merging.temp_id}/merge`, { phone: `+91${phone.replace(/\D/g, "").slice(-10)}` });
      setMerging(null);
      setPhone("");
      void qc.invalidateQueries({ queryKey: ["hosp-patients"] });
      toast("Patient identity merged", "success");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-[26px] font-extrabold">Unknown patients</h1>
      <p className="text-[16px] text-muted">When an unconscious or unidentified patient is later identified, merge their record here so it links to their real profile.</p>
      {q.isLoading ? <LoadingState /> : q.isError ? <ErrorState text={errorText(q.error)} onRetry={() => q.refetch()} /> : !q.data?.patients.length ? (
        <EmptyState icon="user" title="No unidentified patients" />
      ) : (
        <div className="flex flex-col gap-3">
          {q.data.patients.map((p) => (
            <Card key={p.temp_id} className="flex items-center gap-3">
              <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-amber-soft text-amber"><Icon name="user" size={22} /></span>
              <div className="min-w-0 flex-1">
                <p className="text-[17px] font-bold">{p.temp_id}</p>
                <p className="text-[14px] text-muted">{p.display}{p.received_at ? ` · ${dateTime(p.received_at)}` : ""} · {p.status.replace(/_/g, " ")}</p>
              </div>
              {p.merged ? <span className="text-[14px] font-semibold text-green">Merged</span> : <Button size="sm" onClick={() => setMerging(p)}>Merge</Button>}
            </Card>
          ))}
        </div>
      )}

      <Sheet open={!!merging} onOpenChange={(o) => !o && setMerging(null)} title={`Merge ${merging?.temp_id ?? ""}`} description="Enter the patient's real phone number to link this record to their profile."
        footer={<Button size="lg" block loading={busy} disabled={phone.replace(/\D/g, "").length < 10} onClick={() => void merge()}>Merge</Button>}>
        <Field label="Mobile number" htmlFor="mphone"><Input id="mphone" inputMode="numeric" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="98765 43210" autoFocus /></Field>
      </Sheet>
    </div>
  );
}
