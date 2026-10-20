"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { Brand, Call108, LanguageSwitcher, MockRibbon } from "@/components/shell";
import Icon, { type IconName } from "@/components/ui/icon";

function AppCard({ href, icon, title, sub }: { href: string; icon: IconName; title: string; sub: string }) {
  return (
    <Link href={href} className="group flex w-full items-center gap-4 rounded-[28px] border border-line bg-card p-5 text-left transition active:scale-[0.99] hover:border-ink/30">
      <span className="grid h-16 w-16 shrink-0 place-items-center rounded-full bg-soft">
        <Icon name={icon} size={30} stroke={2} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[21px] font-bold leading-tight">{title}</span>
        <span className="mt-0.5 block text-[16px] text-muted">{sub}</span>
      </span>
      <Icon name="chevron" size={24} className="shrink-0 opacity-70" />
    </Link>
  );
}

export default function AppsPage() {
  const t = useTranslations("landing");

  return (
    <div className="min-h-dvh bg-page">
      <MockRibbon />
      <header className="mx-auto flex max-w-2xl items-center justify-between gap-3 px-5 pt-5">
        <Brand />
        <LanguageSwitcher compact />
      </header>

      <main className="mx-auto flex max-w-2xl flex-col gap-14 px-5 pb-16 pt-10">
        {/* Hero */}
        <section className="flex flex-col gap-4">
          <h1 className="text-[36px] font-extrabold leading-[1.08] tracking-tight">{t("title")}</h1>
          <p className="text-[18px] text-muted leading-relaxed">{t("subtitle")}</p>
          <p className="text-[15px] font-semibold text-red-ink">When anything fails, we fail toward 108 — never toward silence.</p>
        </section>

        {/* Apps */}
        <section className="flex flex-col gap-4">
          <h2 className="text-[22px] font-extrabold">Open the real, working apps</h2>
          <p className="text-[15px] text-muted -mt-2">Everything below is real — a real backend, a real database, real dispatch logic. Nothing here is a scripted demo.</p>
          <div className="flex flex-col gap-3">
            <AppCard href="/patient" icon="phone" title={t("sectionPatient")} sub={t("sectionPatientSub")} />
            <AppCard href="/ambulance" icon="ambulance" title={t("sectionAmbulance")} sub={t("sectionAmbulanceSub")} />
            <AppCard href="/hospital" icon="hospital" title={t("sectionHospital")} sub={t("sectionHospitalSub")} />
          </div>
        </section>

        {/* Addition requirement: multi-patient allocation + forecasting */}
        <section className="flex flex-col gap-4">
          <h2 className="text-[22px] font-extrabold">Allocation &amp; forecasting demo</h2>
          <p className="text-[15px] text-muted -mt-2">A standalone scenario for the batch-allocation and availability-forecasting requirement.</p>
          <AppCard href="/demo/allocation" icon="chart" title="Run patient surge scenario" sub="Batch allocation across hospitals, with replanning and forecast vs baseline comparison" />
        </section>

        <Call108 />

        <footer className="pt-6 text-center text-[14px] text-muted">
          GoldenHour · HackMatrix 5.0 · Track 02 Healthcare · Team Rocket
        </footer>
      </main>
    </div>
  );
}
