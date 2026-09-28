"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { errorText, post } from "@/lib/api";
import type { EmergencyView, FollowupState, RerouteNotice, WsEnvelope, WsLocation } from "@/lib/api-types";
import { fetchEmergency, fetchFollowup, isFinal, trackUrlFor } from "@/lib/patient";
import { useChannel, useWsClient, useWsStatus } from "@/components/realtime/WsProvider";
import Map from "@/components/map";
import { AcuityBadge, Confidence, EtaRange, FacilityChip } from "@/components/emergency/badges";
import { FirstAidCard, FollowupCard, StatusStepper } from "@/components/emergency/parts";
import CprCoach from "@/components/emergency/CprCoach";
import { Banner, Card, ErrorState, LoadingState, SectionLabel, SimulatedBadge } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { minutes, reg } from "@/lib/format";
import { cn } from "@/lib/cn";

export default function LiveEmergency() {
  const { id } = useParams<{ id: string }>();
  const t = useTranslations("live");
  const ts = useTranslations("status");
  const tc = useTranslations("common");
  const { session } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const ws = useWsClient("EMERGENCIES", session?.token);
  const wsStatus = useWsStatus(ws);
  const [live, setLive] = useState<WsLocation | null>(null);
  const [reroute, setReroute] = useState<RerouteNotice | null>(null);
  const [cpr, setCpr] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [answering, setAnswering] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const q = useQuery({
    queryKey: ["emergency", id],
    queryFn: () => fetchEmergency(id),
    // WS is the live truth; poll slowly as a safety net, faster if the socket is down
    refetchInterval: (query) => (query.state.data && isFinal(query.state.data.status) ? false : wsStatus === "open" ? 15000 : 4000),
  });
  const fu = useQuery({ queryKey: ["followup", id], queryFn: () => fetchFollowup(id), refetchInterval: wsStatus === "open" ? 20000 : 6000 });

  const refetch = () => {
    void qc.invalidateQueries({ queryKey: ["emergency", id] });
    void qc.invalidateQueries({ queryKey: ["followup", id] });
  };

  useChannel(ws, `emergency:${id}`, (ev: WsEnvelope) => {
    if (ev.event === "ambulance.location") {
      setLive(ev.data as WsLocation);
      return;
    }
    if (ev.event === "reroute") setReroute(ev.data as RerouteNotice);
    if (ev.event === "alert") toast((ev.data as { message: string }).message, "info");
    if (ev.event === "emergency.followup" || ev.event === "emergency.first_aid") void qc.invalidateQueries({ queryKey: ["followup", id] });
    void qc.invalidateQueries({ queryKey: ["emergency", id] });
  }, refetch);

  if (q.isLoading) return <LoadingState />;
  if (q.isError || !q.data) return <ErrorState text={errorText(q.error)} onRetry={() => q.refetch()} />;
  const e: EmergencyView = q.data;
  const f: FollowupState | null | undefined = fu.data;

  const amb = e.ambulance;
  const loc = live && amb ? { ...amb, location: { lat: live.lat, lng: live.lng }, heading: live.heading, eta_sec: live.eta_sec ?? amb.eta_sec, eta_low_sec: live.eta_low_sec ?? amb.eta_low_sec, eta_high_sec: live.eta_high_sec ?? amb.eta_high_sec, signal: live.signal } : amb;
  const title = e.for_self === false ? t("title", { who: t("someone") }) : t("titleSelf");
  const trackUrl = e.family_track_url ?? trackUrlFor(id);
  const final = isFinal(e.status);
  const canCancel = ["received", "triaged", "dispatching", "ambulance_assigned"].includes(e.status);
  const firstAid = f?.first_aid ?? e.first_aid;
  const rr = reroute ?? e.reroute;

  const answer = async (a: string) => {
    if (!f?.question) return;
    setAnswering(true);
    try {
      await post(`/emergencies/${id}/followup`, { question_id: f.question.id, answer: a });
      toast(t("thanks"), "success");
      refetch();
    } catch (err) {
      toast(errorText(err), "error");
      refetch();
    } finally {
      setAnswering(false);
    }
  };

  const cancel = async () => {
    setCancelling(true);
    try {
      await post(`/emergencies/${id}/cancel`, { reason: "Caller cancelled from the app" });
      setCancelOpen(false);
      refetch();
    } catch (err) {
      toast(errorText(err), "error");
      refetch();
    } finally {
      setCancelling(false);
    }
  };

  const share = async () => {
    if (!trackUrl) return;
    const url = new URL(trackUrl, window.location.origin).toString();
    try {
      if (navigator.share) await navigator.share({ title: "GoldenHour", text: "Follow the ambulance live", url });
      else {
        await navigator.clipboard.writeText(url);
        toast(t("copied"), "success");
      }
    } catch {
      /* dismissed */
    }
  };

  // Hero: one sentence that says what is happening now
  const hero = (() => {
    switch (e.status) {
      case "received":
      case "triaged":
        return { tone: "dark", icon: "clock" as const, head: t("sending"), sub: t("sendingSub") };
      case "dispatching":
        return { tone: "dark", icon: "search" as const, head: t("finding"), sub: t("findingSub") };
      case "ambulance_assigned":
        return { tone: "blue", icon: "ambulance" as const, head: t("onTheWay"), sub: null, eta: true };
      case "at_scene":
        return { tone: "green", icon: "check" as const, head: t("arrived"), sub: t("arrivedSub") };
      case "patient_on_board":
        return { tone: "blue", icon: "ambulance" as const, head: t("toHospital"), sub: null };
      case "hospital_selecting":
        return { tone: "blue", icon: "hospital" as const, head: t("toHospital"), sub: t("askingHospitalSub") };
      case "hospital_confirmed":
        return { tone: "green", icon: "hospital" as const, head: t("hospitalReady"), sub: e.hospital?.name ?? null, eta: true };
      case "arrived_hospital":
        return { tone: "green", icon: "door" as const, head: t("atHospital"), sub: e.hospital?.name ?? null };
      case "handed_off":
      case "closed":
        return { tone: "green", icon: "check" as const, head: t("handedOver"), sub: t("handedOverSub") };
      case "cancelled":
        return { tone: "dark", icon: "x" as const, head: t("cancelled"), sub: null };
      default:
        return { tone: "dark", icon: "info" as const, head: ts(e.status), sub: null };
    }
  })();
  const heroCls = { dark: "bg-ink text-bg", blue: "bg-blue text-white", green: "bg-green text-white" }[hero.tone as "dark" | "blue" | "green"];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 pt-1">
        <Link href="/patient" className="grid h-12 w-12 place-items-center rounded-full bg-soft" aria-label={tc("back")}><Icon name="back" size={22} /></Link>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[22px] font-extrabold">{title}</h1>
          <p className="text-[14px] text-muted">#{id.slice(0, 6).toUpperCase()}</p>
        </div>
      </div>

      {e.call_108_prompt && (
        <a href="tel:108" className="flex items-center gap-3 rounded-[22px] bg-red px-5 py-4 text-[19px] font-bold text-white" role="alert">
          <Icon name="phone" size={26} />{t("call108Now")}
        </a>
      )}

      <section className={cn("rounded-[28px] p-5", heroCls)} aria-live="polite">
        <div className="flex items-center gap-3">
          <span className="grid h-12 w-12 place-items-center rounded-full bg-white/15"><Icon name={hero.icon} size={26} /></span>
          <p className="flex-1 text-[23px] font-extrabold leading-tight">{hero.head}</p>
        </div>
        {hero.eta && loc?.eta_sec != null && (
          <div className="mt-4">
            <p className="text-[16px] opacity-85">{t("arriveIn")}</p>
            <EtaRange eta={loc.eta_sec} low={loc.eta_low_sec} high={loc.eta_high_sec} big />
          </div>
        )}
        {hero.sub && <p className="mt-2 text-[17px] opacity-90">{hero.sub}</p>}
      </section>

      {rr && !final && (
        <Banner tone="blue" icon="refresh">
          <span className="block">{t("reroute", { to: rr.to_hospital })}</span>
          <span className="block text-[15px] font-medium opacity-80">{rr.reason}</span>
        </Banner>
      )}
      {loc?.signal === "weak" && !final && <Banner tone="amber" icon="wifiOff">{t("signalWeak")}</Banner>}
      {loc?.signal === "lost" && !final && <Banner tone="amber" icon="wifiOff">{t("signalLost")}</Banner>}

      {!final && (e.pickup || loc?.location) && (
        <Map
          height={260}
          ambulance={loc?.location ? { ...loc.location, heading: loc.heading, signal: loc.signal, label: `Ambulance ${reg(loc.registration_no)}` } : null}
          pickup={e.status === "ambulance_assigned" || e.status === "dispatching" || e.status === "at_scene" ? e.pickup ?? null : null}
          destination={e.hospital?.location ? { ...e.hospital.location, name: e.hospital.name } : null}
          route={e.route}
          routeTone={e.leg === "to_hospital" ? "red" : "blue"}
          label={hero.head}
        />
      )}

      {f?.question && !final && <FollowupCard q={f.question} onAnswer={(a) => void answer(a)} busy={answering} />}

      {e.hospital && (
        <Card>
          <div className="flex items-center justify-between gap-2">
            <SectionLabel>{t("hospital")}</SectionLabel>
            {e.hospital.is_simulated && <SimulatedBadge />}
          </div>
          <p className="mt-1.5 text-[22px] font-bold leading-snug">{e.hospital.name}</p>
          {e.hospital.address && <p className="text-[16px] text-muted">{e.hospital.address}</p>}
          <div className="mt-3 flex flex-col gap-2.5">
            {(e.handoff?.entrance_note ?? e.hospital.er_entrance_note) && (
              <p className="flex items-start gap-2.5 text-[18px]"><Icon name="door" size={22} className="mt-0.5 shrink-0" /><span><span className="text-muted">{t("enter")}: </span><b>{e.handoff?.entrance_note ?? e.hospital.er_entrance_note}</b></span></p>
            )}
            {e.handoff?.room_location_note && <p className="flex items-start gap-2.5 text-[18px]"><Icon name="bed" size={22} className="mt-0.5 shrink-0" /><span><span className="text-muted">{t("room")}: </span><b>{e.handoff.room_location_note}</b></span></p>}
            {e.handoff?.receiving_team && <p className="flex items-start gap-2.5 text-[18px]"><Icon name="doctor" size={22} className="mt-0.5 shrink-0" /><span><span className="text-muted">{t("team")}: </span><b>{e.handoff.receiving_team}</b></span></p>}
          </div>
          {e.hospital.location && (
            <Button asChild variant="outline" block className="mt-4">
              <a href={`https://www.google.com/maps/dir/?api=1&destination=${e.hospital.location.lat},${e.hospital.location.lng}`} target="_blank" rel="noreferrer"><Icon name="pin" size={20} />{t("directions")}</a>
            </Button>
          )}
        </Card>
      )}

      {amb && !final && (
        <Card>
          <div className="flex items-center gap-4">
            <span className="grid h-14 w-14 shrink-0 place-items-center rounded-full bg-blue-soft text-blue"><Icon name="ambulance" size={28} /></span>
            <div className="min-w-0 flex-1">
              <SectionLabel>{t("ambulance")}</SectionLabel>
              <p className="whitespace-nowrap text-[21px] font-bold tracking-wide">{reg(amb.registration_no)}</p>
              <p className="text-[15px] text-muted">{amb.type === "ALS" ? "Advanced life support" : "Basic life support"}{amb.is_simulated ? " · " + tc("simulated") : ""}</p>
            </div>
          </div>
          {amb.crew_phone && <Button asChild variant="soft" size="md" block className="mt-3"><a href={`tel:${amb.crew_phone}`}><Icon name="phone" size={20} />{t("callCrew")}</a></Button>}
        </Card>
      )}

      {firstAid && !final && <FirstAidCard aid={firstAid} onCpr={() => setCpr(true)} />}

      {e.triage && (
        <Card>
          <SectionLabel>{t("aiThinks")}</SectionLabel>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <AcuityBadge acuity={e.triage.acuity} />
            <FacilityChip facility={e.triage.facility} />
            <Confidence value={e.triage.confidence} confirmed={e.triage.confirmed} />
          </div>
        </Card>
      )}

      <Card>
        <StatusStepper status={e.status} timeline={e.timeline} />
      </Card>

      {trackUrl && !final && (
        <Card className="flex items-center gap-3">
          <Icon name="users" size={24} className="shrink-0" />
          <p className="flex-1 text-[17px] font-semibold">{t("familyLink")}</p>
          <Button variant="soft" onClick={() => void share()}><Icon name="share" size={18} />{t("shareLink")}</Button>
        </Card>
      )}

      {canCancel && (
        <Button variant="ghost" block onClick={() => setCancelOpen(true)} className="text-muted">{t("cancelHelp")}</Button>
      )}
      {final && <Button asChild size="lg" block variant="primary"><Link href="/patient">{t("backHome")}</Link></Button>}

      <Sheet open={cancelOpen} onOpenChange={setCancelOpen} title={t("cancelTitle")} description={t("cancelSub")}
        footer={<>
          <Button size="lg" variant="primary" onClick={() => setCancelOpen(false)}>{t("cancelNo")}</Button>
          <Button size="lg" variant="dangerOutline" loading={cancelling} onClick={() => void cancel()}>{t("cancelYes")}</Button>
        </>} />

      {cpr && <CprCoach onClose={() => setCpr(false)} etaText={loc?.eta_sec ? `${t("ambulance")}: ${tc("min", { n: minutes(loc.eta_sec) ?? 1 })}` : null} />}
    </div>
  );
}
