"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { ApiError, errorText, get } from "@/lib/api";
import type { Acuity, EmergencyStatus, Facility } from "@/lib/enums";
import { dateTime } from "@/lib/format";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/bits";
import { AcuityBadge } from "@/components/emergency/badges";
import Icon from "@/components/ui/icon";

type Item = { id: string; status: EmergencyStatus; received_at: string; acuity: Acuity; facility: Facility; hospital_name: string | null; for_self: boolean };

export default function HistoryPage() {
  const t = useTranslations("patient");
  const ts = useTranslations("status");
  const tf = useTranslations("facility");
  const q = useQuery({ queryKey: ["my-emergencies"], queryFn: () => get<Item[]>("/me/emergencies"), retry: false });
  return (
    <div className="flex flex-col gap-5 pt-2">
      <h1 className="text-[28px] font-extrabold">{t("historyTitle")}</h1>
      {q.isLoading ? <LoadingState /> : q.isError ? (
        q.error instanceof ApiError && q.error.status === 404 ? <EmptyState icon="history" title={t("noHistory")} /> : <ErrorState text={errorText(q.error)} onRetry={() => q.refetch()} />
      ) : !q.data?.length ? <EmptyState icon="history" title={t("noHistory")} /> : (
        <ul className="flex flex-col gap-3">
          {q.data.map((e) => (
            <li key={e.id}>
              <Link href={`/patient/emergency/${e.id}`} className="flex items-center gap-3 rounded-[22px] border border-line bg-card p-4">
                <div className="min-w-0 flex-1">
                  <p className="text-[18px] font-bold">{tf(e.facility)} · {ts(e.status)}</p>
                  <p className="text-[15px] text-muted">{dateTime(e.received_at)}{e.hospital_name ? ` · ${e.hospital_name}` : ""}</p>
                </div>
                <AcuityBadge acuity={e.acuity} />
                <Icon name="chevron" size={20} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
