# medico

Clinical referral decision-support prototype: React + FastAPI + SQLite
(PostgreSQL-ready). Clinic staff enter a synthetic patient assessment; a
modular rule engine classifies urgency (**GREEN** Routine / **ORANGE** Urgent /
**RED** Emergency) and returns an initial clinic decision with clear
explanations.

**This is decision support, not autonomous diagnosis.** Every result states that it
must be reviewed by a qualified healthcare professional. The demonstration rules
are placeholder logic for the prototype — they are **not clinically validated**
and must be replaced or validated before any real use.

## Stack

| Layer     | Technology                                              |
|-----------|---------------------------------------------------------|
| Frontend  | React (Vite), plain CSS                                  |
| Backend   | Python, FastAPI, Uvicorn                                |
| Database  | SQLite by default; PostgreSQL via `DATABASE_URL` (no ORM) |
| Rules     | Custom rule engine (condition / severity / weight / explanation) |
| Maps      | OpenStreetMap tiles, Nominatim geocoding, OSRM routing (later prompts) |

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
│   │   ├── main.py       # FastAPI app, CORS, lifespan (DB init), API description
│   │   ├── config.py     # environment-driven settings (DATABASE_URL, CORS origin)
│   │   ├── api/
│   │   │   ├── schemas.py   # request/response models + input validation
│   │   │   └── routes.py    # all HTTP endpoints under /api
│   │   ├── rules/
│   │   │   ├── engine.py      # condition evaluator (all/any/not, 10 operators)
│   │   │   ├── demo_rules.py  # demonstration GREEN/ORANGE/RED rules (not clinical)
│   │   │   ├── urgency.py     # highest-severity-wins classification + explanations
│   │   │   ├── decision.py    # urgency -> initial clinic decision
│   │   │   └── registry.py    # reserved for validated rules later
│   │   ├── db/
│   │   │   ├── connection.py        # dialect-aware SQLite/PostgreSQL layer
│   │   │   ├── schema.sql           # SQLite tables (locations, assessments)
│   │   │   ├── schema.postgres.sql  # PostgreSQL tables
│   │   │   └── repository.py        # assessment/location persistence
│   │   └── maps/           # geo helpers (used in later prompts)
│   └── tests/              # pytest: rules, urgency, decisions, db, api
└── frontend/
    ├── package.json
    ├── vite.config.js      # dev server + /api proxy to the backend
    └── src/
        ├── App.jsx            # assessment flow: form <-> result view
        ├── lib/api.js         # API service layer + 422 field mapping
        ├── hooks/useAsync.js  # small data-loading hook
        └── components/
            ├── Layout.jsx         # shell + safety banner (header, main, footer)
            ├── HealthBadge.jsx    # live /api/health indicator
            ├── ui.jsx             # Field / TextInput / TextArea / SelectField
            ├── AssessmentForm.jsx # patient + vitals form with client validation
            ├── UrgencyBadge.jsx   # GREEN/ORANGE/RED pill
            └── ResultView.jsx     # urgency band, reasons, decision, rule details
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

## API overview

| Method | Path                             | Purpose                                        |
|--------|----------------------------------|------------------------------------------------|
| GET    | `/api/health`                    | Status + DB check (URL credentials redacted)   |
| POST   | `/api/assessments`               | Run assessment: returns urgency + decision     |
| GET    | `/api/assessments?limit=N`       | Recent saved assessments (id, urgency, score)  |
| GET    | `/api/assessments/{id}`          | One saved assessment with full result          |
| POST   | `/api/rules/score`               | Raw rule engine: `{input, rules?}`             |
| GET    | `/api/maps/config`               | Tile/geocoder/router config (later prompts)    |
| GET    | `/api/locations`                 | List locations (SQLite CRUD)                   |
| POST   | `/api/locations`                 | Create a location                              |
| GET    | `/api/locations/{id}`            | Fetch one location                             |
| DELETE | `/api/locations/{id}`            | Delete a location                              |

Interactive API docs: http://localhost:8000/docs

Example:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/assessments -Method Post `
  -ContentType "application/json" -Body '{
    "patient_id": "SYN-001",
    "age_years": 50,
    "sex": "female",
    "chief_complaint": "Shortness of breath",
    "vitals": {
      "heart_rate": 118,
      "systolic_bp": 96,
      "diastolic_bp": 55,
      "respiratory_rate": 25,
      "oxygen_saturation": 92,
      "temperature_c": 38.6
    }
  }'
```

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
4. **Decision** — `decide(urgency)` maps to `manage_locally` (GREEN),
   `referral_recommended` (ORANGE), `immediate_referral` (RED). The function
   takes an optional context reserved for later clinic/hospital inputs.
5. **Persistence** — each assessment is saved (`assessments` table) with the
   input snapshot and full result; results are re-fetchable by id.

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
The engine is generic; the bundled rules live in `demo_rules.py` and are
labeled `RULES_SOURCE="demonstration"`. The real validated rules belong in
`registry.py` once they are approved.

## Database

- Default: SQLite file at `backend/data/medico.db`, created on first start.
- PostgreSQL: set `DATABASE_URL=postgresql://...`; `schema.postgres.sql` is
  used and the connection layer adapts placeholders/`RETURNING` per dialect.
- Tables: `assessments` (input snapshot + result) and `locations` (map
  feature data for later prompts). Credentials are never logged or returned.

## Tests

```powershell
cd medico/backend
.\.venv\Scripts\python.exe -m pytest tests -q
```

33 tests: rule engine operators, urgency classification (GREEN/ORANGE/RED),
decision mapping, input validation (ranges, BP order, missing fields),
assessment persistence and API error handling.

## Scope boundaries

- Decision-support prototype only — not a medical device, not a diagnosis.
- No personal data: never add names, phone numbers, or addresses of patients.
- Hospital matching, routing, capacity ranking, referral tracking and
  summaries are intentionally **not implemented** yet — they belong to
  later prompts.

## Commands at a glance

```powershell
# backend
cd medico\backend ; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
# frontend
cd medico\frontend ; npm run dev
# tests
cd medico\backend ; .\.venv\Scripts\python.exe -m pytest tests -q
```
