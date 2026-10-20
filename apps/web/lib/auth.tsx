"use client";

// Auth (technical.md §7.2): short-lived access JWT kept in memory (and this tab's
// sessionStorage so a reload keeps you signed in), refresh token in an httpOnly cookie.
// Each tab keeps its own session, so one browser can show the patient, ambulance and
// hospital apps side by side; a refresh that comes back as a different person signs
// this tab out instead of silently switching identity.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { post, setTokenSource } from "./api";
import type { LoginResponse, User } from "./api-types";
import type { Role } from "./enums";

type Session = { token: string; user: User };
type Ctx = {
  session: Session | null;
  ready: boolean;
  signIn: (r: LoginResponse) => void;
  signOut: () => Promise<void>;
  updateUser: (u: Partial<User>) => void;
  /** Adopt a fresh access token issued outside the normal login/refresh flow
   * (e.g. right after ambulance registration, whose new token carries a
   * just-assigned ambulance_id the old one didn't have). */
  setToken: (token: string) => void;
  /** Try to silently restore a session for a known role (RequireRole's own
   * prop) using only the httpOnly refresh cookie -- for when sessionStorage
   * came back empty but the cookie didn't. Returns the new token, or null
   * if there's genuinely no valid session for that role. */
  refreshAs: (role: string) => Promise<string | null>;
};

const AuthContext = createContext<Ctx | null>(null);
const KEY = "gh-session";

export function decodeClaims(token: string): { sub: string; role: Role; hospital_id?: string; ambulance_id?: string; exp: number } | null {
  try {
    const part = token.split(".")[1];
    const json = atob(part.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(part.length / 4) * 4, "="));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

function userFromToken(token: string, prev?: User | null): User | null {
  const c = decodeClaims(token);
  if (!c) return null;
  if (prev && prev.id === c.sub) return { ...prev, role: c.role, hospital_id: c.hospital_id ?? prev.hospital_id, ambulance_id: c.ambulance_id ?? prev.ambulance_id };
  return { id: c.sub, role: c.role, hospital_id: c.hospital_id ?? null, ambulance_id: c.ambulance_id ?? null };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const ref = useRef<Session | null>(null);
  const refreshing = useRef<Promise<string | null> | null>(null);

  const save = useCallback((s: Session | null) => {
    ref.current = s;
    setSession(s);
    try {
      if (s) sessionStorage.setItem(KEY, JSON.stringify(s));
      else sessionStorage.removeItem(KEY);
    } catch {
      /* private mode */
    }
  }, []);

  const doRefresh = useCallback(async (role: string): Promise<string | null> => {
    try {
      const res = await fetch(`/api/v1/auth/refresh?role=${encodeURIComponent(role)}`, { method: "POST", credentials: "same-origin", headers: { "idempotency-key": crypto.randomUUID() } });
      if (!res.ok) return null;
      const body = (await res.json()) as { access_token: string; user?: User };
      const prev = ref.current?.user ?? null;
      const user = body.user ?? userFromToken(body.access_token, prev);
      if (!user) return null;
      if (prev && prev.id !== user.id) {
        // the cookie belongs to someone who signed in on another tab
        save(null);
        return null;
      }
      save({ token: body.access_token, user: { ...prev, ...user } });
      return body.access_token;
    } catch {
      return null;
    }
  }, [save]);

  const refresh = useCallback(async (): Promise<string | null> => {
    if (refreshing.current) return refreshing.current;
    refreshing.current = (async () => {
      // The refresh cookie is now named per-role (refresh_token_<role>) so
      // concurrent logins as different roles in the same browser can't
      // overwrite each other -- this tab tells the backend which one is
      // its own via the role it already knows itself as. A tab that has
      // never had a role-tagged session has nothing to refresh.
      const role = ref.current?.user?.role;
      if (!role) return null;
      try {
        return await doRefresh(role);
      } finally {
        setTimeout(() => (refreshing.current = null), 0);
      }
    })();
    return refreshing.current;
  }, [doRefresh]);

  // Mobile browsers can silently wipe sessionStorage on a backgrounded tab
  // (OS memory reclaim, tab discard on screen lock/app switch) even though
  // nothing actually expired -- the access token lives there specifically
  // so one browser can hold separate patient/ambulance/hospital sessions in
  // different tabs (a shared localStorage key would clobber between them),
  // but that means a wiped tab has no in-memory role to refresh with and
  // used to go straight to login even though the httpOnly refresh cookie
  // (unaffected by sessionStorage loss) was still perfectly valid. Each
  // route already knows which role it requires (RequireRole's own prop),
  // so it can ask for a refresh using THAT role before giving up.
  const refreshAs = useCallback(async (role: string): Promise<string | null> => {
    if (refreshing.current) return refreshing.current;
    refreshing.current = (async () => {
      try {
        return await doRefresh(role);
      } finally {
        setTimeout(() => (refreshing.current = null), 0);
      }
    })();
    return refreshing.current;
  }, [doRefresh]);

  useEffect(() => {
    setTokenSource({ get: () => ref.current?.token ?? null, refresh, onLoggedOut: () => save(null) });
    let stored: Session | null = null;
    try {
      stored = JSON.parse(sessionStorage.getItem(KEY) ?? "null");
    } catch {
      stored = null;
    }
    const claims = stored ? decodeClaims(stored.token) : null;
    if (stored && claims && claims.exp * 1000 > Date.now() + 10_000) {
      ref.current = stored;
      setSession(stored);
      setReady(true);
    } else if (stored) {
      // Expired access token but we know which role this tab was signed in
      // as -- refresh() uses that to read the matching per-role cookie.
      ref.current = stored;
      void refresh().finally(() => setReady(true));
    } else {
      // Never signed in on this tab: no role to refresh with, and no point
      // guessing at some other role's cookie. Straight to logged-out.
      setReady(true);
    }
    // renew a minute before the 15 minute access token runs out
    const id = setInterval(() => {
      const c = ref.current ? decodeClaims(ref.current.token) : null;
      if (c && c.exp * 1000 - Date.now() < 60_000) void refresh();
    }, 30_000);
    return () => clearInterval(id);
  }, [refresh, save]);

  const value = useMemo<Ctx>(() => ({
    session,
    ready,
    signIn: (r) => save({ token: r.access_token, user: r.user }),
    signOut: async () => {
      try {
        const role = session?.user.role;
        await post(role ? `/auth/logout?role=${encodeURIComponent(role)}` : "/auth/logout");
      } catch {
        /* still sign out locally */
      }
      save(null);
    },
    updateUser: (u) => {
      if (ref.current) save({ ...ref.current, user: { ...ref.current.user, ...u } });
    },
    setToken: (token) => {
      const user = userFromToken(token, ref.current?.user ?? null);
      if (user) save({ token, user });
    },
    refreshAs,
  }), [session, ready, save, refreshAs]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const c = useContext(AuthContext);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}
