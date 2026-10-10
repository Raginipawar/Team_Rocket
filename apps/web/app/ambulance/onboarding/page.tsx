"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { get, post, errorText, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Brand, LanguageSwitcher, MockRibbon } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Card, Field, Input, LoadingState, Select } from "@/components/ui/bits";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/cn";

type RegStatus = { status: "pending" | "approved" | "rejected" | "demo" | null; ambulance_id: string | null; registration_no?: string | null; rejection_reason?: string | null };

const CAPABILITIES = [
  { id: "general", label: "General emergency transport" },
  { id: "cardiac", label: "Cardiac / advanced life support" },
  { id: "trauma", label: "Trauma and critical care" },
  { id: "pediatric", label: "Paediatric care" },
  { id: "ventilator", label: "Ventilator-capable transport" },
];
const EQUIPMENT = [
  { id: "oxygen", label: "Oxygen delivery" },
  { id: "aed", label: "AED / defibrillator" },
  { id: "monitor", label: "Patient monitor" },
  { id: "ventilator", label: "Ventilator" },
  { id: "suction", label: "Suction equipment" },
  { id: "stretcher", label: "Stretcher & immobilisation" },
];
const CATEGORIES = [
  { id: "A", label: "A -- Patient transport" },
  { id: "B", label: "B -- Basic life support" },
  { id: "C", label: "C -- Advanced life support" },
  { id: "D", label: "D -- Mobile ICU" },
];

function MultiSelect({ options, value, onChange }: { options: { id: string; label: string }[]; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => {
        const on = value.includes(o.id);
        return (
          <button key={o.id} type="button" onClick={() => onChange(on ? value.filter((v) => v !== o.id) : [...value, o.id])}
            className={cn("rounded-full border-2 px-4 py-2 text-[15px] font-semibold", on ? "border-ink bg-ink text-bg" : "border-line bg-card text-ink")}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export default function AmbulanceOnboarding() {
  const router = useRouter();
  const toast = useToast();
  const { session, ready, setToken } = useAuth();
  const [mode, setMode] = useState<"choose" | "live" | "demoBusy">("choose");

  const reg = useQuery({ queryKey: ["amb-reg-status"], queryFn: () => get<RegStatus>("/ambulance/registration-status") });

  useEffect(() => {
    if (ready && !session) router.replace("/login?role=paramedic");
  }, [ready, session, router]);

  useEffect(() => {
    if (reg.data?.status === "demo" || reg.data?.status === "approved") router.replace("/ambulance");
  }, [reg.data, router]);

  const goDemo = async () => {
    setMode("demoBusy");
    try {
      const r = await post<{ access_token: string }>("/ambulance/register/demo", {});
      setToken(r.access_token);
      toast("Demo ambulance ready", "success");
      router.replace("/ambulance");
    } catch (e) {
      toast(errorText(e), "error");
      setMode("choose");
    }
  };

  if (!ready || reg.isLoading) return <LoadingState />;

  return (
    <div className="min-h-dvh bg-page">
      <MockRibbon />
      <header className="mx-auto flex max-w-xl items-center justify-between px-5 pt-5">
        <Brand small />
        <LanguageSwitcher compact />
      </header>
      <main className="mx-auto flex max-w-xl flex-col gap-5 px-5 pb-16 pt-8">
        {reg.data?.status === "pending" ? (
          <PendingStatus regNo={reg.data.registration_no} />
        ) : reg.data?.status === "rejected" ? (
          <RejectedStatus reason={reg.data.rejection_reason} onRetry={() => setMode("live")} />
        ) : mode === "choose" ? (
          <>
            <div>
              <h1 className="text-[28px] font-extrabold leading-tight">Operating mode</h1>
              <p className="mt-1 text-[17px] text-muted">Your phone number is verified. Now register your ambulance to go live, or use Demo to try the app.</p>
            </div>
            <Card className="flex flex-col gap-3">
              <p className="text-[19px] font-bold">Live</p>
              <p className="text-[15px] text-muted">Real ambulance registration. Submitted for review -- you can't accept real emergencies until our team approves it.</p>
              <Button size="lg" block onClick={() => setMode("live")}>Register my ambulance</Button>
            </Card>
            <Card className="flex flex-col gap-3">
              <p className="text-[19px] font-bold">Demo</p>
              <p className="text-[15px] text-muted">Prefilled demonstration ambulance. Lets you try the full app immediately -- clearly labelled, isolated from real review.</p>
              <Button size="lg" block variant="outline" loading={(mode as string) === "demoBusy"} onClick={() => void goDemo()}>Use demo ambulance</Button>
            </Card>
          </>
        ) : (
          <LiveRegisterForm onBack={() => setMode("choose")} onSubmitted={(token) => { setToken(token); void reg.refetch(); }} />
        )}
      </main>
    </div>
  );
}

function PendingStatus({ regNo }: { regNo?: string | null }) {
  return (
    <Card className="flex flex-col items-center gap-3 py-10 text-center">
      <Icon name="clock" size={40} />
      <p className="text-[22px] font-extrabold">Application under review</p>
      <p className="text-[16px] text-muted">{regNo ? `${regNo} is ` : "Your ambulance is "}submitted and pending verification by our team. You'll be notified once it's approved. Real dispatch stays off until then.</p>
    </Card>
  );
}

function RejectedStatus({ reason, onRetry }: { reason?: string | null; onRetry: () => void }) {
  return (
    <Card className="flex flex-col gap-3 py-8 text-center">
      <Icon name="alert" size={36} className="mx-auto text-red" />
      <p className="text-[22px] font-extrabold">Application needs changes</p>
      <p className="text-[16px] text-muted">{reason ?? "Your registration wasn't approved. Please review and resubmit."}</p>
      <Button size="lg" block onClick={onRetry}>Update and resubmit</Button>
    </Card>
  );
}

function LiveRegisterForm({ onBack, onSubmitted }: { onBack: () => void; onSubmitted: (token: string) => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [f, setF] = useState({
    operator_name: "", email: "", organisation: "",
    registration_no: "", make_model: "", category: "B", year: "",
    operating_area: "", base_location: "",
    capabilities: ["general"] as string[], equipment: [] as string[],
    driver_license_no: "", crew_details: "", rc_number: "", insurance_number: "", permit_number: "",
    declaration_confirmed: false,
  });
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((s) => ({ ...s, [k]: v }));

  const submit = async () => {
    setErr(null);
    if (!f.operator_name || !f.registration_no || !f.make_model || !f.operating_area || !f.base_location || !f.driver_license_no) {
      setErr("Please fill in all required fields.");
      return;
    }
    if (!f.declaration_confirmed) {
      setErr("Please confirm the declaration to submit.");
      return;
    }
    setBusy(true);
    try {
      const r = await post<{ access_token: string }>("/ambulance/register", { ...f, year: f.year ? Number(f.year) : null });
      toast("Registration submitted for review", "success");
      onSubmitted(r.access_token);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="flex flex-col gap-5" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
      <div className="flex items-center gap-2">
        <Button type="button" variant="ghost" size="icon" onClick={onBack}><Icon name="back" size={20} /></Button>
        <h1 className="text-[24px] font-extrabold">Live registration</h1>
      </div>

      <Card className="flex flex-col gap-3">
        <p className="text-[14px] font-bold uppercase tracking-wider text-muted">A · Operator</p>
        <Field label="Full name" htmlFor="opname"><Input id="opname" value={f.operator_name} onChange={(e) => set("operator_name", e.target.value)} /></Field>
        <Field label="Email" htmlFor="email"><Input id="email" type="email" value={f.email} onChange={(e) => set("email", e.target.value)} /></Field>
        <Field label="Organisation / ambulance service name" htmlFor="org"><Input id="org" value={f.organisation} onChange={(e) => set("organisation", e.target.value)} /></Field>
      </Card>

      <Card className="flex flex-col gap-3">
        <p className="text-[14px] font-bold uppercase tracking-wider text-muted">B · Vehicle</p>
        <Field label="Vehicle registration number" hint="e.g. MH12AB1234" htmlFor="regno"><Input id="regno" value={f.registration_no} onChange={(e) => set("registration_no", e.target.value.toUpperCase())} /></Field>
        <Field label="Make and model" htmlFor="make"><Input id="make" value={f.make_model} onChange={(e) => set("make_model", e.target.value)} /></Field>
        <Field label="Ambulance category (AIS-125)" htmlFor="cat">
          <Select id="cat" value={f.category} onChange={(e) => set("category", e.target.value)}>
            {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </Select>
        </Field>
        <Field label="Year of manufacture" htmlFor="year"><Input id="year" inputMode="numeric" value={f.year} onChange={(e) => set("year", e.target.value.replace(/\D/g, "").slice(0, 4))} /></Field>
        <Field label="Primary operating area" htmlFor="area"><Input id="area" value={f.operating_area} onChange={(e) => set("operating_area", e.target.value)} /></Field>
        <Field label="Base station address" htmlFor="base"><Input id="base" value={f.base_location} onChange={(e) => set("base_location", e.target.value)} /></Field>
      </Card>

      <Card className="flex flex-col gap-3">
        <p className="text-[14px] font-bold uppercase tracking-wider text-muted">C · Medical capabilities</p>
        <p className="text-[15px] text-muted -mt-1">Used to match the right ambulance to a case -- e.g. a cardiac call prefers a cardiac-capable unit.</p>
        <MultiSelect options={CAPABILITIES} value={f.capabilities} onChange={(v) => set("capabilities", v)} />
        <p className="mt-2 text-[14px] font-bold uppercase tracking-wider text-muted">Equipment on board</p>
        <MultiSelect options={EQUIPMENT} value={f.equipment} onChange={(v) => set("equipment", v)} />
      </Card>

      <Card className="flex flex-col gap-3">
        <p className="text-[14px] font-bold uppercase tracking-wider text-muted">D · Authorisation information</p>
        <p className="text-[15px] text-muted -mt-1">Document numbers and details for our team to verify -- no file upload needed here; we'll request supporting documents separately where applicable.</p>
        <Field label="Driver licence number" htmlFor="dl"><Input id="dl" value={f.driver_license_no} onChange={(e) => set("driver_license_no", e.target.value)} /></Field>
        <Field label="Crew details" hint="Names/roles, EMT or paramedic qualifications where applicable" htmlFor="crew"><Input id="crew" value={f.crew_details} onChange={(e) => set("crew_details", e.target.value)} /></Field>
        <Field label="RC (registration certificate) number" htmlFor="rc"><Input id="rc" value={f.rc_number} onChange={(e) => set("rc_number", e.target.value)} /></Field>
        <Field label="Insurance number" htmlFor="ins"><Input id="ins" value={f.insurance_number} onChange={(e) => set("insurance_number", e.target.value)} /></Field>
        <Field label="Permit / authorisation number, if applicable" htmlFor="permit"><Input id="permit" value={f.permit_number} onChange={(e) => set("permit_number", e.target.value)} /></Field>
        <p className="text-[13px] text-muted">The exact documents required depend on your ambulance category, state and legal arrangement -- our team will confirm what's applicable to you during review.</p>
      </Card>

      <Card className="flex flex-col gap-3">
        <p className="text-[14px] font-bold uppercase tracking-wider text-muted">Official guidelines</p>
        <a href="https://morth.nic.in/sites/default/files/AIS-125%20Part%201.pdf" target="_blank" rel="noopener noreferrer" className="flex items-center justify-between rounded-2xl border border-line bg-card px-4 py-3 text-[15px] font-semibold">
          AIS-125 Part 1 -- Ambulance construction & functional requirements <Icon name="chevron" size={18} />
        </a>
        <a href="https://morth.nic.in/" target="_blank" rel="noopener noreferrer" className="flex items-center justify-between rounded-2xl border border-line bg-card px-4 py-3 text-[15px] font-semibold">
          AIS-125 Part 2 -- Medical equipment requirements (Ministry of Road Transport & Highways) <Icon name="chevron" size={18} />
        </a>
      </Card>

      <Card className="flex flex-col gap-3">
        <p className="text-[14px] font-bold uppercase tracking-wider text-muted">E · Declaration</p>
        <button type="button" onClick={() => set("declaration_confirmed", !f.declaration_confirmed)} className="flex items-start gap-3 text-left">
          <span className={cn("mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md border-2", f.declaration_confirmed ? "border-ink bg-ink" : "border-line")}>
            {f.declaration_confirmed && <Icon name="check" size={16} className="text-bg" />}
          </span>
          <span className="text-[15px]">I confirm that the registration information is accurate and that I am authorised to register this vehicle and operator.</span>
        </button>
      </Card>

      {err && <p className="text-[15px] font-semibold text-red-ink">{err}</p>}
      <Button type="submit" size="xl" block loading={busy}>Submit for review</Button>
    </form>
  );
}
