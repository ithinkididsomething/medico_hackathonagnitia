# medico

Clinical referral decision-support prototype: React + FastAPI + SQLite
(PostgreSQL-ready). Clinic staff enter a synthetic patient assessment; a
modular rule engine classifies urgency (**GREEN** Routine / **ORANGE** Urgent /
**RED** Emergency), checks whether the current clinic's configured resources
can cover the case, produces an initial clinic decision, and — when referral
is required — ranks nearby hospitals by transparent capability scores with
hard constraints, **live OSRM road routing** (distance + travel time), an
OpenStreetMap referral map, generated "why not" explanations and dynamic
fallback. Selected recommendations become a **structured referral summary**,
persisted as an auditable **referral record** that clinic staff track on a
filterable dashboard through pending → referred → accepted → transferred →
completed.

**This is decision support, not autonomous diagnosis.** Every result states that it
must be reviewed by a qualified healthcare professional. The demonstration rules
and hospital data are placeholder logic for the prototype — they are **not
clinically validated** and the hospital records are **synthetic**, not real
facilities or real availability.

## Stack

| Layer     | Technology                                              |
|-----------|---------------------------------------------------------|
| Frontend  | React (Vite), plain CSS                                  |
| Backend   | Python, FastAPI, Uvicorn                                |
| Database  | SQLite by default; PostgreSQL via `DATABASE_URL` (no ORM) |
| Rules     | Custom rule engine (condition / severity / weight / explanation) |
| Matching  | Hard constraints + weighted capability + travel-aware scoring + fallback |
| Maps      | OpenStreetMap tiles (Leaflet/react-leaflet), Nominatim geocoding, OSRM road routing with graceful placeholder fallback |

All external endpoints and any future API keys are read from environment
variables — see `.env.example`. No secrets are committed. No personal data is
stored: only a clinic-assigned `patient_id`, never names or contact details.

## Project structure

```
medico/
├── .env.example          # copy to .env for local overrides (never commit .env)
├── .gitignore
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── data/medico.db    # created automatically on first start (git-ignored)
│   ├── app/
│   │   ├── main.py       # FastAPI app, CORS, lifespan (DB init + hospital seed)
│   │   ├── config.py     # environment-driven settings (DATABASE_URL, CORS origin)
│   │   ├── api/
│   │   │   ├── schemas.py   # request/response models + input validation
│   │   │   └── routes.py    # all HTTP endpoints under /api
│   │   ├── rules/
│   │   │   ├── engine.py      # condition evaluator (all/any/not, 10 operators)
│   │   │   ├── demo_rules.py  # demonstration GREEN/ORANGE/RED rules (not clinical)
│   │   │   ├── urgency.py     # highest-severity-wins classification + explanations
│   │   │   ├── decision.py    # urgency + clinic capability -> clinic decision
│   │   │   └── registry.py    # reserved for validated rules later
│   │   ├── matching/          # Prompts 2-3: clinic + hospitals + scoring
│   │   │   ├── clinic.py       # configurable clinic capabilities/location + Part 1 check
│   │   │   ├── requirements.py # demo requirement rules (reuse rule engine)
│   │   │   ├── catalog.py      # Hospital model + SYNTHETIC demonstration data
│   │   │   └── scoring.py      # hard constraints + travel-aware weights + fallback
│   │   ├── db/
│   │   │   ├── connection.py        # dialect-aware SQLite/PostgreSQL layer
│   │   │   ├── schema.sql           # SQLite tables (locations, assessments, hospitals, referrals)
│   │   │   ├── schema.postgres.sql  # PostgreSQL tables
│   │   │   └── repository.py        # persistence incl. referral CRUD + status audit
│   │   ├── referrals.py     # summary builder + hospital selection + status machine
│   │   └── maps/                 # OpenStreetMap integration
│   │       ├── geo.py      # haversine helpers (no network)
│   │       ├── geocode.py  # Nominatim geocoding
│   │       ├── routing.py  # OSRM route provider (distance, time, geometry)
│   │       └── travel.py   # TravelEstimator: routing + graceful placeholder fallback
│   └── tests/              # pytest: rules, urgency, matching, routing, referral flow
└── frontend/
    ├── package.json
    ├── vite.config.js      # dev server + /api proxy to the backend
    └── src/
        ├── App.jsx            # navigation: assessment flow <-> referral dashboard
        ├── lib/api.js         # API service layer + 422 field mapping
        ├── hooks/useAsync.js  # small data-loading hook
        └── components/
            ├── Layout.jsx         # shell + nav tabs + safety banner
            ├── HealthBadge.jsx    # live /api/health indicator
            ├── ui.jsx             # Field / TextInput / TextArea / SelectField
            ├── AssessmentForm.jsx # patient + vitals form with client validation
            ├── UrgencyBadge.jsx   # GREEN/ORANGE/RED pill
            ├── FlowSteps.jsx      # Part 1: visible end-to-end workflow strip
            ├── ClinicCapabilityCard.jsx   # Part 1: can this clinic manage locally?
            ├── HospitalRecommendations.jsx # best match + alternatives + why-not
            ├── ReferralMap.jsx            # OpenStreetMap referral map
            ├── ReferralSummary.jsx        # structured summary + print/export
            ├── ReferralDashboard.jsx      # filterable list + detail + status audit
            └── ResultView.jsx     # urgency, decision, matches, referral creation
```

## Setup

### 1. Backend

```powershell
cd medico/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```powershell
cd medico/frontend
npm install
npm run dev
```

Open http://localhost:5173 — the header badge should show **backend online**.
The Vite dev server proxies `/api` to the backend (`BACKEND_URL`), so CORS
rarely needs configuration locally.

### 3. Configuration (optional)

```powershell
Copy-Item ..\.env.example ..\.env     # from the backend or frontend folder
```

Defaults work out of the box (local SQLite file, no API keys). Key settings:

| Variable           | Purpose                                            |
|--------------------|----------------------------------------------------|
| `DATABASE_URL`     | `sqlite:///...` (default) or `postgresql://...`    |
| `DATABASE_PATH`    | SQLite-only shortcut for the local file path       |
| `FRONTEND_ORIGIN`  | CORS origin allowed to call the API                |
| `BACKEND_URL`      | Where the Vite dev server proxies `/api`           |
| `ROUTING_ENABLED`  | `false` disables live OSRM (placeholder estimates) |
| `CLINIC_LATITUDE` / `CLINIC_LONGITUDE` | Demo clinic location (routing origin) |

## API overview

| Method | Path                             | Purpose                                        |
|--------|----------------------------------|------------------------------------------------|
| GET    | `/api/health`                    | Status + DB check (URL credentials redacted)   |
| POST   | `/api/assessments`               | Assess: urgency + requirements + clinic check + decision (+ hospital matches when referral) |
| GET    | `/api/assessments?limit=N`       | Recent saved assessments (id, urgency, score)  |
| GET    | `/api/assessments/{id}`          | One saved assessment with full result          |
| POST   | `/api/referrals/match`           | Match/rank hospitals (hard constraints + scoring + fallback) |
| POST   | `/api/referrals`                 | Create referral record + structured summary (409 when no suitable hospital) |
| GET    | `/api/referrals`                 | Dashboard list with filters (`urgency`, `status`, `recommendation`, `date_from`, `date_to`) + counts |
| GET    | `/api/referrals/{ref}`           | One referral (by id or `REF-...`) with summary + status history |
| PATCH  | `/api/referrals/{ref}/status`    | Explicit audited status transition (409 on invalid transition) |
| GET    | `/api/referrals/{ref}/summary.txt` | Plain-text summary (print/export helper) |
| GET    | `/api/hospitals`                 | Hospital list (SYNTHETIC demonstration data)   |
| GET    | `/api/clinics/current`           | Current clinic profile + capabilities + location |
| PATCH  | `/api/clinics/current`           | Override clinic capabilities/location (process-local) |
| DELETE | `/api/clinics/current`           | Reset clinic override to the demo default      |
| POST   | `/api/route`                     | Route two coordinates (distance, time, geometry; 502 on provider failure) |
| POST   | `/api/rules/score`               | Raw rule engine: `{input, rules?}`             |
| GET    | `/api/maps/config`               | Tile/geocoder/router config + `routing_enabled` (no secrets) |
| GET    | `/api/locations`                 | List locations (SQLite CRUD)                   |
| POST   | `/api/locations`                 | Create a location                              |
| GET    | `/api/locations/{id}`            | Fetch one location                             |
| DELETE | `/api/locations/{id}`            | Delete a location                              |

Interactive API docs: http://localhost:8000/docs

## Assessment flow

1. **Input** — clinic-assigned `patient_id` (no names/contact), age, sex,
   chief complaint, optional vitals (HR, BP, respiratory rate, SpO₂,
   temperature) and an explicit emergency indicator.
2. **Validation** — server-side Pydantic ranges (e.g. SpO₂ 50–100 %, HR
   20–300 bpm, systolic ≥ diastolic); the browser mirrors these rules and
   maps 422 field errors back onto the form.
3. **Urgency** — `classify_urgency()` runs the demonstration rules; the
   **highest triggered severity wins** (RED > ORANGE > GREEN), score is the
   sum of triggered weights, and every triggered rule adds a plain-language
   reason.
4. **Case requirements** — `derive_requirements()` turns assessment + urgency
   into `required_specialty`, `needs_emergency` (none/basic/full),
   `needs_icu`, `required_diagnostics`, `required_treatment` using
   configurable demonstration rules (same condition engine) plus
   staff-selected specialty and complaint keyword hints.
5. **Clinic capability (Part 1)** — `assess_clinic_capability()` compares the
   requirements with the clinic's configured capabilities/specialties and
   lists met items and gaps. A GREEN case the clinic cannot cover is upgraded
   to **referral recommended** by `decide()`.
6. **Hospital matching (Parts 3–6)** — when the decision is
   referral/immediate, `match_hospitals()` applies **hard constraints**
   (availability, capacity, specialty, emergency level, ICU, diagnostics,
   treatments) that fully exclude unsuitable hospitals, estimates **real road
   distance and travel time** from the clinic via OSRM (`TravelEstimator`,
   placeholder fallback on failure), then **scores** the eligible ones on
   configurable weights with automatic **fallback** + generated explanations
   when the top hospital is unavailable in the simulated feed.
7. **Persistence** — each assessment is saved (`assessments` table) with the
   input snapshot and full result; results are re-fetchable by id.

## Complete workflow

The UI shows this flow explicitly (`FlowSteps.jsx`) and the dashboard closes
it:

```
Doctor/Clinic Staff
  → Patient assessment
  → Urgency assessment (GREEN / ORANGE / RED)
  → Can the clinic manage the patient?
      YES → Manage locally (flow ends, no referral)
      NO  → Referral required
            → Hospital capability matching (hard constraints)
            → Availability / capacity check
            → Distance + travel time (OSRM)
            → Hospital ranking (best + alternatives)
            → Referral summary (structured record)
            → Referral tracking (pending → referred → accepted
                                 → transferred → completed)
```

## Referral summary and record

Selecting **Create referral record** (available once matching produced a
best match) re-runs matching server-side — client-supplied scores are never
trusted — and persists:

- **Summary** (`summary_json`): patient id, age, sex, main complaint,
  important clinical findings, vital signs, urgency level, reason for
  referral, required specialty/facilities, recommended hospital (score,
  why-this reasons, distance, estimated travel time), alternative hospital,
  generated explanation, why-not reasons for alternatives, fallback detail,
  travel-source note, timestamps and disclaimers. No names or contact data.
- **Record** (`referrals` table): referral id (`REF-YYYYMMDD-XXXXXX`),
  assessment link, urgency, recommendation code, recommended/alternative
  hospital ids, status, explanation, created/updated timestamps.
- **Audit trail** (`referral_status_events`): every status change stores
  from → to, an optional note, the actor and a timestamp. The state machine
  (`pending → referred → accepted|transferred → completed`) is enforced
  server-side; invalid transitions return 409.

The summary can be viewed on-screen, **printed / saved as PDF** (print
stylesheet), or downloaded as **plain text** (`GET .../summary.txt`).

## Referral dashboard

`ReferralDashboard.jsx` lists referrals as a table (Case | Priority |
Recommendation | Hospital | Status | Created) with filters for **priority**
(emergency/urgent/routine), **status**, **recommendation** and **date
range**, plus count chips and a clear empty state. Opening a row shows the
full summary, the status history, and a status editor that only offers
server-approved next transitions with an audit note.

## Matching architecture

```
requirements ──► check_eligibility (HARD CONSTRAINTS, exclude not rank-down)
                     │ pass
                     ▼
TravelEstimator(clinic origin) ──► OSRM route per hospital
   (per-hospital fallback to straight-line placeholder on failure)
                     │ {distance_km, travel_minutes, source, route_coordinates}
                     ▼
                 score_hospital (weights: specialty 25, emergency 20, ICU 15,
                                 diagnostics 15, treatment 10, capacity 9,
                                 distance 3, travel_time 3 — normalised over
                                 applicable factors; medical ≈ 94 of 100 pts)
                     │
                     ▼
                 rank by total_score ──► best_match + alternatives + excluded
                     │ (top hospital in simulated outage?)
                     ▼
                 fallback: re-evaluate eligibility, reuse computed
                 scores/routes, select next eligible hospital;
                 fallback_detail + why_not explain every choice
```

- Every factor returns `earned / possible / reason`; the total is
  `100 × earned / applicable` so cases only pay for factors that apply.
- Weights are configurable per request (`weights` on `/api/referrals/match`).
- **Capability beats proximity:** the geographic factors hold at most
  6 points by default, and a closer hospital that fails a hard constraint is
  excluded outright — proximity can never outrank a better-matched hospital.
- Scores measure **capability fit for this case** — not clinical quality and
  not a "nearest hospital" ranking.

## Routing architecture

```
React map ──► GET /api/maps/config (tiles, router URL, routing_enabled)
Match flow ──► app/maps/travel.py TravelEstimator(origin)
                   │ route_fn abstraction (default: app/maps/routing.py → OSRM)
                   ├─ success  → {source: "osrm", distance_km, travel_minutes,
                   │             route_coordinates (thinned to ≤60 points)}
                   └─ failure/disabled → {source: "placeholder", straight-line
                                 distance, 25 km/h estimate, explicit reason}
POST /api/route ──► same routing.py provider (single-route requests; 502 on failure)
```

- The provider sits behind an abstraction (`route_fn` / `routing.py`), so the
  routing engine can be swapped (self-hosted OSRM, other OSM engines) without
  touching scoring or the UI. `ROUTING_ENABLED=false` forces placeholders.
- Failures never break matching: each hospital falls back independently and
  the estimate's `note` states exactly why the numbers are placeholders.
- Route polylines (thinned) travel with the match result and are drawn on the
  referral map without extra requests.

## Referral map (frontend)

`ReferralMap.jsx` (Leaflet + OpenStreetMap tiles) renders inside the hospital
recommendations: clinic marker, recommended-hospital marker, alternative
markers, excluded candidates, and the routed polyline to the recommended
hospital with distance + estimated travel time. Clicking any marker shows the
hospital's capabilities, suitability score, travel estimate and its
why-not/why-this reasoning. No paid map provider, no API key, no browser
geolocation (the clinic location is configurable server-side).

## Hospital data (SYNTHETIC)

Six clearly-labelled synthetic hospitals (`SYN-HOSP-01..06`) are seeded into
the `hospitals` table on first start: a full-service general hospital, a
cardiac/trauma centre, a small district hospital (no ICU), a multi-specialty
centre with limited ICU, a teaching hospital that is full + diverting, and a
capable but distant suburban hub. They exist only to exercise every matching
scenario (exclusion, ranking, fallback) and **do not represent real
facilities or real current availability**.

## Rule engine

Rules are data, not code:

```json
{
  "id": "demo_low_oxygen_saturation",
  "severity": "RED",
  "weight": 25,
  "priority": 10,
  "condition": {"field": "vitals.oxygen_saturation", "op": "lt", "value": 90},
  "explanation": "Oxygen saturation below configured demonstration threshold (<90%)."
}
```

Conditions support `eq, ne, gt, gte, lt, lte, in, not_in, contains, exists`,
dotted paths (`vitals.oxygen_saturation`) and nest with `all` / `any` / `not`.
The engine is generic; the bundled rules live in `demo_rules.py`
(urgency) and `matching/requirements.py` (case requirements), both labeled
`demonstration`. The real validated rules belong in `registry.py` once they
are approved.

## Database

- Default: SQLite file at `backend/data/medico.db`, created on first start.
- PostgreSQL: set `DATABASE_URL=postgresql://...`; `schema.postgres.sql` is
  used and the connection layer adapts placeholders/`RETURNING` per dialect.
- Tables: `assessments` (input snapshot + result), `hospitals` (capability
  model, seeded with synthetic rows), `referrals` (structured summary
  snapshot + status), `referral_status_events` (audit trail),
  `locations` (map feature data). Credentials are never logged or returned.

## Tests

```powershell
cd medico/backend
.\.venv\Scripts\python.exe -m pytest tests -q
```

110 tests: rule engine operators, urgency classification, decision mapping
(including the clinic-capability flip), input validation, assessment
persistence, requirement derivation, the full matching scenario matrix
(missing specialty/ICU, insufficient capacity, diverting status, multiple
suitable hospitals, no suitable hospital, configurable weights, fallback),
travel estimation (successful routing, provider failure, missing coordinates,
routing disabled, batch estimates, geometry thinning), travel-aware ranking
(nearer-but-weaker hospital vs farther-but-better-matched, excluded despite
proximity), why-not generation, fallback detail, clinic location
configuration, `POST /api/route` (success/failure/validation), the
hospitals/clinics/match API endpoints, and the complete referral flow:
the three end-to-end cases (routine → managed locally with referral
rejected; urgent → referral with full summary; emergency → matching →
ranking → summary → pending→referred→accepted→transferred→completed audit
trail), no-suitable-hospital 409 (no fabricated recommendation), fallback
referral, routing-failure resilience, hospital selection, dashboard
filters/counts/empty states, invalid filters, and status-transition
validation (409s, unknown statuses, terminal states).

End-to-end HTTP smoke of the same scenarios (live OSRM, both routing modes,
frontend + proxy) is run manually against running servers.

## Known prototype limitations

- **Not clinically validated.** The rules, requirement logic and scoring
  weights are demonstration-only. Real deployment would require clinical
  validation, authorized (real) hospital capability data, privacy/security
  controls and appropriate regulatory review (e.g. medical-device and data
  protection law as applicable).
- **Hospital availability is simulated**, not real-time; capacity fields are
  static synthetic data. The "unavailable hospital" input exists purely to
  exercise fallback logic.
- Routing uses public OSRM with **no live traffic**; estimates are typical
  driving times only, and fall back to straight-line placeholders per
  hospital when routing fails or is disabled.
- No authentication, no user accounts, no role-based access: the audit
  trail records a generic `clinic_staff` actor.
- No PII by design — which also means no real patient records: a production
  system needs encryption at rest/in transit, retention policies, consent
  handling and audit access controls.
- The clinic profile override is process-local (resets on restart);
  referrals live in the database but assessments are not linked back into a
  longitudinal patient history.
- Single-process demo assumptions: no queueing, no rate limiting, no
  background jobs.
- **Suggested referral levels (1-4) are prototype decision-support
  categories**, not a diagnosis and not a substitute for clinical judgment.
  The example symptoms/keyword rules are configurable prototype data, not
  universally validated clinical protocols. Production deployment requires
  review and validation by qualified healthcare professionals, and emergency
  decisions must follow applicable local clinical protocols.

## Recommended next steps for production

1. Clinical governance: replace demo rules/weights with validated,
   version-controlled clinical protocols under clinician oversight.
2. Authorized hospital data: integrate a maintained facility directory with
   availability feeds and clear data provenance/licensing.
3. Security: authentication + RBAC, TLS, secrets management, encrypted
   storage, rate limiting, structured audit logging with real user
   identity.
4. Privacy: DPIA/consent flows, data minimisation beyond the current
   patient_id-only design, retention/deletion policies, jurisdictional
   compliance.
5. Reliability: self-hosted or commercial routing with SLAs, monitoring,
   backups, migrations, and HA for the database.
6. Validation: prospective usability + clinical safety testing, regulatory
   classification review, and post-deployment surveillance.

## Commands at a glance

```powershell
# backend
cd medico\backend ; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
# frontend
cd medico\frontend ; npm run dev
# tests
cd medico\backend ; .\.venv\Scripts\python.exe -m pytest tests -q
```
