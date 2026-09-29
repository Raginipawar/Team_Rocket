"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { HospitalRequestCard, Room, Staff } from "@/lib/api-types";
import type { RejectReason } from "@/lib/enums";
import { ENUMS } from "@/lib/enums";
import { errorText, post } from "@/lib/api";
import { AcuityBadge, FacilityChip, WhyYou } from "@/components/emergency/badges";
import CountdownRing from "@/components/ambulance/CountdownRing";
import { Card, SectionLabel, Select, Textarea } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { minutes, reg } from "@/lib/format";
import { useHosp } from "@/app/hospital/context";

const REASON_LABEL: Record<RejectReason, string> = { NO_BED: "No bed available", NO_SPECIALIST: "No specialist on duty", EQUIPMENT_DOWN: "Equipment down", OVER_CAPACITY: "Over capacity", NOT_EQUIPPED_FOR_CASE: "Not equipped for this case", OTHER: "Other" };

export default function RequestCard({ req, rooms, staff }: { req: HospitalRequestCard; rooms: Room[]; staff: Staff[] }) {
  const toast = useToast();
  const qc = useQueryClient();
  const { refetch } = useHosp();
  const [accepting, setAccepting] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [roomId, setRoomId] = useState(req.suggested_room_id ?? "");
  const [staffIds, setStaffIds] = useState<string[]>(req.suggested_staff_ids ?? []);
  const [reason, setReason] = useState<RejectReason>("NO_BED");
  const [note, setNote] = useState("");

  const freeRooms = rooms.filter((r) => r.status === "free" || r.id === roomId);

  const accept = async () => {
    setBusy(true);
    try {
      await post(`/hospital/requests/${req.request_id}/accept`, { room_id: roomId || undefined, staff_ids: staffIds.length ? staffIds : undefined });
      setAccepting(false);
      refetch();
      void qc.invalidateQueries({ queryKey: ["hosp-dashboard"] });
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };
  const reject = async () => {
    setBusy(true);
    try {
      await post(`/hospital/requests/${req.request_id}/reject`, { reason_code: reason, note: note || undefined });
      setRejecting(false);
      refetch();
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="border-2 border-red/30">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <AcuityBadge acuity={req.patient.acuity} size="lg" />
          <FacilityChip facility={req.patient.facility} />
          {req.patient.mlc_flag && <span className="rounded-full bg-amber-soft px-2.5 py-1 text-[13px] font-bold text-amber">Medico-legal</span>}
          {req.is_family_choice && <span className="rounded-full bg-blue-soft px-2.5 py-1 text-[13px] font-bold text-blue">Family choice</span>}
          {req.is_priority && <span className="rounded-full bg-red-soft px-2.5 py-1 text-[13px] font-bold text-red-ink">Priority</span>}
          {req.patient.confirmed_by_paramedic && <span className="flex items-center gap-1 rounded-full bg-green-soft px-2.5 py-1 text-[13px] font-bold text-green"><Icon name="check" size={13} stroke={3} />Confirmed by crew</span>}
        </div>
        <CountdownRing until={req.expires_at} total={req.is_priority ? 30 : req.patient.acuity === "critical" ? 45 : 60} size={64} stroke={7} />
      </div>

      <p className="mt-3 text-[20px] font-bold">{req.patient.display}{req.patient.temp_id ? ` · ${req.patient.temp_id}` : ""}</p>
      {req.profile && (
        <p className="mt-1 text-[16px]">
          {req.profile.blood_group && <>Blood <b>{req.profile.blood_group}</b> · </>}
          {req.profile.allergies.length ? <b className="text-red-ink">Allergy: {req.profile.allergies.join(", ")}</b> : null}
          {req.profile.conditions.length ? ` · ${req.profile.conditions.join(", ")}` : ""}
          {req.profile.medications.length ? ` · ${req.profile.medications.join(", ")}` : ""}
        </p>
      )}

      {req.handover_note && (
        <div className="mt-3 rounded-2xl bg-soft p-4 text-[15px] leading-relaxed">
          <p><b>S:</b> {req.handover_note.situation}</p>
          <p><b>B:</b> {req.handover_note.background}</p>
          <p><b>A:</b> {req.handover_note.assessment}</p>
          <p><b>R:</b> {req.handover_note.recommendation}</p>
        </div>
      )}

      {!!req.prep_checklist.length && (
        <div className="mt-3">
          <SectionLabel>Prepare</SectionLabel>
          <div className="mt-1.5 flex flex-col gap-1.5">
            {req.prep_checklist.map((p) => (
              <div key={p.item} className="flex items-center gap-2">
                <span className="w-36 shrink-0 text-[15px] capitalize">{p.item.replace(/_/g, " ")}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-soft-2"><div className="h-full rounded-full bg-blue" style={{ width: `${Math.round(p.prob * 100)}%` }} /></div>
                <span className="w-10 shrink-0 text-right text-[14px] text-muted">{Math.round(p.prob * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-3 flex items-center gap-3 rounded-2xl bg-soft p-3">
        <Icon name="ambulance" size={22} className="shrink-0 text-blue" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[16px] font-bold">{reg(req.ambulance.registration_no) || "Ambulance not yet assigned"}</p>
          <p className="text-[14px] text-muted">{req.ambulance.eta_sec != null ? `${minutes(req.ambulance.eta_sec)} min away` : ""}</p>
        </div>
        {req.ambulance.eta_sec != null && <span className="text-[22px] font-extrabold">{minutes(req.ambulance.eta_sec)}<span className="text-[13px] font-normal text-muted"> min</span></span>}
      </div>

      {!!req.why_you.length && <div className="mt-3"><SectionLabel>Why you</SectionLabel><div className="mt-1.5"><WhyYou reasons={req.why_you} /></div></div>}

      <div className="mt-4 grid grid-cols-2 gap-3">
        <Button size="lg" variant="dangerOutline" onClick={() => setRejecting(true)}>Reject</Button>
        <Button size="lg" variant="success" onClick={() => setAccepting(true)}><Icon name="check" size={22} stroke={2.8} />Accept</Button>
      </div>

      <Sheet open={accepting} onOpenChange={setAccepting} title="Accept this patient" description="Room and team are prefilled; change them if needed." wide
        footer={<Button size="lg" block loading={busy} onClick={() => void accept()}>Confirm and reserve</Button>}>
        <div className="flex flex-col gap-4">
          <div>
            <p className="mb-1.5 text-[16px] font-semibold">Room</p>
            <Select value={roomId} onChange={(e) => setRoomId(e.target.value)}>
              <option value="">Auto-allocate</option>
              {freeRooms.map((r) => <option key={r.id} value={r.id}>{r.code} · {r.type.replace(/_/g, " ")}</option>)}
            </Select>
          </div>
          <div>
            <p className="mb-1.5 text-[16px] font-semibold">Receiving team</p>
            <div className="flex flex-col gap-2">
              {staff.filter((s) => s.on_duty).slice(0, 8).map((s) => (
                <label key={s.id} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2.5">
                  <input type="checkbox" className="h-5 w-5" checked={staffIds.includes(s.id)} onChange={(e) => setStaffIds((xs) => (e.target.checked ? [...xs, s.id] : xs.filter((x) => x !== s.id)))} />
                  <span className="text-[16px]">{s.name} <span className="text-muted">· {(s.specialty ?? s.role ?? "").replace(/_/g, " ")}</span></span>
                </label>
              ))}
            </div>
          </div>
        </div>
      </Sheet>

      <Sheet open={rejecting} onOpenChange={setRejecting} title="Reject this request" description="A reason is required so the system can route around it."
        footer={<Button size="lg" variant="dangerOutline" block loading={busy} onClick={() => void reject()}>Confirm reject</Button>}>
        <div className="flex flex-col gap-4">
          <Select value={reason} onChange={(e) => setReason(e.target.value as RejectReason)}>
            {ENUMS.RejectReason.map((r) => <option key={r} value={r}>{REASON_LABEL[r]}</option>)}
          </Select>
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note (optional)" aria-label="Note" />
        </div>
      </Sheet>
    </Card>
  );
}
