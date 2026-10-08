"""Government Healthcare Schemes & Benefits API (Prompt 6).

The scheme layer is deliberately separate from the clinical matching API and
NEVER alters hospital ranking. Endpoints here return prototype scheme data,
store the minimum patient benefit-matching profile (no PII/Aadhaar), record
patient-vs-scheme statuses (never fabricated by the system), and expose
hospital scheme-compatibility as informational data.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import repository
from ..matching import derive_requirements
from ..rules import RuleError, classify_urgency
from ..schemes import (
    BENEFITS_PROFILE_PRIVACY_NOTE,
    SCHEME_MATCH_DISCLAIMER,
    benefits_for_assessment,
    normalize_benefits_profile,
)
from .schemas import AssessmentIn

router = APIRouter()


# --------------------------------------------------------------------------- #
# Scheme catalogue (Parts 6 & 11)
# --------------------------------------------------------------------------- #
@router.get("/schemes", summary="List the prototype government-scheme catalogue")
def list_schemes(
    state: str | None = Query(default=None, description="Filter to state-specific schemes"),
    government_level: str | None = Query(
        default=None, pattern="^(central|state|central_state)$"
    ),
    situation: str | None = Query(default=None, description="Filter by situation tag"),
) -> dict[str, Any]:
    schemes = repository.list_schemes(
        state=state, government_level=government_level, situation=situation
    )
    return {
        "schemes": schemes,
        "count": len(schemes),
        "note": (
            "Prototype configuration based on official public sources. Not "
            "live government data - verify via the listed official sources."
        ),
        "privacy_note": BENEFITS_PROFILE_PRIVACY_NOTE,
        "disclaimer": SCHEME_MATCH_DISCLAIMER,
    }


@router.get("/schemes/documents", summary="Document checklist catalogue (Part 10)")
def list_documents(scheme_id: str | None = Query(default=None)) -> dict[str, Any]:
    return {
        "documents": repository.list_scheme_documents(scheme_id=scheme_id),
        "note": "Checklist guidance only; the operating scheme workflow remains the authority.",
    }


@router.get("/schemes/sources", summary="Official/public sources (Part 11)")
def list_sources() -> dict[str, Any]:
    return {
        "sources": repository.list_scheme_sources(),
        "note": "Official government domains only; no blogs or unofficial pages.",
    }


@router.get("/schemes/{scheme_id}", summary="Get one scheme from the catalogue")
def get_scheme(scheme_id: str) -> dict[str, Any]:
    scheme = repository.get_scheme(scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail="Scheme not found")
    return scheme


# --------------------------------------------------------------------------- #
# Scheme matching (Part 3). Result is "potentially relevant" only.
# --------------------------------------------------------------------------- #
class SchemeMatchRequest(BaseModel):
    assessment_id: int | None = Field(default=None)
    assessment: AssessmentIn | None = Field(default=None)
    benefits_profile: dict[str, Any] | None = Field(
        default=None,
        description="Minimum benefit-matching data. Sensitive personal data "
        "(Aadhaar, name, contact) is rejected with 422.",
    )


@router.post("/schemes/match", summary="Match potentially-relevant schemes to a case")
def match_schemes(request: SchemeMatchRequest) -> dict[str, Any]:
    if request.assessment_id is not None:
        record = repository.get_assessment(request.assessment_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Assessment not found")
        assessment = record["input"]
        urgency = record["result"]["urgency"]
        requirements = derive_requirements(
            assessment, urgency["level"], urgency.get("score", 0.0)
        ).to_dict()
        stored_profile = repository.get_benefit_profile(
            record["input"].get("patient_id", "")
        )
    elif request.assessment is not None:
        assessment = request.assessment.model_dump()
        try:
            urgency = classify_urgency(assessment).to_dict()
            requirements = derive_requirements(
                assessment, urgency["level"], urgency.get("score", 0.0)
            ).to_dict()
        except (RuleError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        stored_profile = None
    else:
        raise HTTPException(
            status_code=422,
            detail="Provide either assessment_id or an inline assessment.",
        )

    benefits_profile: dict[str, Any] = {}
    if request.benefits_profile:
        try:
            benefits_profile = normalize_benefits_profile(request.benefits_profile)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not benefits_profile and stored_profile:
        benefits_profile = stored_profile

    benefits = benefits_for_assessment(
        assessment=assessment,
        requirements=requirements,
        age_years=assessment.get("age_years"),
        benefits_profile=benefits_profile,
        urgency=urgency["level"],
    )
    return {
        "patient_id": assessment.get("patient_id"),
        **benefits,
        "benefits_profile": benefits_profile,
        "privacy_note": BENEFITS_PROFILE_PRIVACY_NOTE,
        "disclaimer": SCHEME_MATCH_DISCLAIMER,
    }


# --------------------------------------------------------------------------- #
# Patient benefit profile (Parts 1 & 2). Minimum data only; no PII/Aadhaar.
# --------------------------------------------------------------------------- #
@router.get(
    "/patients/{patient_id}/benefits",
    summary="Get a patient's stored benefit-matching profile",
)
def get_patient_benefits(patient_id: str) -> dict[str, Any]:
    profile = repository.get_benefit_profile(patient_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="No benefit profile stored for this patient")
    return {**profile, "privacy_note": BENEFITS_PROFILE_PRIVACY_NOTE}


class BenefitsProfileBody(BaseModel):
    benefits_profile: dict[str, Any]


@router.put(
    "/patients/{patient_id}/benefits",
    summary="Store the minimum benefit-matching profile (privacy-guarded)",
)
def put_patient_benefits(patient_id: str, body: BenefitsProfileBody) -> dict[str, Any]:
    try:
        profile = normalize_benefits_profile(body.benefits_profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    stored = repository.upsert_benefit_profile(patient_id, profile)
    return {**stored, "privacy_note": BENEFITS_PROFILE_PRIVACY_NOTE}


# --------------------------------------------------------------------------- #
# Patient scheme status (Part 3). Recorded statuses only - never invented.
# --------------------------------------------------------------------------- #
@router.get(
    "/patients/{patient_id}/schemes",
    summary="Potentially-relevant schemes + recorded statuses for a patient",
)
def get_patient_schemes(patient_id: str) -> dict[str, Any]:
    profile = repository.get_benefit_profile(patient_id)
    if profile is None:
        return {
            "patient_id": patient_id,
            "matched_schemes": [],
            "potentially_eligible_count": 0,
            "confirmed_count": 0,
            "message": "No benefit profile recorded for this patient yet.",
            "status": "prototype_display",
            "disclaimer": SCHEME_MATCH_DISCLAIMER,
        }

    recorded = {
        row["scheme_id"]: row for row in repository.list_patient_scheme_statuses(patient_id)
    }
    context_profile = {
        k: v for k, v in profile.items() if k != "patient_id"
    }
    # Derive situations from the profile alone (no assessment available here).
    benefits = benefits_for_assessment(
        assessment={},
        requirements={},
        age_years=None,
        benefits_profile=context_profile,
    )
    for match in benefits["matched_schemes"]:
        scheme_id = match["scheme"]["scheme_id"]
        if scheme_id in recorded:
            match["recorded_status"] = recorded[scheme_id]["status"]
            match["status_note"] = recorded[scheme_id]["note"]
            match["status_source"] = "recorded_by_clinic"
    return {
        "patient_id": patient_id,
        **benefits,
        "privacy_note": BENEFITS_PROFILE_PRIVACY_NOTE,
    }


class SchemeStatusBody(BaseModel):
    status: str
    note: str = Field(default="", max_length=500)


@router.put(
    "/patients/{patient_id}/schemes/{scheme_id}/status",
    summary="Record a patient-vs-scheme status (verified/not_verified/etc.)",
)
def put_patient_scheme_status(
    patient_id: str, scheme_id: str, body: SchemeStatusBody
) -> dict[str, Any]:
    if body.status not in repository.SCHEME_STATUS_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of {sorted(repository.SCHEME_STATUS_VALUES)}",
        )
    try:
        return repository.upsert_patient_scheme_status(
            patient_id, scheme_id, body.status, body.note
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# --------------------------------------------------------------------------- #
# Hospital scheme compatibility (Part 8). INFORMATIONAL ONLY.
# --------------------------------------------------------------------------- #
@router.get(
    "/hospitals/{hospital_id}/schemes",
    summary="Informational scheme compatibility for a hospital",
)
def get_hospital_schemes(hospital_id: str) -> dict[str, Any]:
    rows = repository.list_hospital_scheme_eligibility(hospital_id)
    hospital = repository.get_hospital_by_id(hospital_id)
    if hospital is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return {
        "hospital_id": hospital_id,
        "hospital_name": hospital["name"],
        "schemes": rows,
        "note": (
            "Empanelment/compatibility is PROTOTYPE configuration for "
            "demonstration. It is never used in matching/ranking and must be "
            "confirmed on the official PM-JAY hospital list before use."
        ),
    }