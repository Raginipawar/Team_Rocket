"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { Brand, Call108, LanguageSwitcher, MockRibbon } from "@/components/shell";
import Icon, { type IconName } from "@/components/ui/icon";

function Section({ href, icon, title, sub }: { href: string; icon: IconName; title: string; sub: string }) {
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

export default function Home() {
  const t = useTranslations("landing");

  return (
    <div className="min-h-dvh bg-page">
      <MockRibbon />
      <header className="mx-auto flex max-w-xl items-center justify-between gap-3 px-5 pt-5">
        <Brand />
        <LanguageSwitcher compact />
      </header>
      <main className="mx-auto flex max-w-xl flex-col gap-4 px-5 pb-12 pt-10">
        <h1 className="text-[32px] font-extrabold leading-[1.1] tracking-tight">{t("title")}</h1>
        <p className="text-[17px] text-muted">{t("subtitle")}</p>

        <div className="mt-4 flex flex-col gap-3">
          <Section href="/patient" icon="phone" title={t("sectionPatient")} sub={t("sectionPatientSub")} />
          <Section href="/ambulance" icon="ambulance" title={t("sectionAmbulance")} sub={t("sectionAmbulanceSub")} />
          <Section href="/hospital" icon="hospital" title={t("sectionHospital")} sub={t("sectionHospitalSub")} />
        </div>

        <div className="mt-4"><Call108 /></div>
      </main>
    </div>
  );
}
