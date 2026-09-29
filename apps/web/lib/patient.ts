"use client";

import type { EmergencyView, FollowupState } from "./api-types";
import { get } from "./api";
import { FINAL_STATUSES, type EmergencyStatus } from "./enums";

/**
 * GET /emergencies/{id}. The mock core returns the §7.3 patient view. The real core on
 * main currently returns the raw emergencies row (services/core/app/api/v1/emergencies.py),
 * so this maps that shape too; once the role projection lands, the first branch is used.
 */
export async function fetchEmergency(id: string): Promise<EmergencyView> {
  const raw = await get<Record<string, unknown>>(`/emergencies/${id}`);
  return normalizeEmergency(raw);
}

export function normalizeEmergency(raw: Record<string, unknown>): EmergencyView {
  if ("triage" in raw || "ambulance" in raw) return raw as unknown as EmergencyView;
  const r = raw as Record<string, never>;
  return {
    id: String(r.id),
    status: r.status as EmergencyStatus,
    version: Number(r.version ?? 1),
    triage: r.ai_acuity ? { acuity: r.final_acuity ?? r.ai_acuity, facility: r.final_facility ?? r.ai_facility ?? "general", confidence: Number(r.ai_confidence ?? 0), confirmed: !!r.final_acuity, needs_review: !!r.needs_review } : null,
    ambulance: null,
    hospital: null,
    handoff: null,
    first_aid: null,
    timeline: { received_at: r.received_at ?? null, assigned_at: r.assigned_at ?? null, at_scene_at: r.at_scene_at ?? null, on_board_at: r.on_board_at ?? null, hospital_confirmed_at: r.hospital_confirmed_at ?? null, arrived_hospital_at: r.arrived_hospital_at ?? null, handed_off_at: r.handed_off_at ?? null },
  };
}

export async function fetchFollowup(id: string): Promise<FollowupState | null> {
  try {
    return await get<FollowupState>(`/emergencies/${id}/followup`);
  } catch {
    return null; // not implemented on this core yet: the card simply stays hidden
  }
}

export const isFinal = (s: EmergencyStatus) => FINAL_STATUSES.includes(s);

/** Remember the last emergency on this phone, so the home screen can link back to it. */
const LAST = "gh-last-emergency";
export function rememberEmergency(id: string, trackUrl?: string) {
  try {
    localStorage.setItem(LAST, JSON.stringify({ id, trackUrl, at: Date.now() }));
  } catch {
    /* ignore */
  }
}
export function lastEmergency(): { id: string; trackUrl?: string; at: number } | null {
  try {
    const v = JSON.parse(localStorage.getItem(LAST) ?? "null");
    return v && Date.now() - v.at < 12 * 3600_000 ? v : null;
  } catch {
    return null;
  }
}
export function trackUrlFor(id: string): string | null {
  const l = lastEmergency();
  return l?.id === id ? l.trackUrl ?? null : null;
}
