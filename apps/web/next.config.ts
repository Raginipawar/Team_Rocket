import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

// Per-area API switching (wd-person-c-frontend.md §6): every router group can point
// at the real core (services/core) or the mock core (mocks/core) independently, so
// each area moves to "real" as soon as its owner's router is live.
//   NEXT_PUBLIC_API_MODE=mock|real            default for every area
//   NEXT_PUBLIC_API_MODE_<AREA>=mock|real     per area: AUTH, ME, EMERGENCIES, AMBULANCE, HOSPITAL, TRACK, OPS
// Requests go through this same origin, so the httpOnly refresh cookie works and no CORS is needed.

const CORE_URL = process.env.CORE_URL ?? "http://localhost:8000";
const MOCK_CORE_URL = process.env.MOCK_CORE_URL ?? "http://localhost:8010";

const AREAS: Record<string, string[]> = {
  AUTH: ["/api/v1/auth/:path*"],
  ME: ["/api/v1/me/:path*"],
  EMERGENCIES: ["/api/v1/emergencies", "/api/v1/emergencies/:path*"],
  AMBULANCE: ["/api/v1/ambulance/:path*", "/api/v1/offers/:path*"],
  HOSPITAL: ["/api/v1/hospital/:path*"],
  TRACK: ["/api/v1/track/:path*"],
  OPS: ["/api/v1/ops/:path*"],
};

function mode(area: string) {
  return (process.env[`NEXT_PUBLIC_API_MODE_${area}`] ?? process.env.NEXT_PUBLIC_API_MODE ?? "mock") === "real" ? "real" : "mock";
}

const nextConfig: NextConfig = {
  env: Object.fromEntries(Object.keys(AREAS).map((a) => [`NEXT_PUBLIC_API_MODE_${a}`, mode(a)])),
  async rewrites() {
    const rules = Object.entries(AREAS).flatMap(([area, sources]) =>
      sources.map((source) => ({ source, destination: `${mode(area) === "real" ? CORE_URL : MOCK_CORE_URL}${source}` })),
    );
    const healthTarget = mode("EMERGENCIES") === "real" ? CORE_URL : MOCK_CORE_URL;
    rules.push({ source: "/core/readyz", destination: `${healthTarget}/readyz` });
    rules.push({ source: "/core/healthz", destination: `${healthTarget}/healthz` });
    rules.push({ source: "/core/dev/:path*", destination: `${MOCK_CORE_URL}/dev/:path*` });
    return rules;
  },
  async headers() {
    return [{ source: "/sw.js", headers: [{ key: "Cache-Control", value: "no-cache" }, { key: "Service-Worker-Allowed", value: "/" }] }];
  },
  allowedDevOrigins: ["192.168.*.*", "10.*.*.*", "*.trycloudflare.com"],
};

export default createNextIntlPlugin("./i18n/request.ts")(nextConfig);
