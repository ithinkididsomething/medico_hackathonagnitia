"""Referral record construction: hospital selection + structured summary.

The summary is a self-contained snapshot built entirely from backend data
(stored assessment, rule output, matching results) — never from client-supplied
scoring values. Only the clinic-assigned patient_id is included; no names or
contact details exist anywhere in the system.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

# Decision codes that can produce a referral record.
REFERRAL_DECISIONS = {"referral_recommended", "immediate_referral"}

# Human-facing priority labels for the dashboard (urgency -> priority).
PRIORITY_LABELS = {"GREEN": "routine", "ORANGE": "urgent", "RED": "emergency"}
PRIORITY_ORDER = {"emergency": 0, "urgent": 1, "routine": 2}

NO_SUITABLE_HOSPITAL_MESSAGE = (
    "No suitable facility found based on the currently configured "
    "capabilities and simulated availability."
)


class ReferralError(ValueError):
    """Base class for referral construction problems (HTTP 422)."""


class NoSuitableHospitalError(ReferralError):
    """No eligible hospital exists — never fabricate a recommendation (409)."""


class NotReferralDecisionError(ReferralError):
    """The assessment decided the patient can be managed locally (422)."""


def new_referral_id() -> str:
    """Human-readable unique id: REF-YYYYMMDD-XXXXXX."""
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"REF-{day}-{secrets.token_hex(3).upper()}"


def priority_label(urgency_level: str) -> str:
    return PRIORITY_LABELS.get(urgency_level, "routine")


def choose_recommendation(
    matches: dict[str, Any], hospital_id: str | None = None
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Pick the recommended hospital (and one alternative) from match results.

    `hospital_id` lets staff explicitly select any *eligible* hospital; the
    best-ranked eligible hospital then becomes the alternative. Without a
    selection, the best-ranked hospital wins and the runner-up is the
    alternative. Ineligible or unknown ids are rejected.
    """
    best = matches.get("best_match")
    alternatives = matches.get("alternatives") or []
    if best is None or not best.get("eligible", True):
        raise NoSuitableHospitalError(NO_SUITABLE_HOSPITAL_MESSAGE)

    if hospital_id is None:
        recommended = best
        alternative = alternatives[0] if alternatives else None
        return recommended, alternative

    eligible = [best, *alternatives]
    for match in eligible:
        if match["hospital"]["hospital_id"] == hospital_id:
            recommended = match
            alternative = next(
                (
                    m
                    for m in [best, *alternatives]
                    if m["hospital"]["hospital_id"] != hospital_id
                ),
                None,
            )
            return recommended, alternative
    raise ReferralError(
        f"Hospital {hospital_id!r} is not eligible for this case. "
        "Choose one of the eligible hospitals from the matching result."
    )


def _travel_fields(match: dict[str, Any]) -> dict[str, Any]:
    travel = match.get("travel") or {}
    minutes = travel.get("travel_minutes")
    if minutes is None:
        minutes = travel.get("travel_minutes_placeholder")
    return {
        "distance_km": travel.get("distance_km"),
        "estimated_travel_minutes": minutes,
        "travel_source": travel.get("source", "placeholder"),
        "travel_note": travel.get("note", ""),
    }


def _hospital_entry(match: dict[str, Any]) -> dict[str, Any]:
    hospital = match["hospital"]
    return {
        "hospital_id": hospital["hospital_id"],
        "name": hospital["name"],
        "suitability_score": match.get("total_score"),
        "reasons": list(match.get("reasons") or []),
        "why_not": list(match.get("why_not") or []),
        **_travel_fields(match),
    }


def build_referral_summary(
    *,
    referral_id: str,
    assessment_input: dict[str, Any],
    urgency: dict[str, Any],
    decision: dict[str, Any],
    requirements: dict[str, Any],
    matches: dict[str, Any],
    recommended: dict[str, Any],
    alternative: dict[str, Any] | None,
    government_benefits: dict[str, Any] | None = None,
    referral_level: dict[str, Any] | None = None,
    diagnostic_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the structured referral summary (Part 2 field list)."""
    findings_parts = [
        text.strip()
        for text in (
            assessment_input.get("clinical_findings") or "",
            assessment_input.get("illness_details") or "",
        )
        if text and text.strip()
    ]

    reasons: list[str] = list(requirements.get("explanations") or [])
    if decision.get("note"):
        reasons.append(decision["note"])
    if not reasons:
        reasons = ["Referral decision recorded by the rule engine."]

    recommended_entry = _hospital_entry(recommended)
    level = dict(referral_level or {})
    summary: dict[str, Any] = {
        "referral_id": referral_id,
        "patient_id": assessment_input.get("patient_id", ""),
        "age_years": assessment_input.get("age_years"),
        "sex": assessment_input.get("sex", "unknown"),
        "chief_complaint": assessment_input.get("chief_complaint", ""),
        "clinical_findings": "\n".join(findings_parts),
        "vitals": dict(assessment_input.get("vitals") or {}),
        "urgency": {
            "level": urgency.get("level", ""),
            "label": urgency.get("label", ""),
            "score": urgency.get("score"),
        },
        "priority": priority_label(urgency.get("level", "")),
        # Prompt 7: structured referral-level fields persisted with the record.
        "referral_level": level or None,
        "referral_level_name": level.get("name", "") if level else "",
        "referral_level_action": level.get("action", "") if level else "",
        "referral_level_reason": level.get("reason", "") if level else "",
        "referral_level_rules": list(level.get("triggered_rules") or []) if level else [],
        "reason_for_referral": reasons,
        "required_specialty": requirements.get("required_specialty"),
        "required_facilities": {
            "emergency_level": requirements.get("needs_emergency", "none"),
            "icu": bool(requirements.get("needs_icu")),
            "diagnostics": list(requirements.get("required_diagnostics") or []),
            "treatment": list(requirements.get("required_treatment") or []),
            "beds": requirements.get("required_beds", 1),
        },
        "recommended_hospital": recommended_entry,
        "alternative_hospital": _hospital_entry(alternative) if alternative else None,
        "distance_km": recommended_entry["distance_km"],
        "estimated_travel_minutes": recommended_entry["estimated_travel_minutes"],
        "travel_source": recommended_entry["travel_source"],
        "recommendation_explanation": " ".join(
            part
            for part in (
                matches.get("summary_explanation", ""),
                recommended.get("explanation", ""),
            )
            if part
        ).strip(),
        "why_alternatives": {
            entry["name"]: entry["why_not"]
            for entry in (
                _hospital_entry(m) for m in (matches.get("alternatives") or [])
            )
            if entry["why_not"]
        },
        "fallback_detail": matches.get("fallback_detail"),
        "travel_estimate_note": matches.get("travel_estimate_note", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "government_benefits": government_benefits,
        # Prompt 8: NEUTRAL diagnostic-risk context notices (advisory only).
        "diagnostic_context": diagnostic_context or None,
        "disclaimers": [
            "Demonstration-only decision support — not clinically validated. "
            "A qualified healthcare professional must review every referral.",
            "Hospital capabilities and availability are SYNTHETIC demonstration "
            "data, not real-time information.",
            "Government scheme suggestions are POTENTIAL matches only. Final "
            "eligibility must be verified through official government systems.",
            "The suggested referral level is a prototype decision-support "
            "category based on entered information — not a diagnosis and not "
            "a substitute for clinical judgment.",
        ],
    }
    return summary


def build_summary_text(summary: dict[str, Any]) -> str:
    """Plain-text rendering of the summary for printing/export."""
    lines: list[str] = []
    recommended = summary.get("recommended_hospital") or {}
    alternative = summary.get("alternative_hospital")
    urgency = summary.get("urgency") or {}
    facilities = summary.get("required_facilities") or {}

    lines.append(f"REFERRAL SUMMARY — {summary.get('referral_id', '')}")
    lines.append("=" * 60)
    lines.append(f"Patient ID: {summary.get('patient_id', '')}")
    lines.append(
        f"Age / Sex: {summary.get('age_years', '')} / {summary.get('sex', '')}"
    )
    lines.append(f"Main complaint: {summary.get('chief_complaint', '')}")
    findings = summary.get("clinical_findings") or "—"
    lines.append(f"Clinical findings: {findings}")
    vitals = summary.get("vitals") or {}
    if vitals:
        lines.append(
            "Vital signs: "
            + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in vitals.items())
        )
    lines.append(
        f"Urgency: {urgency.get('level', '')} ({urgency.get('label', '')}) "
        f"· priority: {summary.get('priority', '')}"
    )
    # Prompt 7: suggested referral level alongside the existing fields.
    level = summary.get("referral_level") or {}
    if level:
        lines.append(
            f"Suggested Referral Level: Level {level.get('level', '')} — "
            f"{level.get('name', '')} (decision-support recommendation, "
            "based on entered information)"
        )
        lines.append(f"Recommended Action: {level.get('action', '')}")
        lines.append(f"Reason: {level.get('reason', '')}")
    lines.append("Reason for referral:")
    for reason in summary.get("reason_for_referral") or []:
        lines.append(f"  - {reason}")
    lines.append(f"Required specialty: {summary.get('required_specialty') or '—'}")
    lines.append(
        "Required facilities: emergency="
        f"{facilities.get('emergency_level', 'none')}, "
        f"icu={'yes' if facilities.get('icu') else 'no'}, "
        f"diagnostics={', '.join(facilities.get('diagnostics') or []) or '—'}, "
        f"treatment={', '.join(facilities.get('treatment') or []) or '—'}"
    )
    lines.append("")
    lines.append(
        f"Recommended hospital: {recommended.get('name', '—')} "
        f"(score {recommended.get('suitability_score')})"
    )
    lines.append(
        f"  Distance: {recommended.get('distance_km')} km · "
        f"Estimated travel time: "
        f"{recommended.get('estimated_travel_minutes')} min "
        f"({recommended.get('travel_source', 'placeholder')})"
    )
    if recommended.get("reasons"):
        lines.append("  Why this hospital:")
        for reason in recommended["reasons"]:
            lines.append(f"    - {reason}")
    if alternative:
        lines.append(
            f"Alternative hospital: {alternative.get('name')} "
            f"(score {alternative.get('suitability_score')})"
        )
    explanation = summary.get("recommendation_explanation") or ""
    if explanation:
        lines.append("")
        lines.append(f"Explanation: {explanation}")
    gov_benefits = summary.get("government_benefits") or {}
    matched_schemes = gov_benefits.get("matched_schemes") or []
    if matched_schemes:
        lines.append("")
        lines.append("POTENTIAL GOVERNMENT SCHEMES (NOT confirmed eligibility):")
        for match in matched_schemes:
            scheme = match.get("scheme") or {}
            lines.append(
                f"  - {scheme.get('short_name') or scheme.get('name', 'Scheme')}: "
                f"{match.get('why', '')}"
            )
            verification = match.get("verification") or {}
            if verification.get("verification_instructions"):
                lines.append(
                    f"      Verify: {verification['verification_instructions']}"
                )
            for document in match.get("documents") or []:
                lines.append(f"      Document: {document}")
        lines.append(f"  {gov_benefits.get('message', '')}")
    lines.append("")
    for disclaimer in summary.get("disclaimers") or []:
        lines.append(f"Note: {disclaimer}")
    return "\n".join(lines)
