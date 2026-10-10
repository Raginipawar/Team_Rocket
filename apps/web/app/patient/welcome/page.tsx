"use client";

import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { Brand } from "@/components/shell";
import { Button } from "@/components/ui/button";
import Icon from "@/components/ui/icon";

// First-ever login for a patient used to go straight from OTP to the SOS
// button with zero welcome, zero prompt to fill health details -- found by
// actually watching a first-time login, not by reading the code (the
// profile/contacts/history endpoints all existed and "worked", but nobody
// was ever told they existed). Shown once (app/login/page.tsx sets
// gh-onboarded-<id> after this), then never again.
function WelcomeInner() {
  const { session } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") ?? "/patient";
  const name = session?.user.name?.split(" ")[0];

  const skip = () => {
    try {
      if (session) localStorage.setItem(`gh-onboarded-${session.user.id}`, "1");
    } catch { /* ignore */ }
    router.replace(next);
  };

  const fillDetails = () => {
    try {
      if (session) localStorage.setItem(`gh-onboarded-${session.user.id}`, "1");
    } catch { /* ignore */ }
    router.push(`/patient/profile?next=${encodeURIComponent(next)}`);
  };

  return (
    <div className="min-h-dvh bg-page">
      <header className="mx-auto flex max-w-md items-center px-5 pt-5">
        <Brand small />
      </header>
      <main className="mx-auto flex max-w-md flex-col gap-6 px-5 pb-10 pt-8">
        <div className="flex flex-col items-center gap-3 text-center">
          <span className="grid h-20 w-20 place-items-center rounded-full bg-red-soft text-red">
            <Icon name="heart" size={40} />
          </span>
          <h1 className="text-[28px] font-extrabold leading-tight">
            {name ? `Welcome, ${name}` : "Welcome to GoldenHour"}
          </h1>
          <p className="text-[17px] text-muted">
            You&apos;re all set to call for help anytime, instantly. One more thing makes a real
            difference if you ever need to.
          </p>
        </div>

        <div className="flex flex-col gap-3 rounded-[28px] border border-line bg-card p-5">
          <div className="flex items-center gap-3">
            <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-soft">
              <Icon name="heart" size={22} />
            </span>
            <div>
              <p className="text-[18px] font-bold">Add your health details</p>
              <p className="text-[15px] text-muted">Blood group, allergies, conditions</p>
            </div>
          </div>
          <p className="text-[16px] leading-relaxed text-muted">
            If you&apos;re ever unable to speak, the ambulance crew and hospital see this
            instantly the moment you send an SOS — it can change how fast they treat you.
          </p>
        </div>

        <div className="flex flex-col gap-3 rounded-[28px] border border-line bg-card p-5">
          <div className="flex items-center gap-3">
            <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-soft">
              <Icon name="users" size={22} />
            </span>
            <div>
              <p className="text-[18px] font-bold">Add emergency contacts</p>
              <p className="text-[15px] text-muted">Up to 5 people who should know</p>
            </div>
          </div>
          <p className="text-[16px] leading-relaxed text-muted">
            You can do this later from Settings too — it just takes under a minute now.
          </p>
        </div>

        <div className="mt-2 flex flex-col gap-3">
          <Button size="xl" block onClick={fillDetails}>
            <Icon name="check" size={24} />
            Add my details now
          </Button>
          <Button size="lg" variant="ghost" block onClick={skip}>
            Skip for now, take me to the app
          </Button>
        </div>
      </main>
    </div>
  );
}

export default function WelcomePage() {
  return (
    <Suspense>
      <WelcomeInner />
    </Suspense>
  );
}
