# GoldenHour — Work Distribution (Overview, v2)

> Read this first, then **your own** file:
> - `wd-person-a-intake-dispatch.md` — **Person A: Intake & Dispatch** (ML + backend)
> - `wd-person-b-hospital-control.md` — **Person B: Hospital, Routing & Control** (ML + backend)
> - `wd-person-c-frontend.md` — **Person C: Frontend + Caller-Assist ML**
>
> `technical.md` is the source of truth for every contract. These files say **who builds what, in which order, in which files**.

---

## 1. The split

**Rule:** 80 % of the AI/ML and 100 % of the backend are split **equally** between A and B. The remaining 20 % of the AI/ML and 100 % of the frontend go to C.

The split is **by domain**, not by layer. A owns everything from "someone asks for help" until "the patient is in the ambulance". B owns everything from "which hospital?" until "patient handed over", plus the control and safety systems. Each person builds both the model and the backend logic for their domain, so most work never crosses a person boundary.

| | Person A — Intake & Dispatch | Person B — Hospital, Routing & Control | Person C — Frontend + Caller Assist |
|---|---|---|---|
| **ML** (16 of 20 capabilities split A/B, 4 to C) | STT · extraction · triage · prank · duplicate · dispatch ranking · resource prediction · handover note · learning loop · demand forecast · pre-positioning | ETA + uncertainty · road comfort · landmark gazetteer · hospital ranking + SHAP · bed nowcast (LightGBM + TFT) · MCI allocation | Follow-up questions · first aid · translation · TTS |
| **Backend** | Auth & security · SOS intake pipeline · location resolution · realtime (WS + outbox) · dispatch (offers, accept, idle, breakdown, radius rounds) · lifecycle (geofence, heartbeats, connectivity, offload) · pre-positioning job · privacy projections · SMS gateway · web push · analytics | Infra (docker, DB schema, migrations, seed) · FSMs · timers / sweeper / leader · hospital selection · reservations + all bed concurrency · room & staff allocation · clinical changes (deterioration, triage change, family override, unknown patient) · hospital APIs · escalation engine · Telegram bot · ops API · audit · simulator + scenario runner + invariant checker | — |
| **Frontend** | — | — | All 5 surfaces (patient, ambulance, hospital, family, ops), maps, WS client, offline queue, PWA, i18n, push UI, E2E tests |
| **Tough-scenario tests owned** (technical §14) | T2 T3 T8 T10 T12 T13 T14 T15 T16 T17 T26 T28 T29 T30 T31 T33 T34 (17) | T1 T4 T5 T6 T7 T9 T11 T18 T19 T20 T21 T22 T23 T24 T25 T27 T32 (17) | Playwright E2E of every surface; UI-level checks for all 34 |
| **Estimated effort** | ≈ 45 units | ≈ 45 units | ≈ frontend + 4 ML capabilities |

Nothing from `project-description.md` is dropped. Every feature has exactly one owner.

## 2. Folder ownership (no two people edit the same file)

### 2.1 `services/ml` — one folder per capability

```
services/ml/app/
├── main.py, config.py, registry.py, util/        → A  (skeleton; routers auto-discovered)
└── capabilities/<name>/{router.py, schemas.py, model.py, mock.py}
     A: stt, extract, triage, prank, duplicate, dispatch_rank, resources, handover, feedback, demand, preposition
     B: eta, road_comfort, hospital_rank, bed_nowcast, mci   (+ app/geo/**)
     C: followup, first_aid, translate, tts                  (+ app/protocols/**)
services/ml/training/<name>/   → same owner as the capability
services/ml/data/<name>/       → same owner as the capability
```

`main.py` auto-discovers every `capabilities/*/router.py`, so adding a capability never touches a shared file. `openapi.ml.yaml` has one section per capability; the section's owner edits it, and A merges.

### 2.2 `services/core`

| Path | Owner |
|---|---|
| `app/main.py`, `config.py`, `deps.py`, `errors.py` (skeleton; routers auto-included) | B |
| `app/db/models/**`, `app/db/migrations/**` (all of technical §5, written in hours 0–3) | B |
| `app/db/repos/{identity,emergencies,dispatch,ambulances}.py` | A |
| `app/db/repos/{hospitals,rooms,resources,reservations,escalations,audit}.py` | B |
| `app/domain/fsm/**`, `app/domain/audit.py` (frozen at hour 3) | B |
| `app/domain/{intake,location,dispatch,lifecycle,connectivity,prepositioning,privacy}.py` | A |
| `app/domain/{selection,reservations,allocation,clinical,escalation,handoff}.py` | B |
| `app/security/**` | A |
| `app/realtime/**` (WS, channels, projector, outbox, pub/sub) | A |
| `app/jobs/{worker,scheduler,sweeper,leader}.py` (framework) | B |
| `app/jobs/handlers/intake_dispatch.py` | A |
| `app/jobs/handlers/hospital_control.py` | B |
| `app/api/v1/{auth,me,emergencies,ambulance,offers,track,webhooks_sms}.py` | A |
| `app/api/v1/{hospital,clinical,ops,health,webhooks_telegram}.py` | B |
| `app/integrations/ml/{base,intake,caller_assist}.py` | A |
| `app/integrations/ml/routing.py` | B |
| `app/integrations/{sms,push}/**` | A |
| `app/integrations/telegram/**` | B |
| `app/analytics/**` | A |
| `app/sim/**`, `tests/invariants.py`, `tests/scenarios/**` | B |
| `tests/unit/<own modules>`, `tests/concurrency/<own tests>` | owner of the module |

### 2.3 Everything else

| Path | Owner |
|---|---|
| `apps/web/**`, `packages/contracts/ws-mock.ts`, Prism mock config, Playwright | C |
| `infra/**`, `data/seed/**`, `.env.example` | B |
| `packages/contracts/enums.json`, `openapi.core.yaml` | B (A reviews, C reviews UI needs) |
| `packages/contracts/ws-events.schema.json` | A (C reviews) |
| `packages/contracts/openapi.ml.yaml` | A merges; each capability section by its owner |

## 3. Contract freeze (hours 0–3, all together)

1. `enums.json` from technical §3 (B).
2. `openapi.core.yaml` from technical §7 (B writes; A reviews its endpoints; C reviews every shape the UI needs).
3. `ws-events.schema.json` from technical §8 (A writes; C reviews).
4. `openapi.ml.yaml` from technical §9 (each owner writes their sections; A merges).
5. DB models + first migration of the whole of technical §5 (B), FSM transition tables (B), `audit.write` (B).
6. The **A ↔ B internal interfaces** (§4), written as real function signatures with no-op or stub bodies.
7. Tag `contracts-v1`.

**Change rule after the freeze:**
- The owner proposes the change in a PR, and the consumer approves.
- Every change is logged in `packages/contracts/CHANGELOG.md` and announced in chat.
- Adding optional fields is allowed with a note. Renaming or removing anything needs all three people.

## 4. A ↔ B internal interfaces inside `services/core` (frozen at hour 3)

### 4.1 A provides, B calls

```python
# app/realtime/outbox.py
async def emit(session, *, channel: str, event: str, data: dict) -> None      # same transaction as the state change

# app/domain/dispatch.py
async def start_dispatch(session, *, emergency_id: UUID, priority: bool = False, reason: str) -> None
async def redispatch_to_point(session, *, emergency_id: UUID, lat: float, lng: float, reason: str) -> None   # breakdown with patient on board

# app/domain/privacy.py
def project(role: str, obj: Any) -> dict

# app/integrations/sms/sender.py and app/integrations/push/sender.py
async def send_sms(phone: str, body: str, *, emergency_id: UUID | None = None, template: str | None = None) -> str
async def send_push(user_id: UUID, title: str, body: str, data: dict) -> None

# app/security/deps.py
get_current_user, require_role(*roles), require_hospital_scope, require_ambulance_scope
```

### 4.2 B provides, A calls

```python
# app/domain/selection.py
async def start_selection(session, *, emergency_id: UUID, reason: Literal["triage_confirmed","deterioration",
                          "triage_changed","family_override","rejected","timeout","override","divert"]) -> None

# app/domain/reservations.py
async def extend_hold_on_heartbeat(session, *, emergency_id: UUID, remaining_eta_sec: int) -> None
async def mark_ambulance_silent(session, *, emergency_id: UUID, last_seen_at: datetime, remaining_eta_sec: int) -> None
async def release_for_emergency(session, *, emergency_id: UUID, reason: str) -> None

# app/domain/handoff.py
async def ambulance_arrived_hospital(session, *, emergency_id: UUID) -> None   # geofence (A) → handoff row (B)

# app/domain/escalation.py
async def raise_escalation(session, *, type: str, emergency_id: UUID | None = None,
                           incident_id: UUID | None = None, context: dict) -> UUID

# app/domain/fsm/*.py
def transition(entity, to_status: str) -> None        # raises InvalidTransition

# app/domain/audit.py
async def write(session, *, actor_type, actor_id, entity, entity_id, action, before, after, reason=None, model_version=None) -> None

# app/jobs/scheduler.py
async def schedule(name: str, *, run_at: datetime, key: str, payload: dict) -> None   # idempotent by key
def register_sweep_check(fn) -> None                                                 # sweeper calls it every 5 s
```

At the freeze, each side commits **stub bodies** (they log the call and return). The other side can integrate from hour 3 and never waits.

## 5. How C stays independent

- **Frontend** builds against the Prism mock of `openapi.core.yaml` and the WS mock replaying event scripts. It switches to the real core router by router as A and B announce them.
- **C's four ML capabilities** are pure functions behind `openapi.ml.yaml` and need nothing from A or B. A's intake pipeline calls them, and uses their mocks until they are live.
- C's ML work is Python, in `services/ml/app/capabilities/{followup,first_aid,translate,tts}` + `protocols/`.

## 6. Git workflow

- `main` is protected. Work on branches `a/*`, `b/*`, `c/*`, with small PRs merged at least every 2–3 hours. CI runs lint, type-check, contract tests and unit tests.
- Never edit a path you don't own (§2). Need a change? Message the owner.

## 7. Shared timeline (24 h)

| Hour | Milestone | Everyone must have |
|---|---|---|
| **0–3** | Contract freeze | Contracts + DB migration + FSMs + A↔B stubs tagged `contracts-v1`; `make up` works for all |
| **3–6** | Skeletons on mocks | Every ML capability has a mock; core creates an emergency end to end on mocks; all 5 UIs render on Prism |
| **6** | ✅ Checkpoint 1 (15 min) | Each person demos their piece on mocks |
| **6–12** | Core features real | A: STT, extraction, triage real; dispatch + realtime. B: ETA, road comfort, hospital rank v1; selection + reservations + timers. C: patient, ambulance, hospital flows wired to real core; follow-up + first aid real |
| **12** | ✅ Checkpoint 2 — first real end-to-end | Voice SOS → real triage → offers → accept → confirm → hospital accept → handoff, in 3 browsers |
| **12–18** | Everything else | All remaining models, edge cases, SMS, Telegram, family, ops, analytics, simulator |
| **18** | ✅ Checkpoint 3 | All 39 features reachable; all 🎬 scenarios run |
| **18–21** | Hardening | All 34 scenario tests green; invariants clean; ML reports generated |
| **21** | 🔒 Feature freeze | |
| **21–23** | 2 demo rehearsals | `docs/DEMO.md` |
| **23–24** | Buffer + submission | |

## 8. Load balancing without creating dependency

If someone is ahead or behind at a checkpoint, move a **whole module** (folder + contract section + tests). Ownership stays single.

| Module | Default | Can move to |
|---|---|---|
| Demand forecast + pre-positioning (ML + job) | A | B |
| MCI allocation solver | B | A |
| Analytics (SQL views + endpoints) | A | B |
| Handover note | A | C |
| Resource prediction | A | C |

## 9. Before the hackathon (setup only; confirm with organisers)

The rules say solutions must be built within the 24 hours. Before the event, do only:
- **Accounts and keys:** Mapbox token, Telegram bot, textbee or httpSMS + spare Android phone with SIM and SMS balance, Firebase (FCM), Kaggle/Colab GPUs, Cloudflare Tunnel.
- **Downloads** of public pretrained weights: Whisper large-v3, IndicConformer, MuRIL, IndicBERT v2, multilingual-E5, IndicTrans2, Indic Parler-TTS, Qwen2.5-7B (Ollama), plus the Maharashtra OSM extract.
- **Reading:** all docs.

## 10. Definition of Done

technical.md §23, for every item. Not done until its tough scenarios pass. **No feature reduction, no simplification, no quality degradation.**
