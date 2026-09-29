import { hospitalById } from "./data";

/** Room, gate, receiving team and "why" chips for whichever hospital accepted. */
export function hospitalInfo(id: string, room = "Resus Bay 2") {
  const h = hospitalById(id);
  if (id === "greenfield") {
    return {
      h, room, gate: "Emergency Gate 2", team: "Dr. A. Kulkarni's team", doctor: "Dr. A. Kulkarni", er: "02027650000", eta: 11,
      why: [{ icon: "check", text: "Cath lab available" }, { icon: "doctor", text: "Cardiologist on duty at arrival" }, { icon: "clock", text: "11 min away" }],
    };
  }
  if (id === "riverside") {
    return {
      h, room: "ER Bay 4", gate: "Gate 1", team: "Dr. M. Rao's team", doctor: "Dr. M. Rao", er: "02027650111", eta: 6,
      why: [{ icon: "bed", text: "Bed likely free (82%)" }, { icon: "doctor", text: "Emergency physician on duty" }, { icon: "clock", text: "6 min away" }],
    };
  }
  return {
    h, room: "ER Bay 1", gate: "Main Gate", team: "Emergency team", doctor: "Duty doctor", er: "02027650222", eta: 14,
    why: [{ icon: "check", text: "Chosen by family" }, { icon: "clock", text: "14 min away" }],
  };
}
