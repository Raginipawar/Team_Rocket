"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText, get, post, ApiError } from "@/lib/api";
import type { CreateEmergencyResponse } from "@/lib/api-types";
import { useGeolocation } from "@/lib/hooks";
import { Button } from "@/components/ui/button";
import { Card, EmptyState, ErrorState, Field, Input, LoadingState } from "@/components/ui/bits";
import { Sheet } from "@/components/ui/sheet";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { phone as fmtPhone } from "@/lib/format";

type Watched = { user_id: string; name: string | null; phone: string; blood_group: string | null; active_emergency_status: string | null };
type WatchedHealth = { name: string | null; blood_group: string | null; allergies: string[]; conditions: string[]; medications: string[]; home_address: string | null };

export default function FamilyPage() {
  const toast = useToast();
  const router = useRouter();
  const qc = useQueryClient();
  const geo = useGeolocation(true);

  const code = useQuery({ queryKey: ["family-code"], queryFn: () => get<{ code: string }>("/me/family-code") });
  const family = useQuery({ queryKey: ["family"], queryFn: () => get<Watched[]>("/me/family") });

  const [connectCode, setConnectCode] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [selected, setSelected] = useState<Watched | null>(null);
  const [health, setHealth] = useState<WatchedHealth | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [calling, setCalling] = useState(false);

  const share = async () => {
    const c = code.data?.code;
    if (!c) return;
    const text = `My GoldenHour family code: ${c}\nAdd me in the Family tab so you can check on me and call an ambulance for me if needed.`;
    try {
      if (navigator.share) await navigator.share({ text });
      else {
        await navigator.clipboard.writeText(c);
        toast("Code copied", "success");
      }
    } catch { /* user cancelled share -- fine */ }
  };

  const connect = async () => {
    if (connectCode.trim().length < 4) return;
    setConnecting(true);
    try {
      await post("/me/family/connect", { code: connectCode.trim() });
      setConnectCode("");
      void qc.invalidateQueries({ queryKey: ["family"] });
      toast("Added to your family space", "success");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setConnecting(false);
    }
  };

  const openMember = async (m: Watched) => {
    setSelected(m);
    setHealth(null);
    setHealthLoading(true);
    try {
      const h = await get<WatchedHealth>(`/me/family/${m.user_id}/health`);
      setHealth(h);
    } catch {
      /* show the sheet anyway without health details */
    } finally {
      setHealthLoading(false);
    }
  };

  const callAmbulanceFor = async () => {
    if (!selected) return;
    setCalling(true);
    try {
      const form = new FormData();
      form.set("channel", "app_button");
      const note = `Called by a family member on GoldenHour for ${selected.name ?? "a family member"}.${health?.home_address ? ` Registered address: ${health.home_address}.` : ""}`;
      form.set("text", note);
      form.set("caller_phone", selected.phone);
      if (geo.pos) {
        form.set("lat", String(geo.pos.lat));
        form.set("lng", String(geo.pos.lng));
        form.set("accuracy_m", String(geo.pos.accuracy));
      }
      const r = await api<CreateEmergencyResponse>("/emergencies", { method: "POST", form });
      toast("Ambulance called", "success");
      setSelected(null);
      router.push(`/patient/emergency/${r.emergency_id}`);
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setCalling(false);
    }
  };

  return (
    <div className="flex flex-col gap-5 pt-2">
      <div>
        <h1 className="text-[28px] font-extrabold">Family space</h1>
        <p className="mt-1 text-[17px] text-muted">Connect with family so you can check on each other and call for help.</p>
      </div>

      <Card className="flex flex-col gap-3">
        <p className="text-[16px] font-bold">Your code</p>
        {code.isLoading ? (
          <LoadingState />
        ) : code.isError ? (
          <ErrorState text={errorText(code.error)} onRetry={() => code.refetch()} />
        ) : (
          <>
            <p className="text-center text-[36px] font-extrabold tracking-[0.2em]">{code.data?.code}</p>
            <p className="text-center text-[15px] text-muted">Share this with family so they can add you</p>
            <Button size="lg" block variant="soft" onClick={() => void share()}>
              <Icon name="share" size={20} />
              Share my code
            </Button>
          </>
        )}
      </Card>

      <Card className="flex flex-col gap-3">
        <p className="text-[16px] font-bold">Add a family member</p>
        <Field label="Their code" htmlFor="fcode">
          <Input id="fcode" value={connectCode} onChange={(e) => setConnectCode(e.target.value.toUpperCase())} placeholder="e.g. H7K4M2" className="text-center text-[20px] tracking-[0.15em]" maxLength={8} />
        </Field>
        <Button size="lg" block loading={connecting} disabled={connectCode.trim().length < 4} onClick={() => void connect()}>Add</Button>
      </Card>

      <div>
        <p className="mb-2 text-[16px] font-bold">Your family</p>
        {family.isLoading ? <LoadingState /> : family.isError ? (
          <ErrorState text={errorText(family.error)} onRetry={() => family.refetch()} />
        ) : !family.data?.length ? (
          <EmptyState icon="users" title="No one added yet" text="Enter a family member's code above to connect" />
        ) : (
          <ul className="flex flex-col gap-3">
            {family.data.map((m) => (
              <li key={m.user_id}>
                <button onClick={() => void openMember(m)} className="flex w-full items-center gap-3 rounded-[22px] border border-line bg-card p-4 text-left">
                  <span className="grid h-14 w-14 shrink-0 place-items-center rounded-full bg-soft text-[20px] font-bold">
                    {(m.name ?? "?").slice(0, 1).toUpperCase()}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[19px] font-bold">{m.name ?? fmtPhone(m.phone)}</p>
                    {m.active_emergency_status ? (
                      <p className="text-[15px] font-semibold text-red-ink">Active emergency right now</p>
                    ) : (
                      <p className="text-[15px] text-muted">{m.blood_group ? `Blood ${m.blood_group}` : "Tap for options"}</p>
                    )}
                  </div>
                  <Icon name="chevron" size={20} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <Sheet open={!!selected} onOpenChange={(o) => !o && setSelected(null)} title={selected?.name ?? "Family member"}>
        <div className="flex flex-col gap-4">
          {selected?.active_emergency_status && (
            <div className="rounded-2xl bg-red-soft p-4 text-[16px] font-semibold text-red-ink">
              They have an active emergency right now.
            </div>
          )}
          {healthLoading ? <LoadingState /> : health && (
            <div className="rounded-2xl bg-soft p-4 text-[15px] leading-relaxed">
              {health.blood_group && <p>Blood group: <b>{health.blood_group}</b></p>}
              {health.allergies.length > 0 && <p>Allergies: <b className="text-red-ink">{health.allergies.join(", ")}</b></p>}
              {health.conditions.length > 0 && <p>Conditions: {health.conditions.join(", ")}</p>}
              {health.medications.length > 0 && <p>Medications: {health.medications.join(", ")}</p>}
              {!health.blood_group && !health.allergies.length && !health.conditions.length && (
                <p className="text-muted">No health details added yet</p>
              )}
            </div>
          )}
          <Button asChild variant="soft" size="lg" block>
            <a href={`tel:${selected?.phone}`}><Icon name="phone" size={20} />Call {selected?.name ?? "them"}</a>
          </Button>
          <Button variant="danger" size="xl" block loading={calling} onClick={() => void callAmbulanceFor()}>
            <Icon name="ambulance" size={24} />
            Call an ambulance for them
          </Button>
        </div>
      </Sheet>
    </div>
  );
}
