"""CRUD operations.

Rows are returned as plain dicts; SQL uses `?` placeholders and
`RETURNING id`, which both SQLite and PostgreSQL understand, so this module
needs no changes when switching databases.
"""
from __future__ import annotations

import json
from typing import Any

from ..config import Settings
from ..matching.catalog import Hospital, synthetic_hospitals
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


# --------------------------------------------------------------------------- #
# Hospitals (capability model; seeded with clearly-labelled synthetic rows)
# --------------------------------------------------------------------------- #
_HOSPITAL_COLUMNS = (
    "hospital_id, name, latitude, longitude, specialties, emergency_capability, "
    "icu_capability, diagnostics, treatment_capabilities, capacity_status, "
    "available_beds, availability_status, is_synthetic, data_note, "
    "ayushman_empaneled, ayushman_verification_date, "
    "scheme_supported_specialties, scheme_supported_packages"
)


def _row_to_hospital(row: dict[str, Any]) -> dict[str, Any]:
    """Deserialise JSON list columns and coerce booleans."""
    record = dict(row)
    for column in (
        "specialties",
        "diagnostics",
        "treatment_capabilities",
        "scheme_supported_specialties",
        "scheme_supported_packages",
    ):
        value = record.get(column)
        if isinstance(value, str):
            try:
                record[column] = json.loads(value)
            except json.JSONDecodeError:
                record[column] = []
    record["is_synthetic"] = bool(record.get("is_synthetic"))
    record["ayushman_empaneled"] = bool(record.get("ayushman_empaneled"))
    return record


def upsert_hospital(hospital: Hospital, settings: Settings | None = None) -> dict[str, Any]:
    """Insert or update one hospital (matched on hospital_id)."""
    payload = (
        hospital.hospital_id,
        hospital.name,
        hospital.latitude,
        hospital.longitude,
        json.dumps(hospital.specialties),
        hospital.emergency_capability,
        hospital.icu_capability,
        json.dumps(hospital.diagnostics),
        json.dumps(hospital.treatment_capabilities),
        hospital.capacity_status,
        hospital.available_beds,
        hospital.availability_status,
        1 if hospital.is_synthetic else 0,
        hospital.data_note,
        1 if hospital.ayushman_empaneled else 0,
        hospital.ayushman_verification_date,
        json.dumps(hospital.scheme_supported_specialties),
        json.dumps(hospital.scheme_supported_packages),
    )
    with db_session(settings) as connection:
        connection.execute(
            "INSERT INTO hospitals "
            "(hospital_id, name, latitude, longitude, specialties, emergency_capability, "
            " icu_capability, diagnostics, treatment_capabilities, capacity_status, "
            " available_beds, availability_status, is_synthetic, data_note, "
            " ayushman_empaneled, ayushman_verification_date, "
            " scheme_supported_specialties, scheme_supported_packages) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (hospital_id) DO UPDATE SET "
            "  name = excluded.name, latitude = excluded.latitude, "
            "  longitude = excluded.longitude, specialties = excluded.specialties, "
            "  emergency_capability = excluded.emergency_capability, "
            "  icu_capability = excluded.icu_capability, "
            "  diagnostics = excluded.diagnostics, "
            "  treatment_capabilities = excluded.treatment_capabilities, "
            "  capacity_status = excluded.capacity_status, "
            "  available_beds = excluded.available_beds, "
            "  availability_status = excluded.availability_status, "
            "  is_synthetic = excluded.is_synthetic, data_note = excluded.data_note, "
            "  ayushman_empaneled = excluded.ayushman_empaneled, "
            "  ayushman_verification_date = excluded.ayushman_verification_date, "
            "  scheme_supported_specialties = excluded.scheme_supported_specialties, "
            "  scheme_supported_packages = excluded.scheme_supported_packages",
            payload,
        )
    return get_hospital_by_id(hospital.hospital_id, settings)  # type: ignore[return-value]


def get_hospital_by_id(
    hospital_id: str, settings: Settings | None = None
) -> dict[str, Any] | None:
    with db_session(settings) as connection:
        row = connection.execute(
            f"SELECT id, {_HOSPITAL_COLUMNS} FROM hospitals WHERE hospital_id = ?",
            (hospital_id,),
        ).fetchone()
    return _row_to_hospital(row) if row else None


def list_hospitals(settings: Settings | None = None) -> list[dict[str, Any]]:
    with db_session(settings) as connection:
        rows = connection.execute(
            f"SELECT id, {_HOSPITAL_COLUMNS} FROM hospitals ORDER BY hospital_id"
        ).fetchall()
    return [_row_to_hospital(row) for row in rows]


def count_hospitals(settings: Settings | None = None) -> int:
    with db_session(settings) as connection:
        row = connection.execute("SELECT COUNT(*) AS n FROM hospitals").fetchone()
    return int(row["n"]) if row else 0


def seed_synthetic_hospitals(settings: Settings | None = None) -> int:
    """Load the built-in SYNTHETIC catalogue when the table is empty.

    Returns the number of rows seeded (0 when hospitals already exist).
    """
    if count_hospitals(settings) > 0:
        return 0
    seeded = 0
    for hospital in synthetic_hospitals():
        upsert_hospital(hospital, settings)
        seeded += 1
    return seeded


# --------------------------------------------------------------------------- #
# Referrals (structured summary snapshot + explicit status audit trail)
# --------------------------------------------------------------------------- #
REFERRAL_STATUSES = ("pending", "referred", "accepted", "transferred", "completed")

# Explicit, auditable state machine. Anything else is rejected.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"referred"},
    "referred": {"accepted", "transferred"},
    "accepted": {"transferred", "completed"},
    "transferred": {"completed"},
    "completed": set(),
}


class InvalidTransitionError(ValueError):
    """Raised when a requested status change is not allowed."""


def _referral_record(row: dict[str, Any]) -> dict[str, Any]:
    record = dict(row)
    record["summary"] = json.loads(record.pop("summary_json"))
    return record


def create_referral(
    *,
    referral_id: str,
    assessment_id: int,
    patient_id: str,
    urgency: str,
    recommendation: str,
    summary: dict[str, Any],
    explanation: str,
    recommended_hospital_id: str | None = None,
    recommended_hospital_name: str | None = None,
    alternative_hospital_id: str | None = None,
    alternative_hospital_name: str | None = None,
    status: str = "pending",
    settings: Settings | None = None,
) -> dict[str, Any]:
    if status not in REFERRAL_STATUSES:
        raise InvalidTransitionError(f"Unknown status {status!r}")
    with db_session(settings) as connection:
        row = connection.execute(
            "INSERT INTO referrals "
            "(referral_id, assessment_id, patient_id, urgency, recommendation, "
            " recommended_hospital_id, recommended_hospital_name, "
            " alternative_hospital_id, alternative_hospital_name, "
            " status, summary_json, explanation) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                referral_id,
                assessment_id,
                patient_id,
                urgency,
                recommendation,
                recommended_hospital_id,
                recommended_hospital_name,
                alternative_hospital_id,
                alternative_hospital_name,
                status,
                json.dumps(summary),
                explanation,
            ),
        ).fetchone()
        new_id = row["id"]
        connection.execute(
            "INSERT INTO referral_status_events "
            "(referral_ref, from_status, to_status, note) VALUES (?, ?, ?, ?)",
            (referral_id, None, status, "Referral record created"),
        )
    return get_referral(new_id, settings)  # type: ignore[return-value]


def get_referral(ref: str | int, settings: Settings | None = None) -> dict | None:
    """Look up by numeric id or by referral_id (REF-...)."""
    column = "id" if isinstance(ref, int) or str(ref).isdigit() else "referral_id"
    with db_session(settings) as connection:
        row = connection.execute(
            f"SELECT * FROM referrals WHERE {column} = ?", (ref,)
        ).fetchone()
    return _referral_record(row) if row else None


def list_referrals(
    *,
    urgency: str | None = None,
    status: str | None = None,
    recommendation: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 200,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """List referrals newest-first with optional dashboard filters."""
    clauses: list[str] = []
    params: list[Any] = []
    if urgency:
        clauses.append("urgency = ?")
        params.append(urgency)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if recommendation:
        clauses.append("recommendation = ?")
        params.append(recommendation)
    if date_from:
        clauses.append("date(created_at) >= date(?)")
        params.append(date_from)
    if date_to:
        clauses.append("date(created_at) <= date(?)")
        params.append(date_to)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    with db_session(settings) as connection:
        rows = connection.execute(
            "SELECT id, referral_id, assessment_id, patient_id, urgency, recommendation, "
            " recommended_hospital_id, recommended_hospital_name, "
            " alternative_hospital_id, alternative_hospital_name, status, explanation, "
            " created_at, updated_at "
            f"FROM referrals {where} ORDER BY id DESC LIMIT ?",
            tuple(params),
        ).fetchall()
    return rows


def referral_counts(settings: Settings | None = None) -> dict[str, Any]:
    """Status/urgency tallies for the dashboard filter chips."""
    with db_session(settings) as connection:
        by_status = connection.execute(
            "SELECT status, COUNT(*) AS n FROM referrals GROUP BY status"
        ).fetchall()
        by_urgency = connection.execute(
            "SELECT urgency, COUNT(*) AS n FROM referrals GROUP BY urgency"
        ).fetchall()
        by_recommendation = connection.execute(
            "SELECT recommendation, COUNT(*) AS n FROM referrals GROUP BY recommendation"
        ).fetchall()
    return {
        "by_status": {row["status"]: row["n"] for row in by_status},
        "by_urgency": {row["urgency"]: row["n"] for row in by_urgency},
        "by_recommendation": {
            row["recommendation"]: row["n"] for row in by_recommendation
        },
    }


def update_referral_status(
    *,
    ref: str | int,
    new_status: str,
    note: str = "",
    changed_by: str = "clinic_staff",
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Apply an explicit status transition and record it in the audit log."""
    if new_status not in REFERRAL_STATUSES:
        raise InvalidTransitionError(f"Unknown status {new_status!r}")
    current = get_referral(ref, settings)
    if current is None:
        raise LookupError(f"Referral {ref!r} not found")
    old_status = current["status"]
    if new_status == old_status:
        raise InvalidTransitionError(
            f"Referral is already {old_status!r}; choose a different status"
        )
    if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
        allowed = ", ".join(sorted(ALLOWED_TRANSITIONS.get(old_status, set()))) or "none"
        raise InvalidTransitionError(
            f"Cannot move from {old_status!r} to {new_status!r} (allowed: {allowed})"
        )
    with db_session(settings) as connection:
        connection.execute(
            "UPDATE referrals SET status = ?, updated_at = datetime('now') "
            "WHERE referral_id = ?",
            (new_status, current["referral_id"]),
        )
        connection.execute(
            "INSERT INTO referral_status_events "
            "(referral_ref, from_status, to_status, note, changed_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (current["referral_id"], old_status, new_status, note, changed_by),
        )
    return get_referral(current["id"], settings)  # type: ignore[return-value]


def list_referral_events(
    ref: str | int, settings: Settings | None = None
) -> list[dict[str, Any]]:
    record = get_referral(ref, settings)
    if record is None:
        return []
    with db_session(settings) as connection:
        rows = connection.execute(
            "SELECT id, from_status, to_status, note, changed_by, created_at "
            "FROM referral_status_events WHERE referral_ref = ? ORDER BY id",
            (record["referral_id"],),
        ).fetchall()
    return rows


# --------------------------------------------------------------------------- #
# Government Healthcare Schemes & Benefits (Prompt 6)
# --------------------------------------------------------------------------- #
_SCHEME_COLUMNS = (
    "scheme_id, name, short_name, government_level, state, department, description, "
    "target_beneficiary_category, age_min, age_max, clinical_categories, coverage_type, "
    "benefit_type, situations, eligibility_rules, documents, "
    "application_verification_method, official_url, source_name, source_url, "
    "verified_at, last_checked, active, is_prototype, version, effective_from, "
    "effective_until, benefit_notes, exclusions_notice"
)

_SCHEME_JSON_COLUMNS = (
    "clinical_categories",
    "situations",
    "eligibility_rules",
    "documents",
    "benefit_notes",
)


def _row_to_scheme(row: dict[str, Any]) -> dict[str, Any]:
    record = dict(row)
    for column in _SCHEME_JSON_COLUMNS:
        value = record.get(column)
        if isinstance(value, str):
            try:
                record[column] = json.loads(value)
            except json.JSONDecodeError:
                record[column] = [] if "rules" not in column else []
    record["active"] = bool(record.get("active"))
    record["is_prototype"] = bool(record.get("is_prototype"))
    return record


def seed_scheme_catalog(settings: Settings | None = None) -> int:
    """Upsert the curated prototype scheme catalogue + sources + documents.

    Returns the number of scheme rows upserted (0 when already present).
    """
    from ..schemes.catalog import DOCUMENT_CATALOG, SCHEMES, SOURCES

    count = 0
    with db_session(settings) as connection:
        for source in SOURCES:
            connection.execute(
                "INSERT INTO scheme_sources "
                "(source_id, source_name, source_url, source_type, region, last_checked, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (source_id) DO UPDATE SET "
                "source_name = excluded.source_name, source_url = excluded.source_url, "
                "source_type = excluded.source_type, region = excluded.region, "
                "last_checked = excluded.last_checked, notes = excluded.notes",
                (
                    source["source_id"],
                    source["source_name"],
                    source.get("source_url"),
                    source.get("source_type", "official"),
                    source.get("region"),
                    source.get("last_checked"),
                    source.get("notes", ""),
                ),
            )
        for code, doc in DOCUMENT_CATALOG.items():
            connection.execute(
                "INSERT INTO scheme_documents (code, label, notes, applicable_scheme_ids) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT (code) DO UPDATE SET "
                "label = excluded.label, notes = excluded.notes, "
                "applicable_scheme_ids = excluded.applicable_scheme_ids",
                (code, doc["label"], doc.get("notes", ""), "[]"),
            )
        for scheme in SCHEMES:
            connection.execute(
                "INSERT INTO government_schemes "
                f"({_SCHEME_COLUMNS}) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (scheme_id) DO UPDATE SET "
                "name = excluded.name, short_name = excluded.short_name, "
                "government_level = excluded.government_level, state = excluded.state, "
                "department = excluded.department, description = excluded.description, "
                "target_beneficiary_category = excluded.target_beneficiary_category, "
                "age_min = excluded.age_min, age_max = excluded.age_max, "
                "clinical_categories = excluded.clinical_categories, "
                "coverage_type = excluded.coverage_type, benefit_type = excluded.benefit_type, "
                "situations = excluded.situations, eligibility_rules = excluded.eligibility_rules, "
                "documents = excluded.documents, "
                "application_verification_method = excluded.application_verification_method, "
                "official_url = excluded.official_url, "
                "source_name = excluded.source_name, source_url = excluded.source_url, "
                "verified_at = excluded.verified_at, last_checked = excluded.last_checked, "
                "active = excluded.active, is_prototype = excluded.is_prototype, "
                "version = excluded.version, effective_from = excluded.effective_from, "
                "effective_until = excluded.effective_until, "
                "benefit_notes = excluded.benefit_notes, "
                "exclusions_notice = excluded.exclusions_notice",
                (
                    scheme["scheme_id"],
                    scheme["name"],
                    scheme.get("short_name"),
                    scheme.get("government_level", "central"),
                    scheme.get("state"),
                    scheme.get("department"),
                    scheme.get("description", ""),
                    scheme.get("target_beneficiary_category"),
                    scheme.get("age_min"),
                    scheme.get("age_max"),
                    json.dumps(scheme.get("clinical_categories", [])),
                    scheme.get("coverage_type"),
                    scheme.get("benefit_type"),
                    json.dumps(scheme.get("situations", [])),
                    json.dumps(scheme.get("eligibility_rules", [])),
                    json.dumps(scheme.get("documents", [])),
                    scheme.get("application_verification_method"),
                    scheme.get("official_url"),
                    scheme.get("source_name"),
                    scheme.get("source_url"),
                    scheme.get("verified_at"),
                    scheme.get("last_checked"),
                    1 if scheme.get("active", True) else 0,
                    1 if scheme.get("is_prototype", True) else 0,
                    scheme.get("version"),
                    scheme.get("effective_from"),
                    scheme.get("effective_until"),
                    json.dumps(scheme.get("benefit_notes", [])),
                    scheme.get("exclusions_notice", ""),
                ),
            )
            count += 1
    return count


def list_schemes(
    *,
    state: str | None = None,
    government_level: str | None = None,
    situation: str | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if state:
        clauses.append("(state = ? OR state IS NULL)")
        params.append(state)
    if government_level:
        clauses.append("government_level = ?")
        params.append(government_level)
    if situation:
        clauses.append("situations LIKE ?")
        params.append(f'%"{situation}"%')
    suffix = " AND active = 1" if clauses else " WHERE active = 1"
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with db_session(settings) as connection:
        rows = connection.execute(
            f"SELECT {_SCHEME_COLUMNS} FROM government_schemes "
            f"{where}{suffix} ORDER BY scheme_id",
            tuple(params),
        ).fetchall()
    return [_row_to_scheme(row) for row in rows]


def get_scheme(scheme_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with db_session(settings) as connection:
        row = connection.execute(
            f"SELECT {_SCHEME_COLUMNS} FROM government_schemes WHERE scheme_id = ?",
            (scheme_id,),
        ).fetchone()
    return _row_to_scheme(row) if row else None


def list_scheme_documents(
    scheme_id: str | None = None, settings: Settings | None = None
) -> list[dict[str, Any]]:
    with db_session(settings) as connection:
        rows = connection.execute(
            "SELECT code, label, notes FROM scheme_documents ORDER BY code"
        ).fetchall()
    docs = rows
    if scheme_id:
        scheme = get_scheme(scheme_id, settings)
        codes = set((scheme or {}).get("documents") or [])
        docs = [doc for doc in docs if doc["code"] in codes]
    return docs


def list_scheme_sources(settings: Settings | None = None) -> list[dict[str, Any]]:
    with db_session(settings) as connection:
        rows = connection.execute(
            "SELECT source_id, source_name, source_url, source_type, region, "
            "last_checked, notes FROM scheme_sources ORDER BY source_id"
        ).fetchall()
    return rows


# --- patient benefit profiles -------------------------------------------------
_PROFILE_JSON_COLUMNS = ("existing_health_schemes",)


def _row_to_profile(row: dict[str, Any]) -> dict[str, Any]:
    record = dict(row)
    for column in _PROFILE_JSON_COLUMNS:
        value = record.get(column)
        if isinstance(value, str):
            try:
                record[column] = json.loads(value)
            except json.JSONDecodeError:
                record[column] = []
    for column in ("pregnant", "disability", "has_bpl_ration_card"):
        if record.get(column) is not None:
            record[column] = bool(record[column])
    return record


def get_benefit_profile(
    patient_id: str, settings: Settings | None = None
) -> dict[str, Any] | None:
    with db_session(settings) as connection:
        row = connection.execute(
            "SELECT * FROM patient_benefit_profiles WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()
    return _row_to_profile(row) if row else None


def upsert_benefit_profile(
    patient_id: str,
    profile: dict[str, Any],
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Store the whitelisted, privacy-checked profile for a patient."""
    payload = (
        patient_id,
        profile.get("state"),
        profile.get("district"),
        profile.get("locality_type"),
        profile.get("socioeconomic_category"),
        profile.get("ayushman_card_status"),
        profile.get("ayushman_status"),
        _bool_or_none(profile.get("pregnant")),
        _bool_or_none(profile.get("disability")),
        profile.get("worker_category"),
        _bool_or_none(profile.get("has_bpl_ration_card")),
        json.dumps(profile.get("existing_health_schemes") or []),
    )
    with db_session(settings) as connection:
        connection.execute(
            "INSERT INTO patient_benefit_profiles "
            "(patient_id, state, district, locality_type, socioeconomic_category, "
            " ayushman_card_status, ayushman_status, pregnant, disability, "
            " worker_category, has_bpl_ration_card, existing_health_schemes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (patient_id) DO UPDATE SET "
            "state = excluded.state, district = excluded.district, "
            "locality_type = excluded.locality_type, "
            "socioeconomic_category = excluded.socioeconomic_category, "
            "ayushman_card_status = excluded.ayushman_card_status, "
            "ayushman_status = excluded.ayushman_status, "
            "pregnant = excluded.pregnant, disability = excluded.disability, "
            "worker_category = excluded.worker_category, "
            "has_bpl_ration_card = excluded.has_bpl_ration_card, "
            "existing_health_schemes = excluded.existing_health_schemes, "
            "updated_at = datetime('now')",
            payload,
        )
    return get_benefit_profile(patient_id, settings)  # type: ignore[return-value]


def _bool_or_none(value: Any) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


# --- patient scheme status ----------------------------------------------------
SCHEME_STATUS_VALUES = (
    "verified",
    "not_verified",
    "not_available",
    "unknown",
    "applied",
    "active",
    "denied",
    "expired",
    "not_relevant",
)


def list_patient_scheme_statuses(
    patient_id: str, settings: Settings | None = None
) -> list[dict[str, Any]]:
    with db_session(settings) as connection:
        rows = connection.execute(
            "SELECT scheme_id, status, note, updated_by, updated_at "
            "FROM patient_scheme_status WHERE patient_id = ? ORDER BY scheme_id",
            (patient_id,),
        ).fetchall()
    return rows


def upsert_patient_scheme_status(
    patient_id: str,
    scheme_id: str,
    status: str,
    note: str = "",
    settings: Settings | None = None,
) -> dict[str, Any]:
    if status not in SCHEME_STATUS_VALUES:
        raise ValueError(
            f"status must be one of {sorted(SCHEME_STATUS_VALUES)}"
        )
    if get_scheme(scheme_id, settings) is None:
        raise LookupError(f"Unknown scheme {scheme_id!r}")
    with db_session(settings) as connection:
        connection.execute(
            "INSERT INTO patient_scheme_status "
            "(patient_id, scheme_id, status, note) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (patient_id, scheme_id) DO UPDATE SET "
            "status = excluded.status, note = excluded.note, "
            "updated_at = datetime('now')",
            (patient_id, scheme_id, status, note),
        )
    return {
        "patient_id": patient_id,
        "scheme_id": scheme_id,
        "status": status,
        "note": note,
    }


# --- hospital scheme eligibility (informational) ------------------------------
def seed_hospital_scheme_eligibility(settings: Settings | None = None) -> int:
    """Seed the informational hospital<->scheme compatibility rows.

    NEVER consulted by the matching/ranking logic (clinical safety first).
    """
    from ..schemes.catalog import HOSPITAL_SCHEME_COMPAT

    count = 0
    with db_session(settings) as connection:
        for hospital_id, entry in HOSPITAL_SCHEME_COMPAT.items():
            connection.execute(
                "INSERT INTO hospital_scheme_eligibility "
                "(hospital_id, scheme_id, empaneled, specialty_codes, packages, "
                " verification_date, source, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (hospital_id, scheme_id) DO UPDATE SET "
                "empaneled = excluded.empaneled, "
                "specialty_codes = excluded.specialty_codes, "
                "packages = excluded.packages, "
                "verification_date = excluded.verification_date, "
                "source = excluded.source, notes = excluded.notes",
                (
                    hospital_id,
                    entry["scheme_id"],
                    1 if entry["empaneled"] else 0,
                    json.dumps(entry.get("specialty_codes") or []),
                    json.dumps(entry.get("packages") or []),
                    entry.get("verification_date"),
                    entry.get("source", "prototype-configuration"),
                    entry.get("notes", ""),
                ),
            )
            count += 1
    return count


def list_hospital_scheme_eligibility(
    hospital_id: str, settings: Settings | None = None
) -> list[dict[str, Any]]:
    with db_session(settings) as connection:
        rows = connection.execute(
            "SELECT hospital_id, scheme_id, empaneled, specialty_codes, packages, "
            "verification_date, source, notes "
            "FROM hospital_scheme_eligibility WHERE hospital_id = ? ORDER BY scheme_id",
            (hospital_id,),
        ).fetchall()
    result = []
    for row in rows:
        record = dict(row)
        record["empaneled"] = bool(record.get("empaneled"))
        record["specialty_codes"] = json.loads(record.get("specialty_codes") or "[]")
        record["packages"] = json.loads(record.get("packages") or "[]")
        result.append(record)
    return result
