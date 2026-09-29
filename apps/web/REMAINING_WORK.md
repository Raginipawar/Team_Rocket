# GoldenHour web app — status and handoff notes

This file exists so work can continue even without me (Claude) around. Read it top to
bottom once; after that, use it as a map. Everything described here lives under
`Team_Rocket/apps/web/` unless said otherwise.

**⚠️ Nothing in `apps/web/` is committed to git yet.** Run `git status` from the
`Team_Rocket` repo root — you'll see `?? apps/` (untracked). The branch is
`ragini/web`, created off `origin/main`. **Commit this work before doing anything
else**, or a `git checkout`/`git clean`/accidental `rm -rf` will destroy it:

```bash
cd Team_Rocket
git add apps/web
git commit -m "feat(web): patient, ambulance, hospital, family, ops apps + mock core"
git push -u origin ragini/web
```

---

## 1. What this project is

`Team_Rocket` is the GoldenHour monorepo (HackMatrix 5.0, HLTH-02: real-time
emergency resource allocator for Pune and Pimpri Chinchwad). The spec is
`../../Problem_approach/technical.md` (the single source of truth — read it if
anything here is ambiguous) plus `../../Problem_approach/wd-person-c-frontend.md`
(my — Person C's — work distribution file).

Two teammates (on `main`) built:
- **Person A** (`services/core` main routers): auth, emergencies intake, ambulance
  offers/heartbeat, analytics, webhooks, WS relay, the domain pipeline
  (`process_emergency`), dispatch accept transaction.
- **Person B** (`origin/sarvesh/hospital-control`, **not merged into main**):
  hospital routes, clinical (triage-confirm/critical/family-override), ops routes,
  DB models, FSMs, the real simulator skeleton, Docker/Alembic/seed data.
- **Person C (me)**: `apps/web` — the whole frontend — plus a **mock core** that
  stands in for whichever of A's/B's routers aren't wired together yet, so the
  frontend is fully clickable today regardless of backend merge status.

## 2. What is DONE (this session's work)

### 2.1 The real Next.js app (`apps/web/`)

A complete Next.js 16 (App Router, TypeScript, Tailwind v4) frontend implementing
**all five surfaces** from `technical.md` §16:

| Surface | Route | Status |
|---|---|---|
| Website landing / role picker | `/` | Done |
| Login (patient OTP, staff password) | `/login` | Done |
| **Patient app** | `/patient/*` | Done — all of §16.2 |
| **Ambulance app** | `/ambulance/*` | Done — all of §16.3 |
| **Hospital dashboard** | `/hospital/*` | Done — all of §16.4 |
| **Family tracking page** | `/track/[token]` | Done — all of §16.5 |
| **Ops page** | `/ops/[token]`, `/ops` | Done — all of §16.6 |

Every screen has loading, empty, error, conflict (409) and offline states, per
`wd-person-c-frontend.md` UI rule 2. Every mutation goes through `lib/api.ts`,
which attaches an `Idempotency-Key` (reused on retry), refreshes the access token
once on 401, and turns the `{error:{code,message}}` envelope into readable text
(`errorText()`). Every ETA shows a range, every AI output shows confidence, every
hospital number shows freshness, every ranking shows "why" — see
`components/emergency/badges.tsx`.

### 2.2 The mock core (`mocks/core/`)

Since B's router work isn't merged to `main` and A's routers don't cover hospital/
ops/clinical at all, I built a **complete, from-scratch mock implementation of
`services/core`** in TypeScript so the frontend has a real, stateful backend to
talk to. This is not a demo/fake — it implements the actual state machines,
concurrency guards, and domain logic from `technical.md` §6, §10, §11, §13, §15:

- **`world.ts`** — the "database" (in-memory `Map`s mirroring §5's tables),
  seeded with 8 fictional hospitals in Pune/PCMC, 15 ambulances, staff with real
  shift times, an offline landmark gazetteer, and demo users matching
  `data/seed/CREDENTIALS.md`-style logins (see §3 below for exact numbers).
- **`domain.ts`** — the actual business logic: dispatch rounds, the accept
  transaction (§11.1, with the same 409 guards as the real spec), hospital
  selection + soft hold with `SKIP LOCKED`-style all-or-nothing reservation
  (§11.3), walk-in override (§11.7), deterioration/divert rule (§11.8, the ≥3
  min gain check), family override, vehicle breakdown re-dispatch (§11.11),
  escalations with the real timers (60s repeat, 120s auto-default, §13).
- **`sim.ts`** — the tick loop (500 ms): moves simulated ambulances along real
  OSRM routes, fires geofence arrivals (§11.9), drives hospital/driver "bots"
  that only act when no real person has that ambulance/hospital open (checked
  via `bus.ts`'s live-subscriber tracking), sweeps expired offers/holds/requests.
- **`ml.ts`** — calls the **real** `services/ml` service first
  (`http://localhost:8001`); if it's not running, falls back to deterministic
  rules and labels the result `model_version: "fallback-*"` so the UI never lies
  about a rule being a model. Follow-up questions and first-aid steps are read
  from the **actual protocol JSON files** in `../../services/ml/app/protocols/`,
  so wording matches whether the fallback or the real ML service answers.
- **`geo.ts`** — real routing via the public OSRM demo server (swap
  `OSRM_URL` for the team's self-hosted one), with a straight-line fallback if
  OSRM is unreachable (never silently invents roads without saying so).
- **`bus.ts`** — WebSocket fan-out with per-channel `seq`, channel
  authorization, and per-role projection (family never gets clinical fields —
  this is T31 from §14, implemented, not just claimed).
- **`analytics.ts`** — §11.16 metrics, computed from live cases plus a seeded
  7-day synthetic history (labelled `synthetic: true`) so charts aren't empty.
- **`scenarios.ts`** — a real scenario runner: `s1_happy_path`,
  `t1_double_booking` (20 concurrent requests race one room), `t2_simultaneous_
  accepts` (4 parallel accepts, exactly 1 wins), `t4_walk_in_override`,
  `t10_ambulance_offline`, `t11_hospital_not_responding`,
  `t13_no_ambulance_accepts`, `t19_all_hospitals_full`, `t20_deterioration` —
  each drives the same domain functions the UI uses, then checks the §14
  invariants (`invariants()` in `scenarios.ts`).
- **`routes.ts`** — every REST route, mounted to match **both** A's and B's
  actual (sometimes spec-deviating) paths where they differ, e.g. offers are
  served at both `/offers/{id}/accept` (spec) and `/ambulance/offers/{id}/accept`
  (A's actual router), so the frontend works against either.
- **`server.ts`** — boots `http.ts`'s router plus a `ws` WebSocket server on
  the same port (8010), handling all three WS auth kinds (access JWT, family
  track token, ops session).

**Run it**: `npm run mock:core` (or `npm run dev`, which runs both mock core and
Next together via `concurrently`).

### 2.3 API-switching design

`next.config.ts` proxies `/api/v1/*` to either the mock core (port 8010) or the
real core (port 8000), **per area** (`AUTH`, `ME`, `EMERGENCIES`, `AMBULANCE`,
`HOSPITAL`, `TRACK`, `OPS`), independently, via env vars
`NEXT_PUBLIC_API_MODE_<AREA>=mock|real`. This means: the moment A's or B's real
routers are ready for one area, flip that one env var — nothing else changes.
See `lib/config.ts` (`areaMode()`, `wsUrl()`) for the runtime side of this.

### 2.4 Contracts

`lib/enums.ts` mirrors `packages/contracts/enums.json` exactly.
`scripts/check-contracts.mjs` fails the build if they drift
(`npm run check:contracts`, also runs automatically before `npm run build`).
`lib/api-types.ts` is a hand-written mirror of `technical.md` §7/§8 (since
`packages/contracts/openapi.core.yaml` doesn't exist yet — once it does, generate
`lib/api-types.gen.ts` with `openapi-typescript` and swap these types for the
generated ones).

### 2.5 Design system

- Tailwind v4 tokens in `app/globals.css` (light + `.dark` for the ambulance
  app's night mode), matching the marketing website's look (pill buttons, big
  rounded cards, red for emergency).
- `components/ui/` — Button, Sheet (Radix Dialog, bottom sheet on phone /
  centred on desktop), Icon (hand-drawn line icon set, no emoji), Toast, and
  `bits.tsx` (Card, Field, Input/Select/Textarea, LoadingState, EmptyState,
  ErrorState, Banner, SimulatedBadge — every "simulated" entity in the UI shows
  this badge per UI rule 10).
- `components/analytics/charts.tsx` — hand-built chart primitives (StatTile,
  HBars, Meter, Percentiles, Heatmap, ChartCard-with-table-toggle) following the
  **dataviz skill**: one hue (`#2a78d6`) for magnitude, reserved status colors
  (good/warning/critical) always paired with an icon + label, a table view so
  nothing is chart-gated. I deliberately did **not** use the `recharts`
  dependency that's in `package.json` — it's still listed but unused; either
  remove it or ignore it.
- `components/map/LiveMap.tsx` — MapLibre GL with real OpenStreetMap tiles
  (swap `NEXT_PUBLIC_MAP_TILES` for the team's own tile server), animated
  ambulance marker, day/night raster paint, fit-to-bounds or follow-ambulance
  camera. `scripts/copy-maplibre-worker.mjs` copies MapLibre's web worker into
  `public/maplibre/` at install/dev/build time (Next can't bundle it directly) —
  **this is why `predev`/`prebuild`/`postinstall` all run that script; don't
  remove it or the map breaks with "Worker failed to load".**

### 2.6 i18n

`next-intl` set up for en/hi/mr (`i18n/request.ts`, cookie-based, no locale in
the URL). Only `lib/i18n/en.json` is written out. **Hindi and Marathi JSON files
do not exist yet** — see §4 below. The family tracking page and hospital/ops
screens are allowed to be English-first per UI rule 8, but the patient and
ambulance apps should get hi/mr for the "every age can use it" goal.

### 2.7 Verified working (browser-tested this session)

Using Playwright against real Edge, headless, WebGL enabled
(`--use-angle=swiftshader`), I drove:
- Patient OTP login → SOS (typed) → live tracking → map → follow-up question
  answered → first-aid card → CPR coach.
- Ambulance login → offer rings → accept → turn-by-turn navigation → geofence
  auto-arrival → triage confirm sheet → hospital selection (dashed → solid
  route) → arrival → door timer.
- Hospital login → incoming request card (with countdown, prep checklist, SBAR
  handover note, WhyYou chips) → accept with room/staff picker → at-the-door →
  Patient received.
- All three apps staying in sync live over WebSocket in separate browser
  contexts (three "phones" open at once, exactly like the real demo will be).

Screenshots from these runs are in the scratchpad
(`…/scratchpad/shots/*.png`) if you want to see them; they're not part of the
repo.

`npx tsc --noEmit` is clean. `npx eslint .` is 0 errors, 28 warnings (all in
the "React Compiler readiness" rules this project doesn't opt into — see the
comment block in `eslint.config.mjs`).

---

## 3. Demo logins (mock core, `mocks/core/world.ts`)

| Role | How to sign in |
|---|---|
| Patient | Any 10-digit number at `/login?role=patient`. The OTP is returned in the dev response (shown right on screen, "Demo code: ######"), also logged to the mock core's console as a fake SMS. Phone `9200000001` = Rahul Kulkarni, has a filled-in health profile, blood O+, diabetic. |
| Paramedic | Phone `+9191000000XX` (XX = 01..15) / password `demo1234`. `01` = ALS MH14 AB 1234 (Akurdi), `02` = ALS MH14 CD 5678 (Pimpri). Shown as one-tap buttons on the login screen in mock mode. |
| Hospital staff | Phone `+9190000000X` (X = 1..8) / password `demo1234`. `1` = Greenfield Heart Centre (Nigdi), `2` = Riverside Multispeciality (Chinchwad), `3` = Metro Neuro and Trauma (Pimpri). One-tap buttons on login too. |
| Developer / Ops | No login screen — click "On call team" on the landing page, which fetches a fresh one-time link from `/core/dev/ops-link` (mock-only endpoint standing in for the real Telegram bot flow) and opens `/ops/<token>`. |

---

## 4. What is REMAINING (in priority order)

### 4.1 ✅ The stall I was chasing when this file was first written — SOLVED, test-only

**Symptom** (as first observed): in a Playwright script that opened a hospital
session and a patient session together, `POST /api/v1/emergencies` from the
patient page would occasionally take 10–40+ seconds to respond, with a false
"We cannot reach GoldenHour right now" banner, even though `curl` against the
same core (direct, or through the Next dev proxy) always answered in single-digit
milliseconds.

**Root cause, confirmed**: it is **not** an app bug, a Next.js proxy bug, or a
backend slowness issue. It only reproduces when Chromium is launched with
`--use-angle=swiftshader --enable-unsafe-swiftshader --ignore-gpu-blocklist`
(forced software WebGL) — flags I was passing to my own debug scripts so
headless Chromium could render MapLibre's WebGL map at all. With those flags,
the hospital dashboard's live map genuinely renders via CPU-bound software
rasterization, continuously (tiles + a marker repositioned every second from
the WS feed). That pegs a CPU core hard enough, in this resource-constrained
sandbox, to starve scheduling for the Node processes running the mock core and
Next dev server on the same machine — so an unrelated browser tab's simple
JSON POST queues behind CPU contention that has nothing to do with the
request itself. Proof: the exact same test script, with those three launch
flags removed (map silently fails to get a WebGL context instead, using no
CPU), is instant and 100% reliable across many repeated runs; with them
restored, the stall reproduces every time, and — confirming the diagnosis
further — the client-side retry added below fires visibly (three attempts,
~10–17s apart, matching its 8s timeout) exactly as designed while the
contention lasts.

**Real users are not affected.** A real browser on real hardware has GPU-
accelerated WebGL and doesn't burn a CPU core software-rendering map tiles,
and a real deployment doesn't run the browser and both servers squeezed onto
one constrained dev sandbox. If you ever need headless screenshots of a page
with the map on it again, you don't need `--ignore-gpu-blocklist`; try without
the software-GL flags first (the map will just not render, which is fine for
screenshotting everything else on the page), or give the VM more CPU.

**What I still changed, because it's correct regardless of the above**:
`lib/api.ts`'s `once()` had no timeout at all on `fetch` — a genuinely slow or
stuck connection (of *any* cause, not just this one) would hang forever with
no feedback. I added an 8-second per-attempt `AbortSignal.timeout()`; a timeout
now triggers an immediate retry on a fresh connection (same Idempotency-Key, so
a slow-but-eventually-successful request is never double-applied), while a
signal the *caller* aborted on purpose (e.g. a component unmounting) still
propagates as a real `AbortError`. This is the "fail safe, never toward
silence" principle from `technical.md` §0.8 applied to the one place (§7.1)
that owns every network call — keep it.

I also found and fixed a real (if minor) hygiene gap while investigating:
`mocks/core/domain.ts`'s `db.audit` array had no cap (unlike
`db.notifications`, which was already capped at 500). It's now capped at 4000
entries, and `mocks/core/sim.ts` now runs `pruneOldEmergencies()` every 60s,
dropping finished emergencies (and their offers/requests/reservations/
handoffs) once they're older than the family track token's own validity
window (§7.6: closed + 6h) — so a mock core left running for many hours of
testing doesn't grow its in-memory `Map`s without bound. This wasn't the cause
of the stall above (a *freshly restarted* mock core reproduced the stall just
as reliably), but it's good practice for a process meant to stay up for a
whole demo session, so I kept it.

### 4.2 Hindi and Marathi translations

`lib/i18n/en.json` has every string. Copy it to `lib/i18n/hi.json` and
`lib/i18n/mr.json` and translate every value (keep the keys and the `{n}`/
`{name}`-style placeholders exactly as-is — `next-intl` uses ICU-lite
interpolation). Per `wd-person-c-frontend.md` §4.1, hi/mr medical wording
should be reviewed by a native speaker before any real use — the website
project (a sibling folder, `../../website/`) already has hi/mr/te/ta/gu
dictionaries for its own marketing copy that could be a source of vocabulary
and tone, though its keys don't line up with this app's.

### 4.3 Wire up the real ML service

Start `services/ml` (`cd ../../services/ml && uvicorn app.main:app --port
8001`) and confirm the mock core's `mocks/core/ml.ts` picks it up automatically
(it probes `http://localhost:8001/ml/v1/*` and falls back only if that's
unreachable — no config needed, just start it). Check the "AI · NN% sure" text
in the app switches from fallback rules to real model output, and that
`model_version` in the audit trail (visible on `/ops` → Incident → an
escalation's Audit trail) no longer says `fallback-*`.

### 4.4 Switch areas to the real core as A's/B's routers merge

- **B's branch (`origin/sarvesh/hospital-control`) is not merged into `main`
  yet.** Until it is, there is no real `/hospital/*`, `/emergencies/{id}/
  triage-confirm`, `/emergencies/{id}/critical`, `/emergencies/{id}/family-
  override`, or `/ops/*` on the real core at all — those areas must stay on
  `mock` (`NEXT_PUBLIC_API_MODE_HOSPITAL=mock`, etc., which is already the
  default) until that merge happens.
- Once merged and `services/core` is running (`docker compose up` per
  `technical.md` §22, then `alembic upgrade head`, then seed), flip one area
  at a time: set `NEXT_PUBLIC_API_MODE_AUTH=real` first (auth is the most
  complete on `main`), verify login still works, then `EMERGENCIES`, then
  `AMBULANCE`, etc. `lib/config.ts` and `next.config.ts` already support this
  per-area switching — no frontend code changes should be needed, only env
  vars, **unless** the real core's response shapes differ from what
  `lib/api-types.ts` assumes. Watch for:
  - The real `/ambulance/active` and `/ambulance/me` endpoints don't exist on
    `main` at all yet (I invented them in the mock — see `lib/ambulance.ts`'s
    `fetchSelf`/`fetchActive`, which gracefully 404-fallback to `localStorage`).
    Someone (A) needs to add these, or the ambulance app needs a different way
    to know "what job am I on" against the real core.
  - A's `POST /emergencies` currently accepts `caller_phone` as a plain form
    field with no auth check tying it to the logged-in user — my mock matches
    that today for compatibility, but this is a real security gap worth
    flagging back to A before it goes live (`services/core/app/api/v1/
    emergencies.py` on `main`).
  - Role projection (`domain/privacy.py` on `main`) is a **pass-through stub**
    marked "DO NOT rely on this for privacy before the real projections land."
    My mock's `bus.ts`/`views.ts` implement the real per-role filtering
    (family never sees clinical fields) — when switching `TRACK` or
    `EMERGENCIES` to the real core, re-verify this by hand before any public
    demo, since the real core admits it isn't safe yet.

### 4.5 Playwright E2E suite (formal, not my ad-hoc debug scripts)

`wd-person-c-frontend.md` C14 asks for a real Playwright suite covering 3
browser contexts (patient/ambulance/hospital) and UI checks for the §14 tough
scenarios (409 dialogs, reroute banners, signal states, stale badges,
escalation states). `@playwright/test` is installed and `npm run test:e2e` is
wired up, but **no test files exist yet** (`playwright.config.ts` is also
missing). The manual scripts I used to debug this session
(`…/scratchpad/full.mjs`, `flow.mjs`, `amb.mjs`) are a good starting skeleton —
they're outside the repo, so copy the patterns you want into a real
`apps/web/tests/e2e/*.spec.ts` structure.

### 4.6 Paramedic offline mode — needs a real device test

`lib/offline-queue.ts` (IndexedDB queue, replays on reconnect) and
`lib/ambulance.ts`'s `useOfflineQueue` are wired into
`app/ambulance/job/[id]/page.tsx` (`queueable: true` on the mutating actions),
and the UI shows a banner with an `sms:` fallback link
(`GH <short_id> ARRIVED` etc. to `NEXT_PUBLIC_SMS_GATEWAY_NUMBER`). This has
**not** been tested with an actual airplane-mode toggle (T10 in §14) — only
reasoned through. Test it: open the ambulance app on a real phone or via
Chrome DevTools' network throttling → offline, do an action, go back online,
confirm it replays exactly once.

### 4.7 PWA / service worker

`app/layout.tsx` references `/manifest.webmanifest` and `app/providers.tsx`
registers `/sw.js` in production — **neither file exists yet**. Per UI rule 9
("PWA = manifest + service worker; no native code"), you need to add:
- `public/manifest.webmanifest` (name, icons, `display: "standalone"`, theme
  color `#dc2626` to match `viewport.themeColor` in `app/layout.tsx`).
- `public/sw.js` — at minimum an offline app-shell cache; ideally also handles
  Firebase Cloud Messaging push for new offers/hospital requests per
  `technical.md` §12.3 (not implemented at all yet — there's no FCM
  integration in this codebase).

### 4.8 Things explicitly out of scope for what I built (say so if asked)

- **No push notifications** (FCM). WS is live while a tab is open; there's no
  "wake a backgrounded tab" story yet.
- **No real translate/TTS pipeline wiring beyond what `ml.ts` calls** — if
  `services/ml`'s `/translate` and `/tts` aren't implemented for real yet
  (check with A/whoever owns that), the fallback is browser
  `speechSynthesis` (see `lib/speech.ts`), which is fine for a demo but not
  the real IndicTrans2/Parler-TTS pipeline the spec wants.
- **No unknown-patient merge UI test with a real merge conflict** — the
  `/hospital/patients` page (`app/hospital/patients/page.tsx`) calls the
  mock's merge endpoint but hasn't been exercised end-to-end in this session.
- **No accessibility audit pass** beyond what's built in by default (48px+
  targets, `aria-live`, focus rings, `prefers-reduced-motion`). A proper pass
  (screen reader testing, color contrast audit with real tools) hasn't
  happened.
- **Analytics numbers are partly synthetic** (labelled `synthetic: true` in
  the mock) so charts aren't empty on a fresh demo — this is intentional and
  documented, not a bug, but don't present those numbers as measured
  production data.

---

## 5. How everything is connected (architecture map)

```
                         ┌────────────────────────────────────────────┐
  Browser tabs  ────────►│  Next.js app (apps/web), port 3000          │
  (patient /              │  - app/**/page.tsx: one file per screen     │
   ambulance /             │  - app/**/layout.tsx: shared shell per app  │
   hospital /              │    (RequireRole guard, WS connection,       │
   family /                │     duty-cycle / offer-ringing / etc.)      │
   ops)                    │  - components/**: shared UI, all client     │
                          │    ("use client" — nothing here is a         │
                          │     server component; it's a live, WS-       │
                          │     driven app, not content)                 │
                          └───────────────┬──────────────────────────────┘
                                          │ fetch("/api/v1/...")  +  new WebSocket("ws://.../ws")
                                          │ (same-origin; next.config.ts rewrites route each
                                          │  path prefix to whichever core owns that area)
                     ┌────────────────────┴─────────────────────┐
                     ▼                                          ▼
        mock core (mocks/core/server.ts)             real core (services/core, port 8000)
        port 8010 — REST + WS                          — only for areas flipped to "real"
        (running today; see §2.2)                       (not usable for hospital/ops/clinical
                                                          until B's branch merges — see §4.4)
```

**Inside the Next app**, the chain for one screen (e.g. the patient live page)
is:

```
app/patient/emergency/[id]/page.tsx
  ├─ useQuery(fetchEmergency)         → lib/patient.ts → lib/api.ts → GET /api/v1/emergencies/{id}
  ├─ useWsClient("EMERGENCIES", token) → components/realtime/WsProvider.tsx → lib/ws.ts
  │     └─ subscribes to `emergency:{id}`; on every event, either patches
  │        local state (ambulance.location) or invalidates the query
  │        (everything else) — "WS is the live truth, REST is the full truth"
  ├─ <Map ambulance=... route=... />   → components/map/index.tsx (dynamic import,
  │                                       client-only) → LiveMap.tsx (MapLibre)
  ├─ <FollowupCard/>, <FirstAidCard/>  → components/emergency/parts.tsx
  ├─ <AcuityBadge/>, <EtaRange/>, ...  → components/emergency/badges.tsx
  └─ <CprCoach/>                       → components/emergency/CprCoach.tsx (full-screen overlay)
```

**Auth** (`lib/auth.tsx`) holds the access token in memory + `sessionStorage`
(so each tab can be a different role at once), and registers itself with
`lib/api.ts` via `setTokenSource()` so every `fetch` can attach
`Authorization: Bearer` and silently refresh once on 401. The refresh token
itself is an httpOnly cookie set by the core (mock or real) — the browser
sends it automatically on `/api/v1/auth/refresh`; JS never touches it.

**Every mutation** goes through `lib/api.ts`'s `api()`/`post()`/`patch()`/
`del()` helpers — never raw `fetch` — because that's the one place that
attaches the Idempotency-Key, retries safely, and turns errors into the
`ApiError` class that every screen's `catch` block reads with `errorText()`.

**The ops page** is the odd one out: it doesn't use `lib/auth.tsx` at all
(there's no "ops" role login). It exchanges a one-time link for a session
(`app/ops/[token]/page.tsx` → `POST /ops/session`), gets back a session token
it stores in `sessionStorage` (`gh-ops-session`) for its own direct
`WsClient`, while REST calls ride the `ops_session` httpOnly cookie
automatically (see `components/ops/OpsTabs.tsx`).

**The mock core**, internally: `server.ts` starts `sim.ts`'s tick loop and
attaches `routes.ts`'s handlers to a raw Node `http.Server` (via `http.ts`'s
tiny router — no Express). Every route handler calls into `domain.ts` for
anything that changes state (never touches `world.ts`'s `Map`s directly except
for simple reads), and `domain.ts` calls `bus.ts`'s `publish()` after every
state change to fan out the WS event, and `views.ts`'s functions to shape the
per-role response. `analytics.ts` and `scenarios.ts` are read-mostly
consumers of the same `world.ts` state.

## 6. How to run everything right now

```bash
cd Team_Rocket/apps/web
npm install                 # also runs postinstall → copies the MapLibre worker
npm run dev                 # starts mock core (:8010) AND Next (:3000) together
```

Then open `http://localhost:3000/` and click through. To run just one:
`npm run dev:web` (Next only, needs mock core running separately) or
`npm run mock:core` (mock core only).

Useful checks before committing anything:
```bash
npm run typecheck           # tsc --noEmit
npx eslint .                # should be 0 errors
npm run check:contracts     # enums.json vs lib/enums.ts must match
```
