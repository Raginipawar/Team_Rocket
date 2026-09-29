// Ambulance crew session + preferences for the demo.
import { useEffect, useState } from "react";

const KEY = "gh-crew";

export interface CrewPrefs {
  loggedIn: boolean;
  checked: boolean;
  dark: "auto" | "on" | "off";
  sounds: boolean;
  landscape: boolean;
}

const DEFAULTS: CrewPrefs = { loggedIn: false, checked: false, dark: "auto", sounds: true, landscape: false };

function read(): CrewPrefs {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || "{}") };
  } catch {
    return DEFAULTS;
  }
}

export function useCrew() {
  const [prefs, setPrefs] = useState<CrewPrefs>(read);
  useEffect(() => {
    try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch { /* ignore */ }
  }, [prefs]);
  const set = (p: Partial<CrewPrefs>) => setPrefs((cur) => ({ ...cur, ...p }));
  const hour = new Date().getHours();
  const isDark = prefs.dark === "on" || (prefs.dark === "auto" && (hour >= 19 || hour < 7));
  return { prefs, set, isDark };
}

/** Loud repeating alert tone while a request is waiting (spec 2.22). */
export function useAlertTone(active: boolean, enabled: boolean) {
  useEffect(() => {
    if (!active || !enabled) return;
    let ctx: AudioContext | null = null;
    try { ctx = new AudioContext(); } catch { return; }
    const ring = () => {
      if (!ctx) return;
      [0, 0.18].forEach((off, i) => {
        const o = ctx!.createOscillator();
        const g = ctx!.createGain();
        o.type = "square";
        o.frequency.value = i ? 988 : 784;
        g.gain.setValueAtTime(0.08, ctx!.currentTime + off);
        g.gain.exponentialRampToValueAtTime(0.001, ctx!.currentTime + off + 0.16);
        o.connect(g).connect(ctx!.destination);
        o.start(ctx!.currentTime + off);
        o.stop(ctx!.currentTime + off + 0.17);
      });
      try { navigator.vibrate?.([400, 200, 400]); } catch { /* ignore */ }
    };
    ring();
    const id = setInterval(ring, 1500);
    return () => { clearInterval(id); ctx?.close(); };
  }, [active, enabled]);
}
