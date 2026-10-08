"""Capability matching subsystem: clinic resources, case requirements,
synthetic hospital catalogue, hard-constraint matching + transparent scoring.

Built across Prompts 2-3 (clinic resources, hospital data model, capability
matching, scoring, travel-aware ranking via OSRM routing, recommendation UI,
dynamic fallback). Hospital data is SYNTHETIC.
"""
from .catalog import (
    SYNTHETIC_DATA_NOTE,
    SYNTHETIC_HOSPITALS,
    Hospital,
    diagnostic_label,
    synthetic_hospitals,
    treatment_label,
)
from .clinic import (
    CAPABILITY_LABELS,
    CLINIC_DISCLAIMER,
    DEFAULT_CLINIC,
    REQUIREMENT_TO_CLINIC_CAPABILITY,
    SPECIALTY_LABELS,
    assess_clinic_capability,
    capability_label,
    default_clinic,
    specialty_label,
)
from .requirements import (
    CaseRequirements,
    DEMO_REQUIREMENT_RULES,
    REQUIREMENTS_DISCLAIMER,
    REQUIREMENTS_SOURCE,
    derive_requirements,
)
from .scoring import (
    DEFAULT_WEIGHTS,
    FACTOR_LABELS,
    TRAVEL_FACTORS,
    TRAVEL_PLACEHOLDER_NOTE,
    WEIGHTS_DISCLAIMER,
    WeightError,
    check_eligibility,
    match_hospitals,
    missing_capabilities_of,
    score_hospital,
)

__all__ = [
    "CAPABILITY_LABELS",
    "CLINIC_DISCLAIMER",
    "DEFAULT_CLINIC",
    "DEFAULT_WEIGHTS",
    "DEMO_REQUIREMENT_RULES",
    "FACTOR_LABELS",
    "Hospital",
    "REQUIREMENTS_DISCLAIMER",
    "REQUIREMENTS_SOURCE",
    "REQUIREMENT_TO_CLINIC_CAPABILITY",
    "SPECIALTY_LABELS",
    "SYNTHETIC_DATA_NOTE",
    "SYNTHETIC_HOSPITALS",
    "TRAVEL_FACTORS",
    "TRAVEL_PLACEHOLDER_NOTE",
    "WEIGHTS_DISCLAIMER",
    "WeightError",
    "CaseRequirements",
    "assess_clinic_capability",
    "capability_label",
    "check_eligibility",
    "default_clinic",
    "derive_requirements",
    "diagnostic_label",
    "match_hospitals",
    "missing_capabilities_of",
    "score_hospital",
    "specialty_label",
    "synthetic_hospitals",
    "treatment_label",
]
