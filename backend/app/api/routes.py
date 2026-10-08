"""API routes. Everything the React frontend talks to lives under /api."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..config import get_settings, redact_database_url
from ..db import repository
from ..db.connection import ping as db_ping
from ..knowledge.loader import get_referral_context_notices
from ..maps import MapsServiceError, TravelEstimator, get_route
from ..maps.travel import OSRM_ROUTING_NOTE
from ..matching import (
    CAPABILITY_LABELS,
    WeightError,
    assess_clinic_capability,
    default_clinic,
    derive_requirements,
    match_hospitals,
)
from ..referrals import (
    REFERRAL_DECISIONS,
    NoSuitableHospitalError,
    ReferralError,
    build_referral_summary,
    build_summary_text,
    choose_recommendation,
    new_referral_id,
    priority_label,
)
from ..rules import (
    DEFAULT_RULES,
    RuleEngine,
    RuleError,
    calculate_referral_level,
    classify_urgency,
    decide,
)
from ..schemes import (
    benefits_for_assessment,
    hospital_scheme_compatibility,
    normalize_benefits_profile,
)
from .schemas import (
    AssessmentIn,
    AssessmentOut,
    AssessmentSummary,
    ClinicCapabilityOut,
    ClinicProfilePatch,
    MatchRequest,
    MatchResultOut,
    ReferralCreateIn,
    ReferralListOut,
    ReferralOut,
    ReferralStatusPatch,
    RouteRequest,
)

router = APIRouter()

API_VERSION = "0.7.0"


# --------------------------------------------------------------------------- #
# Active clinic profile (Part 1: configurable clinic resources + location).
# Process-local override; the demo default (env-configurable location) is the
# starting point.
# --------------------------------------------------------------------------- #
_clinic_override: dict[str, Any] | None = None


def current_clinic() -> dict[str, Any]:
    return _clinic_override or default_clinic()


def reset_clinic() -> None:
    global _clinic_override
    _clinic_override = None


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
@router.get("/health", summary="Health check for the frontend")
def health() -> dict[str, Any]:
    settings = get_settings()
    db_ok, db_error = db_ping(settings)
    return {
        "status": "ok" if db_ok else "degraded",
        "version": API_VERSION,
        "database": {
            "ok": db_ok,
            "url": redact_database_url(settings.database_url),
            "path": str(settings.database_path) if settings.database_path else None,
            "error": db_error,
        },
    }


# --------------------------------------------------------------------------- #
# Rule engine
# --------------------------------------------------------------------------- #
class ScoreRequest(BaseModel):
    input: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured input the rules are evaluated against.",
    )
    rules: list[dict[str, Any]] | None = Field(
        default=None,
        description="Rules for this call. Omit to use the server's default "
        "rule set (currently empty — the final rules are not defined yet).",
    )


@router.post("/rules/score", summary="Run the rule/scoring engine")
def score(request: ScoreRequest) -> dict[str, Any]:
    payloads = request.rules if request.rules is not None else DEFAULT_RULES
    try:
        engine = RuleEngine.from_dicts(payloads)
        result = engine.evaluate(request.input)
    except RuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.to_dict()


# --------------------------------------------------------------------------- #
# Patient assessments (assess -> urgency -> requirements -> clinic capability
# -> initial decision -> hospital matching when referral is implied)
# --------------------------------------------------------------------------- #
def _enrich_matches_with_scheme_compat(matches: dict[str, Any]) -> dict[str, Any]:
    """Attach INFORMATIONAL scheme compatibility to matched hospitals.

    Runs strictly AFTER ranking; never touches total_score/reasons/rank so the
    clinical safety hierarchy is preserved.
    """
    for key in ("best_match", "alternatives", "excluded"):
        entries = matches.get(key)
        if isinstance(entries, dict):
            entries = [entries]
        for entry in entries or []:
            hospital = entry.get("hospital") or {}
            entry["scheme_compatibility"] = hospital_scheme_compatibility(
                hospital.get("hospital_id", ""), hospital
            )
    return matches


def _run_matching(
    requirements_payload: dict[str, Any],
    unavailable_hospital_ids: list[str] | None = None,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Match hospitals from the DB against a requirements payload.

    Travel estimates come from the routing provider (OSRM) via TravelEstimator,
    which falls back to straight-line placeholders per hospital on failure.
    """
    clinic = current_clinic()
    clinic_location = None
    if clinic.get("latitude") is not None and clinic.get("longitude") is not None:
        clinic_location = (float(clinic["latitude"]), float(clinic["longitude"]))
    hospitals = repository.list_hospitals()

    travel_lookup: dict[str, dict] = {}
    if clinic_location is not None and hospitals:
        estimator = TravelEstimator(clinic_location)
        destinations: dict[str, tuple[float, float] | None] = {}
        for h in hospitals:
            if h.get("latitude") is not None and h.get("longitude") is not None:
                destinations[h["hospital_id"]] = (
                    float(h["latitude"]),
                    float(h["longitude"]),
                )
            else:
                destinations[h["hospital_id"]] = None
        travel_lookup = estimator.estimate_many(destinations)

    result = match_hospitals(
        requirements=requirements_payload,
        hospitals=hospitals,
        clinic_location=clinic_location,
        weights=weights,
        unavailable_ids=unavailable_hospital_ids,
        travel_lookup=travel_lookup,
    )
    return _enrich_matches_with_scheme_compat(result)


def _case_benefits(
    assessment: dict[str, Any],
    requirements_payload: dict[str, Any],
    profile: dict[str, Any] | None = None,
    urgency_level: str | None = None,
) -> dict[str, Any]:
    """Prototype government-scheme matches (never confirmed eligibility)."""
    return benefits_for_assessment(
        assessment=assessment,
        requirements=requirements_payload,
        age_years=assessment.get("age_years"),
        benefits_profile=profile or {},
        urgency=urgency_level,
    )


def _case_knowledge_context(
    assessment: dict[str, Any],
    requirements_payload: dict[str, Any],
) -> dict[str, Any]:
    """NEUTRAL diagnostic-risk context notices (Prompt 8).

    Runs strictly AFTER decision/urgency/requirements. It only adds advisory
    context (possible mimic wording, resource-sensitivity notes) and never
    changes the decision, the requirements, or the hospital ranking.
    """
    return get_referral_context_notices(assessment, requirements_payload)


@router.post(
    "/assessments",
    status_code=201,
    response_model=AssessmentOut,
    summary="Assess a patient: urgency + clinic capability + decision (+ matches)",
)
def create_assessment(payload: AssessmentIn) -> dict[str, Any]:
    assessment = payload.model_dump()
    try:
        urgency = classify_urgency(assessment)
        requirements = derive_requirements(
            assessment, urgency.level, urgency.score
        )
        clinic_capability = assess_clinic_capability(
            requirements.to_dict(), current_clinic()
        )
        decision = decide(
            urgency.level, context={"clinic_capability": clinic_capability}
        )
    except (RuleError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    hospital_matches = None
    if decision["code"] in {"referral_recommended", "immediate_referral"}:
        try:
            hospital_matches = _run_matching(requirements.to_dict())
        except WeightError as exc:  # pragma: no cover - no weights passed here
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Prompt 7: suggested rural referral level (1-4). Computed AFTER urgency /
    # requirements and floored by them, so it can never downgrade safety.
    referral_level = calculate_referral_level(
        assessment,
        urgency,
        requirements,
        clinic_capability,
    )

    # Prompt 8: neutral diagnostic-risk context notices (advisory only).
    knowledge_context = _case_knowledge_context(assessment, requirements.to_dict())

    stored_profile = repository.get_benefit_profile(payload.patient_id)
    benefits = _case_benefits(
        assessment,
        requirements.to_dict(),
        profile=stored_profile,
        urgency_level=urgency.level,
    )

    record = repository.create_assessment(
        patient_id=payload.patient_id,
        age_years=payload.age_years,
        sex=payload.sex,
        urgency=urgency.level,
        decision=decision["code"],
        score=urgency.score,
        input_data=assessment,
        result_data={
            "urgency": urgency.to_dict(),
            "decision": decision,
            "requirements": requirements.to_dict(),
            "clinic_capability": clinic_capability,
            "hospital_matches": hospital_matches,
            "government_benefits": benefits,
            "referral_level": dict(referral_level),
            "knowledge_context": knowledge_context,
        },
    )
    return {
        "id": record["id"],
        "created_at": record["created_at"],
        "urgency": urgency.to_dict(),
        "decision": decision,
        "assessment": assessment,
        "requirements": requirements.to_dict(),
        "clinic_capability": clinic_capability,
        "hospital_matches": hospital_matches,
        "government_benefits": benefits,
        "referral_level": dict(referral_level),
        "knowledge_context": knowledge_context,
    }


@router.get(
    "/assessments",
    response_model=list[AssessmentSummary],
    summary="List recent assessments",
)
def list_assessments(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    return repository.list_assessments(limit=limit)


@router.get(
    "/assessments/{assessment_id}",
    response_model=AssessmentOut,
    summary="Get a stored assessment with its result",
)
def get_assessment(assessment_id: int) -> dict[str, Any]:
    record = repository.get_assessment(assessment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    result = record["result"]
    return {
        "id": record["id"],
        "created_at": record["created_at"],
        "urgency": result["urgency"],
        "decision": result["decision"],
        "assessment": record["input"],
        "requirements": result.get("requirements"),
        "clinic_capability": result.get("clinic_capability"),
        "hospital_matches": result.get("hospital_matches"),
        "government_benefits": result.get("government_benefits"),
        "referral_level": result.get("referral_level"),
        "knowledge_context": result.get("knowledge_context"),
    }


# --------------------------------------------------------------------------- #
# Clinic resources (Part 1: configurable capabilities)
# --------------------------------------------------------------------------- #
# Empty GREEN assessment used only to preview a clinic's baseline coverage.
_EMPTY_ASSESSMENT: dict[str, Any] = {
    "patient_id": "SYN-CLINIC-PREVIEW",
    "age_years": 40,
    "sex": "unknown",
    "chief_complaint": "routine clinic preview case",
    "vitals": {
        "heart_rate": 75,
        "systolic_bp": 118,
        "diastolic_bp": 76,
        "respiratory_rate": 16,
        "oxygen_saturation": 98,
        "temperature_c": 36.8,
    },
    "known_specialty": None,
    "emergency_indicator": False,
}


@router.get(
    "/clinics/current",
    summary="Current clinic profile + configured capabilities",
)
def get_current_clinic() -> dict[str, Any]:
    profile = current_clinic()
    return {
        **profile,
        "source": "override" if _clinic_override else "default",
        "capability_labels": dict(sorted(CAPABILITY_LABELS.items())),
        "disclaimer": (
            "Clinic capabilities are configurable demonstration settings, "
            "not verified facility credentials."
        ),
    }


@router.patch(
    "/clinics/current",
    response_model=ClinicCapabilityOut,
    summary="Override the current clinic's capabilities (process-local)",
)
def patch_current_clinic(patch: ClinicProfilePatch) -> dict[str, Any]:
    global _clinic_override
    base = dict(current_clinic())
    if patch.capabilities is not None:
        base["capabilities"] = sorted(set(patch.capabilities))
    if patch.specialties is not None:
        base["specialties"] = sorted(set(patch.specialties))
    if patch.latitude is not None:
        base["latitude"] = patch.latitude
    if patch.longitude is not None:
        base["longitude"] = patch.longitude
    base["source"] = "override"
    _clinic_override = base
    # Preview: show coverage for the baseline routine preview case.
    preview = derive_requirements(_EMPTY_ASSESSMENT, "GREEN")
    return assess_clinic_capability(preview.to_dict(), base)


@router.delete(
    "/clinics/current",
    summary="Reset the clinic override back to the demo default",
)
def delete_clinic_override() -> dict[str, str]:
    reset_clinic()
    return {"status": "reset", "source": "default"}


# --------------------------------------------------------------------------- #
# Hospital matching (Parts 3-6)
# --------------------------------------------------------------------------- #
@router.get("/hospitals", summary="List hospitals (SYNTHETIC demonstration data)")
def list_hospitals() -> dict[str, Any]:
    hospitals = repository.list_hospitals()
    return {
        "hospitals": hospitals,
        "count": len(hospitals),
        "data_disclaimer": (
            "All hospitals listed here are SYNTHETIC demonstration records. "
            "They do not represent real facilities or real current availability."
        ),
    }


@router.post(
    "/referrals/match",
    response_model=MatchResultOut,
    summary="Match and rank hospitals for a case (hard constraints + scoring)",
)
def match_referral(request: MatchRequest) -> dict[str, Any]:
    if request.assessment_id is not None:
        record = repository.get_assessment(request.assessment_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Assessment not found")
        assessment = record["input"]
        urgency = record["result"]["urgency"]
        requirements = derive_requirements(
            assessment, urgency["level"], urgency.get("score", 0.0)
        )
        stored_profile = repository.get_benefit_profile(
            record["input"].get("patient_id", "")
        )
    elif request.assessment is not None:
        assessment = request.assessment.model_dump()
        try:
            urgency = classify_urgency(assessment).to_dict()
            requirements = derive_requirements(
                assessment, urgency["level"], urgency.get("score", 0.0)
            )
        except (RuleError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        stored_profile = None
    else:
        raise HTTPException(
            status_code=422,
            detail="Provide either assessment_id or an inline assessment.",
        )

    # Prompt 6: accept minimum benefit-matching data when supplied inline.
    benefits_profile: dict[str, Any] = {}
    if request.benefits_profile:
        try:
            benefits_profile = normalize_benefits_profile(request.benefits_profile)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if request.assessment is not None:
            repository.upsert_benefit_profile(
                assessment["patient_id"], benefits_profile
            )
    if not benefits_profile and stored_profile:
        benefits_profile = stored_profile

    try:
        result = _run_matching(
            requirements.to_dict(),
            unavailable_hospital_ids=request.unavailable_hospital_ids,
            weights=request.weights,
        )
    except WeightError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result["requirements"] = requirements.to_dict()
    result["benefits"] = _case_benefits(
        assessment,
        requirements.to_dict(),
        profile=benefits_profile,
        urgency_level=urgency["level"],
    )
    return result


# --------------------------------------------------------------------------- #
# Referrals (Parts 3-5: create record, dashboard list, detail, status audit)
# --------------------------------------------------------------------------- #
def _referral_out(
    record: dict[str, Any],
    *,
    include_summary: bool = True,
    include_history: bool = False,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": record["id"],
        "referral_id": record["referral_id"],
        "assessment_id": record["assessment_id"],
        "patient_id": record["patient_id"],
        "urgency": record["urgency"],
        "priority": priority_label(record["urgency"]),
        "recommendation": record["recommendation"],
        "recommended_hospital_id": record.get("recommended_hospital_id"),
        "recommended_hospital_name": record.get("recommended_hospital_name"),
        "alternative_hospital_id": record.get("alternative_hospital_id"),
        "alternative_hospital_name": record.get("alternative_hospital_name"),
        "status": record["status"],
        "explanation": record.get("explanation", ""),
        "created_at": record["created_at"],
        "updated_at": record.get("updated_at", record["created_at"]),
        "status_history": [],
    }
    if include_summary:
        out["summary"] = record.get("summary")
    if include_history:
        out["status_history"] = repository.list_referral_events(record["id"])
    return out


@router.post(
    "/referrals",
    status_code=201,
    response_model=ReferralOut,
    summary="Create a referral record with a structured summary",
)
def create_referral(payload: ReferralCreateIn) -> dict[str, Any]:
    record = repository.get_assessment(payload.assessment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Assessment not found")

    result = record["result"]
    decision = result["decision"]
    if decision["code"] not in REFERRAL_DECISIONS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Assessment decision '{decision['code']}' does not require a "
                "referral (patient can be managed locally)."
            ),
        )

    # Matching is always re-run server-side against current data; client-supplied
    # scores are never trusted.
    try:
        matches = _run_matching(
            result["requirements"],
            unavailable_hospital_ids=payload.unavailable_hospital_ids,
        )
    except WeightError as exc:  # pragma: no cover - no weights passed here
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    matches["requirements"] = result["requirements"]

    try:
        recommended, alternative = choose_recommendation(matches, payload.hospital_id)
        referral_id = new_referral_id()
        stored_profile = repository.get_benefit_profile(
            record["input"].get("patient_id", "")
        )
        benefits = _case_benefits(
            record["input"],
            result["requirements"],
            profile=stored_profile,
            urgency_level=result["urgency"]["level"],
        )
        # Prompt 7: suggested referral level persisted with the referral record
        # so the dashboard and summary can display it later.
        referral_level = calculate_referral_level(
            record["input"],
            result["urgency"],
            result["requirements"],
            result.get("clinic_capability"),
        )
        # Prompt 8: neutral diagnostic-risk context included in the summary.
        diagnostic_context = _case_knowledge_context(
            record["input"], result["requirements"]
        )
        summary = build_referral_summary(
            referral_id=referral_id,
            assessment_input=record["input"],
            urgency=result["urgency"],
            decision=decision,
            requirements=result["requirements"],
            matches=matches,
            recommended=recommended,
            alternative=alternative,
            government_benefits=benefits,
            referral_level=dict(referral_level),
            diagnostic_context=diagnostic_context,
        )
    except NoSuitableHospitalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ReferralError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    explanation = summary["recommendation_explanation"]
    if payload.note:
        explanation = f"{explanation} Staff note: {payload.note}".strip()

    created = repository.create_referral(
        referral_id=referral_id,
        assessment_id=record["id"],
        patient_id=record["input"].get("patient_id", ""),
        urgency=result["urgency"]["level"],
        recommendation=decision["code"],
        summary=summary,
        explanation=explanation,
        recommended_hospital_id=recommended["hospital"]["hospital_id"],
        recommended_hospital_name=recommended["hospital"]["name"],
        alternative_hospital_id=(
            alternative["hospital"]["hospital_id"] if alternative else None
        ),
        alternative_hospital_name=(
            alternative["hospital"]["name"] if alternative else None
        ),
    )
    return _referral_out(created, include_summary=True, include_history=True)


@router.get(
    "/referrals",
    response_model=ReferralListOut,
    summary="List referrals with dashboard filters (urgency/status/date/hospital)",
)
def list_referrals(
    urgency: str | None = Query(
        default=None, pattern="^(GREEN|ORANGE|RED)$", description="Urgency filter"
    ),
    status: str | None = Query(
        default=None,
        pattern="^(pending|referred|accepted|transferred|completed)$",
        description="Status filter",
    ),
    recommendation: str | None = Query(
        default=None,
        pattern="^(referral_recommended|immediate_referral|manage_locally)$",
        description="Recommendation/decision filter",
    ),
    date_from: str | None = Query(
        default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD"
    ),
    date_to: str | None = Query(
        default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD"
    ),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    rows = repository.list_referrals(
        urgency=urgency,
        status=status,
        recommendation=recommendation,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    referrals = [_referral_out(row) for row in rows]
    applied = {
        key: value
        for key, value in {
            "urgency": urgency,
            "status": status,
            "recommendation": recommendation,
            "date_from": date_from,
            "date_to": date_to,
        }.items()
        if value
    }
    empty_message = ""
    if not referrals:
        empty_message = (
            "No referrals match the current filters."
            if applied
            else "No referrals recorded yet. Complete an assessment that requires "
            "a referral to create the first record."
        )
    return {
        "referrals": referrals,
        "count": len(referrals),
        "counts": repository.referral_counts(),
        "options": {
            "urgency": ["RED", "ORANGE", "GREEN"],
            "status": list(repository.REFERRAL_STATUSES),
            "recommendation": ["immediate_referral", "referral_recommended"],
        },
        "applied_filters": applied,
        "empty_state_message": empty_message,
    }


@router.get(
    "/referrals/{referral_ref}",
    response_model=ReferralOut,
    summary="Get one referral with its full summary and status history",
)
def get_referral(referral_ref: str) -> dict[str, Any]:
    record = repository.get_referral(referral_ref)
    if record is None:
        raise HTTPException(status_code=404, detail="Referral not found")
    return _referral_out(record, include_summary=True, include_history=True)


@router.patch(
    "/referrals/{referral_ref}/status",
    response_model=ReferralOut,
    summary="Apply an explicit, audited referral status transition",
)
def update_referral_status(referral_ref: str, patch: ReferralStatusPatch) -> dict[str, Any]:
    try:
        record = repository.update_referral_status(
            ref=referral_ref, new_status=patch.status, note=patch.note
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except repository.InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _referral_out(record, include_summary=True, include_history=True)


@router.get(
    "/referrals/{referral_ref}/summary.txt",
    summary="Plain-text referral summary (print/export helper)",
)
def referral_summary_text(referral_ref: str) -> dict[str, Any]:
    record = repository.get_referral(referral_ref)
    if record is None:
        raise HTTPException(status_code=404, detail="Referral not found")
    return {
        "referral_id": record["referral_id"],
        "content_type": "text/plain; charset=utf-8",
        "text": build_summary_text(record["summary"]),
    }


# --------------------------------------------------------------------------- #
# Rule engine
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Maps configuration (public, non-secret values only)
# --------------------------------------------------------------------------- #
@router.get("/maps/config", summary="Map/tile/routing configuration for the frontend")
def maps_config() -> dict[str, Any]:
    settings = get_settings()
    return {
        "tile_url": settings.osm_tile_url,
        "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        "geocoder_url": settings.geocoder_base_url,
        "router_url": settings.router_base_url,
        "router_profile": settings.router_profile,
        "routing_enabled": settings.routing_enabled,
        # Note: routing_api_key is deliberately never exposed.
    }


# --------------------------------------------------------------------------- #
# Routing (Part 2: provider-agnostic single-route requests for the map UI)
# --------------------------------------------------------------------------- #
@router.post(
    "/route",
    summary="Route between two coordinates (distance, time, geometry)",
)
def route(request: RouteRequest) -> dict[str, Any]:
    try:
        result = get_route(
            (request.origin.latitude, request.origin.longitude),
            (request.destination.latitude, request.destination.longitude),
            profile=request.profile,
        )
    except MapsServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "distance_km": result["distance_km"],
        "duration_minutes": result["duration_minutes"],
        "source": "osrm",
        "coordinates": result.get("coordinates") or [],
        "geometry": result.get("geometry"),
        "note": OSRM_ROUTING_NOTE,
    }


# --------------------------------------------------------------------------- #
# Locations (minimal CRUD to verify the SQLite layer end-to-end)
# --------------------------------------------------------------------------- #
class LocationIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str | None = None


@router.get("/locations", summary="List stored locations")
def list_locations() -> list[dict[str, Any]]:
    return repository.list_locations()


@router.post("/locations", status_code=201, summary="Create a location")
def create_location(payload: LocationIn) -> dict[str, Any]:
    return repository.create_location(
        name=payload.name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        address=payload.address,
    )


@router.get("/locations/{location_id}", summary="Get one location")
def get_location(location_id: int) -> dict[str, Any]:
    location = repository.get_location(location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


@router.delete("/locations/{location_id}", status_code=204, summary="Delete a location")
def delete_location(location_id: int) -> None:
    if not repository.delete_location(location_id):
        raise HTTPException(status_code=404, detail="Location not found")
