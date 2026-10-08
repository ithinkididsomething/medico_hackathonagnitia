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


class AssessmentOut(BaseModel):
    id: int
    created_at: str
    urgency: UrgencyOut
    decision: DecisionOut
    assessment: dict[str, Any]


class AssessmentSummary(BaseModel):
    id: int
    patient_id: str
    age_years: int
    sex: str
    urgency: str
    decision: str
    score: float
    created_at: str
