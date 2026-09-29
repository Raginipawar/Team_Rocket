import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { initialState, type DemoState } from "./engine";
import { CHANNEL, DemoContext, loadState, saveState } from "./store";

/** Holds the demo emergency and keeps it in sync across every open tab. */
export default function DemoProvider({ children }: { children: ReactNode }) {
  const [s, setS] = useState<DemoState>(loadState);
  const channel = useRef<BroadcastChannel | null>(null);

  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return;
    const bc = new BroadcastChannel(CHANNEL);
    channel.current = bc;
    bc.onmessage = (e: MessageEvent<DemoState>) => {
      setS((cur) => (e.data && e.data.v > cur.v ? e.data : cur));
    };
    return () => bc.close();
  }, []);

  const publish = useCallback((next: DemoState) => {
    saveState(next);
    channel.current?.postMessage(next);
  }, []);

  const update = useCallback(
    (patch: Partial<DemoState> | ((s: DemoState) => Partial<DemoState>)) => {
      setS((cur) => {
        const p = typeof patch === "function" ? patch(cur) : patch;
        const next = { ...cur, ...p, v: Math.max(cur.v, Date.now()) + 1 };
        publish(next);
        return next;
      });
    },
    [publish]
  );

  const reset = useCallback(() => {
    setS((cur) => {
      const next = { ...initialState(), autoplay: cur.autoplay, online: cur.online, v: Math.max(cur.v, Date.now()) + 1 };
      publish(next);
      return next;
    });
  }, [publish]);

  const value = useMemo(() => ({ s, update, reset }), [s, update, reset]);
  return <DemoContext.Provider value={value}>{children}</DemoContext.Provider>;
}
