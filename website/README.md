# GoldenHour Website and App Demo (React + Vite)

This folder holds two things for **GoldenHour**, the HackMatrix 5.0 project described in [`../Problem_approach/Project idea.pdf`](../Problem_approach/Project%20idea.pdf):

1. **The public website** (`#/`). It explains the idea in plain language for anyone: patients, families and judges.
2. **A clickable demo of every app screen** (`#/demo`). It is built from `../frontend-screens.md` (Frontend Content Specification v2) and covers the patient app, the ambulance app, the hospital dashboard, the family tracking page and the ops page. All five share one simulated emergency.

The demo runs entirely in the browser. There is no backend, and every hospital, ambulance and person in it is simulated sample data from spec section 9.

## Run it

```
npm install     # first time only
npm run dev     # opens on http://localhost:5173
npm run build   # production build into dist/
npm run lint
```

## Addresses

| Address | What it is | Demo sign in |
| --- | --- | --- |
| `#/` | Public website | none |
| `#/demo` | Demo launcher: how to try it, links to every app | none |
| `#/app` | Patient app (P1 to P26) | any 10 digit number, OTP **482913** |
| `#/crew` | Ambulance app (A1 to A11), dark at night | password **demo** |
| `#/hospital` | Hospital dashboard (H1 to H9), for a laptop | password **demo** |
| `#/track/8Kq2` | Family tracking page, the page the SMS link opens | none |
| `#/ops` | Ops page (O1 to O3), opened from Telegram | none |

## How to try the demo

1. Open `#/demo`, then open the ambulance app and the hospital dashboard in new tabs.
2. In the patient app, sign in with code 482913 and hold SOS for one second.
3. Accept in the ambulance, confirm the patient, accept in the hospital. Every tab updates in real time.

With **Autoplay** on (the default), bots step in for anyone who doesn't tap, so one tab is enough to watch the whole emergency. The **demo panel** (beside the phone on a laptop, a small "Demo" pill on a phone) can also move to the next step, reset, or simulate a weak or lost signal.

## How the shared demo works

- **One state, many tabs.** `demo/engine.ts` stores only what people actually did (SOS pressed at, accepted at, and so on) as timestamps. Everything else, such as the stage, the ambulance position, the ETA and hospital rerouting, is worked out from those timestamps and the current time by `derive()`. This means every tab shows exactly the same thing.
- **Sync.** `demo/DemoProvider.tsx` sends each change to other tabs with a BroadcastChannel and saves it in localStorage, so a reload keeps the emergency.
- **Scripted story.** Greenfield Heart Centre is asked first. If it rejects or doesn't answer in 45 seconds, the case moves to Riverside. The crew can ask the family to choose. The door timer runs at 8 times speed so the demo stays short.
- **Maps are schematic.** `ui/DemoMap.tsx` draws a simple road sketch of Akurdi, Nigdi and Pimpri, not a real map. The camera frames the ambulance and where it is heading, or every hospital on the overview maps.

## Design

- **Plain language, one flow.** Ask for help, we understand, an ambulance comes, the hospital is ready. No code and no technical terms.
- **White theme** with rerun.io's type scale and light 450 weight headings, on the normal system font.
- **citizen.com's oval phone frames**, taken from its production CSS: `border-radius: 13% / 6%` (elliptical corners), an 8px dark ring via `box-shadow: 0 0 0 8px #1a1a1a`, and a slow 2rem slide up (1.5s, `cubic-bezier(0.17, 0.67, 0.21, 0.95)`) as each phone enters the screen. The phone apps use the same frame on a laptop and go full screen on a phone.
- **Pill shapes** (40px radius) for buttons and tags, and large rounded panels, also following citizen.com.
- **Charts** use one blue, plain stat tiles and bars, and every chart can switch to a table.
- The ambulance app is dark by default at night, with a setting to change it.
- Animations turn off for visitors who ask their device for reduced motion.

## Languages

The website is available in **English, हिन्दी (Hindi), मराठी (Marathi), తెలుగు (Telugu), தமிழ் (Tamil) and ગુજરાતી (Gujarati)**. The family tracking page is also in all six, because relatives open it from an SMS. The other app screens are in English for this demo, and the patient app settings say so.

- A language button in the header switches instantly. The choice is remembered on that device.
- On a first visit the site opens in the visitor's phone language if it is one of these six, otherwise English.
- The page `lang` attribute and browser tab title change with the language.
- Indian scripts get the Nirmala UI / Noto Sans fonts and taller line spacing so vowel signs are never clipped.
- The product itself understands voice and text in Hindi, Marathi and English, as the project plan says, and the text says so honestly in every language.

Translations were written for this site and should be checked by native speakers before any public launch, especially the medical and emergency wording.

## Website page order

1. **Hero**: headline, two buttons, three phones (asking for help, ambulance on the way, hospital ready).
2. **How it works**: four clickable steps; the phone beside them changes screen as each step plays.
3. **Everyone works together**: the ambulance crew app and the hospital app, one phone each.
4. **Why it's different**: six simple cards, plus a "See all 39 features" button that opens the full list.
5. **If something goes wrong**: four reassuring cards.
6. **Across Pune and Pimpri Chinchwad**: area pills.
7. **Questions**: five FAQs.
8. **Closing panel** and a one line **footer**.

## Files

### Start up
- `index.html`: page shell, title, favicon.
- `src/main.tsx`: starts React and loads the website styles.
- `src/App.tsx`: wraps everything in the language, motion, demo and toast providers, and maps each address to its app. The apps load only when opened.

### Website
- `src/site/SitePage.tsx`: puts the website sections in order and makes in page links (like `#faq`) scroll instead of changing the address.
- `src/index.css`: all website styles and colors, including the oval phone frame (`.phone`).
- `src/components/Header.tsx`: top bar, with the "Live demo" link.
- `src/components/Hero.tsx`: the opening section.
- `src/components/HowItWorks.tsx`: the four steps with the changing phone.
- `src/components/Sections.tsx`: the rest of the page (the two apps, why it's different, if something goes wrong, the Pune areas, questions, the closing panel, the footer).
- `src/components/Screens.tsx`: the six phone screens used on the website.
- `src/components/PhoneFrame.tsx`: the citizen style oval phone, with its slide up entrance.
- `src/components/Reveal.tsx`: fades a block in when you scroll to it.
- `src/components/motion.ts`: the two animation curves (rerun.io's soft entrance, citizen.com's phone slide).
- `src/components/LanguageMenu.tsx`: the language button and dropdown in the header.

### Languages
- `src/i18n/types.ts`: the shape every language file must fill; the build fails if any language is missing a line.
- `src/i18n/en.ts`, `hi.ts`, `mr.ts`, `te.ts`, `ta.ts`, `gu.ts`: all website and family page text, one file per language.
- `src/i18n/context.ts`: the language list, the `useI18n()` hook, and remembering or detecting the language.
- `src/i18n/I18nProvider.tsx`: holds the current language and updates the page `lang` and title.

### Shared demo engine (`src/demo/`)
- `data.ts`: the sample data from spec section 9: the Kulkarni family, emergency contacts, eight hospitals, ambulances, routes, the doctor's questions, first aid and CPR steps, reject reasons and the on call team.
- `engine.ts`: the demo state, the timings, the stages, and `derive()`, which works out everything shown on screen from the timestamps.
- `store.ts`: loading and saving the state, `useNow()` (a ticking clock) and `useDemo()`.
- `DemoProvider.tsx`: shares the state between tabs.
- `actions.ts`: every button's action (SOS, accept, confirm, reject, family choice, cancel, answer, next step, reset, and so on) and the plain English name of each stage.
- `format.ts`: clock times, ETA ranges, distances, "3 min ago", initials and avatar colors.
- `hospitalInfo.ts`: room, gate, team and doctor for each receiving hospital.
- `steps.ts`: the progress steps shown to the patient and the family.

### Shared building blocks (`src/ui/`, spec section 2)
- `Icon.tsx`: simple line icons and category icons. No emoji anywhere.
- `Bits.tsx`: severity badge, category chip, AI confidence, ETA, progress stepper, countdown ring, "updated 5 min ago", signal badge, room chip, ambulance type, "why this hospital" chips, banners, avatars, the "Simulated" tag, empty states, loading skeletons and the call button.
- `DemoMap.tsx`: the schematic map with the ambulance, the pickup pin, routes and hospitals, plus zoom, follow, recenter and full screen.
- `charts.tsx`: stat tiles, chart cards with a table view, columns, horizontal bars, meters and a heatmap.
- `Dialog.tsx`: the bottom sheet dialog and the reject reason dialog.
- `toast.ts` and `ToastProvider.tsx`: short messages at the bottom of the screen.

### App shell (`src/apps/shell/`)
- `PhoneShell.tsx`: shows an app inside the oval phone with the demo panel on a laptop, or full screen on a phone.
- `DemoBar.tsx`: the demo panel (next step, reset, autoplay, signal, links to the other apps) and its small "Demo" pill.

### Patient app (`src/apps/patient/`)
- `PatientApp.tsx`: the patient app addresses, and the check that sends signed out visitors to sign in.
- `layout.tsx`: top bar, bottom tabs, the Call 108 bar and the screen wrapper.
- `Onboarding.tsx`: splash, phone number, OTP, permissions and profile setup.
- `Home.tsx`: "Who needs help?", the hold to SOS button, speaking or typing what happened, and adjusting the location.
- `speech.ts`: reading text aloud and listening for "yes" or "no" answers.
- `Live.tsx`: sending, help requested, the doctor's questions, first aid, the live emergency screen with the map and hospital card, and the summary after hand over.
- `Cpr.tsx`: hands only CPR with a 110 beats per minute sound and voice guidance.
- `Family.tsx`: the family space, member profiles, invite by QR code, joining a family and adding a dependent.
- `Account.tsx`: profile, emergency contacts (drag to reorder), history, notifications and settings.
- `people.ts`: names for "who needs help" and the saved location.
- `session.ts`: remembers that the demo user is signed in.

### Ambulance app (`src/apps/ambulance/`)
- `AmbulanceApp.tsx`: sign in, vehicle check, on duty, incoming request with a 20 second ring, navigation with turn by turn steps, the patient card, one tap patient confirm, taking the patient to hospital, asking the family, at the hospital with the door timer, history and settings.
- `crew.ts`: crew settings (dark mode, sounds, landscape) and the alert tone.

### Hospital dashboard (`src/apps/hospital/`)
- `HospitalApp.tsx`: sign in, side menu and top bar.
- `Dashboard.tsx`: new requests with a 45 second respond ring, incoming ambulances, at the door, and the capacity snapshot.
- `Pages.tsx`: rooms, resources, staff and shifts, patient details, alerts and settings.
- `Analytics.tsx`: the hospital's charts.
- `shared.ts`: rooms, the alert tone and live room status.

### Other pages
- `src/apps/family/FamilyTrack.tsx`: the family tracking page. It shows where the ambulance is, when it arrives and which hospital, and never shows medical details.
- `src/apps/ops/OpsApp.tsx`: the ops page with an escalation ("no hospital accepting") that has one tap options and a safe default after 60 seconds, system analytics, and the scenario runner.
- `src/apps/DemoLauncher.tsx`: the `#/demo` page.
- `src/apps/app.css`: styles shared by all apps (buttons, phone shell, forms, patient screens, building blocks, map, dialogs, demo panel, dark theme).
- `src/apps/screens.css`: styles for the ambulance, hospital, charts, family page, ops page and launcher.

## Honest limits of this demo

- There is no server. Tabs stay in sync only inside one browser.
- The map is a schematic sketch, not a real map, and routes are drawn, not computed.
- AI results (severity, category, confidence, handover summary) are scripted sample outputs.
- In the ops page, "Normal heart emergency" runs the real demo; the other scenarios only preview what the checks would look like.
- The language screen (P2) is left out, because the app screens are English only for now.

## Notes

- No em dashes or en dashes in any visible text. Ranges are written as "7 to 12 min".
- Hospitals, ambulances and people shown are simulated, and every screen says so.
- Calling 108 is always offered: on the website and on every patient screen.
- Footer: © 2026 Ragini Pawar. All rights reserved for the layout and UI/UX design.
