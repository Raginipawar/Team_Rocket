"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Brand, Call108, LanguageSwitcher, MockRibbon } from "@/components/shell";
import Icon, { type IconName } from "@/components/ui/icon";
import { areaMode } from "@/lib/config";
import { cn } from "@/lib/cn";

function Choice({ href, icon, title, sub, tone = "plain", onClick }: { href?: string; icon: IconName; title: string; sub: string; tone?: "red" | "plain"; onClick?: () => void }) {
  const cls = cn(
    "group flex w-full items-center gap-4 rounded-[28px] p-5 text-left transition active:scale-[0.99]",
    tone === "red" ? "bg-red text-white shadow-[0_18px_40px_-18px_rgba(220,38,38,.7)]" : "border border-line bg-card hover:border-ink/30",
  );
  const inner = (
    <>
      <span className={cn("grid h-16 w-16 shrink-0 place-items-center rounded-full", tone === "red" ? "bg-white/20" : "bg-soft")}>
        <Icon name={icon} size={30} stroke={2} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[21px] font-bold leading-tight">{title}</span>
        <span className={cn("mt-0.5 block text-[16px]", tone === "red" ? "text-white/85" : "text-muted")}>{sub}</span>
      </span>
      <Icon name="chevron" size={24} className="shrink-0 opacity-70" />
    </>
  );
  if (onClick) return <button onClick={onClick} className={cls}>{inner}</button>;
  return <Link href={href!} className={cls}>{inner}</Link>;
}

export default function Home() {
  const t = useTranslations("landing");
  const router = useRouter();
  const [opsNote, setOpsNote] = useState<string | null>(null);

  const openOps = async () => {
    if (areaMode("OPS") === "mock") {
      try {
        const r = await fetch("/core/dev/ops-link");
        const j = (await r.json()) as { path: string };
        router.push(j.path);
        return;
      } catch {
        /* fall through */
      }
    }
    setOpsNote("Open the one-time link from the Telegram alert. Send /ops to the bot for a new link.");
  };

  return (
    <div className="min-h-dvh bg-page">
      <MockRibbon />
      <header className="mx-auto flex max-w-xl items-center justify-between gap-3 px-5 pt-5">
        <Brand />
        <LanguageSwitcher compact />
      </header>
      <main className="mx-auto flex max-w-xl flex-col gap-4 px-5 pb-12 pt-8">
        <h1 className="text-[34px] font-extrabold leading-[1.1] tracking-tight">{t("title")}</h1>
        <p className="text-[18px] text-muted">{t("subtitle")}</p>

        <div className="mt-2 flex flex-col gap-3">
          <Choice href="/patient" icon="phone" title={t("needHelp")} sub={t("needHelpSub")} tone="red" />
          <Call108 />
        </div>

        <div className="mt-6 flex flex-col gap-3">
          <Choice href="/ambulance" icon="ambulance" title={t("crew")} sub={t("crewSub")} />
          <Choice href="/hospital" icon="hospital" title={t("hospital")} sub={t("hospitalSub")} />
          <Choice icon="shield" title={t("team")} sub={t("teamSub")} onClick={openOps} />
          {opsNote && <p className="rounded-2xl bg-soft px-4 py-3 text-[16px]">{opsNote}</p>}
        </div>

        <div className="mt-4 flex items-start gap-3 rounded-[24px] bg-soft p-5">
          <Icon name="sms" size={26} className="mt-0.5 shrink-0" />
          <div>
            <p className="text-[18px] font-bold">{t("family")}</p>
            <p className="text-[16px] text-muted">{t("familySub")}</p>
          </div>
        </div>

        <p className="mt-6 text-center text-[14px] text-muted">{t("mockNote")}</p>
      </main>
    </div>
  );
}
