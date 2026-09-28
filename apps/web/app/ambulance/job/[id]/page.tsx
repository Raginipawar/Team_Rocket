"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, errorText, get, post } from "@/lib/api";
import type { ActiveJob, FamilyOverrideOption, RerouteNotice, WsEnvelope, WsLocation } from "@/lib/api-types";
import { ENUMS, type Acuity, type Facility } from "@/lib/enums";
import { fetchActive } from "@/lib/ambulance";
import { SMS_GATEWAY_NUMBER } from "@/lib/config";
import { km, minutes, mmss, phone } from "@/lib/format";
import { useNow, buzz } from "@/lib/hooks";
import { useChannel } from "@/components/realtime/WsProvider";
import Map from "@/components/map";
import { AcuityBadge, Confidence, FacilityChip } from "@/components/emergency/badges";
import { Banner, Card, ErrorState, LoadingState, SectionLabel, Textarea } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import Icon, { type IconName } from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/cn";
import { useAmb } from "../../context";

const FAC_LABEL: Record<Facility, string> = { cardiac: "Heart", stroke: "Stroke", trauma: "Injury", burns: "Burns", respiratory: "Breathing", obstetric: "Pregnancy", pediatric: "Child", poisoning: "Poison", general: "General" };

function turnIcon(s: string): IconName {
  const l = s.toLowerCase();
  if (l.includes("left")) return "turnLeft";
  if (l.includes("right")) return "turnRight";
  if (l.includes("arrived")) return "pin";
  return "straight";
}

function TriageConfirmSheet({ job, open, onOpenChange, onDone }: { job: ActiveJob; open: boolean; onOpenChange: (o: boolean) => void; onDone: () => void }) {
  const t = useTranslations("amb");
  const toast = useToast();
  const [acuity, setAcuity] = useState<Acuity>(job.triage.ai_acuity ?? job.triage.acuity);
  const [facility, setFacility] = useState<Facility>(job.triage.ai_facility ?? job.triage.facility);
  const [count, setCount] = useState(job.patient.patient_count || 1);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      await post(`/emergencies/${job.emergency_id}/triage-confirm`, { acuity, facility, patient_count: count, version: job.version }, { queueable: true });
      buzz(60);
      onOpenChange(false);
      onDone();
    } catch (e) {
      toast(errorText(e), "error");
      if (e instanceof ApiError && e.code === "VERSION_CONFLICT") onDone();
    } finally {
      setBusy(false);
    }
  };
  const aiA = job.triage.ai_acuity;
  const aiF = job.triage.ai_facility;
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={t("confirmTitle")} description={t("confirmSub")} wide
      footer={<Button size="xl" variant="success" block loading={busy} onClick={() => void submit()}><Icon name="check" size={26} stroke={2.6} />{t("confirmSend")}</Button>}>
      <div className="flex flex-col gap-5">
        <div className="flex items-center gap-2"><span className="text-[15px] text-muted">AI:</span><Confidence value={job.triage.confidence} /></div>
        <div>
          <p className="mb-2 text-[18px] font-bold">{t("howSerious")}</p>
          <div className="grid grid-cols-3 gap-2">
            {ENUMS.Acuity.map((a) => (
              <button key={a} onClick={() => setAcuity(a)} aria-pressed={acuity === a}
                className={cn("relative h-16 rounded-2xl border-2 text-[18px] font-bold capitalize", acuity === a ? (a === "critical" ? "border-red bg-red text-white" : a === "urgent" ? "border-amber bg-amber text-white" : "border-green bg-green text-white") : "border-line bg-card")}>
                {a}
                {aiA === a && <span className="absolute -top-2 right-2 rounded-full bg-ink px-1.5 text-[11px] text-bg">AI</span>}
              </button>
            ))}
          </div>
        </div>
        <div>
          <p className="mb-2 text-[18px] font-bold">{t("whatKind")}</p>
          <div className="grid grid-cols-3 gap-2">
            {ENUMS.Facility.map((f) => (
              <button key={f} onClick={() => setFacility(f)} aria-pressed={facility === f}
                className={cn("relative h-14 rounded-2xl border-2 text-[16px] font-bold", facility === f ? "border-ink bg-ink text-bg" : "border-line bg-card")}>
                {FAC_LABEL[f]}
                {aiF === f && <span className="absolute -top-2 right-2 rounded-full bg-blue px-1.5 text-[11px] text-white">AI</span>}
              </button>
            ))}
          </div>
        </div>
        <div>
          <p className="mb-2 text-[18px] font-bold">{t("howMany")}</p>
          <div className="flex items-center gap-4">
            <Button size="icon" variant="soft" className="h-14 w-14" onClick={() => setCount((c) => Math.max(1, c - 1))} aria-label="One less"><Icon name="minus" size={24} /></Button>
            <span className="w-12 text-center text-[32px] font-extrabold tabular-nums" aria-live="polite">{count}</span>
            <Button size="icon" variant="soft" className="h-14 w-14" onClick={() => setCount((c) => Math.min(30, c + 1))} aria-label="One more"><Icon name="plus" size={24} /></Button>
            {count >= 5 && <span className="text-[15px] font-semibold text-red-ink">Mass casualty: the on call team is alerted</span>}
          </div>
        </div>
      </div>
    </Sheet>
  );
}

function FamilySheet({ job, open, onOpenChange, onDone }: { job: ActiveJob; open: boolean; onOpenChange: (o: boolean) => void; onDone: () => void }) {
  const t = useTranslations("amb");
  const toast = useToast();
  const [pick, setPick] = useState<FamilyOverrideOption | null>(null);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const q = useQuery({
    queryKey: ["family-options", job.emergency_id],
    enabled: open,
    queryFn: async () => {
      try {
        return (await post<{ data: FamilyOverrideOption[] }>(`/emergencies/${job.emergency_id}/family-override/options`)).data;
      } catch (e) {
        // B's router serves this as GET
        if (e instanceof ApiError && (e.status === 404 || e.status === 405)) return (await get<{ data: FamilyOverrideOption[] }>(`/emergencies/${job.emergency_id}/family-override/options`)).data;
        throw e;
      }
    },
  });
  const submit = async () => {
    if (!pick) return;
    setBusy(true);
    try {
      await post(`/emergencies/${job.emergency_id}/family-override`, { hospital_id: pick.hospital_id, consent: true });
      onOpenChange(false);
      onDone();
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Sheet open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) { setPick(null); setConsent(false); } }} title={t("familyChoice")} description="Show the family what changes with each hospital, then ask for their consent." wide
      footer={<Button size="lg" block disabled={!pick || !consent} loading={busy} onClick={() => void submit()}>Send the patient to {pick?.name ?? "this hospital"}</Button>}>
      {q.isLoading ? <LoadingState /> : q.isError ? <ErrorState text={errorText(q.error)} onRetry={() => q.refetch()} /> : (
        <div className="flex flex-col gap-2">
          {(q.data ?? []).map((o) => (
            <button key={o.hospital_id} disabled={o.is_current} onClick={() => setPick(o)} aria-pressed={pick?.hospital_id === o.hospital_id}
              className={cn("flex items-start gap-3 rounded-2xl border-2 p-4 text-left", pick?.hospital_id === o.hospital_id ? "border-ink" : "border-line", o.is_current && "opacity-60")}>
              <div className="min-w-0 flex-1">
                <p className="text-[17px] font-bold">{o.name} {o.is_current && <span className="text-[14px] text-muted">(current)</span>}</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  <span className={cn("rounded-full px-2.5 py-0.5 text-[14px] font-bold", o.delta_sec > 60 ? "bg-amber-soft text-amber" : "bg-green-soft text-green")}>
                    {o.delta_sec > 0 ? `+${minutes(o.delta_sec)} min` : o.delta_sec < 0 ? `${minutes(-o.delta_sec)} min faster` : "same time"}
                  </span>
                  {o.notes.map((n) => <span key={n} className="rounded-full bg-red-soft px-2.5 py-0.5 text-[14px] font-semibold text-red-ink">{n}</span>)}
                </div>
              </div>
              <span className="text-[16px] font-semibold text-muted">{minutes(o.eta_sec)} min</span>
            </button>
          ))}
          {pick && (
            <label className="mt-2 flex items-start gap-3 rounded-2xl bg-soft p-4 text-[17px]">
              <input type="checkbox" className="mt-1 h-6 w-6" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              The family understands {pick.delta_sec > 0 ? `this takes ${minutes(pick.delta_sec)} minutes longer` : "the change"}{pick.notes.length ? ` and that it has: ${pick.notes.join(", ")}` : ""}, and agrees.
            </label>
          )}
        </div>
      )}
    </Sheet>
  );
}

function DoorTimer({ since }: { since: string }) {
  const now = useNow(1000);
  const s = (now - new Date(since).getTime()) / 1000;
  return <span className={cn("text-[40px] font-extrabold tabular-nums", s > 900 ? "text-red-ink" : "")}>{mmss(s)}</span>;
}

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const t = useTranslations("amb");
  const tc = useTranslations("common");
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();
  const { ws, dark, queued, online, refetchSelf, self } = useAmb();
  const [live, setLive] = useState<WsLocation | null>(null);
  const [reroute, setReroute] = useState<RerouteNotice | null>(null);
  const [sheet, setSheet] = useState<"confirm" | "family" | "vehicle" | "refused" | "critical" | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const q = useQuery({ queryKey: ["amb-active"], queryFn: fetchActive, refetchInterval: 4000 });
  const job = q.data && q.data.emergency_id === id ? q.data : null;
  const refresh = () => void qc.invalidateQueries({ queryKey: ["amb-active"] });

  useChannel(ws, `emergency:${id}`, (ev: WsEnvelope) => {
    if (ev.event === "ambulance.location") setLive(ev.data as WsLocation);
    else {
      if (ev.event === "reroute") setReroute(ev.data as RerouteNotice);
      if (ev.event === "handoff.ready") buzz([80, 60, 80]);
      refresh();
    }
  }, refresh);

  useEffect(() => {
    if (q.isSuccess && !q.data) {
      // job finished or was taken away: back to the duty screen
      refetchSelf();
      router.replace("/ambulance");
    }
  }, [q.isSuccess, q.data, router, refetchSelf]);

  if (q.isLoading || (!job && q.isSuccess)) return <LoadingState />;
  if (q.isError || !job) return <div className="p-4"><ErrorState text={errorText(q.error)} onRetry={() => q.refetch()} /></div>;

  const act = async (key: string, path: string, body?: unknown, ok?: string) => {
    setBusy(key);
    try {
      const r = await post<{ queued?: boolean; reason?: string }>(path, body, { queueable: true });
      if (r?.queued) toast("Saved. It will send when the signal is back.", "info");
      else if (ok || r?.reason) toast(r?.reason ?? ok!, "success");
      setSheet(null);
      refresh();
    } catch (e) {
      toast(errorText(e), "error");
      refresh();
    } finally {
      setBusy(null);
    }
  };

  const pos = live ? { lat: live.lat, lng: live.lng, heading: live.heading } : self?.location ? { ...self.location, heading: 0 } : null;
  const eta = live?.eta_sec ?? job.eta_sec ?? null;
  const toHospital = job.leg === "to_hospital";
  const s = job.status;
  const sms = (cmd: string) => `sms:${SMS_GATEWAY_NUMBER}?body=${encodeURIComponent(`GH ${job.short_id} ${cmd}`)}`;
  const nextTurn = job.turns?.[1] ?? job.turns?.[0];

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-3 px-3 pb-44 pt-3">
      <div className="flex items-center gap-2">
        <Link href="/ambulance" className="grid h-12 w-12 place-items-center rounded-full bg-soft" aria-label={tc("back")}><Icon name="back" size={22} /></Link>
        <div className="min-w-0 flex-1">
          <p className="text-[20px] font-extrabold leading-tight">
            {s === "ambulance_assigned" ? "Going to patient" : s === "at_scene" ? "With the patient" : s === "arrived_hospital" ? t("doorTimer") : toHospital || s === "hospital_confirmed" ? "Going to hospital" : s === "patient_on_board" || s === "hospital_selecting" ? "Finding hospital" : s.replace(/_/g, " ")}
          </p>
          <p className="text-[14px] text-muted">#{job.short_id}</p>
        </div>
        <AcuityBadge acuity={job.triage.acuity} />
      </div>

      {!online && <Banner tone="amber" icon="wifiOff">No signal. Actions are saved and sent later. <a className="underline" href={sms(s === "ambulance_assigned" ? "ARRIVED" : s === "hospital_confirmed" ? "ARRIVED" : "ONBOARD")}>{t("smsFallback")}</a></Banner>}
      {queued > 0 && online && <Banner tone="amber" icon="refresh">{t("queued", { n: queued })}</Banner>}
      {reroute && <Banner tone="blue" icon="refresh">Hospital changed to {reroute.to_hospital}. {reroute.reason}</Banner>}

      {(s === "ambulance_assigned" || toHospital) && (
        <div className="flex items-center gap-3 rounded-[22px] bg-blue px-4 py-3 text-white">
          <Icon name={nextTurn ? turnIcon(nextTurn) : "straight"} size={34} stroke={2.4} />
          <p className="flex-1 text-[19px] font-bold leading-snug">{nextTurn ?? "Follow the blue line"}</p>
          {eta != null && <div className="text-right"><p className="text-[26px] font-extrabold leading-none">{minutes(eta)}</p><p className="text-[13px] opacity-85">min</p></div>}
        </div>
      )}

      {s !== "arrived_hospital" && (
        <Map
          height={toHospital || s === "ambulance_assigned" ? 330 : 220}
          dark={dark}
          followDefault
          ambulance={pos ? { ...pos, tone: "dark" } : null}
          pickup={s === "ambulance_assigned" || s === "at_scene" ? job.pickup : null}
          destination={job.destination?.hospital.location ? { ...job.destination.hospital.location, name: job.destination.hospital.name } : null}
          route={job.route}
          routeTone={toHospital ? "red" : "blue"}
          routeDashed={!!job.hospital_selecting}
        />
      )}

      {/* stage card */}
      {s === "ambulance_assigned" && (
        <Card>
          <SectionLabel>{t("pickup")}</SectionLabel>
          <p className="mt-1 flex items-start gap-2 text-[21px] font-bold"><Icon name="pin" size={24} className="mt-0.5 shrink-0 text-red" />{job.pickup.landmark ?? "Caller's location"}</p>
          <p className="mt-1 text-[16px] text-muted">{job.distance_m != null ? `${km(job.distance_m)} to go` : ""}{job.pickup.accuracy_m ? ` · ± ${Math.round(job.pickup.accuracy_m)} m` : ""}</p>
        </Card>
      )}

      {(s === "patient_on_board" || s === "hospital_selecting") && (
        <Card className="flex items-center gap-4">
          <span className="h-8 w-8 animate-spin rounded-full border-4 border-blue border-t-transparent" aria-hidden />
          <div className="flex-1">
            <p className="text-[19px] font-bold">{job.hospital_selecting ? t("askingHospital", { name: job.hospital_selecting.hospital_name }) : "Choosing the best hospital"}</p>
            <p className="text-[16px] text-muted">Keep driving on the dashed line. It turns solid once the hospital says yes.</p>
          </div>
        </Card>
      )}

      {job.destination && (s === "hospital_confirmed" || s === "arrived_hospital") && (
        <Card className="border-2 border-green/50">
          <SectionLabel className="text-green">{t("destination")}</SectionLabel>
          <p className="mt-1 text-[23px] font-extrabold leading-tight">{job.destination.hospital.name}</p>
          <div className="mt-3 grid gap-2 text-[18px]">
            <p className="flex items-start gap-2"><Icon name="door" size={22} className="mt-0.5 shrink-0" /><b>{job.destination.entrance_note ?? job.destination.hospital.er_entrance_note}</b></p>
            {job.destination.room_location_note && <p className="flex items-start gap-2"><Icon name="bed" size={22} className="mt-0.5 shrink-0" /><span>{job.destination.room_location_note}</span></p>}
            {job.destination.receiving_team && <p className="flex items-start gap-2"><Icon name="doctor" size={22} className="mt-0.5 shrink-0" /><span>{job.destination.receiving_team}</span></p>}
          </div>
          {job.destination.is_family_choice && <p className="mt-2 text-[15px] font-semibold text-amber">Family&apos;s choice</p>}
          {job.destination.hospital.phone && <Button asChild variant="soft" block className="mt-3"><a href={`tel:${job.destination.hospital.phone}`}><Icon name="phone" size={20} />Call the ER</a></Button>}
        </Card>
      )}

      {s === "arrived_hospital" && (
        <Card className="flex flex-col items-center gap-2 py-6 text-center">
          <p className="text-[18px] font-semibold text-muted">{t("doorTimer")}</p>
          {job.arrived_at && <DoorTimer since={job.arrived_at} />}
          <p className="text-[16px] text-muted">The hospital taps &ldquo;Patient received&rdquo; when they take over.</p>
        </Card>
      )}

      {/* patient card */}
      <Card>
        <div className="flex items-start justify-between gap-2">
          <SectionLabel>{t("patient")}</SectionLabel>
          <Confidence value={job.triage.confidence} confirmed={job.triage.confirmed} />
        </div>
        <p className="mt-1 text-[21px] font-bold">{job.patient.display}{job.patient.temp_id ? ` · ${job.patient.temp_id}` : ""}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <FacilityChip facility={job.triage.facility} />
          {job.triage.mlc_flag && <span className="rounded-full bg-amber-soft px-3 py-1 text-[14px] font-bold text-amber">Medico-legal case</span>}
          {job.patient.patient_count > 1 && <span className="rounded-full bg-amber-soft px-3 py-1 text-[14px] font-bold text-amber">{job.patient.patient_count} patients</span>}
        </div>
        {job.patient.profile && (
          <div className="mt-3 grid gap-1 text-[17px]">
            {job.patient.profile.blood_group && <p>Blood <b>{job.patient.profile.blood_group}</b></p>}
            {!!job.patient.profile.allergies.length && <p className="font-bold text-red-ink">Allergy: {job.patient.profile.allergies.join(", ")}</p>}
            {!!job.patient.profile.conditions.length && <p>{job.patient.profile.conditions.join(", ")}</p>}
            {!!job.patient.profile.medications.length && <p className="text-muted">{job.patient.profile.medications.join(", ")}</p>}
          </div>
        )}
        {job.transcript && <p className="mt-3 rounded-2xl bg-soft px-4 py-3 text-[16px]">&ldquo;{job.transcript}&rdquo;</p>}
        {job.caller_phone && s === "ambulance_assigned" && (
          <Button asChild variant="soft" block className="mt-3"><a href={`tel:${job.caller_phone}`}><Icon name="phone" size={20} />{t("callCaller")} · {phone(job.caller_phone)}</a></Button>
        )}
      </Card>

      {job.turns && job.turns.length > 1 && (s === "ambulance_assigned" || toHospital) && (
        <details className="rounded-[24px] border border-line bg-card p-4">
          <summary className="cursor-pointer text-[17px] font-bold">{t("turns")}</summary>
          <ol className="mt-2 flex flex-col gap-2">
            {job.turns.map((x, i) => <li key={i} className="flex items-center gap-3 text-[16px]"><Icon name={turnIcon(x)} size={20} />{x}</li>)}
          </ol>
        </details>
      )}

      {/* secondary actions */}
      <div className="grid grid-cols-2 gap-2">
        {["at_scene", "patient_on_board", "hospital_selecting", "hospital_confirmed", "ambulance_assigned"].includes(s) && (
          <Button variant="dangerOutline" size="lg" onClick={() => setSheet("critical")}><Icon name="alert" size={20} />{t("critical")}</Button>
        )}
        {["patient_on_board", "hospital_selecting", "hospital_confirmed"].includes(s) && (
          <Button variant="outline" size="lg" onClick={() => setSheet("family")}><Icon name="users" size={20} />{t("familyChoice")}</Button>
        )}
        {s !== "arrived_hospital" && <Button variant="outline" size="lg" onClick={() => setSheet("vehicle")}><Icon name="wrench" size={20} />{t("vehicleIssue")}</Button>}
        {["at_scene", "patient_on_board", "hospital_selecting"].includes(s) && (
          <Button variant="outline" size="lg" onClick={() => setSheet("refused")}><Icon name="x" size={20} />{t("refused")}</Button>
        )}
      </div>

      {/* primary action, thumb reachable */}
      <div className={cn("fixed inset-x-0 bottom-0 z-40 border-t border-line bg-page/95 px-4 pb-[max(env(safe-area-inset-bottom),14px)] pt-3 backdrop-blur")}>
        <div className="mx-auto max-w-2xl">
          {s === "ambulance_assigned" && <Button size="xl" block variant="success" loading={busy === "arrive"} onClick={() => void act("arrive", `/emergencies/${id}/arrived-scene`)}><Icon name="pin" size={26} />{t("arrived")}</Button>}
          {s === "at_scene" && <Button size="xl" block variant="primary" onClick={() => setSheet("confirm")}><Icon name="check" size={26} stroke={2.6} />{t("confirmTitle")}</Button>}
          {s === "hospital_confirmed" && <Button size="xl" block variant="success" loading={busy === "arrh"} onClick={() => void act("arrh", `/emergencies/${id}/arrived-hospital`)}><Icon name="hospital" size={26} />{t("arrivedHospital")}</Button>}
          {(s === "patient_on_board" || s === "hospital_selecting") && <Button size="xl" block variant="soft" disabled><span className="h-6 w-6 animate-spin rounded-full border-[3px] border-current border-t-transparent" />Waiting for the hospital</Button>}
          {s === "arrived_hospital" && <Button size="xl" block variant="soft" disabled>Waiting for the hospital team</Button>}
        </div>
      </div>

      <TriageConfirmSheet job={job} open={sheet === "confirm"} onOpenChange={(o) => setSheet(o ? "confirm" : null)} onDone={refresh} />
      <FamilySheet job={job} open={sheet === "family"} onOpenChange={(o) => setSheet(o ? "family" : null)} onDone={refresh} />
      <Sheet open={sheet === "critical"} onOpenChange={(o) => setSheet(o ? "critical" : null)} title={t("critical")} description={t("criticalSub")}
        footer={<Button size="xl" variant="danger" block loading={busy === "crit"} onClick={() => void act("crit", `/emergencies/${id}/critical`)}><Icon name="alert" size={24} />Patient is now CRITICAL</Button>} />
      <Sheet open={sheet === "vehicle"} onOpenChange={(o) => setSheet(o ? "vehicle" : null)} title={t("vehicleIssue")} description={t("vehicleIssueSub")}
        footer={<Button size="lg" variant="danger" block loading={busy === "veh"} onClick={() => void act("veh", "/ambulance/vehicle-issue", { note }, "Another ambulance is being sent")}>Report problem</Button>}>
        <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="What happened? (optional)" aria-label="Note" />
      </Sheet>
      <Sheet open={sheet === "refused"} onOpenChange={(o) => setSheet(o ? "refused" : null)} title={t("refused")} description="This ends the job and frees the hospital room."
        footer={<Button size="lg" variant="dangerOutline" block loading={busy === "ref"} onClick={() => void act("ref", `/emergencies/${id}/refused-transport`, { note })}>Record refusal</Button>}>
        <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note (optional)" aria-label="Note" />
      </Sheet>

    </div>
  );
}
