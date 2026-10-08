"""Runtime loader and query engine for Rural Diagnostic Risk & Context (Prompt 8 §18).

Provides in-memory caching of `diseases.json` and query functions for:
- Conditions, mimics, and diagnostic confusion relationships
- Systemic drivers and diagnostic impacts
- Injury diagnostic risks
- Resource dependency mapping
- Generating NEUTRAL decision-support notices for referral summaries (Sections 11 & 12)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .builder import KNOWLEDGE_DATA_DIR, build_knowledge_dataset, write_artifacts

_DATASET_CACHE: dict[str, Any] | None = None


def load_knowledge_dataset(data_dir: Path | None = None) -> dict[str, Any]:
    """Load canonical JSON dataset from file, building artifacts if missing."""
    global _DATASET_CACHE
    if _DATASET_CACHE is not None and data_dir is None:
        return _DATASET_CACHE

    target_dir = data_dir or KNOWLEDGE_DATA_DIR
    diseases_file = target_dir / "diseases.json"

    if not diseases_file.exists():
        write_artifacts(target_dir)

    try:
        content = diseases_file.read_text(encoding="utf-8")
        dataset = json.loads(content)
    except Exception:
        # Fallback to direct build if reading fails
        dataset = build_knowledge_dataset()

    if data_dir is None:
        _DATASET_CACHE = dataset
    return dataset


def reset_cache() -> None:
    global _DATASET_CACHE
    _DATASET_CACHE = None


def get_all_conditions(data_dir: Path | None = None) -> list[dict[str, Any]]:
    return load_knowledge_dataset(data_dir).get("conditions") or []


def get_condition_by_id(condition_id: str, data_dir: Path | None = None) -> dict[str, Any] | None:
    for cond in get_all_conditions(data_dir):
        if cond.get("condition_id") == condition_id:
            return cond
    return None


def get_systemic_drivers(data_dir: Path | None = None) -> list[dict[str, Any]]:
    return load_knowledge_dataset(data_dir).get("systemic_drivers") or []


def get_injury_risks(data_dir: Path | None = None) -> list[dict[str, Any]]:
    return load_knowledge_dataset(data_dir).get("injury_diagnostic_risks") or []


def query_mimics(condition_id_or_name: str, data_dir: Path | None = None) -> list[dict[str, Any]]:
    """Return documented confusion/mimic relationships for a given condition."""
    target = str(condition_id_or_name).lower().strip()
    cond = get_condition_by_id(condition_id_or_name, data_dir)
    if cond:
        return cond.get("diagnostic_confusion") or []

    for c in get_all_conditions(data_dir):
        if c.get("canonical_name", "").lower() == target:
            return c.get("diagnostic_confusion") or []

    return []


def query_conditions_by_resource(resource_code: str, data_dir: Path | None = None) -> list[dict[str, Any]]:
    """Find conditions that list a specific diagnostic/treatment resource dependency."""
    code = str(resource_code).strip().lower()
    matches: list[dict[str, Any]] = []
    for c in get_all_conditions(data_dir):
        deps = (c.get("rural_context") or {}).get("resource_dependencies") or []
        if code in [d.lower() for d in deps]:
            matches.append(c)
    return matches


def match_conditions_from_assessment(
    chief_complaint: str,
    findings: str = "",
    data_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Find conditions whose keywords overlap with the assessment presentation text."""
    text = f"{chief_complaint} {findings}".lower()
    matched: list[dict[str, Any]] = []

    for c in get_all_conditions(data_dir):
        symptoms = [s.lower() for s in c.get("symptoms") or []]
        name = c.get("canonical_name", "").lower()

        # Simple keyword overlap check
        if any(sym in text for sym in symptoms) or any(word in text for word in name.split()):
            matched.append(c)

    return matched


def match_injury_risks_from_assessment(
    chief_complaint: str,
    findings: str = "",
    data_dir: Path | None = None,
) -> list[dict[str, Any]]:
    text = f"{chief_complaint} {findings}".lower()
    matched: list[dict[str, Any]] = []

    for risk in get_injury_risks(data_dir):
        itype = risk.get("injury_type", "").lower()
        cname = risk.get("canonical_name", "").lower()
        targets = [t.lower() for t in risk.get("possible_confusion_targets") or []]

        if itype in text or any(word in text for word in cname.split() if len(word) > 3):
            matched.append(risk)

    return matched


def get_referral_context_notices(
    assessment: dict[str, Any],
    requirements: dict[str, Any] | None = None,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate NEUTRAL decision-support notices (Sections 11 & 12).

    Rules:
    - Never state a definitive diagnosis ("You have X").
    - Use neutral decision support phrasing ("Some conditions can present with similar symptoms...").
    - Highlight resource sensitivity when local clinic capabilities do not cover derived requirements.
    """
    chief_complaint = str(assessment.get("chief_complaint") or "")
    findings = str(assessment.get("clinical_findings") or "")
    reqs = requirements or {}

    matched_conds = match_conditions_from_assessment(chief_complaint, findings, data_dir)
    matched_injuries = match_injury_risks_from_assessment(chief_complaint, findings, data_dir)

    notices: list[str] = []
    relevant_mimics: list[dict[str, Any]] = []
    resource_risks: list[str] = []

    # 1. Mimic / confusion context
    for c in matched_conds:
        confusions = c.get("diagnostic_confusion") or []
        for conf in confusions:
            relevant_mimics.append({
                "condition_id": c.get("condition_id"),
                "canonical_name": c.get("canonical_name"),
                "confused_with": conf.get("confused_with_name"),
                "relationship_type": conf.get("relationship_type"),
                "why": conf.get("why_confusion_can_occur"),
                "distinguishing_info": conf.get("distinguishing_information"),
                "evidence_status": conf.get("evidence_status"),
            })

    if relevant_mimics:
        notices.append(
            "Some conditions can present with similar symptoms. Additional evaluation "
            "may be appropriate depending on clinical findings."
        )

    # 2. Resource-sensitive risks
    needed_diags = reqs.get("required_diagnostics") or []
    needed_treats = reqs.get("required_treatment") or []

    if needed_diags or needed_treats:
        resource_risks.append(
            "Diagnostic uncertainty may be increased when required testing or specialist "
            "evaluation is unavailable locally."
        )

    for inj in matched_injuries:
        resource_risks.append(
            f"Trauma context ({inj.get('injury_type')}): {inj.get('why_difficult_clinically')}"
        )

    # Combine into a clean structured payload
    return {
        "notices": list(dict.fromkeys(notices)),
        "relevant_mimics": relevant_mimics[:5],  # Cap for presentation
        "matched_injury_risks": matched_injuries[:3],
        "resource_sensitivity_notes": list(dict.fromkeys(resource_risks)),
        "disclaimer": (
            "Neutral decision-support context. Does not constitute a clinical diagnosis "
            "or replacement for professional clinical evaluation."
        ),
    }
