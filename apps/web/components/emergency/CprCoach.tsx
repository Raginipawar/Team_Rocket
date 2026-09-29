"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { speak, stopSpeaking } from "@/lib/speech";
import Icon from "@/components/ui/icon";
import { Button } from "@/components/ui/button";
import { buzz } from "@/lib/hooks";
import { cn } from "@/lib/cn";

/** Full screen hands-only CPR coach: 110 beats per minute with sound and vibration. */
export default function CprCoach({ onClose, etaText }: { onClose: () => void; etaText?: string | null }) {
  const t = useTranslations("cpr");
  const tc = useTranslations("common");
  const locale = useLocale();
  const [on, setOn] = useState(false);
  const [count, setCount] = useState(0);
  const [beat, setBeat] = useState(false);
  const ctx = useRef<AudioContext | null>(null);

  useEffect(() => {
    if (!on) return;
    ctx.current ??= new AudioContext();
    const ac = ctx.current;
    const id = setInterval(() => {
      const o = ac.createOscillator();
      const g = ac.createGain();
      o.frequency.value = 880;
      g.gain.setValueAtTime(0.35, ac.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.08);
      o.connect(g).connect(ac.destination);
      o.start();
      o.stop(ac.currentTime + 0.09);
      buzz(30);
      setBeat(true);
      setTimeout(() => setBeat(false), 120);
      setCount((c) => c + 1);
    }, 60000 / 110);
    return () => clearInterval(id);
  }, [on]);

  useEffect(() => () => {
    stopSpeaking();
    void ctx.current?.close();
  }, []);

  const steps = t.raw("steps") as string[];

  return (
    <div className="fixed inset-0 z-[95] flex flex-col bg-neutral-950 text-white" role="dialog" aria-modal="true" aria-label={t("title")}>
      <div className="flex items-center justify-between px-5 pt-5">
        <h2 className="text-[24px] font-extrabold">{t("title")}</h2>
        <button onClick={onClose} className="grid h-12 w-12 place-items-center rounded-full bg-white/10" aria-label={tc("close")}><Icon name="x" size={24} /></button>
      </div>
      {etaText && <p className="mx-5 mt-3 inline-flex w-fit rounded-full bg-white/10 px-4 py-1.5 text-[16px] font-semibold">{etaText}</p>}
      <div className="flex flex-1 flex-col items-center justify-center gap-5 px-5">
        <button
          onClick={() => {
            const next = !on;
            setOn(next);
            if (next) void speak(t("rhythm"), locale);
          }}
          className={cn("grid h-64 w-64 place-items-center rounded-full bg-red text-center transition-transform", beat && "scale-95")}
          aria-pressed={on}
        >
          <span>
            <span className="block text-[30px] font-black">{on ? t("rhythm") : t("tap")}</span>
            <span className="mt-1 block text-[18px] text-white/85">110 / min</span>
          </span>
        </button>
        <p className="text-[22px] font-bold" aria-live="polite">{t("count", { n: count })}</p>
      </div>
      <ol className="flex flex-col gap-2.5 px-6 pb-4">
        {steps.map((s, i) => <li key={i} className="flex gap-3 text-[18px]"><b className="w-6 shrink-0 text-white/60">{i + 1}.</b>{s}</li>)}
      </ol>
      <div className="grid grid-cols-2 gap-3 px-5 pb-[max(env(safe-area-inset-bottom),20px)]">
        <Button size="lg" variant="soft" className="bg-white/10 text-white" onClick={() => void speak(steps, locale)}><Icon name="speaker" size={20} />{tc("listen")}</Button>
        <a href="tel:108" className="flex h-[60px] items-center justify-center gap-2 rounded-full bg-red text-[19px] font-bold"><Icon name="phone" size={22} />{tc("call108")}</a>
      </div>
    </div>
  );
}
