"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { buzz } from "@/lib/hooks";
import { cn } from "@/lib/cn";

/** Giant SOS: press and hold 1 second, so a pocket tap never sends it (§16.2). Keyboard: hold Space or Enter. */
export default function SosButton({ onFire, busy }: { onFire: () => void; busy?: boolean }) {
  const t = useTranslations("patient");
  const [p, setP] = useState(0);
  const start = useRef<number | null>(null);
  const raf = useRef(0);
  const fired = useRef(false);

  const tick = () => {
    if (start.current === null) return;
    const k = Math.min(1, (performance.now() - start.current) / 1000);
    setP(k);
    if (k >= 1 && !fired.current) {
      fired.current = true;
      buzz([60, 40, 120]);
      onFire();
      return;
    }
    raf.current = requestAnimationFrame(tick);
  };
  const down = () => {
    if (busy) return;
    fired.current = false;
    start.current = performance.now();
    buzz(25);
    raf.current = requestAnimationFrame(tick);
  };
  const up = () => {
    start.current = null;
    cancelAnimationFrame(raf.current);
    if (!fired.current) setP(0);
  };
  useEffect(() => () => cancelAnimationFrame(raf.current), []);

  const R = 118;
  const C = 2 * Math.PI * R;
  const label = busy ? t("sending") : p > 0 && p < 1 ? t("keepHolding") : t("holdSos");

  return (
    <div className="relative mx-auto grid h-[268px] w-[268px] place-items-center">
      <span className="gh-pulse absolute inset-6 rounded-full bg-red/25" aria-hidden />
      <svg className="absolute inset-0 -rotate-90" viewBox="0 0 268 268" aria-hidden>
        <circle cx="134" cy="134" r={R} fill="none" stroke="var(--red-soft)" strokeWidth="14" />
        <circle cx="134" cy="134" r={R} fill="none" stroke="var(--red)" strokeWidth="14" strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C * (1 - p)} />
      </svg>
      <button
        type="button"
        onPointerDown={down}
        onPointerUp={up}
        onPointerLeave={up}
        onPointerCancel={up}
        onKeyDown={(e) => { if ((e.key === " " || e.key === "Enter") && start.current === null) { e.preventDefault(); down(); } }}
        onKeyUp={(e) => { if (e.key === " " || e.key === "Enter") up(); }}
        onContextMenu={(e) => e.preventDefault()}
        disabled={busy}
        aria-label={`${t("sos")}. ${t("holdSos")}`}
        className={cn(
          "relative grid h-[210px] w-[210px] touch-none select-none place-items-center rounded-full text-white transition",
          "bg-[radial-gradient(circle_at_35%_30%,#f87171,#dc2626_55%,#b91c1c)] shadow-[0_24px_50px_-18px_rgba(220,38,38,.8),inset_0_-8px_20px_rgba(0,0,0,.18)]",
          p > 0 && "scale-[0.97]",
        )}
      >
        <span className="flex flex-col items-center">
          <span className="text-[58px] font-black leading-none tracking-wider">{t("sos")}</span>
          <span className="mt-2 text-[17px] font-semibold text-white/90">{label}</span>
        </span>
      </button>
    </div>
  );
}
