"use client";

// Family tracking page (technical.md §7.6, §16.5): public, read-only, no auth.
// Renders ONLY non-clinical fields — status, map, ETA range, hospital, entrance,
// room location note, receiving team. No acuity, no facility, no profile, ever.

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get } from "@/lib/api";
import type { TrackView, WsEnvelope, WsLocation } from "@/lib/api-types";
import { isFinal } from "@/lib/patient";
import type { EmergencyStatus } from "@/lib/enums";
import { WsClient } from "@/lib/ws";
import Map from "@/components/map";
import { StatusStepper } from "@/components/emergency/parts";
import { EtaRange } from "@/components/emergency/badges";
import { Banner, Card, ErrorState, LoadingState, SectionLabel } from "@/components/ui/bits";
import { Brand, Call108, LanguageSwitcher } from "@/components/shell";
import Icon from "@/components/ui/icon";
import { wsUrl } from "@/lib/config";

async function fetchTrack(token: string): Promise<TrackView> {
  return get<TrackView>(`/track/${token}`, { auth: false });
}

export default function TrackPage() {
  const { token } = useParams<{ token: string }>();
  const t = useTranslations("track");
  const ts = useTranslations("status");
  const tc = useTranslations("common");
  const qc = useQueryClient();
  const [live, setLive] = useState<WsLocation | null>(null);
  const [ws, setWs] = useState<WsClient | null>(null);

  const q = useQuery({ queryKey: ["track", token], queryFn: () => fetchTrack(token), refetchInterval: (query) => (query.state.data && isFinal(query.state.data.status as EmergencyStatus) ? false : 8000) });

  // token doubles as the WS auth for the family channel (§8)
  useEffect(() => {
    const client = new WsClient(wsUrl("TRACK"), token);
    setWs(client);
    return () => client.close();
  }, [token]);

  useEffect(() => {
    if (!ws) return;
    return ws.subscribe(`track:${token}`, (ev: WsEnvelope) => {
      if (ev.event === "ambulance.location") setLive(ev.data as WsLocation);
      else void qc.invalidateQueries({ queryKey: ["track", token] });
    }, () => void qc.invalidateQueries({ queryKey: ["track", token] }));
  }, [ws, token, qc]);

  if (q.isLoading) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-lg flex-col px-4 pt-6">
        <Header />
        <LoadingState />
      </div>
    );
  }
  if (q.isError || !q.data) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-lg flex-col gap-6 px-4 pt-6">
        <Header />
        <ErrorState title={t("invalid")} text={t("invalidSub")} />
        <Call108 />
      </div>
    );
  }

  const view = q.data;
  const amb = live && view.ambulance ? { ...view.ambulance, location: { lat: live.lat, lng: live.lng }, eta_sec: live.eta_sec ?? view.ambulance.eta_sec, eta_low_sec: live.eta_low_sec ?? view.ambulance.eta_low_sec, eta_high_sec: live.eta_high_sec ?? view.ambulance.eta_high_sec } : view.ambulance;
  const final = isFinal(view.status as EmergencyStatus);
  const title = view.patient_first_name ? t("title", { name: view.patient_first_name }) : t("titleGeneric");

  const hero = (() => {
    switch (view.status) {
      case "ambulance_assigned": return { cls: "bg-blue text-white", icon: "ambulance" as const, text: ts("ambulance_assigned"), eta: true };
      case "at_scene": return { cls: "bg-green text-white", icon: "check" as const, text: ts("at_scene") };
      case "patient_on_board":
      case "hospital_selecting": return { cls: "bg-blue text-white", icon: "hospital" as const, text: ts(view.status) };
      case "hospital_confirmed": return { cls: "bg-green text-white", icon: "hospital" as const, text: ts("hospital_confirmed"), eta: true };
      case "arrived_hospital": return { cls: "bg-green text-white", icon: "door" as const, text: ts("arrived_hospital") };
      case "handed_off":
      case "closed": return { cls: "bg-ink text-bg", icon: "check" as const, text: ts("handed_off") };
      default: return { cls: "bg-ink text-bg", icon: "clock" as const, text: ts(view.status as EmergencyStatus) ?? view.status };
    }
  })();

  return (
    <div className="mx-auto flex min-h-dvh max-w-lg flex-col gap-4 px-4 pb-8 pt-6">
      <Header />
      <h1 className="text-[24px] font-extrabold">{title}</h1>

      <section className={`rounded-[26px] p-5 ${hero.cls}`} aria-live="polite">
        <div className="flex items-center gap-3">
          <span className="grid h-12 w-12 place-items-center rounded-full bg-white/15"><Icon name={hero.icon} size={26} /></span>
          <p className="text-[21px] font-extrabold leading-tight">{hero.text}</p>
        </div>
        {hero.eta && amb?.eta_sec != null && <div className="mt-3"><EtaRange eta={amb.eta_sec} low={amb.eta_low_sec} high={amb.eta_high_sec} big /></div>}
      </section>

      {view.reroute && !final && <Banner tone="blue" icon="refresh">{t("hospitalPending")} {view.reroute.reason}</Banner>}

      {!final && (view.pickup || amb?.location) && (
        <Map
          height={260}
          ambulance={amb?.location ? { ...amb.location, label: "Ambulance" } : null}
          pickup={view.status === "ambulance_assigned" ? view.pickup : null}
          destination={view.hospital?.location ? { ...view.hospital.location, name: view.hospital.name } : null}
          label={hero.text}
        />
      )}

      {view.hospital && (
        <Card>
          <SectionLabel>Hospital</SectionLabel>
          <p className="mt-1.5 text-[21px] font-bold">{view.hospital.name}</p>
          {view.hospital.address && <p className="text-[15px] text-muted">{view.hospital.address}</p>}
          <div className="mt-3 flex flex-col gap-2">
            {view.hospital.entrance_note && <p className="flex items-start gap-2 text-[17px]"><Icon name="door" size={20} className="mt-0.5 shrink-0" /><b>{view.hospital.entrance_note}</b></p>}
            {view.handoff?.room_location_note && <p className="flex items-start gap-2 text-[17px]"><Icon name="bed" size={20} className="mt-0.5 shrink-0" />{view.handoff.room_location_note}</p>}
            {view.handoff?.receiving_team && <p className="flex items-start gap-2 text-[17px]"><Icon name="doctor" size={20} className="mt-0.5 shrink-0" />{view.handoff.receiving_team}</p>}
          </div>
        </Card>
      )}
      {!view.hospital && !final && <Card><p className="text-[16px] text-muted">{t("hospitalPending")}</p></Card>}

      <Card><StatusStepper status={view.status as EmergencyStatus} timeline={view.timeline} /></Card>

      <p className="flex items-center gap-2 rounded-2xl bg-soft px-4 py-3 text-[14px] text-muted"><Icon name="lock" size={16} className="shrink-0" />{t("privacy")}</p>

      <Call108 />
      <p className="text-center text-[13px] text-muted">{tc("simulated")}</p>
    </div>
  );
}

function Header() {
  return (
    <div className="mb-2 flex items-center justify-between">
      <Brand small />
      <LanguageSwitcher compact />
    </div>
  );
}
