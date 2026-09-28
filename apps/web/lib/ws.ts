"use client";

// Single WebSocket client (technical.md §8): channel subscriptions, per-channel seq
// ordering, resync on a gap or reconnect, exponential backoff 1 s to 15 s, keepalive.
// "WS is the live truth and REST is the full truth": on any doubt, handlers refetch.

import type { WsEnvelope } from "./api-types";

type Handler = (ev: WsEnvelope) => void;
type Resync = () => void;
export type WsStatus = "connecting" | "open" | "closed";

export class WsClient {
  private ws: WebSocket | null = null;
  private handlers = new Map<string, Set<Handler>>();
  private resyncs = new Map<string, Set<Resync>>();
  private lastSeq = new Map<string, number>();
  private statusListeners = new Set<(s: WsStatus) => void>();
  private backoff = 1000;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private ping: ReturnType<typeof setInterval> | null = null;
  private stopped = false;
  status: WsStatus = "closed";

  constructor(private url: string, private token: string) {
    this.connect();
  }

  private setStatus(s: WsStatus) {
    this.status = s;
    this.statusListeners.forEach((l) => l(s));
  }

  private connect() {
    if (this.stopped || !this.url || !this.token) return;
    this.setStatus("connecting");
    let ws: WebSocket;
    try {
      ws = new WebSocket(`${this.url}?token=${encodeURIComponent(this.token)}`);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;
    ws.onopen = () => {
      this.backoff = 1000;
      this.setStatus("open");
      for (const ch of this.handlers.keys()) this.send({ op: "subscribe", channel: ch });
      // reconnect: REST resync for everything we follow
      for (const [ch, set] of this.resyncs) {
        this.lastSeq.delete(ch);
        set.forEach((r) => r());
      }
      this.ping = setInterval(() => this.send({ op: "ping" }), 25_000);
    };
    ws.onmessage = (m) => {
      let ev: WsEnvelope;
      try {
        ev = JSON.parse(m.data as string);
      } catch {
        return;
      }
      if (!ev.channel || typeof ev.seq !== "number") return;
      const last = this.lastSeq.get(ev.channel);
      if (last !== undefined && ev.seq <= last) return; // out of order or duplicate
      if (last !== undefined && ev.seq > last + 1) this.resyncs.get(ev.channel)?.forEach((r) => r()); // gap
      this.lastSeq.set(ev.channel, ev.seq);
      this.handlers.get(ev.channel)?.forEach((h) => h(ev));
    };
    ws.onclose = (e) => {
      if (this.ping) clearInterval(this.ping);
      this.ws = null;
      this.setStatus("closed");
      if (e.code === 4401) return; // bad token: the auth layer will sign in again
      this.scheduleReconnect();
    };
    ws.onerror = () => ws.close();
  }

  private scheduleReconnect() {
    if (this.stopped) return;
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.connect(), this.backoff);
    this.backoff = Math.min(15_000, this.backoff * 2);
  }

  private send(msg: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
  }

  subscribe(channel: string, handler: Handler, resync?: Resync) {
    if (!this.handlers.has(channel)) {
      this.handlers.set(channel, new Set());
      this.send({ op: "subscribe", channel });
    }
    this.handlers.get(channel)!.add(handler);
    if (resync) {
      if (!this.resyncs.has(channel)) this.resyncs.set(channel, new Set());
      this.resyncs.get(channel)!.add(resync);
    }
    return () => {
      const set = this.handlers.get(channel);
      set?.delete(handler);
      if (resync) this.resyncs.get(channel)?.delete(resync);
      if (set && set.size === 0) {
        this.handlers.delete(channel);
        this.lastSeq.delete(channel);
        this.send({ op: "unsubscribe", channel });
      }
    };
  }

  heartbeat(data: { lat: number; lng: number; heading?: number; speed_kmh?: number }) {
    this.send({ op: "heartbeat", data });
  }

  onStatus(fn: (s: WsStatus) => void) {
    this.statusListeners.add(fn);
    return () => this.statusListeners.delete(fn);
  }

  close() {
    this.stopped = true;
    if (this.timer) clearTimeout(this.timer);
    if (this.ping) clearInterval(this.ping);
    this.ws?.close();
  }
}
