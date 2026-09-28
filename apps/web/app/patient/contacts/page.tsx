"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { del, errorText, get, post } from "@/lib/api";
import type { EmergencyContact } from "@/lib/api-types";
import { phone as fmtPhone } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, Field, Input, LoadingState, Select } from "@/components/ui/bits";
import { Sheet } from "@/components/ui/sheet";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";

export default function ContactsPage() {
  const t = useTranslations("patient");
  const tc = useTranslations("common");
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["contacts"], queryFn: () => get<EmergencyContact[]>("/me/contacts") });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", phone: "", relation: "", language: "mr" });
  const [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState<EmergencyContact | null>(null);

  const add = async () => {
    setBusy(true);
    try {
      await post("/me/contacts", { ...form, phone: form.phone.replace(/\D/g, "").slice(-10) });
      setOpen(false);
      setForm({ name: "", phone: "", relation: "", language: "mr" });
      void qc.invalidateQueries({ queryKey: ["contacts"] });
      toast(tc("saved"), "success");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (c: EmergencyContact) => {
    try {
      await del(`/me/contacts/${c.id}`);
      setRemoving(null);
      void qc.invalidateQueries({ queryKey: ["contacts"] });
    } catch (e) {
      toast(errorText(e), "error");
    }
  };

  return (
    <div className="flex flex-col gap-5 pt-2">
      <div>
        <h1 className="text-[28px] font-extrabold">{t("contactsTitle")}</h1>
        <p className="mt-1 text-[17px] text-muted">{t("contactsSub")}</p>
      </div>
      {q.isLoading ? <LoadingState /> : q.isError ? <ErrorState text={errorText(q.error)} onRetry={() => q.refetch()} /> : !q.data?.length ? (
        <EmptyState icon="users" title={t("noContacts")} text={t("noContactsSub")} />
      ) : (
        <ul className="flex flex-col gap-3">
          {q.data.map((c) => (
            <li key={c.id} className="flex items-center gap-3 rounded-[22px] border border-line bg-card p-4">
              <span className="grid h-14 w-14 shrink-0 place-items-center rounded-full bg-soft text-[20px] font-bold">{c.name.slice(0, 1).toUpperCase()}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[19px] font-bold">{c.name}</p>
                <p className="text-[16px] text-muted">{[c.relation, fmtPhone(c.phone)].filter(Boolean).join(" · ")}</p>
              </div>
              <Button variant="ghost" size="icon" aria-label={`${t("remove")} ${c.name}`} onClick={() => setRemoving(c)}><Icon name="trash" size={22} /></Button>
            </li>
          ))}
        </ul>
      )}
      {(q.data?.length ?? 0) < 5 && <Button size="lg" block onClick={() => setOpen(true)}><Icon name="plus" size={22} />{t("addContact")}</Button>}

      <Sheet open={open} onOpenChange={setOpen} title={t("addContact")}
        footer={<Button size="lg" block loading={busy} disabled={!form.name.trim() || form.phone.replace(/\D/g, "").length < 10} onClick={() => void add()}>{tc("save")}</Button>}>
        <div className="flex flex-col gap-4">
          <Field label={t("contactName")} htmlFor="cname"><Input id="cname" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus /></Field>
          <Field label="Mobile number" htmlFor="cphone"><Input id="cphone" inputMode="numeric" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="98765 43210" /></Field>
          <Field label={t("relation")} htmlFor="crel"><Input id="crel" value={form.relation} onChange={(e) => setForm({ ...form, relation: e.target.value })} placeholder="Wife, Son, Daughter" /></Field>
          <Field label={t("contactLang")} htmlFor="clang">
            <Select id="clang" value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })}>
              <option value="mr">मराठी</option>
              <option value="hi">हिन्दी</option>
              <option value="en">English</option>
            </Select>
          </Field>
        </div>
      </Sheet>

      <Sheet open={!!removing} onOpenChange={(o) => !o && setRemoving(null)} title={`${t("remove")} ${removing?.name ?? ""}?`}
        footer={<>
          <Button size="lg" variant="soft" onClick={() => setRemoving(null)}>{tc("cancel")}</Button>
          <Button size="lg" variant="dangerOutline" onClick={() => removing && void remove(removing)}>{t("remove")}</Button>
        </>} />
    </div>
  );
}
