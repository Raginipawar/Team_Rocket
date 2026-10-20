"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { buzz } from "@/lib/hooks";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/lib/enums";
import { cn } from "@/lib/cn";
import Icon from "@/components/ui/icon";
import { LoadingState } from "@/components/ui/bits";
import { useHealth } from "@/app/providers";
import { anyMock } from "@/lib/config";

/** Patient tab pages (Health/Family/History) reached via the bottom nav
 * had no way back to Home except re-tapping that same tab -- no visible
 * affordance at the top like every other sub-page in this app has. One
 * shared header instead of duplicating the same Link+Icon block 3x. */
export function BackHeader({ title, sub, href = "/patient" }: { title: string; sub?: string; href?: string }) {
  const tc = useTranslations("common");
  return (
    <div className="flex items-center gap-3 pt-1">
      <Link href={href} className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-soft" aria-label={tc("back")}>
        <Icon name="back" size={22} />
      </Link>
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[28px] font-extrabold">{title}</h1>
        {sub && <p className="mt-1 text-[17px] text-muted">{sub}</p>}
      </div>
    </div>
  );
}

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

/** Globe icon -> popover with the 3 languages + sign out. LanguageSwitcher's
 * inline pill row ("English हिन्दी मराठी") doesn't fit the patient header's
 * width next to the GoldenHour wordmark -- it just overflows off-screen.
 * A single icon that expands on demand fits any width. */
export function LanguageMenu() {
  const locale = useLocale();
  const router = useRouter();
  const t = useTranslations("common");
  const { signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const set = (code: string) => {
    document.cookie = `NEXT_LOCALE=${code}; path=/; max-age=31536000; samesite=lax`;
    setOpen(false);
    router.refresh();
  };
  return (
    <div className="relative">
      <button type="button" aria-label={t("language")} aria-expanded={open} onClick={() => setOpen((v) => !v)}
        className="grid h-10 w-10 place-items-center rounded-full bg-soft">
        <Icon name="globe" size={20} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
          <div role="menu" className="absolute right-0 top-12 z-50 w-48 rounded-2xl border border-line bg-card p-1.5 shadow-xl">
            {LANGS.map((l) => (
              <button key={l.code} role="menuitemradio" aria-checked={locale === l.code} onClick={() => set(l.code)} lang={l.code}
                className={cn("flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-[16px] font-semibold", locale === l.code ? "bg-soft text-ink" : "text-muted")}>
                {l.label}
                {locale === l.code && <Icon name="check" size={16} />}
              </button>
            ))}
            <div className="my-1 h-px bg-line" />
            <button role="menuitem" onClick={() => void signOut()}
              className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left text-[16px] font-semibold text-red-ink">
              <Icon name="logout" size={18} />
              {t("signOut")}
            </button>
          </div>
        </>
      )}
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

/** Connection banners: offline, reconnecting (a single blip -- quiet, not
 * alarming, covers a Render free-tier cold start), or genuinely down after
 * sustained failure (then Call 108 becomes a full-width banner). */
export function ConnectionBanners({ patient }: { patient?: boolean }) {
  const { down, reconnecting, online } = useHealth();
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
  if (reconnecting) {
    return (
      <div className="flex items-center gap-2 rounded-2xl bg-soft px-4 py-3 text-[15px] font-semibold text-muted" role="status">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden />
        Reconnecting…
      </div>
    );
  }
  return null;
}

const HOME: Record<Role, string> = { patient: "/patient", paramedic: "/ambulance", hospital_staff: "/hospital", developer: "/" };

/** Role guard: server enforces RBAC too (§18); this only routes people to the right app. */
export function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { session, ready, refreshAs } = useAuth();
  const router = useRouter();
  const path = usePathname();
  const [ok, setOk] = useState(false);
  const [triedRestore, setTriedRestore] = useState(false);
  useEffect(() => {
    if (!ready) return;
    if (!session) {
      // sessionStorage can come back empty on a backgrounded mobile tab
      // even though the httpOnly refresh cookie is still valid -- try a
      // silent restore for the role this route actually needs before
      // treating it as a real logout.
      if (!triedRestore) {
        setTriedRestore(true);
        void refreshAs(role).then((token) => {
          if (!token) router.replace(`/login?role=${role}&next=${encodeURIComponent(path)}`);
        });
        return;
      }
      router.replace(`/login?role=${role}&next=${encodeURIComponent(path)}`);
      return;
    }
    if (session.user.role !== role) {
      router.replace(HOME[session.user.role] ?? "/");
      return;
    }
    setOk(true);
  }, [ready, session, role, router, path, triedRestore, refreshAs]);
  if (!ok) return <LoadingState />;
  return <>{children}</>;
}

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:5173";

export function MockRibbon() {
  if (!anyMock) return null;
  return (
    <div className="flex items-center justify-center gap-3 bg-neutral-900 px-4 py-1.5 text-center text-[12px] font-semibold tracking-wide text-white/85">
      <span>Demo data · every hospital, ambulance and person is simulated</span>
      <a href={SITE_URL} className="shrink-0 rounded-full bg-white/15 px-2.5 py-0.5 text-white hover:bg-white/25">
        ← Back to GoldenHour
      </a>
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

/** A distinct sound for the hospital dashboard -- it reused the exact same
 * urgent square-wave beeping the ambulance app uses for crew offers, which
 * sounds identical and tells staff nothing about which screen rang. This is
 * a warm two-note sine chime instead: a front-desk/PA-system notification,
 * not an emergency siren. Does not touch useOfferAlert (ambulance.ts) at all. */
export function useHospitalAlert(ringing: boolean) {
  useEffect(() => {
    if (!ringing) return;
    let ctx: AudioContext | null = null;
    try {
      ctx = new AudioContext();
    } catch {
      return;
    }
    const chime = () => {
      if (!ctx) return;
      [{ t: 0, f: 1046.5 }, { t: 0.22, f: 784 }].forEach(({ t, f }) => {
        const o = ctx!.createOscillator();
        const g = ctx!.createGain();
        o.type = "sine";
        o.frequency.value = f;
        g.gain.setValueAtTime(0.0001, ctx!.currentTime + t);
        g.gain.exponentialRampToValueAtTime(0.22, ctx!.currentTime + t + 0.03);
        g.gain.exponentialRampToValueAtTime(0.0001, ctx!.currentTime + t + 0.5);
        o.connect(g).connect(ctx!.destination);
        o.start(ctx!.currentTime + t);
        o.stop(ctx!.currentTime + t + 0.52);
      });
      buzz([150, 80, 150]);
    };
    chime();
    const id = setInterval(chime, 2200);
    return () => {
      clearInterval(id);
      void ctx?.close();
    };
  }, [ringing]);
}
