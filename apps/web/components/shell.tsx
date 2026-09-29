"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/lib/enums";
import { cn } from "@/lib/cn";
import Icon from "@/components/ui/icon";
import { LoadingState } from "@/components/ui/bits";
import { useHealth } from "@/app/providers";
import { anyMock } from "@/lib/config";

const LANGS = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
  { code: "mr", label: "मराठी" },
] as const;

export function LanguageSwitcher({ compact }: { compact?: boolean }) {
  const locale = useLocale();
  const router = useRouter();
  const t = useTranslations("common");
  const set = (code: string) => {
    document.cookie = `NEXT_LOCALE=${code}; path=/; max-age=31536000; samesite=lax`;
    router.refresh();
  };
  return (
    <div role="group" aria-label={t("language")} className={cn("inline-flex rounded-full bg-soft p-1", compact && "scale-95")}>
      {LANGS.map((l) => (
        <button
          key={l.code}
          onClick={() => set(l.code)}
          aria-pressed={locale === l.code}
          className={cn("h-10 rounded-full px-3.5 text-[15px] font-semibold transition", locale === l.code ? "bg-card text-ink shadow-sm" : "text-muted")}
          lang={l.code}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}

/** Always visible on patient screens (UI rule 6). */
export function Call108({ variant = "bar" }: { variant?: "bar" | "button" | "banner" }) {
  const t = useTranslations("common");
  if (variant === "banner") {
    return (
      <a href="tel:108" className="flex items-center justify-center gap-3 rounded-2xl bg-red px-5 py-4 text-[19px] font-bold text-white shadow-lg" role="alert">
        <Icon name="phone" size={24} stroke={2.4} />
        {t("serverDown")}
      </a>
    );
  }
  return (
    <a
      href="tel:108"
      className={cn(
        "flex items-center justify-center gap-2.5 rounded-full font-bold",
        variant === "bar" ? "h-14 w-full border-2 border-red/25 bg-red-soft text-[18px] text-red-ink" : "h-12 bg-red px-5 text-[16px] text-white",
      )}
    >
      <Icon name="phone" size={21} stroke={2.4} />
      {t("call108")}
    </a>
  );
}

/** Connection banners: offline, or core down (then Call 108 becomes a full-width banner). */
export function ConnectionBanners({ patient }: { patient?: boolean }) {
  const { down, online } = useHealth();
  const t = useTranslations("common");
  if (patient && (down || !online)) return <Call108 variant="banner" />;
  if (!online) {
    return (
      <div className="flex items-center gap-2 rounded-2xl bg-amber-soft px-4 py-3 text-[16px] font-semibold text-amber" role="status">
        <Icon name="wifiOff" size={20} />
        {t("offline")}
      </div>
    );
  }
  if (down) {
    return (
      <div className="flex items-center gap-2 rounded-2xl bg-red-soft px-4 py-3 text-[16px] font-semibold text-red-ink" role="alert">
        <Icon name="alert" size={20} />
        Server not reachable. Data may be out of date.
      </div>
    );
  }
  return null;
}

const HOME: Record<Role, string> = { patient: "/patient", paramedic: "/ambulance", hospital_staff: "/hospital", developer: "/" };

/** Role guard: server enforces RBAC too (§18); this only routes people to the right app. */
export function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { session, ready } = useAuth();
  const router = useRouter();
  const path = usePathname();
  const [ok, setOk] = useState(false);
  useEffect(() => {
    if (!ready) return;
    if (!session) {
      router.replace(`/login?role=${role}&next=${encodeURIComponent(path)}`);
      return;
    }
    if (session.user.role !== role) {
      router.replace(HOME[session.user.role] ?? "/");
      return;
    }
    setOk(true);
  }, [ready, session, role, router, path]);
  if (!ok) return <LoadingState />;
  return <>{children}</>;
}

export function MockRibbon() {
  if (!anyMock) return null;
  return (
    <div className="bg-neutral-900 px-4 py-1.5 text-center text-[12px] font-semibold tracking-wide text-white/85">
      Demo data · every hospital, ambulance and person is simulated
    </div>
  );
}

export function Brand({ small }: { small?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-bold tracking-tight", small ? "text-[17px]" : "text-[20px]")}>
      <span className={cn("grid place-items-center rounded-full bg-red text-white", small ? "h-7 w-7" : "h-8 w-8")} aria-hidden>
        <svg width={small ? 14 : 16} height={small ? 14 : 16} viewBox="0 0 24 24"><path d="M12 4v16M4 12h16" stroke="currentColor" strokeWidth="4" strokeLinecap="round" /></svg>
      </span>
      GoldenHour
    </span>
  );
}
