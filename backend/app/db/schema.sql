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
