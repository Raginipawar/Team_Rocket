// Mirror of packages/contracts/enums.json (technical.md §3) with literal types.
// `npm run check:contracts` fails the build if this file and the JSON drift apart,
// so enums.json stays the single definition.

export const ENUMS = {
  Role: ["patient", "paramedic", "hospital_staff", "developer"],
  Acuity: ["critical", "urgent", "stable"],
  Facility: ["cardiac", "stroke", "trauma", "burns", "respiratory", "obstetric", "pediatric", "poisoning", "general"],
  AmbulanceType: ["BLS", "ALS"],
  AmbulanceStatus: ["offline", "available", "dispatched", "at_scene", "transporting", "at_hospital", "cleaning", "out_of_service"],
  EmergencyStatus: [
    "received", "triaged", "dispatching", "ambulance_assigned", "at_scene", "patient_on_board",
    "hospital_selecting", "hospital_confirmed", "arrived_hospital", "handed_off", "closed",
    "cancelled", "refused_transport", "merged_duplicate",
  ],
  Channel: ["app_button", "app_voice", "app_text", "sms"],
  OfferStatus: ["pending", "accepted", "declined", "expired", "superseded"],
  HospitalRequestStatus: ["pending", "accepted", "rejected", "timeout", "cancelled", "superseded"],
  ReservationStatus: ["held", "confirmed", "consumed", "released", "expired", "overridden"],
  RoomType: ["er_bed", "resus_bay", "trauma_bay", "icu_bed", "labour_room", "burns_unit", "pediatric_er"],
  RoomStatus: ["free", "reserved", "occupied", "cleaning", "out_of_service"],
  ResourceType: [
    "ventilator", "cath_lab", "ct_scanner", "mri", "defibrillator", "blood_o_neg", "blood_o_pos",
    "blood_a_pos", "blood_b_pos", "blood_ab_pos", "dialysis", "operating_theatre",
  ],
  Capability: [
    "cardiac_cathlab", "stroke_thrombolysis", "trauma_center", "burns_unit", "obstetrics",
    "pediatrics", "toxicology", "icu", "neurosurgery", "general_er",
  ],
  StaffSpecialty: [
    "emergency_physician", "cardiologist", "neurologist", "trauma_surgeon", "burns_surgeon",
    "obstetrician", "pediatrician", "pulmonologist", "anesthetist", "er_nurse",
  ],
  RejectReason: ["NO_BED", "NO_SPECIALIST", "EQUIPMENT_DOWN", "OVER_CAPACITY", "NOT_EQUIPPED_FOR_CASE", "OTHER"],
  OverrideReason: ["WALK_IN_CRITICAL", "BED_UNUSABLE", "INTERNAL_TRANSFER", "OTHER"],
  EscalationType: ["mass_casualty", "no_ambulance", "no_hospital", "system_anomaly"],
  EscalationStatus: ["open", "claimed", "resolved", "auto_defaulted"],
  Freshness: ["fresh", "aging", "stale"],
  Language: ["hi", "mr", "en", "hi-en", "mr-en"],
} as const;

type E = typeof ENUMS;
export type Role = E["Role"][number];
export type Acuity = E["Acuity"][number];
export type Facility = E["Facility"][number];
export type AmbulanceType = E["AmbulanceType"][number];
export type AmbulanceStatus = E["AmbulanceStatus"][number];
export type EmergencyStatus = E["EmergencyStatus"][number];
export type Channel = E["Channel"][number];
export type OfferStatus = E["OfferStatus"][number];
export type HospitalRequestStatus = E["HospitalRequestStatus"][number];
export type ReservationStatus = E["ReservationStatus"][number];
export type RoomType = E["RoomType"][number];
export type RoomStatus = E["RoomStatus"][number];
export type ResourceType = E["ResourceType"][number];
export type Capability = E["Capability"][number];
export type StaffSpecialty = E["StaffSpecialty"][number];
export type RejectReason = E["RejectReason"][number];
export type OverrideReason = E["OverrideReason"][number];
export type EscalationType = E["EscalationType"][number];
export type EscalationStatus = E["EscalationStatus"][number];
export type Freshness = E["Freshness"][number];
export type Language = E["Language"][number];

/** Statuses after which an emergency is over for the caller. */
export const FINAL_STATUSES: readonly EmergencyStatus[] = ["handed_off", "closed", "cancelled", "refused_transport", "merged_duplicate"];

/** Room types each facility may use (technical.md §11.5). */
export const ACCEPTABLE_ROOMS: Record<Facility, RoomType[]> = {
  cardiac: ["resus_bay", "er_bed"],
  stroke: ["resus_bay", "er_bed"],
  trauma: ["trauma_bay", "resus_bay"],
  burns: ["burns_unit", "resus_bay"],
  respiratory: ["resus_bay", "er_bed", "icu_bed"],
  obstetric: ["labour_room"],
  pediatric: ["pediatric_er", "er_bed"],
  poisoning: ["er_bed", "resus_bay"],
  general: ["er_bed", "resus_bay"],
};

/** Capability a hospital needs for each facility (hard constraint, technical.md §9.13). */
export const REQUIRED_CAPABILITY: Record<Facility, Capability> = {
  cardiac: "cardiac_cathlab",
  stroke: "stroke_thrombolysis",
  trauma: "trauma_center",
  burns: "burns_unit",
  respiratory: "icu",
  obstetric: "obstetrics",
  pediatric: "pediatrics",
  poisoning: "toxicology",
  general: "general_er",
};

/** Specialist the receiving team needs for each facility. */
export const FACILITY_SPECIALIST: Record<Facility, StaffSpecialty> = {
  cardiac: "cardiologist",
  stroke: "neurologist",
  trauma: "trauma_surgeon",
  burns: "burns_surgeon",
  respiratory: "pulmonologist",
  obstetric: "obstetrician",
  pediatric: "pediatrician",
  poisoning: "emergency_physician",
  general: "emergency_physician",
};
