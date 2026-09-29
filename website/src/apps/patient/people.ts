import { PEOPLE } from "../../demo/data";

/** Display name for whoever the emergency is for. */
export function whoLabel(forWhom: string) {
  if (forWhom === "someone") return "someone else";
  if (forWhom === "rahul") return "you";
  return PEOPLE.find((p) => p.id === forWhom)?.short ?? "Papa";
}

export function whoPerson(forWhom: string) {
  return PEOPLE.find((p) => p.id === forWhom) ?? null;
}

const LOC_KEY = "gh-location";
export function getLocation() {
  try {
    return localStorage.getItem(LOC_KEY) || "Sector 26, Pradhikaran, Akurdi";
  } catch {
    return "Sector 26, Pradhikaran, Akurdi";
  }
}
export function saveLocation(label: string) {
  try {
    localStorage.setItem(LOC_KEY, label);
  } catch {
    /* ignore */
  }
}
