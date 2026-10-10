# Person C — Frontend + Caller-Assist ML

> **You own:** `apps/web/**`, `packages/contracts/ws-mock.ts`, Prism mock config, Playwright E2E, and four ML capabilities in `services/ml/app/capabilities/{followup, first_aid, translate, tts}/` + `services/ml/app/protocols/**`.
> **You depend on:** A and B only through the frozen contracts (`openapi.core.yaml`, `ws-events.schema.json`, `openapi.ml.yaml`). Use Prism + WS mock until their routers go live.
> **Specs:** technical.md §7 (as consumer), §8 (as consumer), §9.7, §9.8, §9.18, §12.4, §16, §21 (E2E).

---

## 1. Your deliverables

1. **The Next.js web app**: patient, ambulance, hospital, family tracking, and ops page. That includes maps, the WS client, the paramedic offline queue, PWA, push UI, i18n (en/hi/mr), and every loading, empty, error, conflict and offline state.
2. **Caller-assist ML (20 % of the AI/ML):** follow-up questions, first aid, translation, text-to-speech.
3. **Playwright E2E** across patient, ambulance and hospital browsers, plus UI-level checks for all 34 tough scenarios.
4. **`docs/DEMO.md`**, the demo script.

## 2. Your files

```
apps/web/
├── app/
│   ├── layout.tsx, providers.tsx
│   ├── login/page.tsx
│   ├── patient/{page.tsx, profile/, contacts/, emergency/[id]/}
│   ├── ambulance/{page.tsx, job/[id]/, history/}
│   ├── hospital/{page.tsx, rooms/, resources/, staff/, handoffs/, patients/, analytics/}
│   ├── track/[token]/page.tsx
│   └── ops/[token]/page.tsx            # tabs: Incident · Analytics · Scenarios
├── components/
│   ├── map/ (LiveMap, RouteLayer, AmbulanceMarker, HospitalMarker, H3Heatmap)
│   ├── realtime/ (WsProvider, useChannel, SignalBadge)
│   ├── sos/ (SosButton, VoiceRecorder, TextReport, LocationIndicator, Call108)
│   ├── emergency/ (StatusStepper, TriageBadge, FollowupCard, FirstAidSteps, HandoffCard, RerouteBanner)
│   ├── ambulance/ (OfferCard, CountdownRing, TriageConfirmSheet, CriticalButton, FamilyOverrideSheet,
│   │               VehicleIssue, DestinationCard, OfflineBanner, RepositionCard)
│   ├── hospital/ (RequestCard, AcceptDialog, RejectDialog, RoomsBoard, OverrideDialog, ResourceEditor,
│   │              FreshnessBadge, ConfirmAvailability, PrepChecklist, HandoverNote, OffloadTimer, WhyYou)
│   ├── ops/ (EscalationPanel, OptionButtons, AuditTrail, ScenarioList, SimControls)
│   ├── analytics/ (Recharts)
│   └── ui/ (shadcn)
├── lib/ (api-types.ts [generated], api.ts, ws.ts, offline-queue.ts, push.ts, i18n/{en,hi,mr}.json, format.ts)
├── public/ (manifest.webmanifest, icons, sounds/offer.mp3)
├── service-worker.ts
├── tests/e2e/
└── mocks/ (prism config, ws-mock runner + event scripts)

services/ml/app/capabilities/{followup, first_aid, translate, tts}/{router.py, schemas.py, model.py, mock.py}
services/ml/app/protocols/{followup/*.json, first_aid/*.json, audio/}
services/ml/tests/test_{followup,first_aid,translate,tts}.py
docs/DEMO.md
```

## 3. Build order

| # | Hours | Task | Done when |
|---|---|---|---|
| C0 | 0–3 | Contract freeze: review `openapi.core.yaml` + WS schema for every screen; write your 4 sections of `openapi.ml.yaml`; define WS-mock event script format | `contracts-v1` |
| C1 | 3–5 | Web skeleton: Next.js + TS strict, Tailwind, shadcn, TanStack Query, next-intl, generated `api-types.ts`, `api.ts`, auth pages, role-based route guards, Prism + `ws-mock.ts` | All routes render on mocks |
| C2 | 3–5 | Mocks for your 4 ML capabilities | A's intake can call them |
| C3 | 4–7 | Maps + realtime foundation: MapLibre (OSM tiles), polyline6 decode, animated ambulance marker, `WsProvider` / `useChannel` with `seq` + resync | Mock ambulance moves smoothly |
| C4 | 5–9 | **Follow-up protocols + first-aid scripts** authored for all 9 facilities; follow-up selection + parse endpoints real (§4.1, §4.2) | Real questions in the pipeline |
| C5 | 5–9 | Patient surface: SOS (press-and-hold 1 s), voice recorder (MediaRecorder, ≤ 60 s, waveform), text, location + accuracy, Call 108, profile, contacts, live emergency page (stepper, map, ETA range, triage, follow-up card with audio + answer buttons / mic, first aid, handoff, reroute) | Works on real core as A's routers land |
| C6 | 7–11 | Ambulance surface: online/offline, offer card (20 s countdown, sound, vibration), accept/decline with `409 ALREADY_TAKEN`, active job (map, caller call button), triage confirm sheet (AI preselected, 9 facility + 3 acuity buttons, patient count), Critical, family override sheet with deltas + consent, vehicle issue, refused transport, destination card, handoff → cleaning → ready, reposition card | Accept race handled correctly |
| C7 | 9–12 | Hospital surface: request cards with countdown, accept (room/staff prefilled) / reject (reason required), incoming map with signal badge, rooms board (`Reserved for MH12… ETA 6 min`), override dialog, resources with freshness badges, Confirm availability, handover note, prep checklist, WhyYou, offload timer, Patient received | ✅ Checkpoint 2 end-to-end |
| C8 | 9–13 | **Translation + TTS** real (§4.3); pre-render all protocol audio (hi/mr/en) | Follow-up questions play in Marathi |
| C9 | 12–15 | Paramedic offline mode: IndexedDB queue replaying with the same Idempotency-Keys, heartbeat batching, offline banner, one-tap `sms:` fallback (`GH <id> <CMD>` to the gateway number) | Airplane-mode test (T10) passes in UI |
| C10 | 12–14 | Family page `/track/[token]`: non-clinical only, language from the contact; FCM registration + service worker notifications (offers, hospital requests, status) | Opens on a second phone and updates live |
| C11 | 13–17 | Ops page from the Telegram link: token exchange, Incident tab (map, summary, options, claim/resolve, manual override with reason, audit trail), Analytics tab, Scenarios tab (list, run, speed, reset, results timeline) | Works on a phone |
| C12 | 15–18 | Analytics UIs: hospital + system (response-time percentiles, offload delays, rejections by reason, triage confusion matrix, stale-data frequency, escalations, H3 demand heatmap actual vs forecast) | Populated from sim data |
| C13 | 17–20 | Unknown-patient merge UI, hospital staff/shifts UI, history pages, i18n completeness, accessibility pass | ✅ Checkpoint 3 |
| C14 | 18–21 | Playwright E2E (3 browser contexts) + UI checks for all tough scenarios (409 dialogs, reroute banners, signal states, stale badges, escalation states) | All green |
| C15 | 21–23 | `docs/DEMO.md`: scenario order, which device shows what, backup recording | Two rehearsals |

## 4. ML specifications (your 20 %)

### 4.1 Follow-up questions — `POST /ml/v1/followup/next`, `POST /ml/v1/followup/parse` (technical §9.7)
- One protocol file per facility (9 files), 6–10 questions each:

```json
{ "facility": "cardiac", "version": "v1",
  "questions": [ { "id": "c_conscious", "field": "conscious", "answer_type": "yes_no", "priority": 1,
                   "text": {"en": "Is he awake and responding?", "hi": "…", "mr": "…"},
                   "audio": {"en": "c_conscious_en.wav", "hi": "…", "mr": "…"} } ] }
```

- **Selection:** the LLM (Ollama `qwen2.5:7b-instruct`, temperature 0, JSON output) receives the current facts, answered IDs and candidate questions (ID + English text), and must return `{question_id}` from the candidates. Validate that the ID exists; otherwise fall back to the highest-priority unanswered question. Stop after 5 or when the tree is exhausted.
- **Parse:** the LLM maps a free answer (any language) to the field's type (`yes_no`, `number`, `choice`), validated with Pydantic.
- **The LLM never writes question text.** Question text and translations are fixed in the JSON; hi/mr texts are produced with IndicTrans2 and **reviewed by a team member who speaks the language**.
- **Tests:** every tree validates against the schema; selection never returns an unknown ID; parse accuracy on 60 hand-written answers per language.

### 4.2 First aid — `POST /ml/v1/first-aid` (technical §9.8)
- Fixed scripts: hands-only CPR, choking, severe bleeding, burns, stroke-signs wait, chest-pain wait, seizure, poisoning, fracture immobilisation, labour, unconscious-but-breathing (recovery position). Each has `title`, `steps[]`, `donts[]` in en/hi/mr, plus audio.
- Written from established lay first-aid guidance (Indian Red Cross / standard BLS lay-rescuer guidance). Put the source reference in each file.
- A deterministic rule table maps (facility, extracted facts) → protocol ID, with priority overrides (`breathing == "none"` → CPR, always).
- **No generated medical text, ever.** Tests cover every rule branch.

### 4.3 Translation + TTS — `POST /ml/v1/translate`, `POST /ml/v1/tts` (technical §9.18)
- IndicTrans2 (en↔hi, en↔mr); Indic Parler-TTS.
- LRU cache by `sha256(text+lang)`. Audio served from `/ml/v1/static/audio/{hash}.wav`.
- **Build step** `python -m app.capabilities.tts.prerender` renders every protocol question and first-aid step in all three languages at startup (cached).
- Report: latency per call and a human quality check of 30 translated SMS templates (rated by a native speaker).

## 5. UI rules (non-negotiable)

1. Every mutation goes through `api.ts`, which attaches an `Idempotency-Key` (reused on retry) and handles:
   - `409 VERSION_CONFLICT` → refetch + toast
   - `409 ALREADY_TAKEN` → specific message
   - `409 ROOM_RESERVED` → override dialog
   - `401` → refresh token, then retry once
2. Every screen has loading, empty, error, conflict and offline states.
3. Every hospital number shows `FreshnessBadge`; every AI output shows confidence; every ranking shows `WhyYou`; every ETA shows its range.
4. The family page renders only non-clinical fields — tested in E2E.
5. SOS, Accept, Confirm and Critical buttons are ≥ 48 px, one-thumb reachable, with `navigator.vibrate` feedback.
6. Call 108 is always visible on patient screens, and becomes a full-width banner when `/readyz` fails twice or an SOS fails after retries.
7. WS is the live truth and REST is the full truth: on a `seq` gap or reconnect, refetch.
8. All strings live in `en/hi/mr.json`. Hospital and ops screens are English-first.
9. PWA = manifest + service worker; **no native code**.
10. Simulated entities show a *Simulated* badge.

## 6. Interfaces

- **You consume:** `openapi.core.yaml` (A: auth, me, emergencies, ambulance, offers, track; B: hospital, clinical, ops, health) and `ws-events.schema.json` (A).
- **You provide:** ML endpoints `followup/next`, `followup/parse`, `first-aid`, `translate`, `tts`, called by A's intake pipeline and SMS templates.
- **Mock switching:** `NEXT_PUBLIC_API_MODE_<area>=mock|real` per router group, so you move to real APIs one area at a time as A and B announce them.

## 7. Hand-offs

| To | What | By hour |
|---|---|---|
| A | Mocks for your 4 capabilities | 5 |
| A | Real follow-up + first aid | 9 |
| A | Real translate + TTS | 13 |
| All | E2E report + screenshots for slides | 21 |
| All | `docs/DEMO.md` | 22 |

## 8. What you receive (and what to do if it's late)

| From | What | If late |
|---|---|---|
| A / B | Routers going live | Stay on Prism + WS mock for that area |
| B | `CREDENTIALS.md` | Use Prism example users |
| B | Scenario endpoints | The Scenarios tab runs against the mock until they land |
