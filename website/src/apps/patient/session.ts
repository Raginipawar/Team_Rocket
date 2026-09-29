// Patient sign-in state for the demo (the real app uses phone + OTP against the backend).
const KEY = "gh-patient-session";

export interface Session {
  phone: string;
  name: string;
  setupDone: boolean;
}

export function getSession(): Session | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function setSession(s: Session | null) {
  try {
    if (s) localStorage.setItem(KEY, JSON.stringify(s));
    else localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
