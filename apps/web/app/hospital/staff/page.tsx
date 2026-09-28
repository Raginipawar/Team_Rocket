"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ENUMS, type StaffSpecialty } from "@/lib/enums";
import { errorText, get, post } from "@/lib/api";
import type { Shift, Staff } from "@/lib/api-types";
import { useHosp } from "../context";
import { Card, ErrorState, Field, Input, LoadingState, Select } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { clock } from "@/lib/format";
import { cn } from "@/lib/cn";

const SPEC_LABEL: Record<StaffSpecialty, string> = { emergency_physician: "Emergency physician", cardiologist: "Cardiologist", neurologist: "Neurologist", trauma_surgeon: "Trauma surgeon", burns_surgeon: "Burns surgeon", obstetrician: "Obstetrician", pediatrician: "Pediatrician", pulmonologist: "Pulmonologist", anesthetist: "Anesthetist", er_nurse: "ER nurse" };

function ShiftsSheet({ staff, open, onOpenChange }: { staff: Staff; open: boolean; onOpenChange: (o: boolean) => void }) {
  const toast = useToast();
  const q = useQuery({ queryKey: ["shifts", staff.id], queryFn: () => get<{ shifts: Shift[] }>(`/hospital/staff/${staff.id}/shifts`), enabled: open });
  const [rows, setRows] = useState<{ start: string; end: string }[]>([]);
  const [busy, setBusy] = useState(false);

  const shifts = rows.length ? rows : (q.data?.shifts ?? []).map((s) => ({ start: toLocal(s.start_at), end: toLocal(s.end_at) }));
  function toLocal(iso: string) {
    const d = new Date(iso);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  }
  const save = async () => {
    setBusy(true);
    try {
      await post(`/hospital/staff/${staff.id}/shifts`, { shifts: shifts.filter((s) => s.start && s.end).map((s) => ({ start_at: new Date(s.start).toISOString(), end_at: new Date(s.end).toISOString() })) });
      toast("Saved", "success");
      onOpenChange(false);
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={`${staff.name}'s shifts`} wide footer={<Button size="lg" block loading={busy} onClick={() => void save()}>Save shifts</Button>}>
      {q.isLoading ? <LoadingState /> : (
        <div className="flex flex-col gap-3">
          {shifts.map((s, i) => (
            <div key={i} className="flex items-center gap-2">
              <Input type="datetime-local" value={s.start} onChange={(e) => { const next = [...shifts]; next[i] = { ...next[i], start: e.target.value }; setRows(next); }} className="text-[15px]" />
              <span className="text-muted">to</span>
              <Input type="datetime-local" value={s.end} onChange={(e) => { const next = [...shifts]; next[i] = { ...next[i], end: e.target.value }; setRows(next); }} className="text-[15px]" />
              <Button variant="ghost" size="icon" onClick={() => setRows(shifts.filter((_, j) => j !== i))} aria-label="Remove shift"><Icon name="trash" size={18} /></Button>
            </div>
          ))}
          <Button variant="outline" onClick={() => setRows([...shifts, { start: "", end: "" }])}><Icon name="plus" size={18} />Add a shift</Button>
        </div>
      )}
    </Sheet>
  );
}

export default function StaffPage() {
  const { dashboard, loading, error, refetch } = useHosp();
  const qc = useQueryClient();
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [shiftsFor, setShiftsFor] = useState<Staff | null>(null);
  const [name, setName] = useState("");
  const [role, setRole] = useState<StaffSpecialty>("er_nurse");
  const [busy, setBusy] = useState(false);

  const all = useQuery({ queryKey: ["hosp-staff"], queryFn: () => get<{ staff: Staff[] }>("/hospital/staff") });

  if (loading || all.isLoading) return <LoadingState />;
  if (error || !dashboard) return <ErrorState text="Could not load staff" onRetry={refetch} />;

  const add = async () => {
    setBusy(true);
    try {
      await post("/hospital/staff", { name, role, specialty: role });
      setAdding(false);
      setName("");
      void qc.invalidateQueries({ queryKey: ["hosp-staff"] });
      toast("Added", "success");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };

  const list = all.data?.staff ?? [];
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-[26px] font-extrabold">Staff and shifts</h1>
        <Button onClick={() => setAdding(true)}><Icon name="plus" size={20} />Add staff</Button>
      </div>
      <div className="flex flex-col gap-2">
        {list.map((s) => (
          <Card key={s.id} className="flex items-center gap-3">
            <span className={cn("h-3 w-3 shrink-0 rounded-full", s.on_duty ? "bg-green" : "bg-line")} title={s.on_duty ? "On duty now" : "Off duty"} />
            <div className="min-w-0 flex-1">
              <p className="text-[17px] font-bold">{s.name}</p>
              <p className="text-[14px] text-muted">{SPEC_LABEL[s.specialty as StaffSpecialty] ?? s.specialty} {s.shift ? `· on until ${clock(s.shift.end_at)}` : ""}</p>
            </div>
            <Button size="sm" variant="soft" onClick={() => setShiftsFor(s)}>Shifts</Button>
          </Card>
        ))}
      </div>

      <Sheet open={adding} onOpenChange={setAdding} title="Add staff" footer={<Button size="lg" block loading={busy} disabled={!name.trim()} onClick={() => void add()}>Add</Button>}>
        <div className="flex flex-col gap-4">
          <Field label="Name" htmlFor="sname"><Input id="sname" value={name} onChange={(e) => setName(e.target.value)} autoFocus /></Field>
          <Field label="Role" htmlFor="srole">
            <Select id="srole" value={role} onChange={(e) => setRole(e.target.value as StaffSpecialty)}>
              {ENUMS.StaffSpecialty.map((r) => <option key={r} value={r}>{SPEC_LABEL[r]}</option>)}
            </Select>
          </Field>
        </div>
      </Sheet>
      {shiftsFor && <ShiftsSheet staff={shiftsFor} open={!!shiftsFor} onOpenChange={(o) => !o && setShiftsFor(null)} />}
    </div>
  );
}
