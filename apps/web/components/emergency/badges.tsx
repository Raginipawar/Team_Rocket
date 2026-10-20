"use client";

import { useTranslations } from "next-intl";
import { useRef } from "react";
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
export function AcuityBadge({ acuity, size = "md" }: { acuity: Acuity | null | undefined; size?: "md" | "lg" }) {
  const t = useTranslations("acuity");
  // An emergency whose triage background task hasn't finished yet (or
  // failed) has acuity=null -- ACUITY_STYLE[null] was undefined, and
  // `.cls` on that crashed the whole page (history list, request cards,
  // anywhere this renders), not just this one badge.
  const s = (acuity && ACUITY_STYLE[acuity]) || { cls: "bg-soft text-muted", icon: "clock" as const };
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full font-bold", s.cls, size === "lg" ? "px-4 py-1.5 text-[17px]" : "px-3 py-1 text-[14px]")}>
      <Icon name={s.icon} size={size === "lg" ? 18 : 15} stroke={2.4} />
      {acuity ? t(acuity).toUpperCase() : "PENDING"}
    </span>
  );
}

const FAC_ICON: Record<Facility, IconName> = {
  cardiac: "heart", stroke: "user", trauma: "alert", burns: "alert", respiratory: "info", obstetric: "users", pediatric: "users", poisoning: "alert", general: "hospital",
};

export function FacilityChip({ facility }: { facility: Facility | null | undefined }) {
  const t = useTranslations("facility");
  if (!facility) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-soft px-3 py-1 text-[14px] font-semibold text-muted">
        <Icon name="clock" size={15} stroke={2.2} />
        Pending
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-soft px-3 py-1 text-[14px] font-semibold">
      <Icon name={FAC_ICON[facility]} size={15} stroke={2.2} />
      {t(facility)}
    </span>
  );
}

// Triage can take a while (the ML service runs real models, not a mock) and
// has no server-side timestamp the client can diff against here, so this
// times from when the caller first saw confidence=0 -- an honest "how long
// you personally have been waiting", not a fake/exact ETA. Past ~25s the
// label changes: triage's own real-call timeout is well past typical, so a
// long wait at that point usually means the fallback already landed
// (confidence stuck at 0, no further update coming) rather than "still
// thinking" -- telling the crew that instead of counting forever gives them
// the "this isn't coming, confirm manually" signal they actually need.
function WaitingConfidence() {
  const startRef = useRef<number | null>(null);
  if (startRef.current === null) startRef.current = Date.now();
  const now = useNow(1000);
  const elapsedS = Math.floor((now - startRef.current) / 1000);
  const slow = elapsedS >= 25;
  return (
    <span className={cn("inline-flex items-center gap-1 text-[14px] font-semibold", slow ? "text-amber" : "text-muted")}>
      <Icon name="clock" size={15} stroke={2.4} />
      {slow ? `Taking longer than usual (${elapsedS}s) — you can confirm details yourself` : `Details coming — usually ready in ~20s (${elapsedS}s)`}
    </span>
  );
}

/** Every AI output shows its confidence (UI rule 3). */
export function Confidence({ value, confirmed }: { value: number; confirmed?: boolean }) {
  const t = useTranslations("live");
  if (confirmed) {
    return <span className="inline-flex items-center gap-1 text-[14px] font-semibold text-green"><Icon name="check" size={15} stroke={2.6} />{t("confirmedByCrew")}</span>;
  }
  // A real AI result is never exactly 0% confident -- that's the
  // MLUnavailable fallback shape (confidence hardcoded to 0.0) or triage
  // genuinely hasn't run yet, not a real "I'm 0% sure" result. Showing it
  // as a confidence number reads as the AI having failed outright, when
  // it just hasn't produced a result to show confidence about yet.
  if (!value) {
    return <WaitingConfidence />;
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
      {reasons.map((raw, i) => {
        const r = typeof raw === "string" ? raw : String(raw ?? "");
        return (
          <span key={i} className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[13px] font-semibold", r.toLowerCase().includes("ago") || r.toLowerCase().includes("stale") ? "bg-amber-soft text-amber" : "bg-green-soft text-green")}>
            <Icon name={r.toLowerCase().includes("ago") ? "clock" : "check"} size={13} stroke={2.6} />
            {r}
          </span>
        );
      })}
    </div>
  );
}
