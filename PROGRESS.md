# GoldenHour — Build Progress

Updated after every completed task. Each entry: what was done, how to verify it yourself, what's still open.

## How to run everything locally

1. **Docker (Postgres + Redis):**
   ```
   docker compose -f infra/docker-compose.yml up -d
   ```
2. **Core backend** (from `services/core`):
   ```
   uvicorn app.main:app --port 8000 --host 127.0.0.1
   ```
3. **ML service** (from `services/ml`), real models (not mock):
   ```
   ML_MODE=real uvicorn app.main:app --port 8001 --host 127.0.0.1
   ```
4. **Frontend** (from `frontend_delivery/Team_Rocket/apps/web`):
   ```
   npm run dev
   ```
   Opens Next.js on `:3000` and the mock core on `:8010` (mock is only used for the `ME` area — contacts/profile/history aren't on the real backend yet).
5. Health check: `curl http://localhost:8000/readyz` should show `db/redis/ml: ok`.

Demo logins: patient = OTP (any phone, code appears in the backend's own terminal log since `SMS_MODE=fake`); paramedic = `+919100000001`..`15` / `demo1234`; hospital staff = `+919000000001`..`08` / `demo1234`.

## Known open issues (tracked, not forgotten)

- **[HIGH] Hospital app sometimes shows/redirects to the ambulance app**, reported on separate laptops/profiles so it isn't a shared-cookie issue. Role-guard code (`RequireRole` in `components/shell.tsx`) and both layouts checked and are correct in isolation — needs the exact on-screen text/screenshot and whether it happens before or after login to pin down.
- Telegram bot not yet real (`TELEGRAM_MODE=mock`) — needs a bot token + group chat id from the user.
- `/ambulance/history`, `/me/contacts`, `/me/emergencies`, `/me/profile` real backend routes: profile/contacts/emergencies now built and verified (see below); ambulance history still returns empty (frontend degrades gracefully).
- Push notifications still deferred (code is real/wired, not yet live-fired end to end).

## Completed

### 2026-10-10 — Real SMS OTP delivery (textbee)
- `SMS_MODE=real`, `SMS_PROVIDER=textbee`, `SMS_API_KEY`, `SMS_GATEWAY_DEVICE_ID` set in `services/core/.env` (teammate's Android phone running the textbee app is the real SMS gateway).
- Fixed a real bug found while verifying this live: `sender.py` was reading credentials with `os.getenv`/`os.environ`, but pydantic-settings' `.env` loading only populates the `Settings` object's fields — it never touches the actual process environment. Every env var read this way silently fell back to its default (`SMS_MODE` stuck on `"mock"`/fake-path even with `SMS_MODE=real` sitting in `.env`). Fixed by switching `sender.py` to read from `app.config.settings` instead, and added the missing `SMS_GATEWAY_DEVICE_ID` field to the `Settings` model.
- **Verified live**: real `POST /api/v1/auth/otp/request` → textbee API returned `201 Created` → backend logged `send_sms OK provider=textbee` → real OTP SMS received on a real phone (+91 75585 28945).

## Completed

### 2026-10-10 — Patient self-service (profile, contacts, history, followup, cancel)
- Built real `/me/profile` (GET/PUT, with proper optimistic-locking UPSERT), `/me/contacts` (GET/POST/DELETE, 5-contact limit enforced server-side), `/me/emergencies` (real history list with hospital name + derived for_self flag)
- Built real `/emergencies/{id}/followup` (GET/POST) and `/emergencies/{id}/cancel`, wired to the real LLM-backed followup-question selection and free-text answer parsing
- Fixed a real asyncpg bug (date strings need Python-side parsing, not SQL CAST)
- Fixed ML timeout mismatches where core-side timeouts were shorter than the ML service's own internal Ollama timeouts, causing real answers to be silently dropped
- **Verified live**: full profile save/conflict-detection cycle, 5-contact limit, real LLM question selection + answer parsing through to a first-aid card, SOS cancellation releasing the ambulance/reservation
- **How to verify yourself**: log in as patient, fill out Profile and save, add up to 5 emergency contacts, send an SOS and watch the "a few more questions" card appear on the live tracking screen

### 2026-10-10 — Dispatch reliability fixes
- Found and fixed: `GET /ambulance/offers` didn't exist (404), and the ambulance app polls it every 3-15s as a WS backup — the 404-to-empty-list fallback was silently wiping a just-delivered live offer off the paramedic's screen within seconds. Built the real endpoint.
- Found and fixed: `raise_escalation()` was being called with positional args in 4 places in `selection.py` when it's keyword-only — would crash any escalation path (no hospital found, etc.)
- Found and fixed: a new FSM validation guard correctly rejected the `at_scene -> hospital_selecting` jump (real graph requires the `patient_on_board` step first) — fixed by making that hop implicit, since the real UI has no separate button for it
- **Verified live**: full SOS -> dispatch -> accept -> arrive -> triage-confirm -> hospital-selection chain, through the real WebSocket, through a real Cloudflare tunnel (not just localhost)

### 2026-10-10 — Backend/ML reconciliation with teammate's branch
- Went file-by-file through every file both this work and Sarvesh's `hospital-control` branch had independently touched; kept whichever version was actually correct against the live DB schema (verified by testing, not by reading)
- Adopted his real improvements: FSM transition guards, real predicted-resource booking (not hardcoded "ventilator"), `/ops/audit` filtering
- Did NOT adopt his versions where they were broken against the real schema: wrong column names (`record_id`/`created_at` vs real `entity_id`/`at`), wrong-case status strings (`'ACCEPTED'` vs real `'accepted'`), a `shap` import that's completely unimportable in this environment

---

### 2026-10-10 — Patient onboarding + Family space (built in ~45 min before mentoring round)
- **Welcome/onboarding flow**: first-ever patient login (detected by "profile never filled", not just account age, so it also catches earlier test accounts) now goes OTP → Welcome screen → "add your health details" (reuses the real Profile page, not a duplicate form) → home. Shown once per user via localStorage flag.
- **Family space** (entirely new feature, real DB schema added: `health_profiles.family_code`, new `family_connections` table):
  - Every patient gets a permanent 6-character shareable code (auto-generated on first visit, collision-safe)
  - Enter someone else's code to connect to them ("watch" them) — real validation (wrong code → 404, your own code → rejected)
  - Family list shows each connected person, with a live "active emergency right now" flag if they currently have one
  - Tapping a family member opens a sheet: their blood group/allergies/conditions (only visible because a real connection exists — enforced server-side, not just hidden in the UI), a direct call button, and a real "Call an ambulance for them" button
  - "Call ambulance for them" creates a genuine SOS attributed to the family member's own account (not the caller's) — reuses the same real, already-tested `/emergencies` endpoint, so it shows up correctly in *their* history and goes through the exact same real dispatch pipeline
- Bottom nav relabeled: Home / Health / Family / History (Family replaces the old bare Contacts tab)
- **Verified live, full real flow**: code generation, connect, wrong-code and self-code rejection, family list, permission-gated health view, ambulance call attributing to the correct patient

**Still open from this session**: real SMS OTP delivery (waiting on teammate's phone + textbee setup), push notifications (code is real and wired, not yet live-fired end to end), the hospital/ambulance mixup bug (still needs exact repro text from the user).
