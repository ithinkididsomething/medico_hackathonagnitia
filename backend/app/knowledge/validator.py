"""Validation rules for the Rural Diagnostic Risk & Context dataset (Prompt 8 §20).

Validates schema consistency, cross-references, provenance requirements,
evidence status enums, and detects unsupported claims or duplicate entries.
"""
from __future__ import annotations

from typing import Any

from .schema import EVIDENCE_STATUSES, KNOWN_CAPABILITY_CODES, RURAL_RELEVANCE_LEVELS


class ValidationError(ValueError):
    """Raised when the dataset fails critical validation rules."""


def validate_dataset(data: dict[str, Any]) -> tuple[bool, list[str], list[dict[str, Any]]]:
    """Validate a complete knowledge dataset mapping.

    Returns:
        (is_valid, errors, review_queue_items)
    """
    errors: list[str] = []
    review_queue: list[dict[str, Any]] = []

    systemic_drivers = data.get("systemic_drivers") or []
    conditions = data.get("conditions") or []
    injury_risks = data.get("injury_diagnostic_risks") or []

    # Map of known condition IDs
    known_condition_ids = {c.get("condition_id") for c in conditions if c.get("condition_id")}

    # 1. Validate systemic drivers
    for idx, driver in enumerate(systemic_drivers):
        driver_id = driver.get("driver_id", f"SYS-{idx+1}")
        if not driver.get("name") or not driver.get("description"):
            errors.append(f"Systemic driver {driver_id} missing required name or description.")
        status = driver.get("evidence_status")
        if status and status not in EVIDENCE_STATUSES:
            errors.append(f"Systemic driver {driver_id} has invalid evidence_status {status!r}.")
        sources = driver.get("source_refs") or []
        if status in ("government_documented", "government_supported") and not sources:
            errors.append(f"Systemic driver {driver_id} marked {status} but has no source_refs.")

    # 2. Validate conditions & diagnostic confusion
    for cond in conditions:
        cid = cond.get("condition_id")
        cname = cond.get("canonical_name")
        if not cid or not cname:
            errors.append(f"Condition record missing condition_id or canonical_name: {cond}")
            continue

        confusions = cond.get("diagnostic_confusion") or []
        seen_targets: set[str] = set()

        for c_idx, confusion in enumerate(confusions):
            target_name = confusion.get("confused_with_name")
            target_id = confusion.get("confused_with_condition_id")
            rel_key = f"{target_id or target_name}"

            # Self-reference check
            if target_id == cid:
                errors.append(f"Condition {cid} ({cname}) self-references in diagnostic_confusion.")

            # Duplicate relationship check
            if rel_key in seen_targets:
                errors.append(f"Condition {cid} has duplicate confusion relationship with {rel_key}.")
            seen_targets.add(rel_key)

            # Sources check
            sources = confusion.get("source_refs") or []
            if not sources:
                errors.append(f"Condition {cid} confusion entry '{target_name}' has no source_refs.")

            # Evidence status check
            status = confusion.get("evidence_status", "manual_review_required")
            if status not in EVIDENCE_STATUSES:
                errors.append(f"Condition {cid} confusion entry '{target_name}' has invalid evidence_status {status!r}.")

            if status in ("government_documented", "government_supported") and not sources:
                errors.append(f"Condition {cid} confusion entry '{target_name}' marked {status} without sources.")

            # Unsupported rural claims
            if confusion.get("rural_specific_claim") and not confusion.get("rural_evidence_supported"):
                review_queue.append({
                    "review_id": f"REV-RURAL-{cid}-{c_idx+1}",
                    "type": "diagnostic_confusion_claim",
                    "condition_id": cid,
                    "claim": f"Rural-specific confusion claim for {target_name}",
                    "reason": "Marked rural_specific_claim but rural_evidence_supported is False.",
                    "sources_checked": [s.get("source_id") for s in sources],
                })

            # Check evidence status requiring review
            if status in ("plausible_but_unverified", "insufficient_evidence", "manual_review_required"):
                review_queue.append({
                    "review_id": f"REV-EVID-{cid}-{c_idx+1}",
                    "type": "unverified_evidence_claim",
                    "condition_id": cid,
                    "claim": f"Diagnostic confusion relationship: {cname} <-> {target_name}",
                    "reason": f"Evidence status is '{status}'. Requires clinical/literature review.",
                    "sources_checked": [s.get("source_id") for s in sources],
                })

            # Unresolved condition ID check
            if target_id and target_id not in known_condition_ids:
                confusion["unresolved_condition_reference"] = True
                review_queue.append({
                    "review_id": f"REV-UNRESOLVED-{cid}-{c_idx+1}",
                    "type": "unresolved_condition_id",
                    "condition_id": cid,
                    "target_id": target_id,
                    "target_name": target_name,
                    "reason": f"Referenced condition ID '{target_id}' not found in registered conditions.",
                    "sources_checked": [],
                })

        # Check resource dependencies validity
        rc = cond.get("rural_context") or {}
        deps = rc.get("resource_dependencies") or []
        for dep in deps:
            if dep not in KNOWN_CAPABILITY_CODES:
                review_queue.append({
                    "review_id": f"REV-CAPABILITY-{cid}-{dep}",
                    "type": "unknown_resource_dependency",
                    "condition_id": cid,
                    "capability_code": dep,
                    "reason": f"Resource dependency '{dep}' is not in standard hospital capability vocabulary.",
                    "sources_checked": [],
                })

    # 3. Validate injury diagnostic risks
    for risk in injury_risks:
        rid = risk.get("risk_id")
        rname = risk.get("canonical_name")
        if not rid or not rname:
            errors.append(f"Injury diagnostic risk record missing risk_id or canonical_name: {risk}")
            continue

        sources = risk.get("source_refs") or []
        if not sources:
            errors.append(f"Injury risk {rid} ({rname}) missing provenance / source_refs.")

        status = risk.get("evidence_status")
        if status and status not in EVIDENCE_STATUSES:
            errors.append(f"Injury risk {rid} has invalid evidence_status {status!r}.")

    is_valid = len(errors) == 0
    return is_valid, errors, review_queue
