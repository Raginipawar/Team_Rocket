// Sample data pack, from frontend-screens spec section 9. Everything here is fictional and simulated.

export type Severity = "critical" | "urgent" | "stable";
export type Category =
  | "cardiac" | "stroke" | "trauma" | "burns" | "respiratory"
  | "obstetric" | "pediatric" | "poisoning" | "general";

export const CATEGORY_LABEL: Record<Category, string> = {
  cardiac: "Heart",
  stroke: "Stroke",
  trauma: "Accident / Injury",
  burns: "Burns",
  respiratory: "Breathing",
  obstetric: "Pregnancy",
  pediatric: "Child",
  poisoning: "Poisoning",
  general: "General",
};
export const CATEGORIES = Object.keys(CATEGORY_LABEL) as Category[];

export const SEVERITY_LABEL: Record<Severity, string> = { critical: "Critical", urgent: "Urgent", stable: "Stable" };

export interface Person {
  id: string;
  name: string;
  short: string;
  relation: string;
  age: number;
  sex: "M" | "F";
  blood: string;
  allergies: string[];
  conditions: string[];
  medicines: string[];
  role: "Admin" | "Member" | "Dependent";
  phone?: string;
}

export const PEOPLE: Person[] = [
  { id: "rahul", name: "Rahul Kulkarni", short: "Rahul", relation: "Me", age: 32, sex: "M", blood: "O+", allergies: [], conditions: [], medicines: [], role: "Admin", phone: "+91 98XXX XX321" },
  { id: "papa", name: "Rajesh Kulkarni", short: "Papa", relation: "Father", age: 61, sex: "M", blood: "B+", allergies: ["Aspirin"], conditions: ["Diabetes"], medicines: ["Metformin 500 mg twice daily"], role: "Member", phone: "+91 98XXX XX540" },
  { id: "aai", name: "Sunita Kulkarni", short: "Aai", relation: "Mother", age: 57, sex: "F", blood: "A+", allergies: [], conditions: ["High BP"], medicines: ["Amlodipine 5 mg"], role: "Member", phone: "+91 98XXX XX118" },
  { id: "riya", name: "Riya Kulkarni", short: "Riya", relation: "Sister", age: 26, sex: "F", blood: "O+", allergies: [], conditions: [], medicines: [], role: "Member", phone: "+91 98XXX XX902" },
  { id: "aaji", name: "Aaji", short: "Aaji", relation: "Grandmother", age: 84, sex: "F", blood: "B+", allergies: [], conditions: ["Heart disease", "Uses walker"], medicines: [], role: "Dependent" },
];

export const CONTACTS = [
  { id: "prakash", name: "Uncle Prakash", relation: "Uncle", phone: "+91 98XXX XX876", lang: "Marathi" },
  { id: "meera", name: "Meera Deshpande", relation: "Neighbour", phone: "+91 97XXX XX210", lang: "English" },
];

export interface Hospital {
  id: string;
  name: string;
  area: string;
  address: string;
  strengths: string;
  free: string;
  x: number;
  y: number;
}

// x / y are positions on the schematic demo map (viewBox 1000 x 700).
export const HOSPITALS: Hospital[] = [
  { id: "greenfield", name: "Greenfield Heart Centre", area: "Nigdi", address: "Plot 12, Nigdi", strengths: "Cath lab, cardiology, ICU", free: "ER 4, Resus 1, ICU 2", x: 205, y: 150 },
  { id: "riverside", name: "Riverside Multispeciality", area: "Akurdi", address: "Link Road, Akurdi", strengths: "General ER, ICU, trauma", free: "ER 6, ICU 3", x: 355, y: 300 },
  { id: "northgate", name: "Northgate Trauma Centre", area: "Chinchwad", address: "Station Road, Chinchwad", strengths: "Trauma, neurosurgery", free: "Trauma bays 1", x: 470, y: 245 },
  { id: "metro", name: "Metro Neuro & Stroke Centre", area: "Pimpri", address: "Old Mumbai Highway, Pimpri", strengths: "Stroke, CT, neurology", free: "ER 2", x: 585, y: 320 },
  { id: "lotus", name: "Lotus Women & Child Hospital", area: "Ravet", address: "BRTS Road, Ravet", strengths: "Maternity, pediatrics", free: "Labour 2, Pediatric ER 3", x: 150, y: 330 },
  { id: "sunrise", name: "Sunrise Burns & Plastic Care", area: "Bhosari", address: "MIDC, Bhosari", strengths: "Burns unit", free: "Burns 1", x: 700, y: 180 },
  { id: "hillview", name: "Hillview Medical College Hospital", area: "Wakad", address: "Datta Mandir Road, Wakad", strengths: "Large general ER, all basics", free: "ER 10, ICU 4", x: 420, y: 520 },
  { id: "unity", name: "Unity Community Hospital", area: "Dehu Road", address: "Main Road, Dehu Road", strengths: "Stabilisation, general ER", free: "ER 3", x: 70, y: 110 },
];
export const hospitalById = (id: string) => HOSPITALS.find((h) => h.id === id) ?? HOSPITALS[0];

export const AMBULANCES = [
  { reg: "MH14 AB 1234", type: "ALS" as const, status: "On job", crew: "Sanjay Patil" },
  { reg: "MH14 CD 5678", type: "ALS" as const, status: "Available", crew: "Amit Pawar" },
  { reg: "MH14 EF 2211", type: "BLS" as const, status: "Available", crew: "Kiran Jadhav" },
  { reg: "MH14 GH 7420", type: "BLS" as const, status: "Cleaning", crew: "Nilesh More" },
  { reg: "MH14 JK 3095", type: "ALS" as const, status: "Offline", crew: "" },
];

// Map geometry. Pickup: near Ganesh Temple, Sector 26, Pradhikaran, Akurdi.
export const PICKUP = { x: 275, y: 225, label: "Near Ganesh Temple, Akurdi", address: "Sector 26, Pradhikaran, Akurdi" };
export const ROUTE_TO_PATIENT: [number, number][] = [[520, 410], [470, 400], [430, 340], [360, 330], [330, 270], [275, 225]];
export const ROUTE_TO_HOSPITAL: Record<string, [number, number][]> = {
  greenfield: [[275, 225], [250, 190], [230, 170], [205, 150]],
  riverside: [[275, 225], [310, 260], [340, 285], [355, 300]],
  lotus: [[275, 225], [230, 260], [190, 300], [150, 330]],
  hillview: [[275, 225], [330, 270], [380, 380], [420, 520]],
};

export interface Question {
  id: string;
  text: string;
  kind: "yesno" | "choice";
  choices?: string[];
}

export const QUESTIONS: Question[] = [
  { id: "awake", text: "Is he awake and responding?", kind: "yesno" },
  { id: "breathing", text: "Is he breathing normally?", kind: "yesno" },
  { id: "spread", text: "Is the pain spreading to his arm, jaw or back?", kind: "yesno" },
  { id: "since", text: "When did the pain start?", kind: "choice", choices: ["Under 30 min", "30 min to 2 h", "Over 2 h"] },
  { id: "before", text: "Has he had a heart problem before?", kind: "yesno" },
];
export const QUESTION_SHORT: Record<string, string> = {
  awake: "Awake", breathing: "Breathing normally", spread: "Pain spreading to arm", since: "Pain started", before: "Heart problem before",
};

export const QUESTIONS_BY_CATEGORY: Record<string, string> = {
  Heart: "Is he awake and responding? · Is he breathing normally? · Is the pain spreading to arm, jaw or back? · When did it start? · Heart problem before?",
  Stroke: "Is one side of the face drooping? · Can he lift both arms? · Is his speech slurred? · When was he last normal? · Is he on blood thinners?",
  Accident: "How many people are hurt? · Is anyone unconscious? · Is there heavy bleeding? · Can they move their neck and legs? · Is anyone trapped?",
  Burns: "What caused the burn? · Is the face or airway burned? · How big is the burn (palm sizes)? · Is the person breathing normally?",
  Breathing: "Can he speak full sentences? · Are lips blue? · Does he have asthma? · Is he using an inhaler?",
  Pregnancy: "How many months pregnant? · Is there bleeding? · Are contractions regular? · Has the water broken?",
  Child: "How old is the child? · Is the child awake and crying? · Any fever or fits? · Did the child swallow something?",
  Poisoning: "What was taken? · How much and when? · Is the person awake? · Vomiting?",
  General: "Is the person awake? · Breathing normally? · Any bleeding? · How long has this been happening?",
};

export const FIRST_AID_CHEST = {
  title: "While you wait: chest pain",
  steps: [
    "Help him sit down, leaning slightly back, knees bent.",
    "Loosen tight clothing.",
    "Keep him calm and still.",
    "If he stops responding and isn't breathing normally, start chest compressions (tap below).",
  ],
  donts: ["Don't give food or water", "Don't let him walk", "Don't give medicines he's allergic to (Aspirin is a listed allergy)"],
};

export const CPR = {
  title: "Hands-only CPR",
  steps: [
    "Place him flat on his back on a hard surface.",
    "Put the heel of your hand in the centre of the chest, other hand on top.",
    "Push hard and fast, about 2 per second.",
    "Don't stop until the ambulance crew takes over.",
  ],
};

export const FIRST_AID_TITLES = [
  "Hands-only CPR", "Choking", "Severe bleeding", "Burns", "Stroke: while you wait", "Chest pain: while you wait",
  "Seizure / fits", "Poisoning", "Broken bone / neck injury: don't move", "Labour / delivery", "Unconscious but breathing (recovery position)",
];

export const REASONS = {
  reject: ["No bed", "No specialist", "Equipment down", "Over capacity", "Not equipped for this case", "Other"],
  roomOverride: ["Walk-in critical patient", "Bed unusable", "Internal transfer", "Other"],
  cancel: ["Patient is better", "Going by own vehicle", "Reported by mistake", "Other"],
  decline: ["Too far", "Vehicle issue", "On break", "Other"],
};

export const TEAM = ["Dr. A. Kulkarni (Cardiology)", "Dr. R. Shah (Emergency)", "Nurse P. Joshi"];
export const CASE_ID = "GH-4821";
export const TRACK_TOKEN = "8Kq2";
