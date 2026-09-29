"use client";

import { createContext, useContext } from "react";
import type { HospitalDashboard } from "@/lib/api-types";
import type { WsClient } from "@/lib/ws";

export type HospCtx = {
  dashboard: HospitalDashboard | null;
  loading: boolean;
  error: boolean;
  refetch: () => void;
  ws: WsClient | null;
  alertOn: boolean;
  setAlertOn: (v: boolean) => void;
};
export const HospitalContext = createContext<HospCtx | null>(null);
export function useHosp() {
  const c = useContext(HospitalContext);
  if (!c) throw new Error("useHosp outside hospital layout");
  return c;
}
