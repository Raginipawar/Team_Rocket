"use client";

// The one place every REST call goes through (wd-person-c-frontend.md §5 rule 1):
// - Bearer access token, with one refresh-and-retry on 401
// - an Idempotency-Key on every mutation, reused on retry
// - the §7.1 error envelope, plus FastAPI's {"detail": ...} wrapping, into ApiError
// - optional offline queueing for paramedic actions (§11.12)

import { enqueue } from "./offline-queue";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: Record<string, unknown> = {}) {
    super(message);
  }
  get isConflict() {
    return this.status === 409;
  }
  get isNetwork() {
    return this.status === 0;
  }
}

type TokenSource = {
  get: () => string | null;
  refresh: () => Promise<string | null>;
  onLoggedOut: () => void;
};

let tokens: TokenSource = { get: () => null, refresh: async () => null, onLoggedOut: () => {} };
export function setTokenSource(t: TokenSource) {
  tokens = t;
}

export const newKey = () => (typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`);

/** Reads the §7.1 envelope, FastAPI's {"detail": {"error": ...}}, {"detail": "text"} and pydantic lists. */
export async function toApiError(res: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* not JSON */
  }
  const b = body as Record<string, unknown> | null;
  const env = (b?.error ?? (b?.detail as Record<string, unknown> | undefined)?.error) as { code?: string; message?: string; details?: Record<string, unknown> } | undefined;
  if (env) return new ApiError(res.status, env.code ?? `HTTP_${res.status}`, env.message ?? res.statusText, env.details ?? {});
  if (typeof b?.detail === "string") return new ApiError(res.status, `HTTP_${res.status}`, b.detail);
  if (Array.isArray(b?.detail)) return new ApiError(res.status, "VALIDATION_ERROR", (b!.detail as { msg?: string }[]).map((d) => d.msg).join("; "));
  return new ApiError(res.status, res.status === 404 ? "NOT_FOUND" : `HTTP_${res.status}`, res.statusText || "Request failed");
}

type Opts = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  form?: FormData;
  auth?: boolean;
  idempotencyKey?: string;
  /** paramedic actions: when the network is down, store and replay later instead of failing */
  queueable?: boolean;
  signal?: AbortSignal;
};

// Next's dev-mode rewrite proxy occasionally reuses a stalled keep-alive socket: the
// same request that answers in single-digit ms from curl or a fresh connection can
// sit open for 10+ seconds on a reused one. A per-attempt timeout turns that stall
// into a fast, visible retry on a fresh connection instead of a silent multi-second
// hang — "fail safe" (technical.md §0.8): degrade toward an explicit retry, never
// toward the caller just waiting with no feedback.
const ATTEMPT_TIMEOUT_MS = 8000;

async function once(path: string, o: Opts, key: string | undefined, token: string | null) {
  const headers: Record<string, string> = {};
  if (token && o.auth !== false) headers.authorization = `Bearer ${token}`;
  if (key) headers["idempotency-key"] = key;
  let body: BodyInit | undefined;
  if (o.form) body = o.form;
  else if (o.body !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(o.body);
  }
  const timeoutSignal = AbortSignal.timeout(ATTEMPT_TIMEOUT_MS);
  const signal = o.signal ? AbortSignal.any([o.signal, timeoutSignal]) : timeoutSignal;
  try {
    return await fetch(`/api/v1${path}`, { method: o.method ?? "GET", headers, body, credentials: "same-origin", signal });
  } catch (err) {
    // Distinguish "our own timeout, please retry" from "the caller cancelled this on
    // purpose" (e.g. a component unmounted) so only the latter propagates as-is.
    if ((err as Error).name === "AbortError" && !o.signal?.aborted) throw new StaleConnectionError();
    throw err;
  }
}

class StaleConnectionError extends Error {
  constructor() {
    super("stale connection timed out");
  }
}

export async function api<T>(path: string, o: Opts = {}): Promise<T> {
  const method = o.method ?? "GET";
  const mutating = method !== "GET";
  const key = mutating ? o.idempotencyKey ?? newKey() : undefined;
  let refreshed = false;
  for (let attempt = 0; attempt < (mutating ? 3 : 2); attempt++) {
    let res: Response;
    try {
      res = await once(path, o, key, tokens.get());
    } catch (err) {
      if (err instanceof StaleConnectionError) {
        continue; // fresh connection, no backoff, same Idempotency-Key: never runs twice
      }
      if ((err as Error).name === "AbortError") throw err; // the caller cancelled this on purpose
      if (o.queueable && key && !o.form) {
        await enqueue({ path, method, body: o.body ?? null, key });
        return { queued: true } as T;
      }
      if (attempt < (mutating ? 2 : 1)) {
        await new Promise((r) => setTimeout(r, 600 * (attempt + 1)));
        continue; // same Idempotency-Key, so a retried POST never runs twice
      }
      throw new ApiError(0, "NETWORK", "No connection to the server");
    }
    if (res.status === 401 && o.auth !== false && !refreshed) {
      refreshed = true;
      const t = await tokens.refresh();
      if (t) {
        attempt--;
        continue;
      }
      tokens.onLoggedOut();
    }
    if (res.status >= 500 && res.status !== 503 && attempt < (mutating ? 2 : 1)) {
      await new Promise((r) => setTimeout(r, 600 * (attempt + 1)));
      continue;
    }
    if (!res.ok) throw await toApiError(res);
    if (res.status === 204) return undefined as T;
    const text = await res.text();
    return (text ? JSON.parse(text) : undefined) as T;
  }
  throw new ApiError(0, "NETWORK", "No connection to the server");
}

export const get = <T>(path: string, o: Omit<Opts, "method"> = {}) => api<T>(path, { ...o, method: "GET" });
export const post = <T>(path: string, body?: unknown, o: Omit<Opts, "method" | "body"> = {}) => api<T>(path, { ...o, method: "POST", body });
export const put = <T>(path: string, body?: unknown, o: Omit<Opts, "method" | "body"> = {}) => api<T>(path, { ...o, method: "PUT", body });
export const patch = <T>(path: string, body?: unknown, o: Omit<Opts, "method" | "body"> = {}) => api<T>(path, { ...o, method: "PATCH", body });
export const del = <T>(path: string, o: Omit<Opts, "method"> = {}) => api<T>(path, { ...o, method: "DELETE" });

/** Friendly text for an error, in plain words (UI rule 1: specific messages for 409s). */
export function errorText(err: unknown): string {
  if (!(err instanceof ApiError)) return "Something went wrong. Please try again.";
  switch (err.code) {
    case "NETWORK":
      return "No internet connection. We will keep trying.";
    case "ALREADY_TAKEN":
      return "Another ambulance already took this emergency.";
    case "OFFER_EXPIRED":
      return "This request has expired.";
    case "VERSION_CONFLICT":
      return "Someone else changed this just now. We loaded the latest version.";
    case "ROOM_RESERVED":
      return "This room is held for an incoming ambulance.";
    case "RESOURCE_UNAVAILABLE":
      return "The room or equipment is no longer free.";
    case "RATE_LIMITED":
      return err.message || "Too many tries. Please wait a moment.";
    case "UNAUTHENTICATED":
      return err.message === "Incorrect code" ? "That code is not right. Please check the SMS and try again." : err.message || "Please sign in again.";
    case "FORBIDDEN":
      return "You do not have access to this.";
    case "DEPENDENCY_UNAVAILABLE":
      return "The service is not available. Please call 108.";
    default:
      return err.message || "Something went wrong. Please try again.";
  }
}
