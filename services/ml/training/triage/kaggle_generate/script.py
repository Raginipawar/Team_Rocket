# Kaggle GPU version of generate_data.py + generate_holdout.py, combined.
# Ollama on a local 6GB laptop GPU serves one request at a time -- at ~40
# samples/min, 8,505 + 405 samples would take hours. A Kaggle T4 can batch
# dozens of prompts through transformers.generate() at once, cutting this to
# well under an hour. Same grids, same prompts, same labels as the local
# scripts -- only the inference backend changes.

import json
import random
import subprocess
import sys

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "bitsandbytes>=0.46.1"], check=True)

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
BATCH_SIZE = 32
MAX_NEW_TOKENS = 120

FACILITIES = ["cardiac", "stroke", "trauma", "burns", "respiratory",
              "obstetric", "pediatric", "poisoning", "general"]
ACUITIES = ["critical", "urgent", "stable"]
LANGUAGES = ["hi", "mr", "en", "hi-en", "mr-en"]
SPEAKERS = ["self", "relative", "bystander"]
STYLES = ["calm", "panicked", "fragmented"]

LANGUAGE_NAMES = {
    "hi": "Hindi, written in Devanagari script",
    "mr": "Marathi, written in Devanagari script",
    "en": "English",
    "hi-en": "code-mixed Hindi-English (Hinglish), written in Latin script",
    "mr-en": "code-mixed Marathi-English, written in Latin script",
}

MAIN_SYSTEM_PROMPT = """You write realistic emergency-call utterances for training
data, as if transcribed from a phone call to an ambulance service in
Maharashtra, India. Write ONLY the utterance itself -- no preamble, no
explanation, no quotes around it. Keep it to 1-4 short sentences, the way a
real caller would actually speak: not a clinical summary, a panicked or
rushed real person describing what's wrong."""

HOLDOUT_SYSTEM_PROMPT = """You write a single realistic, DIFFICULT emergency-call
utterance, as if transcribed from a real phone call to an ambulance service
in Pune/Pimpri-Chinchwad, Maharashtra. Make it genuinely hard to classify:
mention a specific local landmark or area name, have the caller contradict
themselves once or trail off mid-sentence, mix in a bystander's confusion or
a crying/shouting background detail, and avoid naming the medical condition
directly -- only describe symptoms and context, the way a real distressed
person actually talks. Write ONLY the utterance -- no preamble, no quotes,
no explanation. 1-4 short sentences."""


def build_main_prompt(facility, acuity, language, speaker, style):
    speaker_desc = {
        "self": "the patient is calling about themselves",
        "relative": "a family member is calling about the patient",
        "bystander": "a stranger/bystander is calling about someone they don't know",
    }[speaker]
    style_desc = {
        "calm": "calm and clear, giving information in order",
        "panicked": "panicked, urgent, raising their voice, maybe repeating themselves",
        "fragmented": "fragmented and confused, giving information out of order, trailing off",
    }[style]
    return (
        f"Write one caller utterance in {LANGUAGE_NAMES[language]}. "
        f"Medical situation: a {facility} emergency of {acuity} severity "
        f"(don't say the word '{facility}' or '{acuity}' literally -- describe symptoms instead). "
        f"Caller: {speaker_desc}. Speaking style: {style_desc}."
    )


def build_holdout_prompt(facility, acuity, language, speaker):
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


def build_main_cells(rng):
    cells = []
    for facility in FACILITIES:
        for acuity in ACUITIES:
            for language in LANGUAGES:
                for speaker in SPEAKERS:
                    for style in STYLES:
                        for _ in range(7):  # 1,215 x 7 = 8,505
                            cells.append({"facility": facility, "acuity": acuity, "language": language,
                                          "speaker": speaker, "style": style})
    rng.shuffle(cells)
    return cells


def build_holdout_cells(rng):
    cells = []
    for facility in FACILITIES:
        for acuity in ACUITIES:
            for language in LANGUAGES:
                for _ in range(3):  # 135 x 3 = 405
                    speaker = rng.choice(SPEAKERS)
                    cells.append({"facility": facility, "acuity": acuity, "language": language, "speaker": speaker})
    rng.shuffle(cells)
    return cells


def generate_batch(model, tokenizer, system_prompt, prompts, temperature):
    texts = []
    for p in prompts:
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": p}]
        texts.append(tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True))
    inputs = tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=512).to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=True,
                              temperature=temperature, pad_token_id=tokenizer.eos_token_id)
    results = []
    for i in range(len(prompts)):
        gen = out[i][inputs["input_ids"].shape[1]:]
        text = tokenizer.decode(gen, skip_special_tokens=True).strip().strip('"')
        results.append(text)
    return results


def run_set(model, tokenizer, cells, system_prompt, prompt_fn, temperature, out_path, label):
    n_written = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for batch_start in range(0, len(cells), BATCH_SIZE):
            batch = cells[batch_start:batch_start + BATCH_SIZE]
            if label == "main":
                prompts = [prompt_fn(c["facility"], c["acuity"], c["language"], c["speaker"], c["style"]) for c in batch]
            else:
                prompts = [prompt_fn(c["facility"], c["acuity"], c["language"], c["speaker"]) for c in batch]
            texts = generate_batch(model, tokenizer, system_prompt, prompts, temperature)
            for cell, text in zip(batch, texts):
                if not text:
                    continue
                row = {**cell, "text": text}
                if label == "holdout":
                    row["source"] = "llm_generated_holdout_NOT_human_verified"
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                n_written += 1
            f.flush()
            print(f"[{label}] progress: {min(batch_start + BATCH_SIZE, len(cells))}/{len(cells)} "
                  f"({n_written} written so far)", flush=True)
    return n_written


def main():
    print("loading model...", flush=True)
    bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, quantization_config=bnb_config, device_map="auto")
    print("model loaded", flush=True)

    rng = random.Random(2026)
    main_cells = build_main_cells(rng)
    print(f"main set: {len(main_cells)} cells", flush=True)
    n_main = run_set(model, tokenizer, main_cells, MAIN_SYSTEM_PROMPT, build_main_prompt,
                      0.9, "/kaggle/working/synthetic.jsonl", "main")
    print(f"DONE main: {n_main}/{len(main_cells)} written", flush=True)

    rng2 = random.Random(9999)
    holdout_cells = build_holdout_cells(rng2)
    print(f"holdout set: {len(holdout_cells)} cells", flush=True)
    n_holdout = run_set(model, tokenizer, holdout_cells, HOLDOUT_SYSTEM_PROMPT, build_holdout_prompt,
                         1.1, "/kaggle/working/holdout_triage.jsonl", "holdout")
    print(f"DONE holdout: {n_holdout}/{len(holdout_cells)} written", flush=True)
    print("REMINDER: holdout_triage.jsonl is LLM-generated, not independently human-verified.")


if __name__ == "__main__":
    main()
