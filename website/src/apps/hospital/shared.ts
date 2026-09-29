import { useEffect, useState } from "react";
import type { RoomStatus } from "../../ui/Bits";
import { useDemoActions } from "../../demo/actions";

export interface Room { code: string; type: string; loc: string; status: RoomStatus; since: number }

const MIN = 60000;
export function initialRooms(now: number): Room[] {
  return [
    { code: "ER-1", type: "ER", loc: "Ground floor, Bay 1", status: "occupied", since: now - 42 * MIN },
    { code: "ER-2", type: "ER", loc: "Ground floor, Bay 2", status: "free", since: now - 12 * MIN },
    { code: "ER-3", type: "ER", loc: "Ground floor, Bay 3", status: "free", since: now - 5 * MIN },
    { code: "ER-4", type: "ER", loc: "Ground floor, Bay 4", status: "cleaning", since: now - 8 * MIN },
    { code: "ER-5", type: "ER", loc: "Ground floor, Bay 5", status: "free", since: now - 30 * MIN },
    { code: "Resus Bay 1", type: "Resus", loc: "Ground floor, Resus", status: "occupied", since: now - 18 * MIN },
    { code: "Resus Bay 2", type: "Resus", loc: "Ground floor, Resus", status: "free", since: now - 55 * MIN },
    { code: "Resus Bay 3", type: "Resus", loc: "Ground floor, Resus", status: "occupied", since: now - 70 * MIN },
    { code: "Trauma 1", type: "Trauma", loc: "Ground floor, Trauma", status: "occupied", since: now - 25 * MIN },
    { code: "Trauma 2", type: "Trauma", loc: "Ground floor, Trauma", status: "out", since: now - 180 * MIN },
    { code: "ICU-4", type: "ICU", loc: "First floor, ICU", status: "free", since: now - 90 * MIN },
    { code: "ICU-5", type: "ICU", loc: "First floor, ICU", status: "free", since: now - 20 * MIN },
    { code: "Labour 1", type: "Labour", loc: "Second floor", status: "free", since: now - 60 * MIN },
    { code: "Burns 1", type: "Burns", loc: "Second floor", status: "occupied", since: now - 240 * MIN },
    { code: "Ped ER 1", type: "Pediatric ER", loc: "Ground floor", status: "free", since: now - 15 * MIN },
  ];
}

/** Distinct hospital alert tone, repeating every 10 s until handled (spec 2.22). */
export function useHospitalTone(active: boolean, enabled: boolean) {
  useEffect(() => {
    if (!active || !enabled) return;
    let ctx: AudioContext | null = null;
    try { ctx = new AudioContext(); } catch { return; }
    const ring = () => {
      if (!ctx) return;
      [0, 0.22, 0.44].forEach((off, i) => {
        const o = ctx!.createOscillator();
        const g = ctx!.createGain();
        o.frequency.value = [660, 880, 660][i];
        g.gain.setValueAtTime(0.07, ctx!.currentTime + off);
        g.gain.exponentialRampToValueAtTime(0.001, ctx!.currentTime + off + 0.2);
        o.connect(g).connect(ctx!.destination);
        o.start(ctx!.currentTime + off);
        o.stop(ctx!.currentTime + off + 0.21);
      });
    };
    ring();
    const id = setInterval(ring, 10000);
    return () => { clearInterval(id); ctx?.close(); };
  }, [active, enabled]);
}

/** Minutes since a timestamp, updating each 15 s. */
export function useMinutesSince(ts: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(id);
  }, []);
  return Math.max(0, Math.floor((now - ts) / 60000));
}

/** Applies the live reservation on top of the stored room list. */
export function useLiveRooms(rooms: Room[]) {
  const { s, d } = useDemoActions();
  const mine = d.hospitalId === "greenfield";
  const reservedActive = mine && d.hospitalAcceptedAt !== null && (d.stage === "transporting" || d.stage === "atDoor");
  const occupiedNow = mine && d.stage === "handedOver";
  return rooms.map((r) => {
    if (r.code !== s.room) return { ...r, detail: undefined as string | undefined };
    if (reservedActive) return { ...r, status: "reserved" as RoomStatus, detail: `MH14 AB 1234 · arriving ${d.stage === "atDoor" ? "now" : `${d.etaMin} min`} · CRITICAL HEART` };
    if (occupiedNow) return { ...r, status: "occupied" as RoomStatus, detail: "Rajesh Kulkarni" };
    return { ...r, detail: undefined };
  });
}

