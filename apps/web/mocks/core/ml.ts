// ML client for the mock core. The primary path is the team's real ML service
// (services/ml, technical.md §9) at ML_BASE_URL. If it is not running, each call
// falls back to a deterministic local rule (the same idea as ML_MODE=mock), and the
// returned model_version says "fallback" so the UI never presents a rule as a model.
// Follow-up questions and first-aid scripts are read from the real protocol files in
// services/ml/app/protocols, so the wording is identical in both paths.

import { readFileSync, readdirSync, existsSync } from "node:fs";
import path from "node:path";
import type { Acuity, Facility } from "../../lib/enums";
import type { FirstAid, PrepItem, Sbar } from "../../lib/api-types";
import { MOCK } from "./config";
import type { ExtractedFacts } from "./world";

const PROTOCOLS = path.resolve(process.cwd(), "../../services/ml/app/protocols");

let mlUp: boolean | null = null;
let mlCheckedAt = 0;

async function post<T>(p: string, body: unknown): Promise<T | null> {
  if (mlUp === false && Date.now() - mlCheckedAt < 30_000) return null;
  try {
    const res = await fetch(`${MOCK.ML_BASE_URL}/ml/v1${p}`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
      signal: AbortSignal.timeout(MOCK.ML_TIMEOUT_MS),
    });
    mlUp = true;
    mlCheckedAt = Date.now();
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    if (mlUp !== false) console.warn(`[mock-core] ML service not reachable at ${MOCK.ML_BASE_URL}, using local fallbacks`);
    mlUp = false;
    mlCheckedAt = Date.now();
    return null;
  }
}

export function mlStatus() {
  return mlUp === true ? "ok" : mlUp === false ? "unreachable" : "unknown";
}

/* ---------- protocols (real files) ---------- */
type ProtoQuestion = { id: string; field: string; answer_type: string; priority: number; choices?: string[]; text: Record<string, string> };
type Proto = { facility: string; questions: ProtoQuestion[] };
type AidFile = { protocol_id: string; title: Record<string, string>; steps: Record<string, string[]>; donts: Record<string, string[]>; rule?: Record<string, unknown> };

const followups = new Map<string, Proto>();
const aids = new Map<string, AidFile>();

function loadProtocols() {
  if (followups.size) return;
  const fdir = path.join(PROTOCOLS, "followup");
  const adir = path.join(PROTOCOLS, "first_aid");
  if (existsSync(fdir)) for (const f of readdirSync(fdir).filter((x) => x.endsWith(".json"))) {
    const p = JSON.parse(readFileSync(path.join(fdir, f), "utf8")) as Proto;
    followups.set(p.facility, p);
  }
  if (existsSync(adir)) for (const f of readdirSync(adir).filter((x) => x.endsWith(".json"))) {
    const a = JSON.parse(readFileSync(path.join(adir, f), "utf8")) as AidFile;
    aids.set(a.protocol_id, a);
  }
  console.log(`[mock-core] loaded ${followups.size} follow-up trees and ${aids.size} first-aid scripts from services/ml/app/protocols`);
}

const lang3 = (l: string) => (l.startsWith("hi") ? "hi" : l.startsWith("mr") ? "mr" : "en");

/* ---------- extraction (§9.2) ---------- */
const WORDS: [RegExp, string][] = [
  [/chest|seene|seena|छाती|सीने|heart|dil|हृदय|दिल/i, "chest_pain"],
  [/breath|saans|श्वास|सांस|choking/i, "breathing_difficulty"],
  [/sweat|pasina|घाम|पसीना/i, "sweating"],
  [/unconscious|behosh|बेहोश|बेशुद्ध|not waking|fainted|collapsed/i, "unconscious"],
  [/bleed|blood|khoon|रक्त|खून/i, "bleeding"],
  [/accident|crash|hit by|takkar|अपघात|दुर्घटना|bike|truck/i, "road_accident"],
  [/burn|jal|भाजल|जल गया|fire|aag/i, "burn"],
  [/pregnan|labour|labor|delivery|गर्भ|प्रसूती|प्रसव/i, "pregnancy"],
  [/stroke|paralys|face drooping|slurred|लकवा|अर्धांग/i, "stroke_signs"],
  [/poison|zeher|विष|जहर|pesticide|overdose/i, "poisoning"],
  [/seizure|fits|jhatke|झटके|फिट/i, "seizure"],
  [/child|baby|bachcha|बाळ|बच्चा|infant/i, "child"],
  [/fell|fall|fracture|broken|haddi|हाड/i, "fall"],
];

export async function extract(text: string, language: string): Promise<{ facts: ExtractedFacts; model_version: string }> {
  const real = await post<ExtractedFacts & { model_version: string }>("/extract", { text, language });
  if (real) return { facts: real, model_version: real.model_version || "extract" };
  const symptoms = WORDS.filter(([re]) => re.test(text)).map(([, s]) => s);
  const age = Number(text.match(/(\d{1,2})\s*(?:year|yr|sal|साल|वर्ष)/i)?.[1] ?? NaN);
  const count = Number(text.match(/(\d+)\s*(?:people|log|लोग|जण|injured|hurt)/i)?.[1] ?? 1);
  const facts: ExtractedFacts = {
    age: Number.isFinite(age) ? age : null,
    sex: /\b(he|him|father|papa|husband|man|male|baba|वडील|पिता)\b/i.test(text) ? "male" : /\b(she|her|mother|aai|wife|woman|female|आई|माँ)\b/i.test(text) ? "female" : null,
    patient_count: Math.max(1, Math.min(20, count)),
    conscious: symptoms.includes("unconscious") ? false : null,
    breathing: /not breathing|no breath|सांस नहीं|श्वास नाही/i.test(text) ? "absent" : symptoms.includes("breathing_difficulty") ? "difficult" : null,
    bleeding: symptoms.includes("bleeding") ? "heavy" : null,
    symptoms,
    mechanism: symptoms.includes("road_accident") ? "road_accident" : symptoms.includes("fall") ? "fall" : symptoms.includes("burn") ? "burn" : "none",
    pregnant: symptoms.includes("pregnancy"),
    landmark: text.match(/near ([^,.]+)/i)?.[1]?.trim() ?? null,
    coherence: text.length > 12 ? 0.8 : 0.4,
  };
  return { facts, model_version: "fallback-keywords" };
}

/* ---------- triage (§9.3) ---------- */
export type TriageOut = { acuity: Acuity; facility: Facility; confidence: number; needs_review: boolean; fragility: boolean; mlc_flag: boolean; model_version: string };

export async function triage(text: string, facts: ExtractedFacts, profileSummary: string | null): Promise<TriageOut> {
  const real = await post<TriageOut>("/triage", { text, extracted: facts, profile_summary: profileSummary, followup_answers: [] });
  if (real) return real;
  const s = new Set(facts.symptoms ?? []);
  let facility: Facility = "general";
  if (s.has("pregnancy")) facility = "obstetric";
  else if (s.has("burn")) facility = "burns";
  else if (s.has("poisoning")) facility = "poisoning";
  else if (s.has("stroke_signs")) facility = "stroke";
  else if (s.has("chest_pain")) facility = "cardiac";
  else if (s.has("road_accident") || s.has("fall") || s.has("bleeding")) facility = "trauma";
  else if (s.has("child")) facility = "pediatric";
  else if (s.has("breathing_difficulty")) facility = "respiratory";
  const critical = s.has("unconscious") || facts.breathing === "absent" || facility === "cardiac" || facility === "stroke" || facts.bleeding === "heavy" || facts.conscious === false;
  const acuity: Acuity = critical ? "critical" : s.size ? "urgent" : "urgent";
  const confidence = !text ? 0.35 : s.size >= 2 ? 0.86 : s.size === 1 ? 0.72 : 0.45;
  return {
    acuity, facility, confidence,
    needs_review: confidence < 0.6,
    fragility: facts.pregnant === true || facility === "pediatric" || s.has("fall"),
    mlc_flag: facts.mechanism === "road_accident" || facility === "burns" || facility === "poisoning",
    model_version: "fallback-rules",
  };
}

/* ---------- resources (§9.10) ---------- */
const PREP: Record<Facility, PrepItem[]> = {
  cardiac: [{ item: "cardiologist", prob: 0.94 }, { item: "cath_lab", prob: 0.88 }, { item: "defibrillator", prob: 0.81 }],
  stroke: [{ item: "neurologist", prob: 0.93 }, { item: "ct_scanner", prob: 0.91 }, { item: "mri", prob: 0.55 }],
  trauma: [{ item: "trauma_surgeon", prob: 0.9 }, { item: "operating_theatre", prob: 0.74 }, { item: "blood_o_neg", prob: 0.7 }],
  burns: [{ item: "burns_surgeon", prob: 0.92 }, { item: "ventilator", prob: 0.35 }],
  respiratory: [{ item: "ventilator", prob: 0.78 }, { item: "pulmonologist", prob: 0.7 }],
  obstetric: [{ item: "obstetrician", prob: 0.96 }, { item: "pediatrician", prob: 0.62 }],
  pediatric: [{ item: "pediatrician", prob: 0.95 }],
  poisoning: [{ item: "emergency_physician", prob: 0.9 }, { item: "ventilator", prob: 0.4 }],
  general: [{ item: "emergency_physician", prob: 0.9 }, { item: "er_nurse", prob: 0.9 }],
};

export async function resources(acuity: Acuity, facility: Facility, facts: ExtractedFacts, blood: string | null): Promise<{ items: PrepItem[]; model_version: string }> {
  const real = await post<{ resources: PrepItem[]; model_version: string }>("/resources", { acuity, facility, extracted: facts });
  if (real) return { items: real.resources, model_version: real.model_version };
  const items = [...PREP[facility]];
  if (blood && (facility === "trauma" || facts.bleeding === "heavy")) items.push({ item: `blood_${blood.toLowerCase().replace("+", "_pos").replace("-", "_neg")}`, prob: 0.72 });
  if (acuity === "critical" && !items.some((i) => i.item === "defibrillator")) items.push({ item: "defibrillator", prob: 0.5 });
  return { items, model_version: "fallback-table" };
}

/* ---------- follow-up questions (§9.7) ---------- */
export async function nextQuestion(facility: Facility, acuity: Acuity, facts: ExtractedFacts, answers: { question_id: string; answer: string }[], language: string) {
  const real = await post<{ question: { id: string; text: string; answer_type: string; choices?: string[] | null; audio_url?: string | null } | null; done: boolean; model_version: string }>(
    "/followup/next", { facility, acuity, extracted: facts, answers, language: lang3(language) },
  );
  if (real) return real;
  loadProtocols();
  const tree = followups.get(facility) ?? followups.get("general");
  if (!tree || answers.length >= 5) return { question: null, done: true, model_version: "fallback-protocol" };
  const answered = new Set(answers.map((a) => a.question_id));
  const q = [...tree.questions].sort((a, b) => a.priority - b.priority).find((x) => !answered.has(x.id));
  if (!q) return { question: null, done: true, model_version: "fallback-protocol" };
  const l = lang3(language);
  return { question: { id: q.id, text: q.text[l] ?? q.text.en, answer_type: q.answer_type, choices: q.choices ?? null, audio_url: null }, done: false, model_version: "fallback-protocol" };
}

export function questionField(facility: Facility, questionId: string): string | null {
  loadProtocols();
  for (const t of [followups.get(facility), ...followups.values()]) {
    const q = t?.questions.find((x) => x.id === questionId);
    if (q) return q.field;
  }
  return null;
}

export function questionText(questionId: string): string {
  loadProtocols();
  for (const t of followups.values()) {
    const q = t.questions.find((x) => x.id === questionId);
    if (q) return q.text.en;
  }
  return questionId;
}

/* ---------- first aid (§9.8): deterministic rule table, never generated text ---------- */
export async function firstAid(facility: Facility, acuity: Acuity, facts: ExtractedFacts, language: string): Promise<FirstAid & { model_version: string }> {
  const real = await post<{ protocol_id: string; title: string; steps: string[]; donts: string[]; model_version: string }>(
    "/first-aid", { facility, acuity, extracted: facts },
  );
  if (real && lang3(language) === "en") return real;
  loadProtocols();
  let id = real?.protocol_id;
  if (!id) {
    if (facts.breathing === "absent") id = "hands_only_cpr";
    else if (facts.conscious === false) id = "recovery_position";
    else if (facts.bleeding === "heavy") id = "severe_bleeding";
    else if ((facts.symptoms ?? []).includes("seizure")) id = "seizure";
    else id = ({ cardiac: "chest_pain_wait", stroke: "stroke_signs_wait", trauma: "fracture_immobilisation", burns: "burns", respiratory: "choking", obstetric: "labour", pediatric: "recovery_position", poisoning: "poisoning", general: "recovery_position" } as Record<Facility, string>)[facility];
  }
  const a = aids.get(id!);
  const l = lang3(language);
  if (!a) return { protocol_id: id!, title: "Stay with the patient", steps: ["Stay calm and stay with the patient.", "Keep your phone on. The ambulance crew may call you."], donts: [], model_version: "fallback-rules" };
  return { protocol_id: a.protocol_id, title: a.title[l] ?? a.title.en, steps: a.steps[l] ?? a.steps.en, donts: a.donts?.[l] ?? a.donts?.en ?? [], model_version: real?.model_version ?? "fallback-rules" };
}

/* ---------- handover note (§9.9) ---------- */
export async function handover(input: { transcript: string; facts: ExtractedFacts; answers: string[]; profile: Record<string, unknown>; acuity: Acuity; facility: Facility; display: string }): Promise<Sbar & { model_version: string }> {
  const real = await post<Sbar & { model_version: string }>("/handover", {
    transcript: input.transcript, extracted: input.facts, followup_answers: input.answers, profile: input.profile,
    triage: { acuity: input.acuity, facility: input.facility },
  });
  if (real) return real;
  const sym = (input.facts.symptoms ?? []).map((s) => s.replace(/_/g, " ")).join(", ") || "details not yet known";
  const p = input.profile as { conditions?: string[]; medications?: string[]; allergies?: string[] };
  const bg = [
    p.conditions?.length ? `Known ${p.conditions.join(", ").toLowerCase()}` : null,
    p.medications?.length ? `on ${p.medications.join(", ")}` : null,
    p.allergies?.length ? `allergic to ${p.allergies.join(", ")}` : "no known allergies",
  ].filter(Boolean).join("; ");
  const rec: Record<Facility, string> = {
    cardiac: "Prepare cath lab and cardiologist.", stroke: "Prepare CT and stroke team.", trauma: "Prepare trauma bay and surgeon.",
    burns: "Prepare burns unit.", respiratory: "Prepare airway support and ventilator.", obstetric: "Prepare labour room and obstetrician.",
    pediatric: "Prepare children's ER.", poisoning: "Prepare decontamination and toxicology support.", general: "Prepare ER bed and emergency physician.",
  };
  return {
    situation: `${input.display} with ${sym}.`,
    background: bg ? `${bg}.` : "No health profile on file.",
    assessment: `Suspected ${input.facility} emergency, ${input.acuity}.${input.answers.length ? " " + input.answers.join(" ") : ""}`,
    recommendation: rec[input.facility],
    model_version: "fallback-template",
  };
}

/* ---------- speech (§9.18) ---------- */
export async function tts(text: string, language: string): Promise<string | null> {
  const real = await post<{ audio_url: string }>("/tts", { text, language: lang3(language) });
  if (!real?.audio_url) return null;
  return real.audio_url.startsWith("http") ? real.audio_url : `${MOCK.ML_BASE_URL}${real.audio_url}`;
}
