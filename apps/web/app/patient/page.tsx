"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { api, errorText, get } from "@/lib/api";
import type { CreateEmergencyResponse } from "@/lib/api-types";
import { useGeolocation } from "@/lib/hooks";
import { isFinal, lastEmergency, rememberEmergency } from "@/lib/patient";
import type { EmergencyStatus } from "@/lib/enums";
import SosButton from "@/components/sos/SosButton";
import VoiceRecorder from "@/components/sos/VoiceRecorder";
import LocationIndicator from "@/components/sos/LocationIndicator";
import { LanguageSwitcher } from "@/components/shell";
import { Sheet } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/bits";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/cn";

type Mine = { id: string; status: EmergencyStatus }[];

export default function PatientHome() {
  const t = useTranslations("patient");
  const locale = useLocale();
  const { session } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const geo = useGeolocation(true);
  const [forSelf, setForSelf] = useState(true);
  const [landmark, setLandmark] = useState("");
  const [busy, setBusy] = useState(false);
  const [sheet, setSheet] = useState<"voice" | "text" | null>(null);
  const [text, setText] = useState("");
  const [live, setLive] = useState<string | null>(null);

  // an emergency still in progress gets a banner at the top
  const mine = useQuery({ queryKey: ["my-emergencies"], queryFn: () => get<Mine>("/me/emergencies"), retry: false });
  useEffect(() => {
    const active = mine.data?.find((e) => !isFinal(e.status));
    if (active) setLive(active.id);
    else if (mine.isError) setLive(lastEmergency()?.id ?? null);
    else setLive(null);
  }, [mine.data, mine.isError]);

  const name = session?.user.name?.split(" ")[0];

  const send = async (channel: "app_button" | "app_voice" | "app_text", extra: { text?: string; audio?: Blob } = {}) => {
    setBusy(true);
    const form = new FormData();
    form.set("channel", channel);
    const words = [extra.text?.trim(), landmark.trim() ? `Near ${landmark.trim()}` : ""].filter(Boolean).join(". ");
    if (words) form.set("text", words);
    if (extra.audio) form.set("audio", extra.audio, `sos.${extra.audio.type.includes("ogg") ? "ogg" : extra.audio.type.includes("mp4") ? "m4a" : "webm"}`);
    if (geo.pos) {
      form.set("lat", String(geo.pos.lat));
      form.set("lng", String(geo.pos.lng));
      form.set("accuracy_m", String(geo.pos.accuracy));
    }
    form.set("for_self", String(forSelf));
    form.set("language", locale);
    if (session?.user.phone) form.set("caller_phone", session.user.phone); // the real core on main reads the caller from this field
    try {
      const r = await api<CreateEmergencyResponse>("/emergencies", { method: "POST", form });
      rememberEmergency(r.emergency_id, r.family_track_url);
      router.push(`/patient/emergency/${r.emergency_id}`);
    } catch (e) {
      setBusy(false);
      toast(`${t("sendFailed")} ${errorText(e)}`, "error");
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3 pt-2">
        <h1 className="text-[28px] font-extrabold tracking-tight">{name ? t("hi", { name }) : t("hiNoName")}</h1>
        <LanguageSwitcher compact />
      </div>

      {live && (
        <Link href={`/patient/emergency/${live}`} className="flex items-center gap-3 rounded-[22px] bg-red px-5 py-4 text-white shadow-lg">
          <span className="relative flex h-3.5 w-3.5"><span className="gh-pulse absolute inset-0 rounded-full bg-white" /><span className="relative h-3.5 w-3.5 rounded-full bg-white" /></span>
          <span className="flex-1 text-[18px] font-bold">{t("liveBanner")}</span>
          <span className="text-[16px] font-semibold underline">{t("open")}</span>
        </Link>
      )}

      <section aria-labelledby="who">
        <p id="who" className="mb-2 text-[19px] font-bold">{t("whoNeedsHelp")}</p>
        <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-labelledby="who">
          {[true, false].map((self) => (
            <button key={String(self)} role="radio" aria-checked={forSelf === self} onClick={() => setForSelf(self)}
              className={cn("flex h-16 items-center justify-center gap-2 rounded-[20px] border-2 text-[19px] font-bold transition",
                forSelf === self ? "border-ink bg-ink text-bg" : "border-line bg-card text-ink")}>
              <Icon name={self ? "user" : "users"} size={22} />
              {self ? t("me") : t("someoneElse")}
            </button>
          ))}
        </div>
        <p className="mt-2 text-[16px] text-muted">{forSelf ? t("meHint") : t("otherHint")}</p>
      </section>

      <SosButton busy={busy} onFire={() => void send("app_button")} />

      <section>
        <p className="mb-2 text-center text-[17px] font-semibold text-muted">{t("orDescribe")}</p>
        <div className="grid grid-cols-2 gap-3">
          <button onClick={() => setSheet("voice")} className="flex flex-col items-start gap-2 rounded-[22px] bg-soft p-4 text-left">
            <span className="grid h-12 w-12 place-items-center rounded-full bg-card"><Icon name="mic" size={24} /></span>
            <span className="text-[19px] font-bold">{t("speak")}</span>
            <span className="text-[15px] text-muted">{t("speakSub")}</span>
          </button>
          <button onClick={() => setSheet("text")} className="flex flex-col items-start gap-2 rounded-[22px] bg-soft p-4 text-left">
            <span className="grid h-12 w-12 place-items-center rounded-full bg-card"><Icon name="keyboard" size={24} /></span>
            <span className="text-[19px] font-bold">{t("type")}</span>
            <span className="text-[15px] text-muted">{t("typeSub")}</span>
          </button>
        </div>
      </section>

      <LocationIndicator geo={geo} landmark={landmark} onLandmark={setLandmark} />

      <Sheet open={sheet === "voice"} onOpenChange={(o) => setSheet(o ? "voice" : null)} title={t("speakTitle")}>
        <VoiceRecorder busy={busy} onDone={(audio, transcript) => void send("app_voice", { audio, text: transcript })} />
      </Sheet>

      <Sheet open={sheet === "text"} onOpenChange={(o) => setSheet(o ? "text" : null)} title={t("typeTitle")}
        footer={<Button size="lg" variant="danger" block loading={busy} disabled={text.trim().length < 3} onClick={() => void send("app_text", { text })}>{t("send")}</Button>}>
        <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={t("typePlaceholder")} maxLength={1000} autoFocus aria-label={t("typeTitle")} />
      </Sheet>
    </div>
  );
}
