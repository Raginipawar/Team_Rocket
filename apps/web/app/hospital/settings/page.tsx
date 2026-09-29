"use client";

import { useAuth } from "@/lib/auth";
import { useHosp } from "../context";
import { Card } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import { LanguageSwitcher } from "@/components/shell";
import { cn } from "@/lib/cn";

export default function SettingsPage() {
  const { dashboard, alertOn, setAlertOn } = useHosp();
  const { session, signOut } = useAuth();
  return (
    <div className="flex max-w-lg flex-col gap-4">
      <h1 className="text-[26px] font-extrabold">Settings</h1>
      <Card>
        <p className="text-[15px] font-bold uppercase tracking-wide text-muted">Signed in as</p>
        <p className="mt-1 text-[18px] font-bold">{session?.user.name ?? "Hospital staff"}</p>
        <p className="text-[16px] text-muted">{dashboard?.hospital.name}</p>
      </Card>
      <Card>
        <label className="flex items-center justify-between gap-3">
          <span>
            <span className="block text-[17px] font-bold">Alert sounds</span>
            <span className="block text-[15px] text-muted">New requests repeat every 10 s until handled</span>
          </span>
          <button role="switch" aria-checked={alertOn} onClick={() => setAlertOn(!alertOn)} className={cn("relative h-8 w-14 shrink-0 rounded-full transition", alertOn ? "bg-green" : "bg-line")}>
            <span className={cn("absolute top-1 h-6 w-6 rounded-full bg-white shadow transition", alertOn ? "left-7" : "left-1")} />
          </button>
        </label>
      </Card>
      <Card>
        <p className="mb-2 text-[17px] font-bold">Language</p>
        <LanguageSwitcher />
      </Card>
      <Button variant="ghost" block onClick={() => void signOut()}><Icon name="logout" size={20} />Sign out</Button>
    </div>
  );
}
