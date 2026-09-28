// Analytics (technical.md §11.16) for the mock core. Live cases are combined with a
// seeded 7-day synthetic history so charts are not empty on a fresh start; the
// response says `synthetic: true` and the UI labels it.

import type { Acuity, EscalationType, Facility, RejectReason } from "../../lib/enums";
import type { Analytics, Percentiles } from "../../lib/api-types";
import { db, now, type HistoryRec } from "./world";

function prng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

export function seedHistory() {
  db.history.length = 0;
  const r = prng(42);
  const hospitals = [...db.hospitals.values()];
  const acuities: Acuity[] = ["critical", "urgent", "stable"];
  const facilities: Facility[] = ["cardiac", "trauma", "stroke", "respiratory", "obstetric", "general", "pediatric", "burns", "poisoning"];
  const reasons: RejectReason[] = ["NO_BED", "NO_BED", "NO_SPECIALIST", "OVER_CAPACITY", "EQUIPMENT_DOWN", "NOT_EQUIPPED_FOR_CASE"];
  const t = now();
  for (let i = 0; i < 260; i++) {
    // more calls in the evening, as in the demand model's training data
    const dayAgo = Math.floor(r() * 7);
    const hour = Math.floor(((r() + r() + r()) / 3) * 24);
    const at = t - dayAgo * 86_400_000 - ((new Date(t).getHours() - hour + 24) % 24) * 3600_000 - Math.floor(r() * 3600_000);
    const acuity = acuities[r() < 0.35 ? 0 : r() < 0.75 ? 1 : 2];
    const ai = r() < 0.86 ? acuity : acuities[Math.floor(r() * 3)];
    const h = hospitals[Math.floor(r() * hospitals.length)];
    const outcomeRoll = r();
    const outcome: HistoryRec["outcome"] = outcomeRoll < 0.78 ? "accepted" : outcomeRoll < 0.93 ? "rejected" : "timeout";
    const accept = 20 + r() * 70;
    const scene = accept + 240 + r() * 540;
    const toHosp = 300 + r() * 900;
    const offload = r() < 0.12 ? 900 + r() * 900 : 120 + r() * 600;
    const esc: EscalationType | null = r() < 0.04 ? (["no_hospital", "no_ambulance", "mass_casualty", "system_anomaly"] as EscalationType[])[Math.floor(r() * 4)] : null;
    db.history.push({
      at, hospital_id: h.id, acuity, ai_acuity: ai, facility: facilities[Math.floor(r() * facilities.length)],
      call_to_accept: accept, call_to_scene: scene, scene_to_hospital: toHosp, call_to_handoff: scene + 300 + toHosp + offload, offload_delay: offload,
      outcome, reject_reason: outcome === "rejected" ? reasons[Math.floor(r() * reasons.length)] : null,
      escalation: esc, claim_sec: esc ? 15 + r() * 90 : null, auto_default: esc ? r() < 0.25 : false,
      stale: r() < (h.name.startsWith("Hillview") ? 0.4 : 0.08),
    });
  }
}

function pct(values: number[]): Percentiles {
  if (!values.length) return { p50: null, p90: null, n: 0 };
  const v = [...values].sort((a, b) => a - b);
  const q = (p: number) => Math.round(v[Math.min(v.length - 1, Math.floor(p * (v.length - 1)))]);
  return { p50: q(0.5), p90: q(0.9), n: v.length };
}

/** Live cases converted to history rows. */
function liveRows(): HistoryRec[] {
  const out: HistoryRec[] = [];
  for (const e of db.emergencies.values()) {
    const ts = e.timestamps;
    if (!ts.received_at || !e.hospital_id) continue;
    const ho = db.handoffs.get(e.id);
    const req = [...db.requests.values()].filter((r) => r.emergency_id === e.id);
    for (const r of req) {
      if (r.status === "pending") continue;
      out.push({
        at: ts.received_at, hospital_id: r.hospital_id, acuity: e.final_acuity ?? e.ai_acuity ?? "urgent", ai_acuity: e.ai_acuity ?? "urgent", facility: e.final_facility ?? e.ai_facility ?? "general",
        call_to_accept: ts.assigned_at ? (ts.assigned_at - ts.received_at) / 1000 : NaN,
        call_to_scene: ts.at_scene_at ? (ts.at_scene_at - ts.received_at) / 1000 : NaN,
        scene_to_hospital: ts.at_scene_at && ts.arrived_hospital_at ? (ts.arrived_hospital_at - ts.at_scene_at) / 1000 : NaN,
        call_to_handoff: ts.handed_off_at ? (ts.handed_off_at - ts.received_at) / 1000 : NaN,
        offload_delay: ho?.offloaded_at && ho.arrived_at ? (ho.offloaded_at - ho.arrived_at) / 1000 : NaN,
        outcome: r.status === "accepted" ? "accepted" : r.status === "timeout" ? "timeout" : "rejected",
        reject_reason: r.reason_code, escalation: null, claim_sec: null, auto_default: false, stale: false,
      });
    }
  }
  return out;
}

export function computeAnalytics(hospitalId: string | null, from?: number, to?: number): Analytics {
  const lo = from ?? now() - 7 * 86_400_000;
  const hi = to ?? now() + 60_000;
  const rows = [...db.history, ...liveRows()].filter((r) => r.at >= lo && r.at <= hi && (!hospitalId || r.hospital_id === hospitalId));
  const ok = (xs: number[]) => xs.filter((x) => Number.isFinite(x));
  const offl = ok(rows.map((r) => r.offload_delay));
  const buckets = [
    { label: "under 5 min", count: offl.filter((x) => x < 300).length },
    { label: "5 to 10 min", count: offl.filter((x) => x >= 300 && x < 600).length },
    { label: "10 to 15 min", count: offl.filter((x) => x >= 600 && x < 900).length },
    { label: "over 15 min", count: offl.filter((x) => x >= 900).length },
  ];
  const outcomes = ["accepted", "rejected", "timeout"].map((o) => ({ outcome: o, count: rows.filter((r) => r.outcome === o).length }));
  const reasonMap = new Map<string, number>();
  for (const r of rows) if (r.reject_reason) reasonMap.set(r.reject_reason, (reasonMap.get(r.reject_reason) ?? 0) + 1);
  const confusion: NonNullable<Analytics["triage_confusion"]> = [];
  const acs: Acuity[] = ["critical", "urgent", "stable"];
  for (const ai of acs) for (const fin of acs) confusion.push({ ai, final: fin, count: rows.filter((r) => r.ai_acuity === ai && r.acuity === fin).length });
  const trueCrit = rows.filter((r) => r.acuity === "critical");
  const hourly = Array.from({ length: 24 }, (_, h) => ({ hour: h, count: rows.filter((r) => new Date(r.at).getHours() === h).length }));
  const staleBy = [...db.hospitals.values()].map((h) => {
    const mine = rows.filter((r) => r.hospital_id === h.id);
    return { hospital: h.name, stale_share: mine.length ? mine.filter((r) => r.stale).length / mine.length : 0 };
  }).filter((x) => !hospitalId || x.stale_share >= 0);
  const escTypes: EscalationType[] = ["no_hospital", "no_ambulance", "mass_casualty", "system_anomaly"];
  const escRows = rows.filter((r) => r.escalation);
  const liveEsc = [...db.escalations.values()];
  const escalations = escTypes.map((type) => {
    const hist = escRows.filter((r) => r.escalation === type);
    const live = liveEsc.filter((x) => x.type === type);
    const claims = [...ok(hist.map((h) => h.claim_sec ?? NaN)), ...live.filter((x) => x.claimed_at).map((x) => (x.claimed_at! - x.created_at) / 1000)].sort((a, b) => a - b);
    const n = hist.length + live.length;
    const autos = hist.filter((h) => h.auto_default).length + live.filter((x) => x.status === "auto_defaulted").length;
    return { type, count: n, auto_default_rate: n ? autos / n : 0, median_claim_sec: claims.length ? Math.round(claims[Math.floor(claims.length / 2)]) : null };
  });
  // demand: actual per hour for the last 24 h vs the forecast (smoothed weekly profile)
  const demand = Array.from({ length: 24 }, (_, i) => {
    const start = now() - (23 - i) * 3600_000;
    const hr = new Date(start).getHours();
    const actual = db.history.filter((r) => Math.abs(r.at - start) < 1800_000).length + [...db.emergencies.values()].filter((e) => Math.abs((e.timestamps.received_at ?? 0) - start) < 1800_000).length;
    const forecast = Math.round((db.history.filter((r) => new Date(r.at).getHours() === hr).length / 7) * 10) / 10;
    return { hour: `${String(hr).padStart(2, "0")}:00`, actual, forecast };
  });
  const flags: string[] = [];
  for (const h of db.hospitals.values()) {
    if (hospitalId && h.id !== hospitalId) continue;
    const since = now() - 86_400_000;
    const mine = rows.filter((r) => r.hospital_id === h.id && r.at > since);
    const rate = mine.length ? mine.filter((r) => r.outcome !== "accepted").length / mine.length : 0;
    if (mine.length >= 4 && rate > 0.4) flags.push(`${h.name}: rejected ${Math.round(rate * 100)}% of requests in 24 h`);
  }
  return {
    synthetic: true,
    response_times: {
      call_to_accept: pct(ok(rows.map((r) => r.call_to_accept))),
      call_to_scene: pct(ok(rows.map((r) => r.call_to_scene))),
      scene_to_hospital: pct(ok(rows.map((r) => r.scene_to_hospital))),
      call_to_handoff: pct(ok(rows.map((r) => r.call_to_handoff))),
    },
    offload_delay: { buckets, p50: pct(offl).p50, p90: pct(offl).p90 },
    request_outcomes: outcomes,
    rejections_by_reason: [...reasonMap].map(([reason, count]) => ({ reason, count })).sort((a, b) => b.count - a.count),
    triage_confusion: confusion,
    critical_recall: trueCrit.length ? trueCrit.filter((r) => r.ai_acuity === "critical").length / trueCrit.length : null,
    stale_data: staleBy,
    escalations,
    demand,
    hourly_calls: hourly,
    flags,
  };
}
