"use client";

import { useCallback, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { errorText, ApiError } from "@/lib/api";
import type { Offer, WsEnvelope } from "@/lib/api-types";
import { acceptOffer, declineOffer, fetchOffers, fetchSelf, normalizeOffer, useHeartbeat, useNightMode, useOfferAlert, useOfflineQueue } from "@/lib/ambulance";
import { useChannel, useWsClient, useWsStatus } from "@/components/realtime/WsProvider";
import { MockRibbon, RequireRole } from "@/components/shell";
import { AcuityBadge, FacilityChip } from "@/components/emergency/badges";
import CountdownRing from "@/components/ambulance/CountdownRing";
import { Button } from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { km, minutes } from "@/lib/format";
import { cn } from "@/lib/cn";
import { buzz } from "@/lib/hooks";
import { AmbulanceContext } from "./context";

function Shell({ children }: { children: ReactNode }) {
  const t = useTranslations("amb");
  const { session } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();
  const [dark, darkPref, setDarkPref] = useNightMode();
  const ws = useWsClient("AMBULANCE", session?.token);
  const wsStatus = useWsStatus(ws);
  const tokenFn = useCallback(() => session?.token ?? null, [session?.token]);
  const { queued, online } = useOfflineQueue(tokenFn);
  const self = useQuery({ queryKey: ["amb-self"], queryFn: fetchSelf, refetchInterval: 15000 });
  const onDuty = !!self.data && self.data.status !== "offline" && self.data.status !== "out_of_service";
  const offers = useQuery({ queryKey: ["offers"], queryFn: fetchOffers, enabled: onDuty, refetchInterval: wsStatus === "open" ? 15000 : 3000 });
  const [gone, setGone] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  useHeartbeat(onDuty, (d) => ws?.heartbeat(d));

  useChannel(ws, self.data ? `ambulance:${self.data.id}` : null, (ev: WsEnvelope) => {
    if (ev.event === "offer.new") {
      const o = normalizeOffer(ev.data as Record<string, unknown>);
      qc.setQueryData<Offer[]>(["offers"], (xs = []) => [...xs.filter((x) => x.offer_id !== o.offer_id), o]);
      buzz([200, 100, 200]);
    } else if (ev.event === "offer.revoked") {
      const d = ev.data as { offer_id: string; reason: string };
      qc.setQueryData<Offer[]>(["offers"], (xs = []) => xs.filter((x) => x.offer_id !== d.offer_id));
      if (d.reason === "taken") setGone((g) => ({ ...g, [d.offer_id]: "taken" }));
    } else if (ev.event === "alert") {
      toast((ev.data as { message: string }).message, "info");
    } else {
      void qc.invalidateQueries({ queryKey: ["amb-active"] });
      void qc.invalidateQueries({ queryKey: ["amb-self"] });
    }
  }, () => {
    void qc.invalidateQueries({ queryKey: ["offers"] });
    void qc.invalidateQueries({ queryKey: ["amb-active"] });
  });

  const live = (offers.data ?? []).filter((o) => new Date(o.expires_at).getTime() > Date.now() - 500);
  const offer = live[0] ?? null;
  useOfferAlert(!!offer);

  const accept = async (o: Offer) => {
    setBusy(o.offer_id);
    try {
      const r = await acceptOffer(o.offer_id);
      qc.setQueryData<Offer[]>(["offers"], []);
      buzz(80);
      void qc.invalidateQueries({ queryKey: ["amb-self"] });
      router.push(`/ambulance/job/${r.emergency_id ?? o.emergency_id}`);
    } catch (e) {
      // 409 ALREADY_TAKEN / OFFER_EXPIRED: say so plainly, remove the card
      qc.setQueryData<Offer[]>(["offers"], (xs = []) => xs.filter((x) => x.offer_id !== o.offer_id));
      toast(e instanceof ApiError && e.isConflict ? (e.code === "OFFER_EXPIRED" ? t("expired") : t("taken")) : errorText(e), "error");
    } finally {
      setBusy(null);
    }
  };
  const decline = async (o: Offer) => {
    qc.setQueryData<Offer[]>(["offers"], (xs = []) => xs.filter((x) => x.offer_id !== o.offer_id));
    try {
      await declineOffer(o.offer_id);
    } catch {
      /* already gone */
    }
  };

  return (
    <AmbulanceContext.Provider value={{ self: self.data ?? null, refetchSelf: () => void self.refetch(), ws, dark, darkPref, setDarkPref, queued, online }}>
      <div className={cn(dark && "dark")}>
        <div className="min-h-dvh bg-page text-ink">
          <MockRibbon />
          {children}
          {Object.entries(gone).slice(-1).map(([id]) => (
            <div key={id} className="fixed inset-x-4 bottom-6 z-[70] flex items-center gap-3 rounded-2xl bg-ink px-5 py-4 text-[17px] font-semibold text-bg shadow-xl" role="status">
              <Icon name="info" size={22} />
              <span className="flex-1">{t("taken")}</span>
              <button onClick={() => setGone({})} className="underline">OK</button>
            </div>
          ))}
          {offer && (
            <div className="fixed inset-0 z-[85] flex flex-col bg-page" role="alertdialog" aria-modal="true" aria-labelledby="offer-title">
              <div className="flex items-center gap-3 bg-red px-5 py-4 text-white">
                <Icon name="bell" size={28} className="gh-ring" />
                <h2 id="offer-title" className="flex-1 text-[24px] font-extrabold">{t("newRequest")}</h2>
                <span className="rounded-full bg-white/20 px-3 py-1 text-[15px] font-bold">{live.length > 1 ? `+${live.length - 1}` : ""}</span>
              </div>
              <div className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-4 overflow-y-auto px-5 py-5">
                <div className="flex items-center gap-4">
                  <CountdownRing until={offer.expires_at} total={20} size={104} label="accept" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[30px] font-extrabold leading-tight">{t("away", { km: km(offer.distance_m).replace(" km", "") })}</p>
                    <p className="text-[18px] text-muted">{t("pickupIn", { min: minutes(offer.eta_to_pickup_sec) ?? 1 })}</p>
                  </div>
                </div>
                <div className="rounded-[24px] border border-line bg-card p-5">
                  <p className="text-[13px] font-bold uppercase tracking-wider text-muted">{t("patient")}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <AcuityBadge acuity={offer.summary.acuity} size="lg" />
                    <FacilityChip facility={offer.summary.facility} />
                  </div>
                  <p className="mt-3 text-[20px] font-bold">
                    {[offer.summary.sex === "male" || offer.summary.sex === "M" ? "Male" : offer.summary.sex === "female" || offer.summary.sex === "F" ? "Female" : null, offer.summary.age ? `~${offer.summary.age}` : null].filter(Boolean).join(", ") || "Details coming"}
                    {offer.summary.patient_count > 1 && <span className="ml-2 rounded-full bg-amber-soft px-2.5 py-0.5 text-[16px] text-amber">{offer.summary.patient_count} patients</span>}
                  </p>
                </div>
                <div className="rounded-[24px] border border-line bg-card p-5">
                  <p className="text-[13px] font-bold uppercase tracking-wider text-muted">{t("pickup")}</p>
                  <p className="mt-1 flex items-start gap-2 text-[20px] font-semibold"><Icon name="pin" size={24} className="mt-0.5 shrink-0 text-red" />{offer.pickup.landmark ?? `${offer.pickup.lat.toFixed(4)}, ${offer.pickup.lng.toFixed(4)}`}</p>
                  {offer.pickup.accuracy_m ? <p className="mt-1 text-[16px] text-muted">± {Math.round(offer.pickup.accuracy_m)} m</p> : null}
                </div>
              </div>
              <div className="mx-auto grid w-full max-w-lg grid-cols-[1fr_2fr] gap-3 px-5 pb-[max(env(safe-area-inset-bottom),20px)] pt-2">
                <Button size="xl" variant="outline" onClick={() => void decline(offer)} disabled={!!busy}>{t("decline")}</Button>
                <Button size="xl" variant="success" onClick={() => void accept(offer)} loading={busy === offer.offer_id}><Icon name="check" size={28} stroke={2.8} />{t("accept")}</Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </AmbulanceContext.Provider>
  );
}

export default function AmbulanceLayout({ children }: { children: ReactNode }) {
  return (
    <RequireRole role="paramedic">
      <Shell>{children}</Shell>
    </RequireRole>
  );
}
