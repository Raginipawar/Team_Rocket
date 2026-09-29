"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, errorText, patch } from "@/lib/api";
import type { Room } from "@/lib/api-types";
import { ENUMS, type OverrideReason, type RoomStatus } from "@/lib/enums";
import { useHosp } from "../context";
import { minutes, reg } from "@/lib/format";
import { Card, LoadingState, Select, ErrorState } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import Icon from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/cn";

const STATUS_STYLE: Record<RoomStatus, string> = {
  free: "border-green/40 bg-green-soft text-green", reserved: "border-amber/40 bg-amber-soft text-amber",
  occupied: "border-line bg-soft text-ink", cleaning: "border-blue/40 bg-blue-soft text-blue", out_of_service: "border-red/30 bg-red-soft text-red-ink",
};
const STATUS_LABEL: Record<RoomStatus, string> = { free: "Free", reserved: "Reserved", occupied: "Occupied", cleaning: "Cleaning", out_of_service: "Out of service" };
const OVERRIDE_LABEL: Record<OverrideReason, string> = { WALK_IN_CRITICAL: "Walk-in critical patient", BED_UNUSABLE: "Bed unusable", INTERNAL_TRANSFER: "Internal transfer", OTHER: "Other" };

export default function RoomsPage() {
  const { dashboard, loading, error, refetch } = useHosp();
  const qc = useQueryClient();
  const toast = useToast();
  const [target, setTarget] = useState<Room | null>(null);
  const [nextStatus, setNextStatus] = useState<RoomStatus>("occupied");
  const [overrideReason, setOverrideReason] = useState<OverrideReason>("WALK_IN_CRITICAL");
  const [needOverride, setNeedOverride] = useState(false);
  const [busy, setBusy] = useState(false);

  if (loading) return <LoadingState />;
  if (error || !dashboard) return <ErrorState text="Could not load rooms" onRetry={refetch} />;

  const setStatus = async (room: Room, status: RoomStatus, reason?: OverrideReason) => {
    setBusy(true);
    try {
      await patch(`/hospital/rooms/${room.id}`, { status, version: room.version, override_reason: reason });
      setTarget(null);
      setNeedOverride(false);
      refetch();
      toast("Updated", "success");
    } catch (e) {
      if (e instanceof ApiError && e.code === "ROOM_RESERVED") {
        setNeedOverride(true);
      } else {
        toast(errorText(e), "error");
        if (e instanceof ApiError && e.code === "VERSION_CONFLICT") refetch();
      }
    } finally {
      setBusy(false);
    }
  };

  const open = (room: Room) => {
    setTarget(room);
    setNextStatus(room.status === "free" ? "occupied" : room.status === "occupied" ? "cleaning" : room.status === "cleaning" ? "free" : "occupied");
    setNeedOverride(false);
  };

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-[26px] font-extrabold">Rooms</h1>
      {Object.entries(dashboard.rooms).map(([type, rooms]) => (
        <section key={type}>
          <h2 className="mb-3 text-[18px] font-bold capitalize">{type.replace(/_/g, " ")}s <span className="font-normal text-muted">· {rooms.filter((r) => r.status === "free").length} free</span></h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {rooms.map((r) => (
              <button key={r.id} onClick={() => open(r)} className={cn("flex flex-col gap-1 rounded-2xl border-2 p-4 text-left", STATUS_STYLE[r.status])}>
                <span className="text-[18px] font-extrabold">{r.code}</span>
                <span className="text-[14px] font-semibold">{STATUS_LABEL[r.status]}</span>
                {r.reservation && <span className="text-[13px] leading-snug">{reg(r.reservation.registration_no)}{r.reservation.eta_sec != null ? ` · ETA ${minutes(r.reservation.eta_sec)} min` : ""}</span>}
                {r.occupant && r.status === "occupied" && <span className="truncate text-[13px]">{r.occupant}</span>}
              </button>
            ))}
          </div>
        </section>
      ))}

      <Sheet open={!!target} onOpenChange={(o) => { if (!o) { setTarget(null); setNeedOverride(false); } }} title={target ? `Room ${target.code}` : ""}
        footer={target && (
          <Button size="lg" block variant={needOverride ? "danger" : "primary"} loading={busy} onClick={() => void setStatus(target, nextStatus, needOverride ? overrideReason : undefined)}>
            {needOverride ? "Confirm override" : "Update"}
          </Button>
        )}>
        {target && (
          <div className="flex flex-col gap-4">
            <div>
              <p className="mb-1.5 text-[16px] font-semibold">New status</p>
              <Select value={nextStatus} onChange={(e) => { setNextStatus(e.target.value as RoomStatus); setNeedOverride(false); }}>
                {ENUMS.RoomStatus.filter((s) => s !== "reserved").map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
              </Select>
            </div>
            {target.status === "reserved" && (
              <p className="flex items-start gap-2 rounded-2xl bg-amber-soft p-3 text-[15px] text-amber"><Icon name="alert" size={18} className="mt-0.5 shrink-0" />This room is held for {reg(target.reservation?.registration_no ?? "")}. Changing it needs a reason.</p>
            )}
            {needOverride && (
              <div>
                <p className="mb-1.5 text-[16px] font-semibold">Reason for override</p>
                <Select value={overrideReason} onChange={(e) => setOverrideReason(e.target.value as OverrideReason)}>
                  {ENUMS.OverrideReason.map((r) => <option key={r} value={r}>{OVERRIDE_LABEL[r]}</option>)}
                </Select>
              </div>
            )}
          </div>
        )}
      </Sheet>
    </div>
  );
}
