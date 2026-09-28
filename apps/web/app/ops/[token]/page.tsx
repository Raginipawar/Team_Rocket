"use client";

// Ops page (technical.md §7.7, §16.6): one-time link exchange for a session cookie,
// then three tabs. Opened from the Telegram escalation alert on a phone or laptop.

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { post } from "@/lib/api";
import { Brand, LanguageSwitcher } from "@/components/shell";
import { ErrorState, LoadingState } from "@/components/ui/bits";
import OpsTabs from "@/components/ops/OpsTabs";

export default function OpsTokenPage() {
  const { token } = useParams<{ token: string }>();
  const [state, setState] = useState<"exchanging" | "ok" | "error">("exchanging");
  const [userName, setUserName] = useState<string | null>(null);
  const [escalationId, setEscalationId] = useState<string | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await post<{ status: string; user: { name?: string | null }; escalation_id?: string | null; session_token?: string }>("/ops/session", { token }, { auth: false });
        if (cancelled) return;
        setUserName(r.user?.name ?? null);
        setEscalationId(r.escalation_id ?? null);
        setSessionToken(r.session_token ?? null);
        try {
          sessionStorage.setItem("gh-ops-session", r.session_token ?? "");
        } catch {
          /* ignore */
        }
        setState("ok");
      } catch {
        if (!cancelled) setState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (state === "exchanging") {
    return (
      <div className="mx-auto flex min-h-dvh max-w-lg flex-col items-center justify-center gap-4 px-4">
        <Brand />
        <LoadingState text="Opening your link" />
      </div>
    );
  }
  if (state === "error") {
    return (
      <div className="mx-auto flex min-h-dvh max-w-lg flex-col items-center justify-center gap-4 px-4">
        <Brand />
        <ErrorState title="This link is not valid" text="Links expire after 15 minutes and can only be used once. Send /ops to the bot for a new one." />
      </div>
    );
  }
  return <OpsTabs userName={userName} focusEscalationId={escalationId} sessionToken={sessionToken} />;
}
