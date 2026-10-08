"""Data models and constants for the Rural Diagnostic Risk & Context knowledge layer (Prompt 8).

Defines the structure for canonical condition records, systemic drivers,
diagnostic confusion relationships, injury diagnostic risks, rural context,
provenance, and validation rules.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

EVIDENCE_STATUSES = (
    "government_documented",
    "government_supported",
    "authoritative_external_source",
    "clinically_recognized",
    "plausible_but_unverified",
    "insufficient_evidence",
    "manual_review_required",
)

RELATIONSHIP_TYPES = (
    "possible_mimic",
    "commonly_confused_with",
    "overlapping_presentation",
    "atypical_presentation",
)

RURAL_RELEVANCE_LEVELS = (
    "rural_specific",
    "rural_relevant",
    "general_clinical_issue",
    "unclear",
)

# Standard diagnostic and treatment capability codes matching app.matching.catalog
KNOWN_CAPABILITY_CODES = {
    # Diagnostics
    "basic_labs",
    "ecg",
    "imaging_xray",
    "ultrasound",
    "ct_scan",
    "pathology",
    # Treatments / Facilities
    "emergency_stabilization",
    "critical_care",
    "surgery_general",
    "orthopedic_surgery",
    "dialysis",
    "obstetric_care",
    "paediatric_care",
    "specialist_consultation",
}


@dataclass
class SourceRef:
    source_id: str
    source_name: str
    source_type: str = "government_authority"  # government_authority | national_health_programme | medical_institution | authoritative_external | secondary
    source_url: str | None = None
    publication_year: int | None = None
    retrieved_at: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiagnosticConfusionEntry:
    confused_with_name: str
    confused_with_condition_id: str | None = None
    relationship_type: str = "possible_mimic"  # possible_mimic | commonly_confused_with | overlapping_presentation
    why_confusion_can_occur: str = ""
    distinguishing_information: list[str] = field(default_factory=list)
    resource_dependency: list[str] = field(default_factory=list)
    evidence_status: str = "manual_review_required"
    source_refs: list[dict[str, Any]] = field(default_factory=list)
    unresolved_condition_reference: bool = False
    rural_specific_claim: bool = False
    rural_evidence_supported: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextRelevance:
    rural_relevance: bool = True
    rural_classification: str = "rural_relevant"  # rural_specific | rural_relevant | general_clinical_issue | unclear
    resource_sensitive: bool = True
    specialist_access_sensitive: bool = False
    diagnostic_equipment_sensitive: bool = False
    evidence_level: str = "plausible_but_unverified"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuralContext:
    diagnostic_risks: list[str] = field(default_factory=list)
    systemic_constraints: list[str] = field(default_factory=list)
    resource_dependencies: list[str] = field(default_factory=list)
    cultural_context: dict[str, Any] = field(default_factory=dict)
    context_relevance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConditionRecord:
    condition_id: str
    canonical_name: str
    category: str = "general_medical"  # general_medical | infectious_disease | injury_trauma | chronic_disease | mental_health
    description: str = ""
    symptoms: list[str] = field(default_factory=list)
    diagnosis: list[str] = field(default_factory=list)
    treatment: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)
    referral_relevance: str = ""
    rural_context: dict[str, Any] = field(default_factory=dict)
    diagnostic_confusion: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SystemicDriver:
    driver_id: str
    name: str
    description: str
    diagnostic_impacts: list[dict[str, Any]] = field(default_factory=list)
    affected_capabilities: list[str] = field(default_factory=list)
    potential_consequences: list[str] = field(default_factory=list)
    referral_implications: list[str] = field(default_factory=list)
    evidence_status: str = "government_documented"
    source_refs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InjuryDiagnosticRisk:
    risk_id: str
    injury_type: str
    canonical_name: str
    possible_confusion_targets: list[str] = field(default_factory=list)
    why_difficult_clinically: str = ""
    imaging_or_diagnostic_relevance: str = ""
    persistence_or_worsening_warning: str = ""
    referral_urgency_relevance: str = ""
    resource_dependencies: list[str] = field(default_factory=list)
    evidence_status: str = "government_documented"
    source_refs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
