"use client";

import { useTranslations } from "next-intl";
import type { GeoState } from "@/lib/hooks";
import Icon from "@/components/ui/icon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/bits";
import { cn } from "@/lib/cn";

/** Location + accuracy (§16.2); asks for a landmark when GPS is weak (T16). */
export default function LocationIndicator({ geo, landmark, onLandmark }: { geo: GeoState & { request: () => void }; landmark: string; onLandmark: (s: string) => void }) {
  const t = useTranslations("patient");
  const acc = geo.pos?.accuracy ?? null;
  const good = acc !== null && acc <= 100;
  const weak = acc !== null && acc > 100;
  return (
    <div className="rounded-[24px] border border-line bg-card p-4">
      <div className="flex items-center gap-3">
        <span className={cn("grid h-12 w-12 shrink-0 place-items-center rounded-full", good ? "bg-green-soft text-green" : weak ? "bg-amber-soft text-amber" : "bg-soft text-muted")}>
          <Icon name="pin" size={24} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[17px] font-bold">{t("location")}</p>
          <p className={cn("text-[15px] font-medium", good ? "text-green" : weak ? "text-amber" : "text-muted")}>
            {good ? t("locationAccurate", { m: acc }) : weak ? t("locationWeak", { m: acc }) : geo.status === "asking" ? "…" : t("locationOff")}
          </p>
        </div>
        {(geo.status === "denied" || geo.status === "unavailable" || geo.status === "idle") && (
          <Button size="sm" variant="soft" onClick={geo.request}>{t("locationAsk")}</Button>
        )}
      </div>
      {!good && (
        <div className="mt-3">
          <label htmlFor="landmark" className="text-[15px] font-semibold">{t("landmark")}</label>
          <Input id="landmark" className="mt-1.5" value={landmark} onChange={(e) => onLandmark(e.target.value)} placeholder={t("landmarkHint")} />
        </div>
      )}
    </div>
  );
}
