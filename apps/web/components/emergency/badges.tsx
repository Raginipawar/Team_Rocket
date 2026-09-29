"use client";

import { useTranslations } from "next-intl";
import type { Acuity, Facility, Freshness } from "@/lib/enums";
import type { Signal } from "@/lib/api-types";
import { cn } from "@/lib/cn";
import Icon, { type IconName } from "@/components/ui/icon";
import { ago, minutes } from "@/lib/format";
import { useNow } from "@/lib/hooks";

const ACUITY_STYLE: Record<Acuity, { cls: string; icon: IconName }> = {
  critical: { cls: "bg-red text-white", icon: "alert" },
  urgent: { cls: "bg-amber-soft text-amber border border-amber/40", icon: "clock" },
  stable: { cls: "bg-green-soft text-green border border-green/40", icon: "check" },
};

/** Severity: colour + icon + word, never colour alone. */
export function AcuityBadge({ acuity, size = "md" }: { acuity: Acuity; size?: "md" | "lg" }) {
  const t = useTranslations("acuity");
  const s = ACUITY_STYLE[acuity];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full font-bold", s.cls, size === "lg" ? "px-4 py-1.5 text-[17px]" : "px-3 py-1 text-[14px]")}>
      <Icon name={s.icon} size={size === "lg" ? 18 : 15} stroke={2.4} />
      {t(acuity).toUpperCase()}
    </span>
  );
}

const FAC_ICON: Record<Facility, IconName> = {
  cardiac: "heart", stroke: "user", trauma: "alert", burns: "alert", respiratory: "info", obstetric: "users", pediatric: "users", poisoning: "alert", general: "hospital",
};

export function FacilityChip({ facility }: { facility: Facility }) {
  const t = useTranslations("facility");
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-soft px-3 py-1 text-[14px] font-semibold">
      <Icon name={FAC_ICON[facility]} size={15} stroke={2.2} />
      {t(facility)}
    </span>
  );
}

/** Every AI output shows its confidence (UI rule 3). */
export function Confidence({ value, confirmed }: { value: number; confirmed?: boolean }) {
  const t = useTranslations("live");
  if (confirmed) {
    return <span className="inline-flex items-center gap-1 text-[14px] font-semibold text-green"><Icon name="check" size={15} stroke={2.6} />{t("confirmedByCrew")}</span>;
  }
  const p = Math.round(value * 100);
  const tone = p >= 80 ? "text-green" : p >= 60 ? "text-amber" : "text-red-ink";
  return <span className={cn("text-[14px] font-semibold", tone)}>AI · {t("confidence", { p })}</span>;
}

/** Every ETA shows its range (UI rule 3). */
export function EtaRange({ eta, low, high, big }: { eta: number | null | undefined; low?: number | null; high?: number | null; big?: boolean }) {
  const t = useTranslations("common");
  if (eta == null) return null;
  const m = minutes(eta)!;
  const lo = minutes(low ?? eta);
  const hi = minutes(high ?? eta);
  if (eta < 30) return <span className={cn("font-bold", big ? "text-[34px] leading-none" : "text-[18px]")}>{t("arrivingNow")}</span>;
  return (
    <span className="inline-flex flex-wrap items-baseline gap-x-2">
      <b className={cn("font-extrabold tracking-tight", big ? "text-[44px] leading-none" : "text-[19px]")}>{t("min", { n: m })}</b>
      {lo !== hi && <span className={cn(big ? "text-[18px] opacity-85" : "text-[15px] text-muted")}>({t("minRange", { low: lo ?? m, high: hi ?? m })})</span>}
    </span>
  );
}

/** Every hospital number shows how fresh it is (UI rule 3, T32). */
export function FreshnessBadge({ at, freshness }: { at: string | null | undefined; freshness?: Freshness }) {
  const now = useNow(15000);
  const f: Freshness = freshness ?? (!at ? "stale" : (now - new Date(at).getTime()) / 60000 <= 10 ? "fresh" : (now - new Date(at).getTime()) / 60000 <= 30 ? "aging" : "stale");
  const cls = f === "fresh" ? "text-green" : f === "aging" ? "text-amber" : "text-red-ink";
  const dot = f === "fresh" ? "bg-green" : f === "aging" ? "bg-amber" : "bg-red";
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-[13px] font-medium", cls)} title={f}>
      <span className={cn("h-2 w-2 rounded-full", dot)} />
      {at ? `updated ${ago(at, now)}` : "never confirmed"}
      {f === "stale" && ", may be outdated"}
    </span>
  );
}

export function SignalBadge({ signal }: { signal: Signal }) {
  const map = { ok: ["bg-green", "Live", "text-green"], weak: ["bg-amber", "Weak signal", "text-amber"], lost: ["bg-red", "Signal lost", "text-red-ink"] } as const;
  const [dot, label, cls] = map[signal];
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-[13px] font-semibold", cls)}>
      <span className={cn("h-2.5 w-2.5 rounded-full", dot, signal === "ok" && "animate-pulse")} />
      {label}
    </span>
  );
}

export function WhyYou({ reasons }: { reasons: string[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {reasons.map((r) => (
        <span key={r} className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[13px] font-semibold", r.toLowerCase().includes("ago") || r.toLowerCase().includes("stale") ? "bg-amber-soft text-amber" : "bg-green-soft text-green")}>
          <Icon name={r.toLowerCase().includes("ago") ? "clock" : "check"} size={13} stroke={2.6} />
          {r}
        </span>
      ))}
    </div>
  );
}
