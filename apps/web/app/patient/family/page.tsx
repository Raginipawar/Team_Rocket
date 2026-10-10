"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText, get, post, ApiError } from "@/lib/api";
import type { CreateEmergencyResponse } from "@/lib/api-types";
import { useAuth } from "@/lib/auth";
import { useChannel, useWsClient } from "@/components/realtime/WsProvider";
import { Button } from "@/components/ui/button";
import { Card, ErrorState, Field, Input, LoadingState } from "@/components/ui/bits";
import { Sheet } from "@/components/ui/sheet";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { phone as fmtPhone } from "@/lib/format";

type Member = {
  id: string; name: string | null; phone: string; blood_group: string | null;
  active_emergency_status: string | null;
  last_location_at: string | null; location_age_sec: number | null;
};
type Family = { family_id: string; code: string; name: string | null; is_owner: boolean; members: Member[] };
type MemberHealth = { name: string | null; blood_group: string | null; allergies: string[]; conditions: string[]; medications: string[]; home_address: string | null };

function locationFreshness(ageSec: number | null): string {
  if (ageSec == null) return "No location yet -- they need to open the app at least once.";
  if (ageSec < 120) return "Location updated moments ago";
  if (ageSec < 3600) return `Location updated ${Math.round(ageSec / 60)} min ago`;
  if (ageSec < 86400) return `Location updated ${Math.round(ageSec / 3600)} h ago -- may be out of date`;
  return "Last location is over a day old -- may be out of date";
}

export default function FamilyPage() {
  const toast = useToast();
  const router = useRouter();
  const qc = useQueryClient();
  const { session } = useAuth();

  // Single source of truth: one family per account, or none. Real-time sync
  // (spec requirement) comes from both a WS event on join AND a 5s poll as a
  // safety net -- a dropped WS connection must not mean a stuck member list.
  const fam = useQuery({
    queryKey: ["my-family"],
    queryFn: () => get<{ family: Family | null }>("/me/family"),
    refetchInterval: 5000,
  });
  const family = fam.data?.family ?? null;

  const ws = useWsClient("ME", session?.token);
  useChannel(ws, family ? `family:${family.family_id}` : null, () => {
    void qc.invalidateQueries({ queryKey: ["my-family"] });
  });

  const [createBusy, setCreateBusy] = useState(false);
  const [joinCode, setJoinCode] = useState("");
  const [joinBusy, setJoinBusy] = useState(false);
  const [joinErr, setJoinErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<Member | null>(null);
  const [health, setHealth] = useState<MemberHealth | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [calling, setCalling] = useState(false);

  const createFamily = async () => {
    setCreateBusy(true);
    try {
      await post("/me/family/create", {});
      void qc.invalidateQueries({ queryKey: ["my-family"] });
      toast("Family created", "success");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setCreateBusy(false);
    }
  };

  const joinFamily = async () => {
    if (joinCode.trim().length < 4) return;
    setJoinBusy(true);
    setJoinErr(null);
    try {
      await post("/me/family/join", { code: joinCode.trim() });
      setJoinCode("");
      void qc.invalidateQueries({ queryKey: ["my-family"] });
      toast("Joined family", "success");
    } catch (e) {
      // Shown inline, not just a toast -- a wrong/typo'd code is the most
      // likely failure here and deserves to stay visible next to the field.
      setJoinErr(e instanceof ApiError && e.status === 404 ? "No family has that code" : errorText(e));
    } finally {
      setJoinBusy(false);
    }
  };

  const share = async () => {
    const c = family?.code;
    if (!c) return;
    const text = `Join my GoldenHour family: code ${c}\nOpen the Family tab and enter it so we can check on each other.`;
    try {
      if (navigator.share) await navigator.share({ text });
      else {
        await navigator.clipboard.writeText(c);
        toast("Code copied", "success");
      }
    } catch { /* user cancelled share -- fine */ }
  };

  const openMember = async (m: Member) => {
    if (m.id === session?.user.id) return; // self -- nothing to view
    setSelected(m);
    setHealth(null);
    setHealthLoading(true);
    try {
      const h = await get<MemberHealth>(`/me/family/${m.id}/health`);
      setHealth(h);
    } catch {
      /* show the sheet anyway without health details */
    } finally {
      setHealthLoading(false);
    }
  };

  const callAmbulanceFor = async () => {
    if (!selected) return;
    // Deliberately sends NO location of our own -- the caller may not even
    // be with the person they're calling for. The backend resolves THEIR
    // own last-reported location instead (POST /me/location, pinged by
    // their own app while it's open), which is what's actually correct
    // here: this person's location, not the caller's.
    if (selected.location_age_sec == null) {
      toast(`We don't have a recent location for ${selected.name ?? "them"} yet -- they need to have the app open.`, "error");
      return;
    }
    setCalling(true);
    try {
      const form = new FormData();
      form.set("channel", "app_button");
      const note = `Called by a family member on GoldenHour for ${selected.name ?? "a family member"}.${health?.home_address ? ` Registered address: ${health.home_address}.` : ""}`;
      form.set("text", note);
      form.set("caller_phone", selected.phone);
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

      {fam.isLoading ? (
        <LoadingState />
      ) : fam.isError ? (
        <ErrorState text={errorText(fam.error)} onRetry={() => fam.refetch()} />
      ) : !family ? (
        // No family yet: offer BOTH create and join. Once in one, this
        // whole block disappears -- an account can only ever see one or
        // the other, never both forms, and never after already belonging
        // to a family (enforced server-side, not just by hiding this UI).
        <div className="flex flex-col gap-4">
          <Card className="flex flex-col gap-3">
            <p className="text-[16px] font-bold">Start a family space</p>
            <p className="text-[15px] text-muted">Create one and share the code with your family.</p>
            <Button size="lg" block loading={createBusy} onClick={() => void createFamily()}>Create family</Button>
          </Card>
          <Card className="flex flex-col gap-3">
            <p className="text-[16px] font-bold">Join a family</p>
            <Field label="Their code" htmlFor="jcode" error={joinErr ?? undefined}>
              <Input id="jcode" value={joinCode} onChange={(e) => { setJoinCode(e.target.value.toUpperCase()); setJoinErr(null); }} placeholder="e.g. H7K4M2" className="text-center text-[20px] tracking-[0.15em]" maxLength={8} />
            </Field>
            <Button size="lg" block loading={joinBusy} disabled={joinCode.trim().length < 4} onClick={() => void joinFamily()}>Join</Button>
          </Card>
        </div>
      ) : (
        <>
          <Card className="flex flex-col gap-3">
            <p className="text-[16px] font-bold">Your family code</p>
            <p className="text-center text-[36px] font-extrabold tracking-[0.2em]">{family.code}</p>
            <p className="text-center text-[15px] text-muted">Share this so more family can join</p>
            <Button size="lg" block variant="soft" onClick={() => void share()}>
              <Icon name="share" size={20} />
              Share code
            </Button>
          </Card>

          <div>
            <p className="mb-2 text-[16px] font-bold">Members ({family.members.length})</p>
            <ul className="flex flex-col gap-3">
              {family.members.map((m) => {
                const isSelf = m.id === session?.user.id;
                return (
                  <li key={m.id}>
                    <button onClick={() => void openMember(m)} disabled={isSelf}
                      className="flex w-full items-center gap-3 rounded-[22px] border border-line bg-card p-4 text-left disabled:opacity-70">
                      <span className="grid h-14 w-14 shrink-0 place-items-center rounded-full bg-soft text-[20px] font-bold">
                        {(m.name ?? "?").slice(0, 1).toUpperCase()}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[19px] font-bold">{m.name ?? fmtPhone(m.phone)}{isSelf ? " (You)" : ""}</p>
                        {m.active_emergency_status ? (
                          <p className="text-[15px] font-semibold text-red-ink">Active emergency right now</p>
                        ) : (
                          <p className="text-[15px] text-muted">{m.blood_group ? `Blood ${m.blood_group}` : isSelf ? "" : "Tap for options"}</p>
                        )}
                      </div>
                      {!isSelf && <Icon name="chevron" size={20} />}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </>
      )}

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
          <p className="flex items-center gap-2 text-[14px] text-muted">
            <Icon name="pin" size={16} />
            {selected && locationFreshness(selected.location_age_sec)}
          </p>
          <Button variant="danger" size="xl" block loading={calling} disabled={selected?.location_age_sec == null} onClick={() => void callAmbulanceFor()}>
            <Icon name="ambulance" size={24} />
            Call an ambulance for them
          </Button>
        </div>
      </Sheet>
    </div>
  );
}
