"""CRUD operations.

Rows are returned as plain dicts; SQL uses `?` placeholders and
`RETURNING id`, which both SQLite and PostgreSQL understand, so this module
needs no changes when switching databases.
"""
from __future__ import annotations

import json
from typing import Any

from ..config import Settings
from .connection import db_session


# --------------------------------------------------------------------------- #
# Locations
# --------------------------------------------------------------------------- #
def create_location(
    name: str,
    latitude: float,
    longitude: float,
    address: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    with db_session(settings) as connection:
        row = connection.execute(
            "INSERT INTO locations (name, latitude, longitude, address) "
            "VALUES (?, ?, ?, ?) RETURNING id",
            (name, latitude, longitude, address),
        ).fetchone()
        location_id = row["id"]
    return get_location(location_id, settings)  # type: ignore[return-value]


def get_location(location_id: int, settings: Settings | None = None) -> dict | None:
    with db_session(settings) as connection:
        row = connection.execute(
            "SELECT * FROM locations WHERE id = ?", (location_id,)
        ).fetchone()
    return row


def list_locations(settings: Settings | None = None) -> list[dict]:
    with db_session(settings) as connection:
        rows = connection.execute("SELECT * FROM locations ORDER BY id").fetchall()
    return rows


def delete_location(location_id: int, settings: Settings | None = None) -> bool:
    with db_session(settings) as connection:
        cursor = connection.execute("DELETE FROM locations WHERE id = ?", (location_id,))
        return cursor.rowcount > 0


# --------------------------------------------------------------------------- #
# Assessments
# --------------------------------------------------------------------------- #
def create_assessment(
    *,
    patient_id: str,
    age_years: int,
    sex: str,
    urgency: str,
    decision: str,
    score: float,
    input_data: dict[str, Any],
    result_data: dict[str, Any],
    settings: Settings | None = None,
) -> dict[str, Any]:
    with db_session(settings) as connection:
        row = connection.execute(
            "INSERT INTO assessments "
            "(patient_id, age_years, sex, urgency, decision, score, input_json, result_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                patient_id,
                age_years,
                sex,
                urgency,
                decision,
                score,
                json.dumps(input_data),
                json.dumps(result_data),
            ),
        ).fetchone()
        assessment_id = row["id"]
    return get_assessment(assessment_id, settings)  # type: ignore[return-value]


def _row_to_record(row: dict[str, Any]) -> dict[str, Any]:
    record = dict(row)
    record["input"] = json.loads(record.pop("input_json"))
    record["result"] = json.loads(record.pop("result_json"))
    return record


def get_assessment(assessment_id: int, settings: Settings | None = None) -> dict | None:
    with db_session(settings) as connection:
        row = connection.execute(
            "SELECT * FROM assessments WHERE id = ?", (assessment_id,)
        ).fetchone()
    return _row_to_record(row) if row else None


def list_assessments(limit: int = 50, settings: Settings | None = None) -> list[dict]:
    with db_session(settings) as connection:
        rows = connection.execute(
            "SELECT id, patient_id, age_years, sex, urgency, decision, score, created_at "
            "FROM assessments ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return rows
