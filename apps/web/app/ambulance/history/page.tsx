"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { ApiError, errorText, get } from "@/lib/api";
import type { AmbulanceHistoryItem } from "@/lib/api-types";
import { dateTime, mmss } from "@/lib/format";
import { AcuityBadge } from "@/components/emergency/badges";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/bits";
import Icon from "@/components/ui/icon";

export default function AmbulanceHistory() {
  const t = useTranslations("amb");
  const ts = useTranslations("status");
  const tf = useTranslations("facility");
  const tc = useTranslations("common");
  const q = useQuery({ queryKey: ["amb-history"], queryFn: () => get<AmbulanceHistoryItem[]>("/ambulance/history"), retry: false });
  return (
    <div className="mx-auto flex max-w-lg flex-col gap-4 px-4 pb-10 pt-4">
      <div className="flex items-center gap-2">
        <Link href="/ambulance" className="grid h-12 w-12 place-items-center rounded-full bg-soft" aria-label={tc("back")}><Icon name="back" size={22} /></Link>
        <h1 className="text-[26px] font-extrabold">{t("history")}</h1>
      </div>
      {q.isLoading ? <LoadingState /> : q.isError ? (
        q.error instanceof ApiError && q.error.status === 404 ? <EmptyState icon="history" title="No past jobs" /> : <ErrorState text={errorText(q.error)} onRetry={() => q.refetch()} />
      ) : !q.data?.length ? <EmptyState icon="history" title="No past jobs yet" /> : (
        <ul className="flex flex-col gap-3">
          {q.data.map((h) => (
            <li key={h.emergency_id} className="rounded-[22px] border border-line bg-card p-4">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[18px] font-bold">{h.facility ? tf(h.facility) : "Emergency"}</p>
                {h.acuity && <AcuityBadge acuity={h.acuity} />}
              </div>
              <p className="mt-1 text-[16px] text-muted">{dateTime(h.at)} · {ts(h.status)}</p>
              {h.hospital_name && <p className="text-[16px]">{h.hospital_name}{h.duration_sec ? ` · ${mmss(h.duration_sec)} total` : ""}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
