import type { Derived } from "./engine";
import { clock } from "./format";

/** The 6-step patient / family status stepper (spec 2.9), with the time each step was reached. */
export function patientSteps(d: Derived, sosAt: number | null, now: number) {
  const marks: [string, number | null][] = [
    ["Help requested", sosAt],
    ["Ambulance on the way", d.accepted],
    ["Ambulance arrived", d.arrivedAt],
    ["Going to hospital", d.confirmed],
    ["At hospital", d.doorAt],
    ["Handed over to doctors", d.received],
  ];
  const firstTodo = marks.findIndex(([, t]) => t === null || t > now);
  return marks.map(([label, t], i) => ({
    label,
    time: t !== null && t <= now ? clock(t) : undefined,
    state: (firstTodo === -1 || i < firstTodo ? "done" : i === firstTodo ? "current" : "todo") as "done" | "current" | "todo",
  }));
}
