"""Rural Diagnostic Risk & Context knowledge inspection API (Prompt 8 §16, §22).

Inspection/developer endpoints that expose the curated knowledge dataset:
conditions (with diagnostic-confusion/mimic relationships and provenance),
systemic driver constraints, injury diagnostic risks, the evidence review
queue, dataset statistics, and NEUTRAL decision-support context for a case.

This layer is ADVISORY ONLY. It never alters hospital matching/ranking, never
produces a diagnosis, and never automates treatment.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..db import repository
from ..knowledge.builder import KNOWLEDGE_DATA_DIR
from ..knowledge.loader import (
    get_all_conditions,
    get_condition_by_id,
    get_injury_risks,
    get_referral_context_notices,
    get_systemic_drivers,
    load_knowledge_dataset,
)
from ..matching import derive_requirements
from ..rules import RuleError, classify_urgency
from .schemas import AssessmentIn

router = APIRouter()

KNOWLEDGE_DISCLAIMER = (
    "Curated rural diagnostic risk & context dataset for demonstration. "
    "All relationships carry explicit evidence status; unresolved or "
    "unverified claims are listed in the review queue and must NOT be "
    "presented as established facts."
)


def _read_json_file(path: Path) -> dict[str, Any] | list[Any]:
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact not generated yet.")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/knowledge", summary="Knowledge layer overview + dataset statistics")
def knowledge_overview() -> dict[str, Any]:
    meta = _read_json_file(KNOWLEDGE_DATA_DIR / "dataset_metadata.json")
    return {
        "title": "Rural Diagnostic Risk & Systemic Constraints knowledge layer",
        "metadata": meta,
        "endpoints": [
            "/api/knowledge/conditions",
            "/api/knowledge/conditions/{condition_id}",
            "/api/knowledge/systemic-drivers",
            "/api/knowledge/injury-risks",
            "/api/knowledge/review-queue",
            "/api/knowledge/metadata",
            "/api/knowledge/context (POST)",
        ],
        "disclaimer": KNOWLEDGE_DISCLAIMER,
    }


@router.get("/knowledge/metadata", summary="Dataset statistics (real computed counts)")
def knowledge_metadata() -> dict[str, Any]:
    meta = _read_json_file(KNOWLEDGE_DATA_DIR / "dataset_metadata.json")
    return {"metadata": meta, "disclaimer": KNOWLEDGE_DISCLAIMER}


@router.get("/knowledge/conditions", summary="List curated condition records")
def list_conditions(
    rural_only: bool = Query(default=False),
    resource_dependency: str | None = Query(default=None),
) -> dict[str, Any]:
    conditions = get_all_conditions()
    if rural_only:
        conditions = [
            c for c in conditions
            if (c.get("rural_context") or {}).get("context_relevance", {}).get("rural_relevance")
        ]
    if resource_dependency:
        conditions = [
            c for c in conditions
            if resource_dependency
            in ((c.get("rural_context") or {}).get("resource_dependencies") or [])
        ]
    return {
        "conditions": conditions,
        "count": len(conditions),
        "documented_relationships_hint": (
            "Each condition lists diagnostic-confusion relationships with an "
            "evidence status. Unresolved or low-confidence ones appear in the review queue."
        ),
        "disclaimer": KNOWLEDGE_DISCLAIMER,
    }


@router.get("/knowledge/conditions/{condition_id}", summary="Condition detail with mimics & sources")
def condition_detail(condition_id: str) -> dict[str, Any]:
    condition = get_condition_by_id(condition_id)
    if condition is None:
        raise HTTPException(status_code=404, detail="Condition not found")
    return {
        "condition": condition,
        "disclaimer": KNOWLEDGE_DISCLAIMER,
    }


@router.get("/knowledge/systemic-drivers", summary="Systemic healthcare constraint drivers")
def systemic_drivers() -> dict[str, Any]:
    drivers = get_systemic_drivers()
    return {
        "systemic_drivers": drivers,
        "count": len(drivers),
        "disclaimer": KNOWLEDGE_DISCLAIMER,
    }


@router.get("/knowledge/injury-risks", summary="Injury diagnostic risk records")
def injury_risks() -> dict[str, Any]:
    risks = get_injury_risks()
    return {
        "injury_risks": risks,
        "count": len(risks),
        "disclaimer": KNOWLEDGE_DISCLAIMER,
    }


@router.get("/knowledge/review-queue", summary="Evidence review queue (unverified/unresolved claims)")
def review_queue() -> dict[str, Any]:
    items = _read_json_file(KNOWLEDGE_DATA_DIR / "review_queue.json")
    items = items if isinstance(items, list) else []
    return {
        "review_queue": items,
        "count": len(items),
        "note": (
            "These items require clinical or literature review. They are NOT "
            "established facts and must not be shown to end users as such."
        ),
    }


class KnowledgeContextRequest(BaseModel):
    assessment_id: int | None = None
    assessment: AssessmentIn | None = None


@router.post(
    "/knowledge/context",
    summary="NEUTRAL decision-support context for a case (never a diagnosis)",
)
def knowledge_context_for_case(request: KnowledgeContextRequest) -> dict[str, Any]:
    if request.assessment_id is not None:
        record = repository.get_assessment(request.assessment_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Assessment not found")
        assessment = record["input"]
        urgency = record["result"]["urgency"]
        requirements = derive_requirements(
            assessment, urgency["level"], urgency.get("score", 0.0)
        ).to_dict()
    elif request.assessment is not None:
        assessment = request.assessment.model_dump()
        try:
            urgency = classify_urgency(assessment).to_dict()
            requirements = derive_requirements(
                assessment, urgency["level"], urgency.get("score", 0.0)
            ).to_dict()
        except (RuleError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        raise HTTPException(
            status_code=422,
            detail="Provide either assessment_id or an inline assessment.",
        )

    return get_referral_context_notices(assessment, requirements)