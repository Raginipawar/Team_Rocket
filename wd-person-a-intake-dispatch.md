# Person A — Intake & Dispatch (ML + Backend)

> **Your domain:** everything from "someone asks for help" until "the patient is in the ambulance", plus realtime, security, SMS, push and analytics.
> **Ownership:** see `work-distribution.md` §2. You never edit B's or C's paths.
> **Specs:** technical.md §7.2–7.4, §7.6, §8, §9.1–9.6, §9.9, §9.10, §9.15, §9.16, §9.19, §10.1, §10.4, §11.1, §11.9–11.12, §11.14 (creation side), §11.15, §11.16, §12.1, §12.3, §18.

---

## 1. Your deliverables

### ML (11 capabilities)
STT · extraction · triage · prank score · duplicate check · dispatch ranking · resource prediction · handover note · learning loop · demand forecast · pre-positioning.
You also write the **ML service skeleton** (`main.py`, `config.py`, `registry.py`, `util/`, auto-discovery of routers, the mock framework, `/health`).

### Backend
Auth & security · SOS intake pipeline · location resolution · realtime (WebSocket, channels, projector, outbox relay, pub/sub) · dispatch (rounds, offers, accept, decline, expiry, supersede, idle / wrong way, breakdown, multiple patients, prank policy, duplicate merge) · lifecycle (heartbeats, geofence, signal states, dead reckoning, offload delay, cleaning → available) · pre-positioning job · privacy projections · SMS gateway (sender, throttle, inbound webhook, parser) · web push · analytics.

## 2. Your files

```
services/ml/app/{main.py, config.py, registry.py, util/}
services/ml/app/capabilities/{stt, extract, triage, prank, duplicate, dispatch_rank, resources, handover, feedback, demand, preposition}/
services/ml/training/{stt, extraction, triage, prank, duplicate, dispatch, resources, demand}/
services/ml/data/{holdout/triage.jsonl, synthetic/…, feedback/}

services/core/app/security/**
services/core/app/realtime/**
services/core/app/domain/{intake, location, dispatch, lifecycle, connectivity, prepositioning, privacy}.py
services/core/app/db/repos/{identity, emergencies, dispatch, ambulances}.py
services/core/app/jobs/handlers/intake_dispatch.py
services/core/app/api/v1/{auth, me, emergencies, ambulance, offers, track, webhooks_sms}.py
services/core/app/integrations/ml/{base, intake, caller_assist}.py
services/core/app/integrations/{sms, push}/**
services/core/app/analytics/**
services/core/tests/{unit, concurrency}/<your modules>
packages/contracts/ws-events.schema.json
```

## 3. Build order

| # | Hours | Task | Done when |
|---|---|---|---|
| A0 | 0–3 | Contract freeze: `ws-events.schema.json`, your sections of `openapi.ml.yaml` (+ merge all sections), review `openapi.core.yaml` for your endpoints, commit stubs for your A→B interfaces | `contracts-v1` |
| A1 | 3–5 | ML skeleton with auto-discovery + mocks for **your** 11 capabilities; start triage data generation and ETA-free background jobs | Contract tests green on mocks |
| A2 | 3–6 | Security: OTP (via your SMS sender, fake mode first), password login, JWT + refresh rotation, role guards, scope guards, rate limits, idempotency middleware, correlation id | Auth endpoints pass contract tests |
| A3 | 4–7 | Intake v1: `POST /emergencies` (202), `process_emergency` job on ML mocks, location resolution (GPS → gazetteer → profile), patient row, family track token | Emergency reaches `dispatching` on mocks |
| A4 | 5–8 | Realtime: outbox table writer + relay, Redis pub/sub, `/ws` auth, channel authorisation, role projector, per-channel `seq`, resync | C's WS client gets real events |
| A5 | 4–7 | **STT** real (§4.1) | Voice SOS transcribed |
| A6 | 5–8 | **Extraction** real (§4.2) | |
| A7 | 4–11 | **Triage**: data gen → fine-tune on Kaggle in background → calibrate → serve (§4.3) | Real triage in pipeline |
| A8 | 7–10 | Dispatch: rounds, candidate query, B's `eta/matrix` + your dispatch-rank, offers, accept transaction (technical §11.1 exact SQL), decline, expiry, supersede, escalation hook | T2, T3 green |
| A9 | 9–12 | Lifecycle: REST + WS heartbeats, geofence (scene → `at_scene`; hospital → B's `ambulance_arrived_hospital`), signal states, dead reckoning, calls to B's `extend_hold_on_heartbeat` / `mark_ambulance_silent`, cleaning → available | ✅ Checkpoint 2 |
| A10 | 10–13 | **Prank + duplicate** real (§4.4, §4.5) + prank policy + duplicate merge + incident clustering + MCI trigger → B's `raise_escalation` | T28, T29 green |
| A11 | 11–14 | **Dispatch ranking** real (§4.6) + export `driver_params.json` to B (simulator) | |
| A12 | 12–15 | Dispatch edge cases: idle / wrong way parallel re-dispatch, breakdown (`redispatch_to_point`), multiple patients, bad GPS path, no-ambulance escalation | T13–T17 green |
| A13 | 12–15 | SMS: real sender (textbee + httpSMS behind one interface), throttle queue, inbound webhook, parser, templates (via C's translate), gateway heartbeat → anomaly, duty-manager SMS function for B | T33 green with a real basic phone |
| A14 | 13–15 | **Handover note + resource prediction** real (§4.7, §4.8); regenerate handover on follow-up answers and on triage confirm | Hospital card shows real SBAR + checklist |
| A15 | 14–16 | Push (FCM) sender + subscriptions endpoint; caller-assist glue (`integrations/ml/caller_assist.py`) running C's follow-up / first-aid loop and re-triage after each answer | |
| A16 | 14–17 | **Demand forecast + pre-positioning** (ML + 15-min job) (§4.10, §4.11) | Suggestions reach ambulances |
| A17 | 15–18 | Analytics: SQL views + materialised views (technical §11.16), hospital-scoped + system-wide endpoints | Dashboards populated from sim |
| A18 | 16–18 | **Learning loop** + MLflow + hot-swap (§4.9) | Correction → retrain → promote-or-reject demo |
| A19 | 18–21 | Hardening: T8, T10, T12, T26, T30, T31, T34; privacy projection tests; latency measurement; ML reports | All your tests green |

## 4. ML specifications

Contracts are in technical.md §9. This section covers how to build each one.

### 4.1 STT (technical §9.1)
- faster-whisper `large-v3` (float16, GPU) + AI4Bharat IndicConformer (hi, mr).
- Pipeline:
  1. ffmpeg decode → 16 kHz mono → loudness normalise → Silero VAD trim.
  2. Whisper language ID.
  3. hi/mr → run both models and keep the higher normalised confidence. en or code-mixed → Whisper.
- Reject > 60 s or > 5 MB with `400`.
- **Eval:** ≥ 60 team-recorded clips (hi/mr/en/code-mixed, quiet + noisy, 3+ speakers) → WER/CER per language → `REPORT.md`. Hand the clips to B for the simulator by hour 10.
- Target ≤ 3 s for 20 s audio.

### 4.2 Extraction (§9.2)
- Ollama `qwen2.5:7b-instruct`, `format=<ExtractedFacts JSON schema>`, temperature 0, system prompt with field definitions and enums.
- Validate with Pydantic; one repair retry with the validation error appended.
- `coherence` in [0,1] feeds the prank model.
- **Eval:** 200 hand-labelled transcripts → field accuracy.

### 4.3 Triage (§9.3)
- **Taxonomy:** acuity {critical, urgent, stable}; facility {cardiac, stroke, trauma, burns, respiratory, obstetric, pediatric, poisoning, general}.
- **`generate_data.py`:**
  - Grid of facility × acuity × language {hi, mr, en, hi-en, mr-en} × speaker {self, relative, bystander} × style {calm, panicked, fragmented}.
  - Target 8–10k balanced samples; deduplicate at embedding similarity > 0.95.
- **`asr_noise.py`:** 30 % of samples go text → Indic Parler-TTS (C's TTS endpoint, or the model directly) → STT, keeping the noisy transcript with the same label.
- **Human holdout:** ≥ 300 team-written, double-labelled utterances in `data/holdout/triage.jsonl`. **Never used for training or tuning.**
- **Model:**
  - MuRIL (`google/muril-base-cased`), two heads.
  - Input: `[TEXT] … [FACTS] … [PROFILE] …`.
  - Weighted CE, with critical ×2 in the acuity head.
  - 3–4 epochs, lr 2e-5, batch 32, max_len 256.
- Train an IndicBERT v2 variant with the same recipe and ship whichever has better validation macro-F1.
- Temperature scaling per head. `needs_review = confidence < 0.60`. Safety rules for `fragility` and `mlc_flag` in code.
- **Report:** macro-F1 per head, per-language F1, confusion matrices, ECE before/after, **critical-recall** (headline), 20 worst errors.

### 4.4 Prank (§9.4)
- Simulated call logs (legitimate vs prank behaviour) → Isolation Forest + rule reasons.
- Threshold at 5 % FPR on validation; report precision/recall.
- Policy in core: never block; critical bypasses verification.

### 4.5 Duplicate (§9.5)
- `intfloat/multilingual-e5-base` (prefix `query: `) cosine similarity + gate (≤ 500 m, ≤ 15 min, ≥ 0.80). DBSCAN incident clustering.
- 100-pair test set → precision/recall.

### 4.6 Dispatch ranking (§9.6)
- Driver behaviour generator (Beta propensity, fatigue, distance aversion, recent-job decline). **Export `driver_params.json` so B's simulator uses the same parameters.**
- LightGBM classifier + latency regressor; `score = p/(eta+E[latency])`; ALS-preservation penalty.
- Report AUC, Brier, latency MAE, and a simulated time-to-accept comparison vs nearest-first.

### 4.7 Handover (§9.9)
- SBAR JSON schema. Every sentence carries a `source_spans` quote; a validator drops any sentence whose quote isn't found (fuzzy ≥ 0.85). Output in English.

### 4.8 Resources (§9.10)
- `mapping.csv` (facility × acuity × facts → items) → noisy dataset → LightGBM one-vs-rest.
- Report per-label AUC and micro-F1. Items with `prob ≥ 0.5` go to the checklist; `≥ 0.7` countable ones go into B's reservation bundle.

### 4.9 Learning loop (§9.19)
- Feedback appends to `data/feedback/`. Retrain merges synthetic + feedback (×3 weight), evaluates on the **fixed holdout**, and promotes only if macro-F1 **and** critical-recall are ≥ the current model's.
- MLflow tracking; registry hot-swap; `POST /retrain` returns `202 {job_id}`, and `GET /ml/v1/jobs/{id}` reports progress.

### 4.10 Demand forecast (§9.15)
- Synthetic 90 days of calls with patterns (highway nights, market evenings, residential cardiac mornings, festival spikes) on H3 res 8.
- LightGBM Poisson with lags 1/24/168 h, neighbour sums, hour, weekday, OSM POI density.
- Report MAE and deviance vs historical average.

### 4.11 Pre-positioning (§9.16)
- OR-Tools MIP: maximise forecast demand covered within 8 min, penalise relocation, keep ≥ 1 ALS per high-demand zone.
- Unit tests for coverage gain and the ALS constraint.

## 5. Backend specifications

- **Intake:** exactly technical §10.1. Every ML call goes through `integrations/ml/*` with the timeout and fallback from technical §9, logged to `ml_predictions`.
- **Location:**
  1. GPS if `accuracy_m ≤ 100`.
  2. Otherwise the landmark → `landmarks` table (pg_trgm similarity, proximity-weighted to coarse GPS or profile home). B seeds this table from the gazetteer.
  3. Otherwise the profile's home location.
  4. Otherwise the first follow-up question asks for a landmark.
- **Dispatch:** technical §11.1. Exact accept SQL. ALS required for critical or `needs_review`. Offers pushed over WS and FCM.
- **Realtime:** technical §8 + §10.4. The outbox row is written in the same transaction as the change (`outbox.emit`). The relay publishes to `ws:{channel}`. Projection goes through `privacy.project` only.
- **Lifecycle / connectivity:** technical §11.9–11.12. Heartbeats update Redis GEO + Postgres (throttled to every 15 s for Postgres). Signal weak at 30 s, lost at 120 s. Dead reckoning along the route.
- **SMS:** technical §12.1. Parser order:
  1. `GH <id> <CMD>` → paramedic command.
  2. `YES` → prank verification.
  3. An open emergency with a pending question → follow-up answer.
  4. Otherwise → new emergency.
  Webhook returns `200` in < 100 ms and processes in the background; dedupe by gateway `message_id`.
- **Privacy:** serializers per role (patient, family, paramedic, hospital, ops). The family view has no clinical fields — test it (T31).
- **Rules:** all locking SQL in `db/repos`; every transition via B's FSM; one transaction = state + audit + outbox; timers re-check state; no business logic in routers.

## 6. Interfaces

- **You provide to B:** `outbox.emit`, `start_dispatch`, `redispatch_to_point`, `privacy.project`, `send_sms`, `send_push`, security deps (work-distribution.md §4.1).
- **You call on B:** `start_selection`, `extend_hold_on_heartbeat`, `mark_ambulance_silent`, `release_for_emergency`, `ambulance_arrived_hospital`, `raise_escalation`, `fsm.transition`, `audit.write`, `schedule`, `register_sweep_check`, and B's ML capabilities `eta/matrix`, `eta`.
- **You call on C (ML):** `followup/next`, `followup/parse`, `first-aid`, `translate`, `tts`. Use their mocks until they're live.

## 7. Hand-offs

| To | What | By hour |
|---|---|---|
| All | Merged `openapi.ml.yaml`, `ws-events.schema.json` | 3 |
| C | Live routers announced (auth → emergencies → WS → ambulance/offers → track) | 5–12 |
| B | Voice clips for simulator callers | 10 |
| B | `driver_params.json` | 12 |
| All | ML reports + latency numbers for slides | 21 |
