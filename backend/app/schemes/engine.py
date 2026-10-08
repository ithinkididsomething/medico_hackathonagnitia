"""Government-scheme matching engine (Prompt 6).

Design decisions
----------------
* Scheme matching is a SEPARATE concern from hospital matching. It never feeds
  the clinical safety/eligibility hierarchy or the hospital ranking.
* We derive situational tags (emergency, maternity, pediatric, ...) from the
  clinical assessment and profile, then evaluate each scheme's
  `eligibility_rules` (same structure as the routing engine: conditions with
  ops eq/ne/gt/gte/lt/lte/in/not_in/contains/exists, plus any/all) over a
  context dict via ``app.rules.engine.evaluate_condition``.
* Output status is ALWAYS "potentially_relevant" / "verification_required".
  We never claim confirmed eligibility or fabricate Ayushman card numbers,
  empanelment, or coverage.

Madhya Pradesh accommodation: the MP state AB scheme (mp_ayushman_state) is in
the catalogue and activates when the clinic records a Madhya Pradesh state, so
state-specific implementation is accommodated without hard-coding.
"""
from __future__ import annotations

from typing import Any

from app.rules.engine import evaluate_condition

from .catalog import (
    SCHEME_MATCH_DISCLAIMER,
    SITUATION_LABELS,
    SCHEMES,
    AYUSHMAN_STATUSES,
)

# Situations we can derive purely from clinical facts in this prototype.
CLINICAL_SITUATION_RULES = {
    "emergency": {"condition": {"field": "emergency_indicator", "op": "eq", "value": True}},
    "critical_care": {"condition": {"field": "critical_care_needed", "op": "eq", "value": True}},
    "trauma": {"condition": {"field": "type", "op": "eq", "value": "trauma"}},
    "hospitalization": {"condition": {"field": "hospitalization", "op": "eq", "value": True}},
    "maternity": {
        "condition": {
            "any": [
                {"field": "specialty", "op": "eq", "value": "obstetrics_gynaecology"},
                {"field": "pregnancy_related", "op": "eq", "value": True},
            ]
        }
    },
    "newborn": {"condition": {"field": "age_years", "op": "lte", "value": 1}},
    "pediatric": {"condition": {"field": "age_years", "op": "lt", "value": 18}},
    "senior_care": {"condition": {"field": "age_years", "op": "gte", "value": 70}},
    "chronic_care": {"condition": {"field": "chronic", "op": "eq", "value": True}},
}


def _situation_key(assessment: dict[str, Any] | None) -> str:
    """Pick the assessment field that best represents a situation key."""
    if not assessment:
        return "specialty"
    for key in ("specialty", "requirements", "situation"):
        if key in assessment:
            return key
    return "specialty"


def derive_situations(
    candidate: dict[str, Any],
    benefits_profile: dict[str, Any] | None = None,
) -> set[str]:
    """Return situational tags relevant for scheme matching.

    ``candidate`` carries clinical facts: age_years, emergency_indicator,
    critical_care_needed, type (interaction_type), hospitalization, specialty,
    pregnancy_related, chronic. The preferred callers already pack facts from
    the assessment/requirements via :func:`build_case_context`.
    """
    profile = benefits_profile or {}
    facts: dict[str, Any] = dict(candidate)

    if profile.get("pregnant") is True:
        facts["pregnancy_related"] = True
    if profile.get("pregnant") is False:
        facts["pregnancy_related"] = False

    # Low-income / vulnerable is derived from the recorded socioeconomic
    # category rather than from clinical facts.
    if profile.get("socioeconomic_category") in ("bpl", "priority_household"):
        facts.setdefault("low_income_household", True)

    situations: set[str] = {
        key
        for key, rule in CLINICAL_SITUATION_RULES.items()
        if evaluate_condition(rule["condition"], facts)
    }

    if "emergency" in situations:
        situations.add("hospitalization")

    if profile.get("socioeconomic_category") in ("bpl", "priority_household"):
        situations.add("low_income")

    return situations


def build_case_context(
    assessment: dict[str, Any] | None,
    requirements: dict[str, Any] | None = None,
    age_years: float | int | None = None,
    benefits_profile: dict[str, Any] | None = None,
    urgency: str | None = None,
    explicit_situations: set[str] | None = None,
) -> dict[str, Any]:
    """Build the single context dict used to evaluate scheme rules."""
    assessment = assessment or {}
    requirements = requirements or {}
    profile = benefits_profile or {}
    num_age = age_years if age_years is not None else assessment.get("age_years")

    candidate: dict[str, Any] = {
        "age_years": float(num_age) if num_age is not None else None,
        "emergency_indicator": bool(assessment.get("emergency_indicator") or requirements.get("emergency_indicator")),
        "critical_care_needed": bool(
            assessment.get("critical_care_needed") or requirements.get("critical_care") is not None
            or requirements.get("icu_care") is not None
        ),
        "hospitalization": bool(
            assessment.get("hospitalization")
            or requirements.get("hospitalization") is True
            or requirements.get("specialty") is not None
            or requirements.get("icu_care") is not None
        ),
        "chronic": bool(assessment.get("chronic") or requirements.get("chronic_condition")),
        "specialty": requirements.get("specialty") or assessment.get("known_specialty"),
        "urgency": (urgency or assessment.get("urgency") or requirements.get("urgency") or "unknown").lower(),
    }

    # Clinical keyword pass-through for condition matching.
    reason = str(assessment.get("chief_complaint") or assessment.get("reason") or "").lower()
    clinical_terms: dict[str, bool] = {
        "pregnancy_related": any(
            t in reason for t in ("pregnan", "delivery", "labour", "vesico", "antenatal", "obstetric")
        ),
        "trauma": bool(
            assessment.get("interaction_type") == "trauma"
            or requirements.get("trauma") is True
            or any(t in reason for t in ("injury", "accident", "fracture", "burn", "trauma", "fall"))
        ),
        "chronic": "chronic" in reason or bool(requirements.get("chronic_condition")),
    }
    candidate.update({k: bool(v) for k, v in clinical_terms.items()})

    context: dict[str, Any] = {
        "assessment": assessment,
        "requirements": requirements,
        "benefits_profile": profile,
        "situations": sorted(
            explicit_situations or derive_situations(candidate, benefits_profile=profile)
        ),
        "age_years": candidate["age_years"],
        "urgency": candidate["urgency"],
        "facts": candidate,
        "state": (profile.get("state") or assessment.get("state") or "").strip().lower(),
    }
    # Convenience flattened access without path resolution.
    context.update(context["facts"])
    return context


def _evaluate_scheme_rules(scheme: dict[str, Any], context: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """Evaluate a scheme's eligibility rules over context.

    Returns (matched_rule_details, best_priority) or empty list when rules are
    unsatisfied. Schemes without rules match only via situations.
    """
    rules = scheme.get("eligibility_rules") or []
    if not rules:
        return [], -1

    matched: list[dict[str, Any]] = []
    for rule in rules:
        try:
            ok = evaluate_condition(rule["condition"], context)
        except Exception:
            ok = False
        if ok:
            matched.append(
                {
                    "condition": rule.get("condition"),
                    "explanation": rule.get("explanation", ""),
                    "priority": int(rule.get("priority", 0)),
                }
            )
    if not matched:
        return [], -1
    return matched, max(int(r["priority"]) for r in matched)


def _resolve_verification(scheme: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Resolve verification needs/status per scheme with correct wording.

    Never fabricates Ayushman card numbers or claims verified coverage on its
    own. If the clinic/bearer recorded a ``verified``/``not_verified``/
    ``not_available``/``unknown`` ayushman_status for a scheme tied to the
    Ayushman card, we surface that recorded status verbatim.
    """
    profile = context.get("benefits_profile") or {}
    recorded = str(profile.get("ayushman_status") or "unknown").lower()
    if recorded not in AYUSHMAN_STATUSES:
        recorded = "unknown"

    needs_card = {"ab_pmjay", "pmjay_senior_vay_vandana", "mp_ayushman_state"}
    requires_verification = bool(scheme.get("application_verification_method"))

    if scheme.get("scheme_id") in needs_card:
        if recorded in ("verified", "not_verified", "not_available"):
            status_hint = recorded
            verification_note = (
                "Ayushman card/eligibility status is recorded from clinic/bearer "
                "input only - confirm against the PM-JAY beneficiary portal "
                "(beneficiary.nha.gov.in / 14555) before acting on it."
            )
        else:
            status_hint = "unknown"
            verification_note = (
                "Ayushman card status not recorded. Confirm the patient's "
                "eligibility/card status via the PM-JAY portal or empanelled "
                "hospital before use."
            )
    elif requires_verification:
        status_hint = "unknown"
        verification_note = (
            "Eligibility and coverage must be confirmed through the official "
            "scheme workflow before any benefit decision."
        )
    else:
        status_hint = "unknown"
        verification_note = "Documentation/verification requirements apply at the point of care."

    return {
        "recorded_status": recorded if scheme.get("scheme_id") in needs_card else None,
        "status_hint": status_hint,
        "verification_status": status_hint if status_hint != "unknown" else "verification_required",
        "requires_verification": True,
        "verification_instructions": (
            scheme.get("application_verification_method")
            or "Confirm through the official scheme workflow."
        ),
        "verification_note": verification_note,
    }


def match_benefit_schemes(
    context: dict[str, Any],
    candidate_schemes: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return potentially-relevant schemes for a case, never confirmed results.

    Confidence is derived ONLY from profile completeness, and is capped so a
    demo can never be read as authoritative.
    """
    schemes = candidate_schemes if candidate_schemes is not None else SCHEMES
    if not schemes:
        return []

    profile = context.get("benefits_profile") or {}
    from .profile import profile_completeness

    filled, total = profile_completeness(profile)
    if total:
        completeness = filled / total
        if completeness >= 0.6:
            confidence = "medium"
        elif completeness >= 0.3:
            confidence = "low"
        else:
            confidence = "minimal"
    else:
        confidence = "minimal"

    results: list[dict[str, Any]] = []
    for scheme in schemes:
        matched_rules, best_priority = _evaluate_scheme_rules(scheme, context)
        if matched_rules:
            situation_hits = sorted(set(scheme.get("situations", [])).intersection(context.get("situations", [])))
            verification = _resolve_verification(scheme, context)
            why_options: list[str] = []
            for rule in matched_rules:
                if rule.get("explanation"):
                    why_options.append(rule["explanation"])
            if situation_hits:
                why_options.append(
                    "; ".join(SITUATION_LABELS.get(s, s) for s in situation_hits)
                )
            why = why_options[0] if why_options else "Potentially relevant to this care pathway."

            results.append(
                {
                    "scheme": {
                        "scheme_id": scheme["scheme_id"],
                        "name": scheme["name"],
                        "short_name": scheme.get("short_name"),
                        "government_level": scheme.get("government_level"),
                        "state": scheme.get("state"),
                        "department": scheme.get("department"),
                        "description": scheme.get("description"),
                        "coverage_type": scheme.get("coverage_type"),
                        "benefit_type": scheme.get("benefit_type"),
                        "benefit_notes": scheme.get("benefit_notes") or [],
                        "exclusions_notice": scheme.get("exclusions_notice"),
                        "official_url": scheme.get("official_url"),
                        "is_prototype": bool(scheme.get("is_prototype", True)),
                        "version": scheme.get("version"),
                        "effective_from": scheme.get("effective_from"),
                        "effective_until": scheme.get("effective_until"),
                    },
                    "match_status": "potentially_relevant",
                    "potentially_eligible": True,
                    "confirmed_eligible": False,
                    "why": why,
                    "matched_rules": matched_rules,
                    "situations": situation_hits,
                    "documents": scheme.get("documents") or [],
                    "verification": verification,
                    "confidence": confidence,
                    "disclaimer": SCHEME_MATCH_DISCLAIMER,
                    "state_specific": bool(scheme.get("state")),
                }
            )

    results.sort(key=lambda r: (max((x.get("priority", 0) for x in r["matched_rules"]), default=0)), reverse=True)
    return results


def benefits_for_assessment(
    assessment: dict[str, Any] | None,
    requirements: dict[str, Any] | None = None,
    age_years: float | int | None = None,
    benefits_profile: dict[str, Any] | None = None,
    urgency: str | None = None,
) -> dict[str, Any]:
    """Top-level convenience used by routes to attach ``benefits`` to responses."""
    context = build_case_context(
        assessment=assessment,
        requirements=requirements,
        age_years=age_years,
        benefits_profile=benefits_profile,
        urgency=urgency,
    )
    matched = match_benefit_schemes(context)
    return {
        "matched_schemes": matched,
        "potentially_eligible_count": sum(1 for m in matched if m.get("potentially_eligible")),
        "confirmed_count": 0,
        "message": (
            "Government scheme suggestions are POTENTIAL matches only. Final "
            "eligibility must be verified through official government systems."
        ),
        "status": "prototype_display",
        "disclaimer": SCHEME_MATCH_DISCLAIMER,
    }