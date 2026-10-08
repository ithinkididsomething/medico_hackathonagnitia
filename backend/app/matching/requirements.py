"""Case requirements derivation — what a hospital must offer for this case.

Takes the structured patient assessment + its urgency classification and
produces a small, explainable requirements object:

    required_specialty, needs_emergency (none/basic/full), needs_icu,
    required_diagnostics, required_treatment, required_beds

The derivation is driven by DEMO_REQUIREMENT_RULES — plain data evaluated
with the same condition engine the urgency rules use (dotted paths,
all/any/not, 10 operators) — so it is configurable and auditable.

IMPORTANT: these are demonstration heuristics, NOT clinically validated
triage logic. Every output must be reviewed by a qualified professional.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from ..rules.engine import evaluate_condition

REQUIREMENTS_SOURCE = "demonstration"
REQUIREMENTS_DISCLAIMER = (
    "Demonstration requirement rules using synthetic heuristics. Not "
    "clinically validated. Any output must be reviewed by a qualified "
    "healthcare professional."
)

# Specialty inferred from complaint keywords when staff did not select one.
# Applied before the staff-selected specialty, which always wins if present.
SPECIALTY_HINTS: list[tuple[str, list[str]]] = [
    ("cardiology", ["chest pain", "palpitation", "cardiac", "heart attack"]),
    ("neurology", ["stroke", "seizure", "unconscious", "slurred speech"]),
    ("obstetrics_gynaecology", ["pregnan", "labour", "postpartum"]),
]


def _hint_rules() -> list[dict[str, Any]]:
    """Keyword-hint rules generated from SPECIALTY_HINTS (single source)."""
    return [
        {
            "id": f"req_specialty_hint_{specialty}",
            "condition": {
                "any": [
                    {"field": "chief_complaint_lower", "op": "contains", "value": hint}
                    for hint in keywords
                ]
            },
            "set": {"required_specialty": specialty},
            "explanation": (
                f"Complaint mentions {specialty.replace('_', ' & ')} keywords - "
                f"{specialty.replace('_', ' & ')} requested for matching."
            ),
        }
        for specialty, keywords in SPECIALTY_HINTS
    ]


@dataclass
class CaseRequirements:
    required_specialty: str | None = None
    needs_emergency: str = "none"  # none | basic | full
    needs_icu: bool = False
    required_diagnostics: list[str] = field(default_factory=list)
    required_treatment: list[str] = field(default_factory=list)
    required_beds: int = 1
    explanations: list[str] = field(default_factory=list)
    triggered_rules: list[str] = field(default_factory=list)
    rules_source: str = REQUIREMENTS_SOURCE
    disclaimer: str = REQUIREMENTS_DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Demonstration requirement rules (data, not code).
# Each rule: id, condition (engine syntax), set (static updates), explanation.
# Evaluated in order against {**assessment, urgency: {...},
# chief_complaint_lower: ...}; later rules may overwrite earlier "set" values.
# --------------------------------------------------------------------------- #
DEMO_REQUIREMENT_RULES: list[dict[str, Any]] = [
    {
        "id": "req_emergency_full_red",
        "condition": {"field": "urgency.level", "op": "eq", "value": "RED"},
        "set": {"needs_emergency": "full"},
        "explanation": "RED (emergency) urgency requires a hospital with full emergency capability.",
    },
    {
        "id": "req_emergency_basic_orange",
        "condition": {"field": "urgency.level", "op": "eq", "value": "ORANGE"},
        "set": {"needs_emergency": "basic"},
        "explanation": "ORANGE (urgent) urgency requires at least basic emergency capability.",
    },
    {
        "id": "req_icu_instability",
        "condition": {
            "all": [
                {"field": "urgency.level", "op": "eq", "value": "RED"},
                {
                    "any": [
                        {"field": "vitals.oxygen_saturation", "op": "lt", "value": 90},
                        {"field": "vitals.systolic_bp", "op": "lt", "value": 90},
                        {"field": "vitals.diastolic_bp", "op": "lt", "value": 50},
                        {"field": "vitals.respiratory_rate", "op": "gt", "value": 30},
                    ]
                },
            ]
        },
        "set": {"needs_icu": True},
        "explanation": (
            "Emergency-level vitals (low oxygen, low blood pressure or very high "
            "respiratory rate) indicate likely need for ICU-level care."
        ),
    },
    # Specialty keyword hints (generated from SPECIALTY_HINTS above).
    *_hint_rules(),
    {
        "id": "req_diagnostics_red",
        "condition": {"field": "urgency.level", "op": "eq", "value": "RED"},
        "set": {"required_diagnostics": ["basic_labs", "ecg"]},
        "explanation": "Emergency cases require basic laboratory tests and ECG availability.",
    },
    {
        "id": "req_diagnostics_orange",
        "condition": {"field": "urgency.level", "op": "eq", "value": "ORANGE"},
        "set": {"required_diagnostics": ["basic_labs"]},
        "explanation": "Urgent cases require basic laboratory tests.",
    },
    {
        "id": "req_treatment_red",
        "condition": {"field": "urgency.level", "op": "eq", "value": "RED"},
        "set": {"required_treatment": ["emergency_stabilization"]},
        "explanation": "Emergency cases require emergency stabilization capability on site.",
    },
]


def build_requirement_context(
    assessment: Mapping[str, Any],
    urgency_level: str,
    urgency_score: float = 0.0,
) -> dict[str, Any]:
    """Combined context the requirement rules evaluate against."""
    context = dict(assessment)
    context["chief_complaint_lower"] = str(assessment.get("chief_complaint") or "").lower()
    context["urgency"] = {"level": urgency_level, "score": urgency_score}
    return context


def derive_requirements(
    assessment: Mapping[str, Any],
    urgency_level: str,
    urgency_score: float = 0.0,
    rules: list[Mapping[str, Any]] | None = None,
) -> CaseRequirements:
    """Derive explainable case requirements from an assessment + urgency."""
    context = build_requirement_context(assessment, urgency_level, urgency_score)
    payloads = list(rules) if rules is not None else DEMO_REQUIREMENT_RULES

    requirements = CaseRequirements()
    for rule in payloads:
        condition = rule.get("condition")
        if not evaluate_condition(condition, context):
            continue
        requirements.triggered_rules.append(str(rule.get("id", "")))
        updates = rule.get("set") or {}
        for key, value in updates.items():
            if hasattr(requirements, key):
                setattr(requirements, key, value)
        explanation = str(rule.get("explanation", ""))
        if explanation:
            requirements.explanations.append(explanation)

    # Staff-selected specialty always wins over keyword hints.
    known = assessment.get("known_specialty")
    if known and known != "other":
        if requirements.required_specialty and requirements.required_specialty != known:
            requirements.explanations.append(
                f"Staff-selected specialty ({known}) overrides the keyword hint "
                f"({requirements.required_specialty})."
            )
        elif not requirements.required_specialty:
            requirements.explanations.append(
                f"Staff selected the required specialty: {known}."
            )
        requirements.required_specialty = str(known)

    # Default specialty so matching always has something concrete to check.
    if not requirements.required_specialty:
        requirements.required_specialty = "internal_medicine"
        requirements.explanations.append(
            "No specialty hint detected - defaulting to internal medicine for matching."
        )

    # ICU-level care implies critical-care treatment availability.
    if requirements.needs_icu and "critical_care" not in requirements.required_treatment:
        requirements.required_treatment.append("critical_care")
        requirements.explanations.append(
            "ICU-level care required - critical care treatment added to the requirements."
        )

    if rules is not None:
        requirements.rules_source = "caller-supplied"
        requirements.disclaimer = (
            "Caller-supplied requirement rules; not clinically validated."
        )

    return requirements


__all__ = [
    "CaseRequirements",
    "DEMO_REQUIREMENT_RULES",
    "REQUIREMENTS_DISCLAIMER",
    "REQUIREMENTS_SOURCE",
    "SPECIALTY_HINTS",
    "build_requirement_context",
    "derive_requirements",
]
