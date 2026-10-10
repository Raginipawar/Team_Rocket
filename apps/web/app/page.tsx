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

function Problem({ icon, title, text }: { icon: IconName; title: string; text: string }) {
  return (
    <div className="flex flex-col gap-2 rounded-[24px] border border-line bg-card p-5">
      <span className="grid h-11 w-11 place-items-center rounded-full bg-red/10 text-red">
        <Icon name={icon} size={22} />
      </span>
      <p className="text-[18px] font-bold leading-tight">{title}</p>
      <p className="text-[15px] text-muted leading-relaxed">{text}</p>
    </div>
  );
}

function Step({ n, title, text }: { n: number; title: string; text: string }) {
  return (
    <div className="flex gap-4">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-ink text-[15px] font-bold text-bg">{n}</span>
      <div>
        <p className="text-[17px] font-bold leading-tight">{title}</p>
        <p className="mt-0.5 text-[15px] text-muted leading-relaxed">{text}</p>
      </div>
    </div>
  );
}

export default function Home() {
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

        {/* The problem */}
        <section className="flex flex-col gap-4">
          <h2 className="text-[22px] font-extrabold">Three things go wrong in the first hour</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <Problem icon="ambulance" title="Disconnected" text="Ambulances and hospitals don't coordinate, so nobody knows which free ambulance is actually closest." />
            <Problem icon="hospital" title="Wrong hospital" text="The nearest hospital is often the wrong one — a cardiac patient at a trauma-only hospital loses minutes being turned away." />
            <Problem icon="bed" title="Not ready" text="The ER finds out about the patient only when the ambulance reaches the door — no bed, doctor or equipment is ready." />
          </div>
        </section>

        {/* How it works */}
        <section className="flex flex-col gap-5">
          <h2 className="text-[22px] font-extrabold">How GoldenHour connects the loop</h2>
          <div className="flex flex-col gap-4">
            <Step n={1} title="Caller sends an SOS" text="Voice note, text, or one button — in Hindi, Marathi or English." />
            <Step n={2} title="AI understands" text="Speech becomes text, facts are extracted, and the case is triaged — acuity and facility type, with a confidence score." />
            <Step n={3} title="Nearest ambulance dispatched" text="The best nearby ambulances get a live offer at once; the first to accept wins." />
            <Step n={4} title="Right hospital matched" text="Ranked by capability, predicted bed availability, traffic-aware ETA and road comfort — not just distance." />
            <Step n={5} title="Hospital is ready" text="A structured handover note, and the bed, specialist and equipment reserved together, before the ambulance arrives." />
            <Step n={6} title="Family stays informed" text="A live tracking link by SMS — location and ETA only, medical details stay private." />
          </div>
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

        <Call108 />

        <footer className="pt-6 text-center text-[14px] text-muted">
          GoldenHour · HackMatrix 5.0 · Track 02 Healthcare · Team Rocket
        </footer>
      </main>
    </div>
  );
}
