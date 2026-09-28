"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { ApiError, errorText, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fetchActive } from "@/lib/ambulance";
import { reg } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Banner, Card, LoadingState, SimulatedBadge } from "@/components/ui/bits";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { ConnectionBanners, LanguageSwitcher } from "@/components/shell";
import { useAmb } from "./context";
import { cn } from "@/lib/cn";

export default function AmbulanceHome() {
  const t = useTranslations("amb");
  const tc = useTranslations("common");
  const { self, refetchSelf, darkPref, setDarkPref, queued } = useAmb();
  const { signOut } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const active = useQuery({ queryKey: ["amb-active"], queryFn: fetchActive, refetchInterval: 5000 });

  useEffect(() => {
    const j = active.data;
    if (j && !["handed_off", "closed", "cancelled", "refused_transport"].includes(j.status)) router.replace(`/ambulance/job/${j.emergency_id}`);
  }, [active.data, router]);

  if (!self) return <LoadingState />;
  const onDuty = self.status !== "offline" && self.status !== "out_of_service";

  const setStatus = async (status: "available" | "offline" | "cleaning_done") => {
    setBusy(true);
    try {
      await post("/ambulance/status", { status, version: self.version });
      refetchSelf();
    } catch (e) {
      if (e instanceof ApiError && e.code === "VERSION_CONFLICT") refetchSelf();
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-4 px-4 pb-10 pt-4">
      <header className="flex items-center gap-3">
        <span className="grid h-12 w-12 place-items-center rounded-full bg-soft"><Icon name="ambulance" size={24} /></span>
        <div className="min-w-0 flex-1">
          <p className="text-[22px] font-extrabold tracking-wide">{reg(self.registration_no)}</p>
          <p className="flex items-center gap-2 text-[15px] text-muted">{self.type === "ALS" ? "Advanced life support" : "Basic life support"} {self.is_simulated && <SimulatedBadge />}</p>
        </div>
        <Link href="/ambulance/history" className="grid h-12 w-12 place-items-center rounded-full bg-soft" aria-label={t("history")}><Icon name="history" size={22} /></Link>
      </header>

      <ConnectionBanners />
      {queued > 0 && <Banner tone="amber" icon="wifiOff">{t("queued", { n: queued })}</Banner>}

      {self.status === "cleaning" ? (
        <Card className="flex flex-col gap-4 text-center">
          <span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-blue-soft text-blue"><Icon name="refresh" size={30} /></span>
          <p className="text-[24px] font-extrabold">{t("cleaning")}</p>
          <Button size="xl" variant="success" block loading={busy} onClick={() => void setStatus("cleaning_done")}><Icon name="check" size={26} />{t("ready")}</Button>
        </Card>
      ) : (
        <Card className={cn("flex flex-col items-center gap-4 py-8 text-center", onDuty ? "border-green/40" : "")}>
          <span className={cn("relative grid h-24 w-24 place-items-center rounded-full", onDuty ? "bg-green-soft text-green" : "bg-soft text-muted")}>
            {onDuty && <span className="gh-pulse absolute inset-0 rounded-full bg-green/20" />}
            <Icon name={onDuty ? "bell" : "moon"} size={40} />
          </span>
          <div>
            <p className="text-[26px] font-extrabold">{onDuty ? t("online") : t("offline")}</p>
            <p className="mt-1 text-[17px] text-muted">{onDuty ? t("waitingSub") : t("offDutySub")}</p>
          </div>
          {self.status === "out_of_service" ? (
            <Banner tone="red" icon="wrench">Vehicle marked out of service. Ask the control room to put it back.</Banner>
          ) : (
            <Button size="xl" block variant={onDuty ? "outline" : "success"} loading={busy} onClick={() => void setStatus(onDuty ? "offline" : "available")}>
              {onDuty ? t("goOffline") : t("goOnline")}
            </Button>
          )}
        </Card>
      )}

      <Card className="flex flex-col gap-3">
        <p className="text-[17px] font-bold">{t("night")}</p>
        <div role="radiogroup" className="grid grid-cols-3 gap-2">
          {(["auto", "on", "off"] as const).map((p) => (
            <button key={p} role="radio" aria-checked={darkPref === p} onClick={() => setDarkPref(p)}
              className={cn("h-12 rounded-full text-[16px] font-semibold", darkPref === p ? "bg-ink text-bg" : "bg-soft")}>
              {p === "auto" ? "Auto" : p === "on" ? "On" : "Off"}
            </button>
          ))}
        </div>
        <LanguageSwitcher />
      </Card>

      <Button variant="ghost" block onClick={() => void signOut()}><Icon name="logout" size={20} />{tc("signOut")}</Button>
    </div>
  );
}
