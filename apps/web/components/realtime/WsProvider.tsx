"use client";

// React glue for lib/ws.ts: one client per (core, token), shared by every screen.

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { WsClient, type WsStatus } from "@/lib/ws";
import { wsUrl, type Area } from "@/lib/config";
import type { WsEnvelope } from "@/lib/api-types";

type Ctx = { get: (area: Area, token: string) => WsClient | null };
const WsContext = createContext<Ctx | null>(null);

export function WsProvider({ children }: { children: ReactNode }) {
  const clients = useRef(new Map<string, WsClient>());
  useEffect(() => {
    const map = clients.current;
    return () => {
      map.forEach((c) => c.close());
      map.clear();
    };
  }, []);
  const get = (area: Area, token: string) => {
    if (typeof window === "undefined" || !token) return null;
    const url = wsUrl(area);
    const key = `${url}|${token}`;
    let c = clients.current.get(key);
    if (!c) {
      // a new token (refresh) replaces the old socket for that core
      for (const [k, old] of clients.current) {
        if (k.startsWith(`${url}|`)) {
          old.close();
          clients.current.delete(k);
        }
      }
      c = new WsClient(url, token);
      clients.current.set(key, c);
    }
    return c;
  };
  return <WsContext.Provider value={{ get }}>{children}</WsContext.Provider>;
}

export function useWsClient(area: Area, token: string | null | undefined) {
  const ctx = useContext(WsContext);
  const [client, setClient] = useState<WsClient | null>(null);
  useEffect(() => {
    setClient(token && ctx ? ctx.get(area, token) : null);
  }, [ctx, area, token]);
  return client;
}

export function useWsStatus(client: WsClient | null): WsStatus {
  const [s, setS] = useState<WsStatus>(client?.status ?? "closed");
  useEffect(() => {
    if (!client) return;
    setS(client.status);
    const off = client.onStatus(setS);
    return () => {
      off();
    };
  }, [client]);
  return s;
}

/** Subscribe to one channel. `resync` runs on reconnect and on seq gaps. */
export function useChannel(client: WsClient | null, channel: string | null, onEvent: (ev: WsEnvelope) => void, resync?: () => void) {
  const evRef = useRef(onEvent);
  const reRef = useRef(resync);
  useEffect(() => {
    evRef.current = onEvent;
    reRef.current = resync;
  });
  useEffect(() => {
    if (!client || !channel) return;
    return client.subscribe(channel, (ev) => evRef.current(ev), () => reRef.current?.());
  }, [client, channel]);
}
