"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { Call108, ConnectionBanners, MockRibbon, RequireRole } from "@/components/shell";
import Icon, { type IconName } from "@/components/ui/icon";
import { cn } from "@/lib/cn";

function Tab({ href, icon, label }: { href: string; icon: IconName; label: string }) {
  const path = usePathname();
  const active = href === "/patient" ? path === "/patient" : path.startsWith(href);
  return (
    <Link href={href} aria-current={active ? "page" : undefined} className={cn("flex flex-1 flex-col items-center gap-1 py-2.5 text-[14px] font-semibold", active ? "text-ink" : "text-muted")}>
      <Icon name={icon} size={25} stroke={active ? 2.3 : 1.9} />
      {label}
    </Link>
  );
}

export default function PatientLayout({ children }: { children: ReactNode }) {
  const t = useTranslations("patient");
  const path = usePathname();
  const live = path.startsWith("/patient/emergency/");
  return (
    <RequireRole role="patient">
      <div className="mx-auto flex min-h-dvh max-w-[520px] flex-col bg-bg sm:my-4 sm:min-h-[calc(100dvh-2rem)] sm:rounded-[36px] sm:border sm:border-line sm:shadow-[0_30px_60px_-30px_rgba(0,0,0,.25)]">
        <MockRibbon />
        <div className="px-4 pt-3"><ConnectionBanners patient /></div>
        <main className="flex-1 px-4 pb-4 pt-2">{children}</main>
        <div className="sticky bottom-0 border-t border-line bg-bg/95 px-4 pb-[max(env(safe-area-inset-bottom),8px)] pt-3 backdrop-blur sm:rounded-b-[36px]">
          <Call108 />
          {!live && (
            <nav className="mt-1 flex" aria-label="Patient">
              <Tab href="/patient" icon="home" label={t("navHome")} />
              <Tab href="/patient/profile" icon="heart" label={t("navProfile")} />
              <Tab href="/patient/contacts" icon="users" label={t("navContacts")} />
              <Tab href="/patient/history" icon="history" label={t("navHistory")} />
            </nav>
          )}
        </div>
      </div>
    </RequireRole>
  );
}
