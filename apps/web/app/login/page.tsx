"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { ApiError, errorText, newKey, post, toApiError } from "@/lib/api";
import type { LoginResponse } from "@/lib/api-types";
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

  const done = (r: LoginResponse) => {
    signIn(r);
    router.replace(r.user.role === role && next ? next : HOME[r.user.role]);
  };

  return (
    <div className="min-h-dvh bg-page">
      <MockRibbon />
      <header className="mx-auto flex max-w-md items-center justify-between px-5 pt-5">
        <Link href="/" aria-label="Home"><Brand small /></Link>
        <LanguageSwitcher compact />
      </header>
      <main className="mx-auto flex max-w-md flex-col gap-5 px-5 pb-10 pt-8">
        {role === "patient" ? <PatientOtp onDone={done} /> : <StaffLogin role={role} onDone={done} />}
        {role === "patient" && <Call108 />}
      </main>
    </div>
  );
}

function PatientOtp({ onDone }: { onDone: (r: LoginResponse) => void }) {
  const t = useTranslations("login");
  const [phone, setPhone] = useState("");
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
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
      onDone(await post<LoginResponse>("/auth/otp/verify", { phone: `+91${digits}`, code: value }, { auth: false }));
    } catch (e) {
      setErr(errorText(e));
      setBusy(false);
    }
  };

  if (step === "phone") {
    return (
      <form className="flex flex-col gap-5" onSubmit={(e) => { e.preventDefault(); void send(); }}>
        <div>
          <h1 className="text-[28px] font-extrabold leading-tight">{t("patientTitle")}</h1>
          <p className="mt-1 text-[17px] text-muted">{t("patientSub")}</p>
        </div>
        <Field label={t("phone")} hint={t("phoneHint")} error={err} htmlFor="phone">
          <div className="flex gap-2">
            <span className="grid h-14 place-items-center rounded-2xl bg-soft px-4 text-[18px] font-semibold">+91</span>
            <Input id="phone" inputMode="numeric" autoComplete="tel-national" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="98765 43210" className="text-[20px] tracking-wide" autoFocus />
          </div>
        </Field>
        <Button type="submit" size="lg" block loading={busy}>{t("sendCode")}</Button>
        {areaMode("AUTH") === "mock" && (
          <button type="button" className="text-left text-[15px] text-muted underline" onClick={() => setPhone("9200000001")}>
            {t("demoLogins")}: 92000 00001 (Rahul, has a health profile)
          </button>
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

export default function LoginPage() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  );
}
