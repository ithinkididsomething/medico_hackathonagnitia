"""Pydantic request/response schemas for the assessment API.

Validation is intentionally strict: required fields are enforced, numeric
vitals must fall in obviously-valid ranges, and no personally identifiable
information (name, contact details) is accepted.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Sex = Literal["female", "male", "other", "unknown"]
KnownSpecialty = Literal[
    "internal_medicine",
    "cardiology",
    "surgery",
    "orthopedics",
    "pediatrics",
    "obstetrics_gynaecology",
    "neurology",
    "emergency_medicine",
    "other",
]

# Validation limits are wider than the demonstration rule thresholds so that
# out-of-range-but-possible values reach the rule engine instead of being
# rejected, while still blocking obviously invalid entries.


class VitalsIn(BaseModel):
    heart_rate: int = Field(description="Beats per minute")
    systolic_bp: int = Field(description="mmHg")
    diastolic_bp: int = Field(description="mmHg")
    respiratory_rate: int = Field(description="Breaths per minute")
    oxygen_saturation: float = Field(description="Percent (0-100)")
    temperature_c: float = Field(description="Celsius")

    @model_validator(mode="after")
    def check_ranges(self) -> "VitalsIn":
        checks = {
            "heart_rate": (self.heart_rate, 20, 300, "bpm"),
            "systolic_bp": (self.systolic_bp, 40, 300, "mmHg"),
            "diastolic_bp": (self.diastolic_bp, 20, 200, "mmHg"),
            "respiratory_rate": (self.respiratory_rate, 4, 80, "breaths/min"),
            "oxygen_saturation": (self.oxygen_saturation, 50, 100, "%"),
            "temperature_c": (self.temperature_c, 30, 45, "°C"),
        }
        for name, (value, low, high, unit) in checks.items():
            if not (low <= value <= high):
                raise ValueError(
                    f"{name.replace('_', ' ').title()} must be between {low} and {high} {unit}."
                )
        if self.systolic_bp < self.diastolic_bp:
            raise ValueError(
                "Systolic blood pressure must not be lower than diastolic blood pressure."
            )
        return self


class AssessmentIn(BaseModel):
    patient_id: str = Field(
        min_length=1,
        max_length=40,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
        description="Clinic-assigned identifier only — no patient names.",
    )
    age_years: int = Field(ge=0, le=120, description="Age in years (0-120)")
    sex: Sex
    chief_complaint: str = Field(min_length=3, max_length=2000)
    vitals: VitalsIn
    clinical_findings: str | None = Field(default=None, max_length=4000)
    illness_details: str | None = Field(default=None, max_length=4000)
    known_specialty: KnownSpecialty | None = None
    emergency_indicator: bool = Field(
        default=False,
        description="Staff-reported explicit emergency indicator (demo field).",
    )

    @model_validator(mode="after")
    def check_text(self) -> "AssessmentIn":
        self.chief_complaint = self.chief_complaint.strip()
        if len(self.chief_complaint) < 3:
            raise ValueError("Main symptoms/complaint is required (at least 3 characters).")
        return self


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #
class RuleDetailOut(BaseModel):
    rule_id: str
    severity: str
    triggered: bool
    score: float
    weight: float
    explanation: str


class UrgencyOut(BaseModel):
    level: str
    label: str
    score: float
    triggered: list[str]
    explanations: list[str]
    rule_details: list[RuleDetailOut]
    rules_source: str
    disclaimer: str


class DecisionOut(BaseModel):
    code: str
    label: str
    note: str
    urgency: str
    basis: str


# --------------------------------------------------------------------------- #
# Clinic capability (Part 1)
# --------------------------------------------------------------------------- #
class ClinicCapabilityOut(BaseModel):
    clinic: dict[str, Any]
    can_manage_locally: bool
    met_requirements: list[str] = []
    missing_capabilities: list[str] = []
    reasons: list[str] = []
    disclaimer: str


class ClinicProfilePatch(BaseModel):
    capabilities: list[str] | None = Field(
        default=None, description="Coarse capability codes (see /api/clinics/current)."
    )
    specialties: list[str] | None = Field(
        default=None, description="Specialty codes the clinic can handle."
    )
    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
        description="Clinic latitude (demo/admin location setting; no browser geolocation).",
    )
    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
        description="Clinic longitude (demo/admin location setting).",
    )


# --------------------------------------------------------------------------- #
# Case requirements (Part 2/3 bridge)
# --------------------------------------------------------------------------- #
class CaseRequirementsOut(BaseModel):
    required_specialty: str | None = None
    needs_emergency: str = "none"
    needs_icu: bool = False
    required_diagnostics: list[str] = []
    required_treatment: list[str] = []
    required_beds: int = 1
    explanations: list[str] = []
    triggered_rules: list[str] = []
    rules_source: str
    disclaimer: str


# --------------------------------------------------------------------------- #
# Hospitals + matching (Parts 2-4, 6)
# --------------------------------------------------------------------------- #
class HospitalOut(BaseModel):
    hospital_id: str
    name: str
    latitude: float
    longitude: float
    specialties: list[str] = []
    emergency_capability: str
    icu_capability: str
    diagnostics: list[str] = []
    treatment_capabilities: list[str] = []
    capacity_status: str
    available_beds: int
    availability_status: str
    is_synthetic: bool = True
    data_note: str = ""


class FactorScoreOut(BaseModel):
    label: str
    earned: float
    possible: float
    reason: str


class TravelEstimateOut(BaseModel):
    distance_km: float | None = None
    travel_minutes: float | None = Field(
        default=None, description="Estimated travel time in minutes (routing or placeholder)."
    )
    # Legacy Prompt-2 field kept so older stored results still validate.
    travel_minutes_placeholder: float | None = None
    source: str = Field(
        default="placeholder",
        description="'osrm' for live road routing, 'placeholder' for straight-line estimates.",
    )
    note: str = ""
    route_coordinates: list[dict[str, Any]] | None = Field(
        default=None,
        description="Thinned route polyline ({latitude, longitude}) for the map, when routed.",
    )


class HospitalMatchOut(BaseModel):
    hospital: HospitalOut
    eligible: bool = True
    total_score: float | None = None
    factor_scores: dict[str, FactorScoreOut] = {}
    reasons: list[str] = []
    missing_capabilities: list[str] = []
    exclusion_reasons: list[str] = []
    why_not: list[str] = Field(
        default_factory=list,
        description="Generated reasons this hospital was not recommended.",
    )
    travel: TravelEstimateOut | None = None
    explanation: str = ""
    # Prompt 6: INFORMATIONAL government-scheme info shown AFTER ranking.
    # Never influences total_score, reasons, or the rank position.
    scheme_compatibility: dict[str, Any] | None = Field(
        default=None,
        description="Informational prototype government-scheme empanelment "
        "details for this hospital; not a ranking factor.",
    )


class MatchResultOut(BaseModel):
    requirements: dict[str, Any]
    weights: dict[str, float]
    clinic_location: dict[str, Any] | None = Field(
        default=None, description="{latitude, longitude} of the clinic used as routing origin."
    )
    best_match: HospitalMatchOut | None = None
    alternatives: list[HospitalMatchOut] = []
    excluded: list[HospitalMatchOut] = []
    evaluated_count: int
    eligible_count: int
    excluded_count: int
    fallback_used: bool = False
    fallback_note: str | None = None
    fallback_detail: dict[str, Any] | None = Field(
        default=None,
        description="Primary/fallback hospital names + reason the fallback happened.",
    )
    summary_explanation: str
    weights_disclaimer: str = ""
    travel_estimate_note: str = ""
    data_disclaimer: str = ""
    # Prompt 6: potential government-scheme matches for the case (computed
    # independently of the ranking above; never merges into scores).
    benefits: dict[str, Any] | None = Field(
        default=None,
        description="Potentially-relevant government schemes (prototype "
        "matches; never confirmed eligibility).",
    )


class MatchRequest(BaseModel):
    assessment_id: int | None = Field(
        default=None, description="Stored assessment to match hospitals for."
    )
    assessment: AssessmentIn | None = Field(
        default=None, description="Inline assessment (alternative to assessment_id)."
    )
    unavailable_hospital_ids: list[str] = Field(
        default_factory=list,
        description="Simulated live-outage hospital ids (fallback testing).",
    )
    weights: dict[str, float] | None = Field(
        default=None, description="Optional scoring weight overrides."
    )
    # Prompt 6: minimum benefit-matching data. Privacy guard enforced in the route.
    benefits_profile: dict[str, Any] | None = Field(
        default=None,
        description="Optional minimum benefit-matching data. Sensitive personal "
        "data (Aadhaar, name, contact) is rejected with 422.",
    )


class AssessmentOut(BaseModel):
    id: int
    created_at: str
    urgency: UrgencyOut
    decision: DecisionOut
    assessment: dict[str, Any]
    requirements: CaseRequirementsOut | None = None
    clinic_capability: ClinicCapabilityOut | None = None
    hospital_matches: MatchResultOut | None = None
    # Prompt 6: potential government-scheme matches for the case.
    government_benefits: dict[str, Any] | None = Field(
        default=None,
        description="Potentially-relevant government schemes (prototype "
        "matches; never confirmed eligibility).",
    )
    # Prompt 7: rural health referral level (1-4), backend-computed.
    referral_level: dict[str, Any] | None = Field(
        default=None,
        description="Suggested referral level (1-4) with backend-generated "
        "explanation. Decision support only — not a diagnosis.",
    )
    # Prompt 8: NEUTRAL diagnostic-risk context from the rural knowledge layer.
    # Advisory only; never a diagnosis and never part of ranking decisions.
    knowledge_context: dict[str, Any] | None = Field(
        default=None,
        description="Neutral decision-support notices from the rural diagnostic "
        "risk knowledge layer (possible mimic overlaps, resource-sensitivity). "
        "Not a diagnosis and never part of hospital ranking.",
    )


class AssessmentSummary(BaseModel):
    id: int
    patient_id: str
    age_years: int
    sex: str
    urgency: str
    decision: str
    score: float
    created_at: str


# --------------------------------------------------------------------------- #
# Routing (Part 2: provider-agnostic route requests)
# --------------------------------------------------------------------------- #
class RoutePointIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RouteRequest(BaseModel):
    origin: RoutePointIn
    destination: RoutePointIn
    profile: str | None = Field(
        default=None, description="Routing profile (e.g. driving); defaults to server config."
    )


class RouteOut(BaseModel):
    distance_km: float
    duration_minutes: float
    source: str = "osrm"
    coordinates: list[dict[str, Any]] = []
    geometry: dict[str, Any] | None = None
    note: str = ""


# --------------------------------------------------------------------------- #
# Referrals (Parts 3-5: summary record, dashboard, status audit)
# --------------------------------------------------------------------------- #
ReferralStatus = Literal[
    "pending", "referred", "accepted", "transferred", "completed"
]


class ReferralCreateIn(BaseModel):
    assessment_id: int = Field(..., ge=1)
    hospital_id: str | None = Field(
        default=None,
        max_length=64,
        description="Optional eligible hospital to recommend; defaults to the best-ranked.",
    )
    unavailable_hospital_ids: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Simulated live-outage hospital ids (fallback testing).",
    )
    note: str = Field(default="", max_length=500)


class ReferralStatusEventOut(BaseModel):
    id: int
    from_status: str | None = None
    to_status: str
    note: str = ""
    changed_by: str = "clinic_staff"
    created_at: str


class ReferralOut(BaseModel):
    id: int
    referral_id: str
    assessment_id: int
    patient_id: str
    urgency: str
    priority: str = Field(description="routine | urgent | emergency")
    recommendation: str
    recommended_hospital_id: str | None = None
    recommended_hospital_name: str | None = None
    alternative_hospital_id: str | None = None
    alternative_hospital_name: str | None = None
    status: ReferralStatus
    explanation: str = ""
    summary: dict[str, Any] | None = None
    created_at: str
    updated_at: str
    status_history: list[ReferralStatusEventOut] = []


class ReferralListOut(BaseModel):
    referrals: list[ReferralOut]
    count: int
    counts: dict[str, Any] = {}
    options: dict[str, list[str]] = {}
    applied_filters: dict[str, str] = {}
    empty_state_message: str = ""


class ReferralStatusPatch(BaseModel):
    status: ReferralStatus
    note: str = Field(default="", max_length=500)
