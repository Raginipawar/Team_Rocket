// Minimal HTTP layer for the mock core: routing, JSON/multipart bodies, the §7.1 error
// envelope, CORS for direct access, and the Idempotency-Key middleware.

import type { IncomingMessage, ServerResponse } from "node:http";
import { createHash, randomUUID } from "node:crypto";
import { C, MOCK } from "./config";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: Record<string, unknown> = {}) {
    super(message);
  }
}

export const badRequest = (message: string, details: Record<string, unknown> = {}) => new ApiError(400, "VALIDATION_ERROR", message, details);
export const unauthenticated = (message = "missing or invalid token") => new ApiError(401, "UNAUTHENTICATED", message);
export const forbidden = (message = "not allowed") => new ApiError(403, "FORBIDDEN", message);
export const notFound = (message = "not found") => new ApiError(404, "NOT_FOUND", message);
export const conflict = (code: string, message: string, details: Record<string, unknown> = {}) => new ApiError(409, code, message, details);

export type Req = {
  method: string;
  path: string;
  query: URLSearchParams;
  headers: IncomingMessage["headers"];
  params: Record<string, string>;
  body: Record<string, unknown>;
  files: Record<string, { name: string; type: string; size: number }>;
  cookies: Record<string, string>;
  correlationId: string;
  setCookie: (cookie: string) => void;
  setHeader: (name: string, value: string) => void;
};

export type Handler = (req: Req) => Promise<unknown> | unknown;
type Route = { method: string; re: RegExp; keys: string[]; handler: Handler; status: number };

const routes: Route[] = [];

/** Register a route. Pattern segments like `{id}` become params. */
export function route(method: string, pattern: string, handler: Handler, status = 200) {
  const keys: string[] = [];
  const re = new RegExp(
    "^" + pattern.replace(/\{(\w+)\}/g, (_, k) => {
      keys.push(k);
      return "([^/]+)";
    }) + "/?$",
  );
  routes.push({ method, re, keys, handler, status });
}

function parseCookies(header: string | undefined) {
  const out: Record<string, string> = {};
  for (const part of (header ?? "").split(";")) {
    const i = part.indexOf("=");
    if (i > 0) out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}

async function readBody(req: IncomingMessage): Promise<Buffer> {
  const chunks: Buffer[] = [];
  for await (const c of req) chunks.push(c as Buffer);
  return Buffer.concat(chunks);
}

async function parseBody(raw: Buffer, contentType: string | undefined) {
  const body: Record<string, unknown> = {};
  const files: Req["files"] = {};
  if (!raw.length) return { body, files };
  if (contentType?.includes("multipart/form-data") || contentType?.includes("application/x-www-form-urlencoded")) {
    // Node's fetch Request parses multipart for us, same as FastAPI Form(...).
    const form = await new Request("http://mock/", { method: "POST", headers: { "content-type": contentType }, body: new Uint8Array(raw) }).formData();
    for (const [k, v] of form.entries()) {
      if (typeof v === "string") body[k] = v;
      else files[k] = { name: (v as File).name, type: (v as File).type, size: (v as File).size };
    }
    return { body, files };
  }
  try {
    const parsed = JSON.parse(raw.toString("utf8"));
    if (parsed && typeof parsed === "object") Object.assign(body, parsed);
  } catch {
    throw badRequest("body is not valid JSON");
  }
  return { body, files };
}

function send(res: ServerResponse, status: number, payload: unknown, headers: Record<string, string> = {}) {
  const text = payload === undefined || status === 204 ? "" : JSON.stringify(payload);
  res.writeHead(status, { "content-type": "application/json", ...headers });
  res.end(text);
}

// Idempotency store (§7.1): same key + same body => replay; different body => 422.
const idem = new Map<string, { hash: string; status: number; body: unknown; at: number }>();

function corsHeaders(origin: string | undefined): Record<string, string> {
  return {
    "access-control-allow-origin": origin ?? MOCK.WEB_ORIGIN,
    "access-control-allow-credentials": "true",
    "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    "access-control-allow-headers": "authorization,content-type,idempotency-key,x-correlation-id",
    "access-control-expose-headers": "x-correlation-id,x-dev-otp",
    vary: "origin",
  };
}

export async function handle(req: IncomingMessage, res: ServerResponse) {
  const url = new URL(req.url ?? "/", "http://mock");
  const method = (req.method ?? "GET").toUpperCase();
  const correlationId = (req.headers["x-correlation-id"] as string) || randomUUID();
  const extraHeaders: Record<string, string> = { ...corsHeaders(req.headers.origin), "x-correlation-id": correlationId };
  const cookies: string[] = [];

  if (method === "OPTIONS") return send(res, 204, undefined, extraHeaders);

  try {
    const match = routes.find((r) => r.method === method && r.re.test(url.pathname));
    if (!match) throw notFound(`no route for ${method} ${url.pathname}`);
    const m = url.pathname.match(match.re)!;
    const params: Record<string, string> = {};
    match.keys.forEach((k, i) => (params[k] = decodeURIComponent(m[i + 1])));

    const raw = await readBody(req);
    const { body, files } = await parseBody(raw, req.headers["content-type"]);

    const key = req.headers["idempotency-key"] as string | undefined;
    const mutating = method === "POST" || method === "PATCH" || method === "PUT" || method === "DELETE";
    const auth = (req.headers.authorization ?? "").slice(-24);
    const storeKey = key && mutating ? `${auth}:${url.pathname}:${key}` : null;
    const bodyHash = createHash("sha256").update(raw).digest("hex");
    if (storeKey) {
      const hit = idem.get(storeKey);
      if (hit && Date.now() - hit.at < C.IDEMPOTENCY_TTL_H * 3600_000) {
        if (hit.hash !== bodyHash) throw new ApiError(422, "IDEMPOTENCY_MISMATCH", "Same key with a different body");
        return send(res, hit.status, hit.body, { ...extraHeaders, "idempotent-replay": "true" });
      }
    }

    const r: Req = {
      method, path: url.pathname, query: url.searchParams, headers: req.headers, params, body, files,
      cookies: parseCookies(req.headers.cookie), correlationId,
      setCookie: (c) => cookies.push(c),
      setHeader: (n, v) => (extraHeaders[n] = v),
    };
    const out = await match.handler(r);
    const status = out === undefined ? 204 : match.status;
    if (storeKey && status < 300) idem.set(storeKey, { hash: bodyHash, status, body: out, at: Date.now() });
    const headers: Record<string, string> = { ...extraHeaders };
    if (cookies.length) res.setHeader("set-cookie", cookies);
    send(res, status, out, headers);
  } catch (e) {
    if (cookies.length) res.setHeader("set-cookie", cookies);
    if (e instanceof ApiError) {
      send(res, e.status, { error: { code: e.code, message: e.message, details: e.details } }, extraHeaders);
    } else {
      console.error("[mock-core] unhandled", e);
      send(res, 500, { error: { code: "INTERNAL", message: String((e as Error)?.message ?? e), details: {} } }, extraHeaders);
    }
  }
}

/** Reads a required string field. */
export function str(body: Record<string, unknown>, key: string, required = true): string {
  const v = body[key];
  if (v === undefined || v === null || v === "") {
    if (required) throw badRequest(`${key} required`);
    return "";
  }
  return String(v);
}

export function num(body: Record<string, unknown>, key: string): number | null {
  const v = body[key];
  if (v === undefined || v === null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
