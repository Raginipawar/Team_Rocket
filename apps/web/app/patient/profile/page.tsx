"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, errorText, get, put } from "@/lib/api";
import type { HealthProfile } from "@/lib/api-types";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { ErrorState, Field, Input, LoadingState, Select, Textarea } from "@/components/ui/bits";
import { useToast } from "@/components/ui/toast";

const BLOOD = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"];
const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

export default function ProfilePage() {
  const t = useTranslations("patient");
  const tc = useTranslations("common");
  const qc = useQueryClient();
  const toast = useToast();
  const { updateUser, signOut } = useAuth();
  const q = useQuery({ queryKey: ["profile"], queryFn: () => get<HealthProfile>("/me/profile") });
  const [f, setF] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!q.data) return;
    const p = q.data;
    setF({
      name: p.name ?? "", dob: p.dob ?? "", sex: p.sex ?? "", blood_group: p.blood_group ?? "",
      allergies: p.allergies.join(", "), conditions: p.conditions.join(", "), medications: p.medications.join(", "),
      home_address: p.home_address ?? "", notes: p.notes ?? "",
    });
  }, [q.data]);

  if (q.isLoading) return <LoadingState />;
  if (q.isError || !q.data) return <ErrorState text={errorText(q.error)} onRetry={() => q.refetch()} />;

  const set = (k: string) => (e: { target: { value: string } }) => setF((x) => ({ ...x, [k]: e.target.value }));
  const save = async () => {
    setSaving(true);
    try {
      const next = await put<HealthProfile>("/me/profile", {
        name: f.name, dob: f.dob || null, sex: f.sex || null, blood_group: f.blood_group || null,
        allergies: list(f.allergies), conditions: list(f.conditions), medications: list(f.medications),
        home_address: f.home_address || null, notes: f.notes || null, version: q.data!.version,
      });
      qc.setQueryData(["profile"], next);
      updateUser({ name: f.name });
      toast(tc("saved"), "success");
    } catch (e) {
      toast(errorText(e), "error");
      if (e instanceof ApiError && e.code === "VERSION_CONFLICT") void q.refetch();
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="flex flex-col gap-5 pt-2" onSubmit={(e) => { e.preventDefault(); void save(); }}>
      <div>
        <h1 className="text-[28px] font-extrabold">{t("profileTitle")}</h1>
        <p className="mt-1 text-[17px] text-muted">{t("profileSub")}</p>
      </div>
      <Field label={t("name")} htmlFor="name"><Input id="name" value={f.name ?? ""} onChange={set("name")} autoComplete="name" /></Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t("dob")} htmlFor="dob"><Input id="dob" type="date" value={f.dob ?? ""} onChange={set("dob")} /></Field>
        <Field label={t("sex")} htmlFor="sex">
          <Select id="sex" value={f.sex ?? ""} onChange={set("sex")}>
            <option value="">-</option>
            <option value="male">{t("male")}</option>
            <option value="female">{t("female")}</option>
            <option value="other">{t("other")}</option>
          </Select>
        </Field>
      </div>
      <Field label={t("bloodGroup")}>
        <div className="grid grid-cols-4 gap-2" role="radiogroup" aria-label={t("bloodGroup")}>
          {BLOOD.map((b) => (
            <button type="button" key={b} role="radio" aria-checked={f.blood_group === b} onClick={() => setF((x) => ({ ...x, blood_group: x.blood_group === b ? "" : b }))}
              className={`h-14 rounded-2xl border-2 text-[18px] font-bold ${f.blood_group === b ? "border-ink bg-ink text-bg" : "border-line bg-card"}`}>{b}</button>
          ))}
        </div>
      </Field>
      <Field label={t("allergies")} hint={t("commaHint")} htmlFor="allergies"><Input id="allergies" value={f.allergies ?? ""} onChange={set("allergies")} placeholder="Aspirin, Penicillin" /></Field>
      <Field label={t("conditions")} hint={t("commaHint")} htmlFor="conditions"><Input id="conditions" value={f.conditions ?? ""} onChange={set("conditions")} placeholder="Diabetes, High BP" /></Field>
      <Field label={t("medications")} hint={t("commaHint")} htmlFor="medications"><Input id="medications" value={f.medications ?? ""} onChange={set("medications")} placeholder="Metformin 500 mg" /></Field>
      <Field label={t("homeAddress")} htmlFor="home"><Input id="home" value={f.home_address ?? ""} onChange={set("home_address")} autoComplete="street-address" /></Field>
      <Field label={t("notes")} htmlFor="notes"><Textarea id="notes" value={f.notes ?? ""} onChange={set("notes")} className="min-h-24" /></Field>
      <Button type="submit" size="lg" block loading={saving}>{tc("save")}</Button>
      <Button type="button" variant="ghost" block onClick={() => void signOut()}>{tc("signOut")}</Button>
    </form>
  );
}
