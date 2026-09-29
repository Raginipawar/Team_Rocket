"use client";

import { createContext, useContext } from "react";
import type { AmbulanceSelf } from "@/lib/api-types";
import type { WsClient } from "@/lib/ws";
import type { DarkPref } from "@/lib/ambulance";

export type AmbCtx = {
  self: AmbulanceSelf | null;
  refetchSelf: () => void;
  ws: WsClient | null;
  dark: boolean;
  darkPref: DarkPref;
  setDarkPref: (p: DarkPref) => void;
  queued: number;
  online: boolean;
};

export const AmbulanceContext = createContext<AmbCtx | null>(null);
export function useAmb() {
  const c = useContext(AmbulanceContext);
  if (!c) throw new Error("useAmb outside ambulance layout");
  return c;
}
