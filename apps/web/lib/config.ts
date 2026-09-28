// Runtime config for the browser. API calls always go to this origin (/api/v1, proxied
// by next.config.ts). The WebSocket connects straight to the core that serves the area.

export type Area = "AUTH" | "ME" | "EMERGENCIES" | "AMBULANCE" | "HOSPITAL" | "TRACK" | "OPS";

const MODES: Record<Area, string | undefined> = {
  AUTH: process.env.NEXT_PUBLIC_API_MODE_AUTH,
  ME: process.env.NEXT_PUBLIC_API_MODE_ME,
  EMERGENCIES: process.env.NEXT_PUBLIC_API_MODE_EMERGENCIES,
  AMBULANCE: process.env.NEXT_PUBLIC_API_MODE_AMBULANCE,
  HOSPITAL: process.env.NEXT_PUBLIC_API_MODE_HOSPITAL,
  TRACK: process.env.NEXT_PUBLIC_API_MODE_TRACK,
  OPS: process.env.NEXT_PUBLIC_API_MODE_OPS,
};

export function areaMode(area: Area): "mock" | "real" {
  return MODES[area] === "real" ? "real" : "mock";
}

export const anyMock = (Object.keys(MODES) as Area[]).some((a) => areaMode(a) === "mock");

/** WS endpoint (§8): the core that owns the live events for this area. */
export function wsUrl(area: Area): string {
  const explicit = process.env.NEXT_PUBLIC_WS_URL;
  if (explicit) return explicit;
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const port = areaMode(area) === "real" ? process.env.NEXT_PUBLIC_CORE_WS_PORT ?? "8000" : process.env.NEXT_PUBLIC_MOCK_WS_PORT ?? "8010";
  return `${proto}://${window.location.hostname}:${port}/ws`;
}

/** SMS gateway number for the paramedic SMS fallback (§11.12). */
export const SMS_GATEWAY_NUMBER = process.env.NEXT_PUBLIC_SMS_GATEWAY_NUMBER ?? "+919000012345";
