"use client";

// Bare /ops: used when the ops_session cookie from an earlier one-time link is still
// valid (a reload, or returning to the tab). A fresh escalation still needs a fresh
// one-time link from the Telegram bot, since each link is single-use.

import { useEffect, useState } from "react";
import Link from "next/link";
import { get } from "@/lib/api";
import { Brand } from "@/components/shell";
import { ErrorState, LoadingState } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import OpsTabs from "@/components/ops/OpsTabs";

export default function OpsHomePage() {
  const [state, setState] = useState<"checking" | "ok" | "none">("checking");
  const [userName, setUserName] = useState<string | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);

  useEffect(() => {
    const token = sessionStorage.getItem("gh-ops-session");
    if (!token) {
      setState("none");
      return;
    }
    get("/ops/overview").then(
      () => {
        setSessionToken(token);
        setState("ok");
      },
      () => setState("none"),
    );
    setUserName(null);
  }, []);

  if (state === "checking") return <div className="flex min-h-dvh items-center justify-center"><LoadingState /></div>;
  if (state === "ok" && sessionToken) return <OpsTabs userName={userName} focusEscalationId={null} sessionToken={sessionToken} />;
  return (
    <div className="mx-auto flex min-h-dvh max-w-lg flex-col items-center justify-center gap-4 px-4 text-center">
      <Brand />
      <ErrorState title="No active ops session" text="Send /ops to the GoldenHour Telegram bot for a one-time link." />
      <Button asChild variant="ghost"><Link href="/">Back to GoldenHour</Link></Button>
    </div>
  );
}
