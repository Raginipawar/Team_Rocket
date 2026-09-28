// System constants, mirrored from technical.md §4 (services/core/app/config.py).
// The mock core uses the same numbers so the UI behaves exactly as it will on the real core.

export const C = {
  DISPATCH_RADII_KM: [5, 10, 20],
  OFFERS_PER_ROUND: 4,
  OFFER_EXPIRY_SEC: 20,
  DISPATCH_ROUND_INTERVAL_SEC: 30,
  NO_AMBULANCE_ESCALATE_AFTER_ROUND: 3,
  HOSPITAL_TIMEOUT_CRITICAL_SEC: 45,
  HOSPITAL_TIMEOUT_OTHER_SEC: 60,
  PRIORITY_REQUEST_TIMEOUT_SEC: 30,
  HOLD_PENDING_EXTRA_SEC: 10,
  HOLD_CONFIRMED_MIN_SEC: 600,
  HEARTBEAT_INTERVAL_SEC: 5,
  SIGNAL_WEAK_SEC: 30,
  SIGNAL_LOST_SEC: 120,
  OFFLINE_HOLD_GRACE_SEC: 900,
  ESCALATION_REPEAT_SEC: 60,
  ESCALATION_DEFAULT_SEC: 120,
  FRESH_MAX_MIN: 10,
  AGING_MAX_MIN: 30,
  MCI_PATIENT_THRESHOLD: 5,
  TRIAGE_REVIEW_CONFIDENCE: 0.6,
  GEOFENCE_SCENE_M: 75,
  GEOFENCE_HOSPITAL_M: 150,
  OFFLOAD_DELAY_ALERT_MIN: 15,
  DETERIORATION_DIVERT_GAIN_SEC: 180,
  IDEMPOTENCY_TTL_H: 24,
  OPS_LINK_TTL_MIN: 15,
  OPS_SESSION_H: 2,
  ACCESS_TOKEN_TTL_MIN: 15,
  REFRESH_TOKEN_TTL_DAYS: 7,
  OTP_TTL_MIN: 5,
  OTP_MAX_ATTEMPTS: 5,
  OTP_REQUEST_LIMIT: 3,
  OTP_REQUEST_WINDOW_MIN: 10,
  HOSPITAL_SEARCH_KM: 25,
  FOLLOWUP_MAX_QUESTIONS: 5,
} as const;

/** Mock-only knobs (env), documented in apps/web/README.md. */
export const MOCK = {
  PORT: Number(process.env.MOCK_CORE_PORT ?? 8010),
  JWT_SECRET: process.env.MOCK_JWT_SECRET ?? "mock-core-dev-secret",
  ML_BASE_URL: process.env.ML_BASE_URL ?? "http://localhost:8001",
  ML_TIMEOUT_MS: Number(process.env.ML_TIMEOUT_MS ?? 2500),
  OSRM_URL: process.env.OSRM_URL ?? "",
  WEB_ORIGIN: process.env.WEB_ORIGIN ?? "http://localhost:3000",
  /** Simulated ambulances drive this many times faster than real traffic, so a demo trip takes a couple of minutes. */
  DRIVE_FACTOR: Number(process.env.MOCK_DRIVE_FACTOR ?? 3),
  /** Hospital bots answer with this acceptance probability (§15). */
  BOT_HOSPITAL_ACCEPT: Number(process.env.MOCK_BOT_HOSPITAL_ACCEPT ?? 0.8),
  /** Driver bots accept an offer with this probability (§15). */
  BOT_DRIVER_ACCEPT: Number(process.env.MOCK_BOT_DRIVER_ACCEPT ?? 0.75),
};
