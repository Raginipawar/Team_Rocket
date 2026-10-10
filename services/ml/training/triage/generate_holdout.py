"""Holdout eval set for the triage model (technical.md §9.3 wants this
HAND-WRITTEN by the team, never by an LLM, because an LLM-written holdout
can't be a true independent check when a similar LLM wrote the training
data too). Generated here as an explicit, time-boxed demo compromise, NOT
a substitute for the real thing -- every report this file feeds into must
say "LLM-written holdout, not independently human-verified" next to any
number computed against it. Deliberately distinct from generate_data.py's
distribution: a different system prompt (harder, noisier, real-sounding
Pune-area calls with interruptions/contradictions/trailing off), a
different seed, and a higher temperature, so it is at least a genuine
stress test rather than more of the exact same thing being re-evaluated
against itself."""

import asyncio
import json
import random

import httpx

RNG = random.Random(9999)

FACILITIES = ["cardiac", "stroke", "trauma", "burns", "respiratory",
              "obstetric", "pediatric", "poisoning", "general"]
ACUITIES = ["critical", "urgent", "stable"]
LANGUAGES = ["hi", "mr", "en", "hi-en", "mr-en"]
SPEAKERS = ["self", "relative", "bystander"]
SAMPLES_PER_CELL = 3  # 9 x 3 x 5 x 3 = 405 samples, above the spec's >=300

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen2.5:7b-instruct"
MAX_CONCURRENCY = 6

LANGUAGE_NAMES = {
    "hi": "Hindi, written in Devanagari script",
    "mr": "Marathi, written in Devanagari script",
    "en": "English",
    "hi-en": "code-mixed Hindi-English (Hinglish), written in Latin script",
    "mr-en": "code-mixed Marathi-English, written in Latin script",
}

SYSTEM_PROMPT = """You write a single realistic, DIFFICULT emergency-call
utterance, as if transcribed from a real phone call to an ambulance service
in Pune/Pimpri-Chinchwad, Maharashtra. Make it genuinely hard to classify:
mention a specific local landmark or area name, have the caller contradict
themselves once or trail off mid-sentence, mix in a bystander's confusion or
a crying/shouting background detail, and avoid naming the medical condition
directly -- only describe symptoms and context, the way a real distressed
person actually talks. Write ONLY the utterance -- no preamble, no quotes,
no explanation. 1-4 short sentences."""


def build_prompt(facility: str, acuity: str, language: str, speaker: str) -> str:
    speaker_desc = {
        "self": "the patient is calling about themselves",
        "relative": "a family member is calling about the patient",
        "bystander": "a stranger/bystander is calling about someone they don't know, and is unsure of some details",
    }[speaker]
    return (
        f"Write one DIFFICULT caller utterance in {LANGUAGE_NAMES[language]}. "
        f"Medical situation: a {facility} emergency of {acuity} severity "
        f"(don't say the word '{facility}' or '{acuity}' literally -- describe symptoms/context instead, "
        f"and make the severity genuinely ambiguous from the wording alone, the way a real caller under "
        f"stress would describe it). Caller: {speaker_desc}."
    )


async def generate_one(client: httpx.AsyncClient, cell: dict, sem: asyncio.Semaphore) -> dict | None:
    prompt = build_prompt(cell["facility"], cell["acuity"], cell["language"], cell["speaker"])
    async with sem:
        try:
            response = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": MODEL, "system": SYSTEM_PROMPT, "prompt": prompt,
                "options": {"temperature": 1.1}, "stream": False,
            }, timeout=30.0)
            response.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
            return None
    text = response.json()["response"].strip().strip('"')
    if not text:
        return None
    return {**cell, "text": text, "source": "llm_generated_holdout_NOT_human_verified"}


async def main() -> None:
    cells = []
    for facility in FACILITIES:
        for acuity in ACUITIES:
            for language in LANGUAGES:
                for _ in range(SAMPLES_PER_CELL):
                    speaker = RNG.choice(SPEAKERS)
                    cells.append({"facility": facility, "acuity": acuity, "language": language, "speaker": speaker})
    RNG.shuffle(cells)
    print(f"generating {len(cells)} holdout samples (LLM-written, NOT a substitute for human-verified)", flush=True)

    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    samples = []
    out_path = "services/ml/data/holdout/triage.jsonl"
    import os
    os.makedirs("services/ml/data/holdout", exist_ok=True)
    async with httpx.AsyncClient() as client:
        with open(out_path, "w", encoding="utf-8") as f:
            for batch_start in range(0, len(cells), 50):
                batch = cells[batch_start:batch_start + 50]
                results = await asyncio.gather(*(generate_one(client, c, sem) for c in batch))
                for r in results:
                    if r is not None:
                        samples.append(r)
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()
                print(f"progress: {len(samples)}/{len(cells)} holdout samples so far", flush=True)

    print(f"DONE: wrote {len(samples)}/{len(cells)} holdout samples to {out_path}")
    print("REMINDER: this holdout is LLM-generated, not independently human-verified. "
          "Any critical_recall/F1 computed against it must be reported with that caveat.")


if __name__ == "__main__":
    asyncio.run(main())
