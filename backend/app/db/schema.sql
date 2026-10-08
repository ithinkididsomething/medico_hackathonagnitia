-- medico SQLite schema. Kept intentionally small; extend as requirements firm up.

CREATE TABLE IF NOT EXISTS locations (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT    NOT NULL,
    latitude  REAL    NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude REAL    NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    address   TEXT,
    created_at TEXT   NOT NULL DEFAULT (datetime('now'))
);

-- Synthetic patient assessments: no names or contact details are stored.
CREATE TABLE IF NOT EXISTS assessments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id  TEXT    NOT NULL,
    age_years   INTEGER NOT NULL,
    sex         TEXT    NOT NULL,
    urgency     TEXT    NOT NULL CHECK (urgency IN ('GREEN', 'ORANGE', 'RED')),
    decision    TEXT    NOT NULL,
    score       REAL    NOT NULL,
    input_json  TEXT    NOT NULL,
    result_json TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Hospitals: capability model for referral matching. Seeded with clearly
-- labelled SYNTHETIC demonstration rows (is_synthetic=1) — never real data.
CREATE TABLE IF NOT EXISTS hospitals (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id           TEXT    NOT NULL UNIQUE,
    name                  TEXT    NOT NULL,
    latitude              REAL    NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude             REAL    NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    specialties           TEXT    NOT NULL,  -- JSON array of specialty codes
    emergency_capability  TEXT    NOT NULL CHECK (emergency_capability IN ('full', 'basic', 'none')),
    icu_capability        TEXT    NOT NULL CHECK (icu_capability IN ('available', 'limited', 'none')),
    diagnostics           TEXT    NOT NULL,  -- JSON array of diagnostic codes
    treatment_capabilities TEXT   NOT NULL,  -- JSON array of treatment codes
    capacity_status       TEXT    NOT NULL CHECK (capacity_status IN ('open', 'limited', 'full')),
    available_beds        INTEGER NOT NULL DEFAULT 0,
    availability_status   TEXT    NOT NULL CHECK (availability_status IN ('open', 'diverting', 'closed')),
    is_synthetic          INTEGER NOT NULL DEFAULT 1,
    data_note             TEXT    NOT NULL DEFAULT '',
    -- Prompt 6: government-scheme info. INFORMATIONAL ONLY - never used in the
    -- clinical eligibility/safety hierarchy or hospital ranking.
    ayushman_empaneled         INTEGER NOT NULL DEFAULT 0,
    ayushman_verification_date TEXT,
    scheme_supported_specialties TEXT NOT NULL DEFAULT '[]',  -- JSON array
    scheme_supported_packages    TEXT NOT NULL DEFAULT '[]',  -- JSON array
    created_at            TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Referral records: one per referral decision made from an assessment.
-- Stores the structured summary snapshot so the record is self-contained.
CREATE TABLE IF NOT EXISTS referrals (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    referral_id                 TEXT    NOT NULL UNIQUE,
    assessment_id               INTEGER NOT NULL REFERENCES assessments(id),
    patient_id                  TEXT    NOT NULL,
    urgency                     TEXT    NOT NULL CHECK (urgency IN ('GREEN', 'ORANGE', 'RED')),
    recommendation              TEXT    NOT NULL,
    recommended_hospital_id     TEXT,
    recommended_hospital_name   TEXT,
    alternative_hospital_id     TEXT,
    alternative_hospital_name   TEXT,
    status                      TEXT    NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'referred', 'accepted', 'transferred', 'completed')),
    summary_json                TEXT    NOT NULL,
    explanation                 TEXT    NOT NULL DEFAULT '',
    created_at                  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at                  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Audit trail of explicit referral status changes.
CREATE TABLE IF NOT EXISTS referral_status_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    referral_ref  TEXT    NOT NULL,
    from_status   TEXT,
    to_status     TEXT    NOT NULL,
    note          TEXT    NOT NULL DEFAULT '',
    changed_by    TEXT    NOT NULL DEFAULT 'clinic_staff',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- =====================================================================
-- Prompt 6: Government Healthcare Schemes & Benefits layer.
-- All rows are PROTOTYPE configuration derived from official public pages.
-- =====================================================================

-- Curated catalogue of government healthcare schemes, one row per scheme.
CREATE TABLE IF NOT EXISTS government_schemes (
    id                             INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_id                      TEXT    NOT NULL UNIQUE,
    name                           TEXT    NOT NULL,
    short_name                     TEXT,
    government_level               TEXT    NOT NULL DEFAULT 'central'
                                   CHECK (government_level IN ('central', 'state', 'central_state')),
    state                          TEXT,
    department                     TEXT,
    description                    TEXT    NOT NULL DEFAULT '',
    target_beneficiary_category    TEXT,
    age_min                        INTEGER,
    age_max                        INTEGER,
    clinical_categories            TEXT    NOT NULL DEFAULT '[]',   -- JSON array
    coverage_type                  TEXT,
    benefit_type                   TEXT,
    situations                     TEXT    NOT NULL DEFAULT '[]',   -- JSON array
    eligibility_rules              TEXT    NOT NULL DEFAULT '[]',   -- JSON array of rules
    documents                      TEXT    NOT NULL DEFAULT '[]',   -- JSON array of doc codes
    application_verification_method TEXT,
    official_url                   TEXT,
    source_name                    TEXT,
    source_url                     TEXT,
    verified_at                    TEXT,
    last_checked                   TEXT,
    active                         INTEGER NOT NULL DEFAULT 1,
    is_prototype                   INTEGER NOT NULL DEFAULT 1,
    version                        TEXT,
    effective_from                 TEXT,
    effective_until                TEXT,
    benefit_notes                  TEXT    NOT NULL DEFAULT '[]',   -- JSON array
    exclusions_notice              TEXT    NOT NULL DEFAULT '',
    created_at                     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Per-scheme document checklist items (Part 10).
CREATE TABLE IF NOT EXISTS scheme_documents (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    code                      TEXT    NOT NULL UNIQUE,
    label                     TEXT    NOT NULL,
    notes                     TEXT    NOT NULL DEFAULT '',
    applicable_scheme_ids     TEXT    NOT NULL DEFAULT '[]',  -- JSON array
    created_at                TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Official/public sources referenced by the scheme catalogue.
CREATE TABLE IF NOT EXISTS scheme_sources (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id      TEXT    NOT NULL UNIQUE,
    source_name    TEXT    NOT NULL,
    source_url     TEXT,
    source_type    TEXT    NOT NULL DEFAULT 'official',
    region         TEXT,
    last_checked   TEXT,
    notes          TEXT    NOT NULL DEFAULT '',
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Patient benefit profiles (clinic needs the minimum info; NO PII/Aadhaar).
CREATE TABLE IF NOT EXISTS patient_benefit_profiles (
    patient_id                  TEXT    PRIMARY KEY NOT NULL,
    state                       TEXT,
    district                    TEXT,
    locality_type               TEXT    CHECK (locality_type IN ('rural', 'urban')),
    socioeconomic_category      TEXT,
    ayushman_card_status        TEXT    CHECK (ayushman_card_status IN ('yes', 'no', 'unknown')),
    ayushman_status             TEXT    CHECK (ayushman_status IN ('verified', 'not_verified', 'not_available', 'unknown')),
    pregnant                    INTEGER,
    disability                  INTEGER,
    worker_category             TEXT,
    has_bpl_ration_card         INTEGER,
    existing_health_schemes     TEXT    NOT NULL DEFAULT '[]',  -- JSON array
    updated_at                  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Recorded status per patient per scheme (never invented by the system).
CREATE TABLE IF NOT EXISTS patient_scheme_status (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id    TEXT    NOT NULL,
    scheme_id     TEXT    NOT NULL REFERENCES government_schemes(scheme_id),
    status        TEXT    NOT NULL
                  CHECK (status IN ('verified', 'not_verified', 'not_available', 'unknown',
                                    'applied', 'active', 'denied', 'expired', 'not_relevant')),
    note          TEXT    NOT NULL DEFAULT '',
    updated_by    TEXT    NOT NULL DEFAULT 'clinic_staff',
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (patient_id, scheme_id)
);

-- Informational hospital empanelment/scheme compatibility. NEVER consulted
-- during matching/ranking (clinical safety first).
CREATE TABLE IF NOT EXISTS hospital_scheme_eligibility (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id       TEXT    NOT NULL,
    scheme_id         TEXT    NOT NULL REFERENCES government_schemes(scheme_id),
    empaneled         INTEGER NOT NULL DEFAULT 0,
    specialty_codes   TEXT    NOT NULL DEFAULT '[]',  -- JSON array
    packages          TEXT    NOT NULL DEFAULT '[]',  -- JSON array
    verification_date TEXT,
    source            TEXT    NOT NULL DEFAULT 'prototype-configuration',
    notes             TEXT    NOT NULL DEFAULT '',
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (hospital_id, scheme_id)
);
