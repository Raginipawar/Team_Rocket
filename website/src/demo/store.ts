import { createContext, useContext, useEffect, useState } from "react";
import { derive, initialState, type DemoState, type Derived } from "./engine";

export interface DemoApi {
  s: DemoState;
  update: (patch: Partial<DemoState> | ((s: DemoState) => Partial<DemoState>)) => void;
  reset: () => void;
}

export const DemoContext = createContext<DemoApi>({ s: initialState(), update: () => {}, reset: () => {} });

const KEY = "gh-demo-state";
export const CHANNEL = "gh-demo";

export function loadState(): DemoState {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return { ...initialState(), ...JSON.parse(raw) };
  } catch {
    /* ignore */
  }
  return initialState();
}

export function saveState(s: DemoState) {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* ignore */
  }
}

/** Current time, re-rendering the caller every `ms`. */
export function useNow(ms = 250) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

/** The shared emergency plus its live derived state. */
export function useDemo(): DemoApi & { d: Derived; now: number } {
  const api = useContext(DemoContext);
  const now = useNow();
  return { ...api, d: derive(api.s, now), now };
}
