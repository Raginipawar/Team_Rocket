"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useHosp } from "../context";
import { patch, post, errorText } from "@/lib/api";
import { Card, Field, Input } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { LanguageSwitcher } from "@/components/shell";
import { cn } from "@/lib/cn";

export default function SettingsPage() {
  const { dashboard, alertOn, setAlertOn, refetch } = useHosp();
  const { session, signOut } = useAuth();
  return (
    <div className="flex max-w-lg flex-col gap-4">
      <h1 className="text-[26px] font-extrabold">Settings</h1>
      <Card>
        <p className="text-[15px] font-bold uppercase tracking-wide text-muted">Signed in as</p>
        <p className="mt-1 text-[18px] font-bold">{session?.user.name ?? "Hospital staff"}</p>
        <p className="text-[16px] text-muted">{dashboard?.hospital.name}</p>
        {dashboard?.hospital.hospital_code && <p className="mt-1 text-[14px] font-semibold text-muted">{dashboard.hospital.hospital_code}</p>}
      </Card>
      <DataIntegrationCard dashboard={dashboard} onSaved={refetch} />
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

function DataIntegrationCard({ dashboard, onSaved }: { dashboard: ReturnType<typeof useHosp>["dashboard"]; onSaved: () => void }) {
  const toast = useToast();
  const h = dashboard?.hospital;
  const [mode, setMode] = useState<"manual" | "api">(h?.integration_mode ?? "manual");
  const [endpoint, setEndpoint] = useState(h?.integration_endpoint_url ?? "");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const save = async () => {
    setErr(null);
    if (mode === "api" && !endpoint.trim() && !h?.integration_endpoint_url) {
      setErr("Enter your API endpoint URL to enable API integration.");
      return;
    }
    setBusy(true);
    try {
      await patch("/hospital/integration", { integration_mode: mode, endpoint_url: endpoint.trim() || null, api_key: apiKey.trim() || undefined });
      setApiKey("");
      toast("Integration settings saved", "success");
      onSaved();
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const syncNow = async () => {
    setErr(null);
    setBusy(true);
    try {
      const r = await post<{ updated: string[]; skipped: unknown[] }>("/hospital/integration/sync");
      toast(r.skipped.length ? `Synced ${r.updated.length} resource type(s), ${r.skipped.length} unrecognised` : `Synced ${r.updated.length} resource type(s)`, "success");
      onSaved();
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      await post("/hospital/integration/disconnect");
      setMode("manual");
      setEndpoint("");
      setApiKey("");
      toast("Disconnected -- back to manual dashboard updates", "success");
      onSaved();
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="flex flex-col gap-3">
      <p className="text-[17px] font-bold">Data integration</p>
      <p className="text-[15px] text-muted -mt-1">Update capacity yourself in-app, or connect your own hospital system. Only the fields below are shared -- never direct database access.</p>

      <div className="grid grid-cols-2 gap-2">
        <button type="button" onClick={() => setMode("manual")}
          className={cn("rounded-2xl border-2 p-3 text-left", mode === "manual" ? "border-ink" : "border-line")}>
          <p className="text-[16px] font-bold">Manual dashboard</p>
          <p className="text-[13px] text-muted">Default -- works right now</p>
        </button>
        <button type="button" onClick={() => setMode("api")}
          className={cn("rounded-2xl border-2 p-3 text-left", mode === "api" ? "border-ink" : "border-line")}>
          <p className="text-[16px] font-bold">API integration</p>
          <p className="text-[13px] text-muted">{h?.integration_mode === "api" ? "Connected" : "Not configured"}</p>
        </button>
      </div>

      {mode === "api" && (
        <div className="flex flex-col gap-3 rounded-2xl bg-soft p-3">
          <Field label="API endpoint URL" htmlFor="endpoint">
            <Input id="endpoint" value={endpoint} onChange={(e) => setEndpoint(e.target.value)} placeholder="https://your-his.example.com/api/capacity" />
          </Field>
          <Field label="API key" htmlFor="apikey" hint={h?.integration_api_key_set ? "A key is already saved -- leave blank to keep it." : "Required to enable the connection."}>
            <Input id="apikey" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={h?.integration_api_key_set ? "••••••••" : ""} />
          </Field>
          {h?.integration_last_synced_at ? (
            <p className="text-[14px] text-muted">Last synced: {new Date(h.integration_last_synced_at).toLocaleString()}</p>
          ) : h?.integration_mode === "api" ? (
            <p className="text-[14px] text-amber">Connected, but no sync has happened yet.</p>
          ) : null}
          {h?.integration_mode === "api" && (
            <Button size="md" variant="outline" loading={busy} onClick={() => void syncNow()}>Sync now</Button>
          )}
        </div>
      )}

      {err && <p className="text-[15px] font-semibold text-red-ink">{err}</p>}
      <div className="flex gap-2">
        <Button size="lg" block loading={busy} onClick={() => void save()}>Save</Button>
        {h?.integration_mode === "api" && <Button size="lg" variant="outline" loading={busy} onClick={() => void disconnect()}>Disconnect</Button>}
      </div>
    </Card>
  );
}
