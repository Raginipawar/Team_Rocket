import type { Category, Severity } from "./data";
import type { Channel, DemoState, Derived, ForWhom, Signal } from "./engine";
import { useDemo } from "./store";
import { T } from "./engine";

/** All user actions on the shared emergency, plus the live derived state. */
export function useDemoActions() {
  const demo = useDemo();
  const { update, reset, d } = demo;

  const now = () => Date.now();

  const actions = {
    sos: (forWhom: ForWhom, channel: Channel, text = "") =>
      update((s) => ({
        ...fresh(s), sosAt: now(), forWhom, channel, text,
      })),
    accept: () => update({ acceptedAt: now() }),
    confirm: (category: Category, severity: Severity, patients: number, changed: boolean) =>
      update({ confirmedAt: now(), confirm: { category, severity, patients, changed } }),
    hospitalAccept: (room: string) => update({ gfAcceptedAt: now(), room }),
    hospitalReject: (reason: string) => update({ gfRejectedAt: now(), gfRejectReason: reason }),
    familyChoice: (hospital: string, by: string) => update({ familyChoice: { hospital, at: now(), by } }),
    worsened: () => update({ worsenedAt: now(), confirm: { ...demo.s.confirm, severity: "critical" } }),
    arriveNow: () => update({ acceptedAt: now() - T.driveToPatient }),
    received: () => update({ receivedAt: now() }),
    ready: () => update({ readyAt: now() }),
    cancel: (reason: string) => update({ cancelledAt: now(), cancelReason: reason }),
    close: () => update({ closedAt: now() }),
    answer: (id: string, answer: string) =>
      update((s) => ({ answers: [...s.answers.filter((a) => a.id !== id), { id, answer, at: now() }] })),
    setOnline: (online: boolean) => update({ online }),
    setSignal: (signal: Signal) => update({ signal }),
    setAutoplay: (autoplay: boolean) => update({ autoplay, autoplaySince: now() }),
    reset,
  };

  /** Performs whichever action moves the emergency forward from where it is now. */
  const next = () => {
    switch (d.stage) {
      case "idle": case "cancelled": return actions.sos("papa", "voice");
      case "offered": return actions.accept();
      case "arrived": return actions.confirm("cardiac", "critical", 1, false);
      case "asking": return d.hospitalId === "greenfield" ? actions.hospitalAccept("Resus Bay 2") : undefined;
      case "atDoor": return actions.received();
      case "handedOver": return d.ambulance === "cleaning" ? actions.ready() : actions.close();
      default: return undefined;
    }
  };

  return { ...demo, actions: { ...actions, next } };
}

function fresh(s: DemoState): Partial<DemoState> {
  return {
    acceptedAt: null, confirmedAt: null, gfAcceptedAt: null, gfRejectedAt: null, gfRejectReason: "",
    familyChoice: null, worsenedAt: null, receivedAt: null, readyAt: null, cancelledAt: null,
    cancelReason: "", closedAt: null, answers: [], confirm: { ...s.confirm, category: "cardiac", severity: "critical", changed: false },
  };
}

export const STAGE_LABEL: Record<Derived["stage"], string> = {
  idle: "Waiting for an SOS",
  sending: "Sending request",
  requested: "Help requested",
  offered: "Offered to 4 ambulances",
  going: "Ambulance going to patient",
  arrived: "At scene, paramedic to confirm",
  choosing: "Choosing the best hospital",
  asking: "Asking the hospital",
  transporting: "Taking patient to hospital",
  atDoor: "At the hospital door",
  handedOver: "Handed over to doctors",
  cancelled: "Cancelled",
};
