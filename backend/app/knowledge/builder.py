"""Canonical dataset builder and metadata generator for Rural Diagnostic Risk & Context (Prompt 8).

Assembles seed data, runs validation, computes dataset statistics, generates
review queue entries, and writes canonical JSON artifacts to `backend/data/knowledge/`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .data import INJURY_DIAGNOSTIC_RISKS, SEED_CONDITIONS, SYSTEMIC_DRIVERS
from .validator import validate_dataset

KNOWLEDGE_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge"


def build_knowledge_dataset() -> dict[str, Any]:
    """Assemble the unified canonical dataset structure."""
    return {
        "systemic_drivers": SYSTEMIC_DRIVERS,
        "conditions": SEED_CONDITIONS,
        "injury_diagnostic_risks": INJURY_DIAGNOSTIC_RISKS,
    }


def compute_metadata(data: dict[str, Any], review_queue: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate real statistics without hardcoding or fabricating numbers."""
    drivers = data.get("systemic_drivers") or []
    conditions = data.get("conditions") or []
    injuries = data.get("injury_diagnostic_risks") or []

    confusion_count = sum(len(c.get("diagnostic_confusion") or []) for c in conditions)

    rural_count = sum(
        1 for c in conditions
        if (c.get("rural_context") or {}).get("context_relevance", {}).get("rural_relevance")
    )

    unresolved_count = sum(
        1 for c in conditions
        for conf in (c.get("diagnostic_confusion") or [])
        if conf.get("unresolved_condition_reference")
    )

    status_counts: dict[str, int] = {}
    for c in conditions:
        for conf in (c.get("diagnostic_confusion") or []):
            st = conf.get("evidence_status", "unknown")
            status_counts[st] = status_counts.get(st, 0) + 1
    for d in drivers:
        st = d.get("evidence_status", "unknown")
        status_counts[st] = status_counts.get(st, 0) + 1
    for i in injuries:
        st = i.get("evidence_status", "unknown")
        status_counts[st] = status_counts.get(st, 0) + 1

    return {
        "systemic_driver_count": len(drivers),
        "condition_count": len(conditions),
        "diagnostic_confusion_relationship_count": confusion_count,
        "injury_risk_relationship_count": len(injuries),
        "rural_relevant_condition_count": rural_count,
        "unresolved_condition_reference_count": unresolved_count,
        "claims_requiring_review": len(review_queue),
        "evidence_status_counts": status_counts,
        "version": "1.0.0-prototype",
    }


def write_artifacts(target_dir: Path | None = None) -> tuple[Path, Path, Path]:
    """Build, validate, and write diseases.json, review_queue.json, dataset_metadata.json."""
    out_dir = target_dir or KNOWLEDGE_DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    dataset = build_knowledge_dataset()
    is_valid, errors, review_queue = validate_dataset(dataset)

    if not is_valid:
        raise ValueError(f"Knowledge dataset validation failed with errors: {errors}")

    metadata = compute_metadata(dataset, review_queue)

    diseases_path = out_dir / "diseases.json"
    queue_path = out_dir / "review_queue.json"
    meta_path = out_dir / "dataset_metadata.json"

    diseases_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")
    queue_path.write_text(json.dumps(review_queue, indent=2, ensure_ascii=False), encoding="utf-8")
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    return diseases_path, queue_path, meta_path
