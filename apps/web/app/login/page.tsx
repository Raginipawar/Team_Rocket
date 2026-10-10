"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { ApiError, errorText, get, newKey, post, toApiError } from "@/lib/api";
import type { HealthProfile, LoginResponse } from "@/lib/api-types";
import type { Role } from "@/lib/enums";
import { areaMode } from "@/lib/config";
import { Brand, Call108, LanguageSwitcher, MockRibbon } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/bits";
import Icon from "@/components/ui/icon";
import { useNow } from "@/lib/hooks";

const HOME: Record<Role, string> = { patient: "/patient", paramedic: "/ambulance", hospital_staff: "/hospital", developer: "/" };

const DEMO: Record<string, { label: string; id: string }[]> = {
  paramedic: [
    { label: "ALS ambulance MH14 AB 1234 (Akurdi)", id: "+919100000001" },
    { label: "ALS ambulance MH14 CD 5678 (Pimpri)", id: "+919100000002" },
  ],
  hospital_staff: [
    { label: "Greenfield Heart Centre, Nigdi", id: "+919000000001" },
    { label: "Riverside Multispeciality, Chinchwad", id: "+919000000002" },
    { label: "Metro Neuro and Trauma, Pimpri", id: "+919000000003" },
  ],
};

function LoginInner() {
  const params = useSearchParams();
  const role = (params.get("role") ?? "patient") as Role;
  const next = params.get("next");
  const { session, ready, signIn } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (ready && session) router.replace(session.user.role === role && next ? next : HOME[session.user.role]);
  }, [ready, session, role, next, router]);

  const done = async (r: LoginResponse) => {
    signIn(r);
    const target = r.user.role === role && next ? next : HOME[r.user.role];
    // First-ever login felt like "enter OTP, you're just... in" -- no
    // welcome, no prompt to fill the health profile that genuinely matters
    // in a real emergency (blood group/allergies/conditions). Detecting
    // "never filled" (not just "brand new account") so a patient who
    // signed up before this existed also gets it once, not just literal
    // day-one accounts.
    if (r.user.role === "patient") {
      try {
        const profile = await get<HealthProfile>("/me/profile");
        const seenKey = `gh-onboarded-${r.user.id}`;
        const neverFilled = !profile.name && !profile.dob && !profile.blood_group;
        let alreadySeen = false;
        try { alreadySeen = localStorage.getItem(seenKey) === "1"; } catch { /* ignore */ }
        if (neverFilled && !alreadySeen) {
          router.replace(`/patient/welcome?next=${encodeURIComponent(target)}`);
          return;
        }
      } catch {
        /* profile fetch failed -- don't block login on it, just skip onboarding */
      }
    }
    if (r.user.role === "paramedic") {
      // Phone OTP verifies the phone, nothing else -- a verified phone with
      // no (or not-yet-approved) ambulance must land on registration/status,
      // never the real dashboard. Backend enforces this independently
      // (kyc_verified gates dispatch eligibility); this is just getting the
      // UI to the right screen.
      try {
        const reg = await get<{ status: string | null }>("/ambulance/registration-status");
        if (reg.status !== "demo" && reg.status !== "approved") {
          router.replace("/ambulance/onboarding");
          return;
        }
      } catch {
        router.replace("/ambulance/onboarding");
        return;
      }
    }
    router.replace(target);
  };

  return (
    <div className="min-h-dvh bg-page">
      <MockRibbon />
      <header className="mx-auto flex max-w-md items-center justify-between px-5 pt-5">
        <Link href="/" aria-label="Home"><Brand small /></Link>
        <LanguageSwitcher compact />
      </header>
      <main className="mx-auto flex max-w-md flex-col gap-5 px-5 pb-10 pt-8">
        {role === "patient" ? <OtpLogin role="patient" onDone={done} /> : role === "paramedic" ? <OtpLogin role="paramedic" onDone={done} /> : <StaffLogin role={role} onDone={done} />}
        {role === "patient" && <Call108 />}
      </main>
    </div>
  );
}

// Ambulance crew used to be a fixed phone+password login, same as hospital
// staff -- that only verifies someone knows a shared password, not that
// THIS specific phone/person is who they claim. Real OTP (same flow as
// patient) verifies phone control; registration/approval is a SEPARATE
// step after login (app/ambulance/onboarding), never conflated with it.
function OtpLogin({ role, onDone }: { role: "patient" | "paramedic"; onDone: (r: LoginResponse) => void }) {
  const t = useTranslations("login");
  const [phone, setPhone] = useState("");
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);

  const signInAsRagini = async () => {
    setErr(null);
    setDemoBusy(true);
    try {
      onDone(await post<LoginResponse>("/auth/login", { username_or_phone: "Ragini Pawar", password: "Ragini@21" }, { auth: false }));
    } catch (e) {
      setErr(errorText(e));
      setDemoBusy(false);
    }
  };
  const [sentAt, setSentAt] = useState(0);
  const now = useNow(1000);
  const wait = Math.max(0, 30 - Math.floor((now - sentAt) / 1000));
  const digits = phone.replace(/\D/g, "").slice(-10);

  const send = async () => {
    setErr(null);
    if (digits.length !== 10) {
      setErr(t("phoneHint"));
      return;
    }
    setBusy(true);
    try {
      const res = await fetch("/api/v1/auth/otp/request", { method: "POST", headers: { "content-type": "application/json", "idempotency-key": newKey() }, body: JSON.stringify({ phone: `+91${digits}` }) });
      if (!res.ok) throw await toApiError(res);
      setDevCode(res.headers.get("x-dev-otp"));
      setStep("code");
      setSentAt(Date.now());
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const verify = async (value = code) => {
    setErr(null);
    setBusy(true);
    try {
      onDone(await post<LoginResponse>("/auth/otp/verify", { phone: `+91${digits}`, code: value, role }, { auth: false }));
    } catch (e) {
      setErr(errorText(e));
      setBusy(false);
    }
  };

  if (step === "phone") {
    return (
      <form className="flex flex-col gap-5" onSubmit={(e) => { e.preventDefault(); void send(); }}>
        <div>
          <h1 className="text-[28px] font-extrabold leading-tight">{role === "paramedic" ? "Ambulance crew sign in" : t("patientTitle")}</h1>
          <p className="mt-1 text-[17px] text-muted">{role === "paramedic" ? "Enter your phone number to sign in or register your ambulance." : t("patientSub")}</p>
        </div>
        <Field label={t("phone")} hint={t("phoneHint")} error={err} htmlFor="phone">
          <div className="flex gap-2">
            <span className="grid h-14 place-items-center rounded-2xl bg-soft px-4 text-[18px] font-semibold">+91</span>
            <Input id="phone" inputMode="numeric" autoComplete="tel-national" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="98765 43210" className="text-[20px] tracking-wide" autoFocus />
          </div>
        </Field>
        <Button type="submit" size="lg" block loading={busy}>{t("sendCode")}</Button>
        {role === "patient" && areaMode("AUTH") === "mock" && (
          <>
            <Button type="button" size="lg" variant="outline" block loading={demoBusy} onClick={() => void signInAsRagini()}>
              Sign in as Ragini Pawar
            </Button>
            <button type="button" className="text-left text-[15px] text-muted underline" onClick={() => setPhone("9200000001")}>
              {t("demoLogins")}: 92000 00001 ({t("demoPatientHint")})
            </button>
          </>
        )}
      </form>
    );
  }
  return (
    <form className="flex flex-col gap-5" onSubmit={(e) => { e.preventDefault(); void verify(); }}>
      <div>
        <h1 className="text-[28px] font-extrabold leading-tight">{t("codeTitle")}</h1>
        <p className="mt-1 text-[17px] text-muted">{t("codeSub", { phone: `+91 ${digits.slice(0, 5)} ${digits.slice(5)}` })}</p>
      </div>
      <Field label={t("code")} error={err} htmlFor="code">
        <Input id="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code}
          onChange={(e) => {
            const v = e.target.value.replace(/\D/g, "").slice(0, 6);
            setCode(v);
            if (v.length === 6) void verify(v);
          }}
          className="h-16 text-center text-[30px] font-bold tracking-[0.4em]" autoFocus />
      </Field>
      {devCode && (
        <button type="button" onClick={() => { setCode(devCode); void verify(devCode); }} className="flex items-center justify-between rounded-2xl border-2 border-dashed border-line px-4 py-3 text-left">
          <span className="text-[16px]">{t("demoCode", { code: devCode })}</span>
          <span className="text-[15px] font-bold underline">Use</span>
        </button>
      )}
      <Button type="submit" size="lg" block loading={busy} disabled={code.length !== 6}>{t("verify")}</Button>
      <div className="flex items-center justify-between">
        <Button type="button" variant="link" onClick={() => { setStep("phone"); setCode(""); setErr(null); }}>{t("changeNumber")}</Button>
        <Button type="button" variant="link" disabled={wait > 0} onClick={() => void send()}>{wait > 0 ? t("resendIn", { s: wait }) : t("resend")}</Button>
      </div>
    </form>
  );
}

function StaffLogin({ role, onDone }: { role: Role; onDone: (r: LoginResponse) => void }) {
  const t = useTranslations("login");
  const [id, setId] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const submit = async (ident = id, pass = pw) => {
    setErr(null);
    setBusy(true);
    try {
      onDone(await post<LoginResponse>("/auth/login", { username_or_phone: ident.trim(), password: pass }, { auth: false }));
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 401 ? "Phone number or password is not right." : errorText(e));
      setBusy(false);
    }
  };
  const who = role === "paramedic" ? "Ambulance crew" : role === "hospital_staff" ? "Hospital staff" : "Staff";

  if (role === "hospital_staff" && mode === "signup") {
    return <HospitalSignup onDone={onDone} onBackToSignIn={() => setMode("signin")} />;
  }

  return (
    <form className="flex flex-col gap-5" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
      <div>
        <p className="flex items-center gap-2 text-[16px] font-semibold text-muted"><Icon name={role === "paramedic" ? "ambulance" : "hospital"} size={20} />{who}</p>
        <h1 className="mt-1 text-[28px] font-extrabold leading-tight">{t("staffTitle")}</h1>
      </div>
      <Field label={t("idLabel")} htmlFor="id">
        <Input id="id" autoComplete="username" value={id} onChange={(e) => setId(e.target.value)} autoFocus />
      </Field>
      <Field label={t("password")} error={err} htmlFor="pw">
        <Input id="pw" type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} />
      </Field>
      <Button type="submit" size="lg" block loading={busy}>{t("signIn")}</Button>
      {role === "hospital_staff" && (
        <button type="button" className="text-center text-[15px] font-semibold text-ink underline" onClick={() => setMode("signup")}>
          Register your hospital
        </button>
      )}
      {areaMode("AUTH") === "mock" && DEMO[role] && (
        <div className="flex flex-col gap-2 rounded-[24px] bg-soft p-4">
          <p className="text-[14px] font-bold uppercase tracking-wider text-muted">{t("demoLogins")} · password demo1234</p>
          {DEMO[role].map((d) => (
            <button key={d.id} type="button" onClick={() => { setId(d.id); setPw("demo1234"); void submit(d.id, "demo1234"); }} className="flex items-center justify-between rounded-2xl bg-card px-4 py-3 text-left text-[16px] font-semibold">
              <span>{d.label}</span>
              <Icon name="chevron" size={18} />
            </button>
          ))}
        </div>
      )}
    </form>
  );
}

const HOSPITAL_CAPABILITIES = [
  { id: "general_er", label: "General ER" },
  { id: "cardiac_cathlab", label: "Cardiac / cath lab" },
  { id: "stroke_thrombolysis", label: "Stroke / thrombolysis" },
  { id: "trauma_center", label: "Trauma center" },
  { id: "burns_unit", label: "Burns unit" },
  { id: "obstetrics", label: "Obstetrics" },
  { id: "pediatrics", label: "Paediatrics" },
  { id: "toxicology", label: "Toxicology" },
  { id: "icu", label: "ICU" },
];

function HospitalSignup({ onDone, onBackToSignIn }: { onDone: (r: LoginResponse) => void; onBackToSignIn: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [f, setF] = useState({
    hospital_name: "", address: "", lat: "", lng: "",
    capabilities: ["general_er"] as string[],
    duty_manager_phone: "", er_entrance_note: "",
    staff_name: "", staff_phone: "", staff_password: "",
    integration_mode: "manual" as "manual" | "api",
  });
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((s) => ({ ...s, [k]: v }));
  const toggleCap = (id: string) => set("capabilities", f.capabilities.includes(id) ? f.capabilities.filter((c) => c !== id) : [...f.capabilities, id]);

  const submit = async () => {
    setErr(null);
    // Field-specific message instead of one blanket "fill in all fields" --
    // a generic message with no way to tell WHICH field the form thinks is
    // still empty is exactly what made a real mobile-autofill bug (dots
    // visibly filled in the password box, but the submit still saw "")
    // impossible to diagnose from a screenshot alone.
    const missing: string[] = [];
    if (!f.hospital_name.trim()) missing.push("Hospital name");
    if (!f.address.trim()) missing.push("Address");
    if (!f.lat.trim() || isNaN(Number(f.lat))) missing.push("Latitude");
    if (!f.lng.trim() || isNaN(Number(f.lng))) missing.push("Longitude");
    if (!f.duty_manager_phone.trim()) missing.push("Duty manager phone");
    if (!f.staff_name.trim()) missing.push("Administrator full name");
    if (!f.staff_phone.trim()) missing.push("Administrator phone");
    if (f.staff_password.length < 8) missing.push(`Password (needs 8+ characters, got ${f.staff_password.length})`);
    if (missing.length) {
      setErr(`Missing or invalid: ${missing.join(", ")}`);
      return;
    }
    setBusy(true);
    try {
      const r = await post<LoginResponse & { hospital_code: string }>("/auth/register-hospital", {
        ...f, lat: Number(f.lat), lng: Number(f.lng),
      }, { auth: false });
      onDone(r);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="flex flex-col gap-5" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
      <div className="flex items-center gap-2">
        <Button type="button" variant="ghost" size="icon" onClick={onBackToSignIn}><Icon name="back" size={20} /></Button>
        <h1 className="text-[24px] font-extrabold">Register your hospital</h1>
      </div>
      <p className="text-[15px] text-muted -mt-3">You'll get access to the dashboard right away. This creates a demo-labelled registration -- not an independently verified claim of real-world accreditation.</p>

      <Field label="Hospital name" htmlFor="hname"><Input id="hname" value={f.hospital_name} onChange={(e) => set("hospital_name", e.target.value)} /></Field>
      <Field label="Address" htmlFor="addr"><Input id="addr" value={f.address} onChange={(e) => set("address", e.target.value)} /></Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Latitude" htmlFor="lat"><Input id="lat" inputMode="decimal" value={f.lat} onChange={(e) => set("lat", e.target.value)} placeholder="18.63" /></Field>
        <Field label="Longitude" htmlFor="lng"><Input id="lng" inputMode="decimal" value={f.lng} onChange={(e) => set("lng", e.target.value)} placeholder="73.80" /></Field>
      </div>
      <Field label="Duty manager phone" htmlFor="dmp"><Input id="dmp" value={f.duty_manager_phone} onChange={(e) => set("duty_manager_phone", e.target.value)} placeholder="+91..." /></Field>
      <Field label="ER entrance note (optional)" htmlFor="ern"><Input id="ern" value={f.er_entrance_note} onChange={(e) => set("er_entrance_note", e.target.value)} /></Field>

      <div>
        <p className="mb-2 text-[14px] font-bold uppercase tracking-wider text-muted">Services available</p>
        <div className="flex flex-wrap gap-2">
          {HOSPITAL_CAPABILITIES.map((c) => {
            const on = f.capabilities.includes(c.id);
            return (
              <button key={c.id} type="button" onClick={() => toggleCap(c.id)}
                className={`rounded-full border-2 px-4 py-2 text-[15px] font-semibold ${on ? "border-ink bg-ink text-bg" : "border-line bg-card text-ink"}`}>
                {c.label}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <p className="mb-2 text-[14px] font-bold uppercase tracking-wider text-muted">Data integration</p>
        <div className="grid grid-cols-2 gap-2">
          <button type="button" onClick={() => set("integration_mode", "manual")}
            className={`rounded-2xl border-2 p-3 text-left ${f.integration_mode === "manual" ? "border-ink" : "border-line"}`}>
            <p className="text-[16px] font-bold">Manual dashboard</p>
            <p className="text-[13px] text-muted">Update capacity yourself in-app</p>
          </button>
          <button type="button" onClick={() => set("integration_mode", "api")}
            className={`rounded-2xl border-2 p-3 text-left ${f.integration_mode === "api" ? "border-ink" : "border-line"}`}>
            <p className="text-[16px] font-bold">API integration</p>
            <p className="text-[13px] text-muted">Connect your own system later</p>
          </button>
        </div>
      </div>

      <div>
        <p className="mb-2 text-[14px] font-bold uppercase tracking-wider text-muted">Administrator account</p>
        <Field label="Full name" htmlFor="sname"><Input id="sname" value={f.staff_name} onChange={(e) => set("staff_name", e.target.value)} /></Field>
        <Field label="Phone (used to sign in)" htmlFor="sphone"><Input id="sphone" value={f.staff_phone} onChange={(e) => set("staff_phone", e.target.value)} placeholder="+91..." /></Field>
        <Field label="Password" htmlFor="spw">
          <Input id="spw" type="password" autoComplete="new-password" value={f.staff_password}
            onChange={(e) => set("staff_password", e.currentTarget.value)}
            onInput={(e) => set("staff_password", e.currentTarget.value)} />
        </Field>
      </div>

      {err && <p className="text-[15px] font-semibold text-red-ink">{err}</p>}
      <Button type="submit" size="xl" block loading={busy}>Create hospital & open dashboard</Button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  );
}
