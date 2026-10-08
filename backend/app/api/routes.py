"""API routes. Everything the React frontend talks to lives under /api."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..config import get_settings, redact_database_url
from ..db import repository
from ..db.connection import ping as db_ping
from ..rules import DEFAULT_RULES, RuleEngine, RuleError, classify_urgency, decide
from .schemas import AssessmentIn, AssessmentOut, AssessmentSummary

router = APIRouter()

API_VERSION = "0.2.0"


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
# Patient assessments (Part 2-4: assess -> urgency -> initial clinic decision)
# --------------------------------------------------------------------------- #
@router.post(
    "/assessments",
    status_code=201,
    response_model=AssessmentOut,
    summary="Assess a patient and return urgency + initial decision",
)
def create_assessment(payload: AssessmentIn) -> dict[str, Any]:
    assessment = payload.model_dump()
    try:
        urgency = classify_urgency(assessment)
        decision = decide(urgency.level)
    except (RuleError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record = repository.create_assessment(
        patient_id=payload.patient_id,
        age_years=payload.age_years,
        sex=payload.sex,
        urgency=urgency.level,
        decision=decision["code"],
        score=urgency.score,
        input_data=assessment,
        result_data={"urgency": urgency.to_dict(), "decision": decision},
    )
    return {
        "id": record["id"],
        "created_at": record["created_at"],
        "urgency": urgency.to_dict(),
        "decision": decision,
        "assessment": assessment,
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
    return {
        "id": record["id"],
        "created_at": record["created_at"],
        "urgency": record["result"]["urgency"],
        "decision": record["result"]["decision"],
        "assessment": record["input"],
    }


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
        # Note: routing_api_key is deliberately never exposed.
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
