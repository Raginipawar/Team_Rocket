"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import type { EmergencyStatus } from "@/lib/enums";
import type { FirstAid, FollowupQuestion, Timeline } from "@/lib/api-types";
import { clock } from "@/lib/format";
import { speak, stopSpeaking } from "@/lib/speech";
import { cn } from "@/lib/cn";
import Icon from "@/components/ui/icon";
import { Button } from "@/components/ui/button";
import { Card, Input, SectionLabel } from "@/components/ui/bits";

const STEPS = ["requested", "coming", "arrived", "toHospital", "atHospital", "handedOver"] as const;
const STEP_OF: Record<EmergencyStatus, number> = {
  received: 0, triaged: 0, dispatching: 0, ambulance_assigned: 1, at_scene: 2, patient_on_board: 3, hospital_selecting: 3,
  hospital_confirmed: 3, arrived_hospital: 4, handed_off: 5, closed: 5, cancelled: -1, refused_transport: -1, merged_duplicate: -1,
};
const STEP_TIME: (keyof Timeline)[] = ["received_at", "assigned_at", "at_scene_at", "on_board_at", "arrived_hospital_at", "handed_off_at"];

/** Status stepper (§16.2): where we are, with the time of each step. */
export function StatusStepper({ status, timeline }: { status: EmergencyStatus; timeline?: Timeline }) {
  const t = useTranslations("live.steps");
  const cur = STEP_OF[status];
  return (
    <ol className="flex flex-col" aria-label="Progress">
      {STEPS.map((s, i) => {
        const done = i < cur || (i === cur && (status === "handed_off" || status === "closed"));
        const now = i === cur && !done;
        const at = timeline?.[STEP_TIME[i]];
        return (
          <li key={s} className="flex items-stretch gap-3" aria-current={now ? "step" : undefined}>
            <div className="flex flex-col items-center">
              <span className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-full border-2",
                done ? "border-ink bg-ink text-bg" : now ? "border-red bg-card" : "border-line bg-soft")}>
                {done ? <Icon name="check" size={16} stroke={3} /> : now ? <span className="h-3 w-3 animate-pulse rounded-full bg-red" /> : null}
              </span>
              {i < STEPS.length - 1 && <span className={cn("w-0.5 flex-1", done ? "bg-ink" : "bg-line")} />}
            </div>
            <div className={cn("flex flex-1 items-start justify-between gap-2 pb-4 pt-1", !done && !now && "text-muted")}>
              <span className={cn("text-[17px]", now ? "font-bold" : "font-medium")}>{t(s)}</span>
              {at && <span className="text-[15px] text-muted">{clock(at)}</span>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function ListenButton({ text, audioUrl }: { text: string | string[]; audioUrl?: string | null }) {
  const locale = useLocale();
  const tc = useTranslations("common");
  const [on, setOn] = useState(false);
  return (
    <Button variant="soft" size="sm" onClick={() => {
      if (on) {
        stopSpeaking();
        setOn(false);
        return;
      }
      setOn(true);
      void speak(text, locale, audioUrl).finally(() => setOn(false));
    }} aria-pressed={on}>
      <Icon name={on ? "stop" : "speaker"} size={18} />
      {on ? tc("stop") : tc("listen")}
    </Button>
  );
}

const CHOICE_LABEL: Record<string, string> = {
  normal: "Normal", difficult: "With difficulty", absent: "Not breathing",
  left_chest: "Left side of chest", center_chest: "Centre of chest", right_chest: "Right side", radiating_arm: "Spreading to the arm", unknown: "Not sure",
};

/** Follow-up question card (§16.2): voice playback + big answer buttons. */
export function FollowupCard({ q, onAnswer, busy }: { q: FollowupQuestion; onAnswer: (a: string) => void; busy?: boolean }) {
  const t = useTranslations("live");
  const tc = useTranslations("common");
  const [free, setFree] = useState("");
  return (
    <Card className="border-2 border-blue/40 bg-blue-soft">
      <div className="flex items-start justify-between gap-3">
        <SectionLabel className="text-blue">{t("question")}</SectionLabel>
        <ListenButton text={q.text} audioUrl={q.audio_url} />
      </div>
      <p className="mt-2 text-[22px] font-bold leading-snug">{q.text}</p>
      <p className="mt-1 text-[15px] text-muted">{t("answerHere")}</p>
      <div className="mt-4 grid gap-2.5">
        {q.answer_type === "yes_no" && (
          <div className="grid grid-cols-3 gap-2.5">
            <Button size="lg" variant="primary" disabled={busy} onClick={() => onAnswer("yes")}>{tc("yes")}</Button>
            <Button size="lg" variant="outline" disabled={busy} onClick={() => onAnswer("no")}>{tc("no")}</Button>
            <Button size="lg" variant="soft" disabled={busy} onClick={() => onAnswer("unknown")}>{tc("notSure")}</Button>
          </div>
        )}
        {q.answer_type === "choice" && (q.choices ?? []).map((c) => (
          <Button key={c} size="lg" variant="outline" block disabled={busy} onClick={() => onAnswer(c)} className="justify-start">{CHOICE_LABEL[c] ?? c.replace(/_/g, " ")}</Button>
        ))}
        {(q.answer_type === "free" || q.answer_type === "number") && (
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (free.trim()) onAnswer(free.trim()); }}>
            <Input value={free} onChange={(e) => setFree(e.target.value)} inputMode={q.answer_type === "number" ? "numeric" : "text"} aria-label={q.text} />
            <Button type="submit" size="lg" disabled={busy || !free.trim()}>{tc("next")}</Button>
          </form>
        )}
      </div>
    </Card>
  );
}

/** First-aid steps with audio (§16.2). Fixed scripts only, never generated text (§9.8). */
export function FirstAidCard({ aid, onCpr }: { aid: FirstAid; onCpr?: () => void }) {
  const t = useTranslations("live");
  const cpr = aid.protocol_id.includes("cpr");
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <SectionLabel>{t("whileYouWait")}</SectionLabel>
        <ListenButton text={[aid.title ?? "", ...aid.steps]} />
      </div>
      {aid.title && <p className="mt-2 text-[20px] font-bold leading-snug">{aid.title.replace(/\s*--\s*/g, ": ")}</p>}
      <ol className="mt-3 flex flex-col gap-3">
        {aid.steps.map((s, i) => (
          <li key={i} className="flex gap-3">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-ink text-[15px] font-bold text-bg">{i + 1}</span>
            <span className="pt-0.5 text-[18px] leading-snug">{s.replace(/\s*--\s*/g, ": ")}</span>
          </li>
        ))}
      </ol>
      {!!aid.donts?.length && (
        <div className="mt-4 rounded-2xl bg-red-soft p-4">
          <p className="flex items-center gap-2 text-[16px] font-bold text-red-ink"><Icon name="x" size={18} stroke={2.6} />{t("dont")}</p>
          <ul className="mt-1.5 flex flex-col gap-1.5 text-[17px]">
            {aid.donts.map((d, i) => <li key={i}>{d}</li>)}
          </ul>
        </div>
      )}
      {onCpr && (
        <Button size="lg" variant={cpr ? "danger" : "outline"} block className="mt-4" onClick={onCpr}>
          <Icon name="heart" size={22} />{t("cpr")}
        </Button>
      )}
    </Card>
  );
}
