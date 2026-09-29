// Auth for the mock core, following services/core/app/security/* on main:
// HS256 JWT (claims sub, role, hospital_id?, ambulance_id?, type, jti, kid),
// 6-digit OTP (5 min, 5 attempts, 3 requests per 10 min), refresh rotation with
// revocation, and one-time tokens stored as SHA-256 hashes (§18).

import { createHash, createHmac, randomBytes, randomInt, randomUUID } from "node:crypto";
import { C, MOCK } from "./config";
import { ApiError, forbidden, unauthenticated, type Req } from "./http";
import { db, type UserRec } from "./world";

const b64 = (b: Buffer | string) => Buffer.from(b).toString("base64url");

export type Claims = { sub: string; role: string; type: "access" | "refresh"; hospital_id?: string; ambulance_id?: string; exp: number; iat: number; jti: string };

function sign(payload: Omit<Claims, "iat" | "exp" | "jti">, ttlSec: number) {
  const iat = Math.floor(Date.now() / 1000);
  const full: Claims = { ...payload, iat, exp: iat + ttlSec, jti: randomUUID() } as Claims;
  const head = b64(JSON.stringify({ alg: "HS256", typ: "JWT", kid: "k1" }));
  const body = b64(JSON.stringify(full));
  const sig = b64(createHmac("sha256", MOCK.JWT_SECRET).update(`${head}.${body}`).digest());
  return `${head}.${body}.${sig}`;
}

export function verify(token: string, type: "access" | "refresh"): Claims {
  const [h, b, s] = token.split(".");
  if (!h || !b || !s) throw unauthenticated("invalid token");
  const expected = b64(createHmac("sha256", MOCK.JWT_SECRET).update(`${h}.${b}`).digest());
  if (expected !== s) throw unauthenticated("invalid token");
  const claims = JSON.parse(Buffer.from(b, "base64url").toString("utf8")) as Claims;
  if (claims.exp * 1000 < Date.now()) throw unauthenticated("token expired");
  if (claims.type !== type) throw unauthenticated(`expected ${type} token`);
  return claims;
}

export function issue(user: UserRec) {
  const access = sign({ sub: user.id, role: user.role, type: "access", ...(user.hospital_id ? { hospital_id: user.hospital_id } : {}), ...(user.ambulance_id ? { ambulance_id: user.ambulance_id } : {}) }, C.ACCESS_TOKEN_TTL_MIN * 60);
  const refresh = sign({ sub: user.id, role: user.role, type: "refresh" }, C.REFRESH_TOKEN_TTL_DAYS * 86400);
  return { access, refresh };
}

export function refreshCookie(token: string, secure: boolean) {
  const attrs = ["Path=/", "HttpOnly", "SameSite=Strict", `Max-Age=${C.REFRESH_TOKEN_TTL_DAYS * 86400}`];
  if (secure) attrs.push("Secure");
  return `refresh_token=${token}; ${attrs.join("; ")}`;
}

export const revoked = new Set<string>();

export type Current = { id: string; role: string; hospital_id: string | null; ambulance_id: string | null; user: UserRec };

export function currentUser(req: Req): Current {
  const h = req.headers.authorization;
  const token = h?.startsWith("Bearer ") ? h.slice(7) : req.query.get("token");
  if (!token) throw unauthenticated();
  const c = verify(token, "access");
  const user = db.users.get(c.sub);
  if (!user) throw unauthenticated("user not found");
  return { id: user.id, role: user.role, hospital_id: user.hospital_id, ambulance_id: user.ambulance_id, user };
}

export function requireRole(req: Req, ...roles: string[]): Current {
  const u = currentUser(req);
  if (!roles.includes(u.role)) throw forbidden(`requires role in (${roles.join(", ")})`);
  return u;
}

/* ---------- OTP ---------- */
const otps = new Map<string, { hash: string; expires: number; attempts: number }>();
const otpRequests = new Map<string, number[]>();

const hashCode = (code: string, phone: string) => createHash("sha256").update(`${phone}:${code}`).digest("hex");

export function requestOtp(phone: string) {
  const t = Date.now();
  const recent = (otpRequests.get(phone) ?? []).filter((x) => t - x < C.OTP_REQUEST_WINDOW_MIN * 60_000);
  if (recent.length >= C.OTP_REQUEST_LIMIT) throw new ApiError(429, "RATE_LIMITED", "Too many OTP requests");
  recent.push(t);
  otpRequests.set(phone, recent);
  const code = String(randomInt(0, 1_000_000)).padStart(6, "0");
  otps.set(phone, { hash: hashCode(code, phone), expires: t + C.OTP_TTL_MIN * 60_000, attempts: 0 });
  return code;
}

export function verifyOtp(phone: string, code: string) {
  const rec = otps.get(phone);
  if (!rec) throw unauthenticated("No OTP requested for this phone");
  if (Date.now() > rec.expires) {
    otps.delete(phone);
    throw unauthenticated("OTP expired");
  }
  if (rec.attempts >= C.OTP_MAX_ATTEMPTS) throw new ApiError(429, "RATE_LIMITED", "Too many attempts");
  if (rec.hash !== hashCode(code, phone)) {
    rec.attempts++;
    throw unauthenticated("Incorrect code");
  }
  otps.delete(phone);
}

/* ---------- one-time tokens (ops links, family track) ---------- */
export const hashToken = (raw: string) => createHash("sha256").update(raw).digest("hex");
export const newToken = () => {
  const raw = randomBytes(32).toString("base64url");
  return { raw, hash: hashToken(raw) };
};

const opsLinks = new Map<string, { expires: number; used: boolean; escalation_id: string | null }>();
export const opsSessions = new Map<string, { user_id: string; expires: number }>();

export function issueOpsLink(escalationId: string | null = null) {
  const { raw, hash } = newToken();
  opsLinks.set(hash, { expires: Date.now() + C.OPS_LINK_TTL_MIN * 60_000, used: false, escalation_id: escalationId });
  return raw;
}

export function exchangeOpsLink(raw: string) {
  const rec = opsLinks.get(hashToken(raw));
  if (!rec) throw new ApiError(401, "INVALID_TOKEN", "Unknown link");
  if (rec.used) throw new ApiError(401, "INVALID_TOKEN", "This link was already used. Ask the bot for a new one with /ops");
  if (Date.now() > rec.expires) throw new ApiError(401, "INVALID_TOKEN", "This link has expired. Ask the bot for a new one with /ops");
  rec.used = true;
  const dev = [...db.users.values()].find((u) => u.role === "developer")!;
  const session = randomBytes(24).toString("base64url");
  opsSessions.set(session, { user_id: dev.id, expires: Date.now() + C.OPS_SESSION_H * 3600_000 });
  return { session, user: dev, escalation_id: rec.escalation_id };
}

/** Ops routes accept the ops_session cookie (B's ops.py), a Bearer ops session, or a developer JWT. */
export function requireOps(req: Req): Current {
  const cookie = req.cookies.ops_session;
  const bearer = req.headers.authorization?.startsWith("Bearer ") ? req.headers.authorization.slice(7) : null;
  for (const s of [cookie, bearer]) {
    if (!s) continue;
    const sess = opsSessions.get(s);
    if (sess && sess.expires > Date.now()) {
      const user = db.users.get(sess.user_id)!;
      return { id: user.id, role: "developer", hospital_id: null, ambulance_id: null, user };
    }
  }
  if (bearer && bearer.split(".").length === 3) return requireRole(req, "developer");
  throw unauthenticated("ops session required");
}
