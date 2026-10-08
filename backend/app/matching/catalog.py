"""Hospital data model + clearly-labelled SYNTHETIC demonstration data.

Every hospital in SYNTHETIC_HOSPITALS is made up for testing the capability
matcher. None of it represents a real facility, a real specialty list, or
real current availability. `is_synthetic` is always True and `data_note`
states this explicitly; API responses carry the same disclaimer.

Capability vocabularies (small on purpose; extend as requirements firm up):

    emergency_capability : full | basic | none
    icu_capability       : available | limited | none
    capacity_status      : open | limited | full
    availability_status  : open | diverting | closed
    diagnostics          : basic_labs, ecg, imaging_xray, ultrasound,
                           ct_scan, pathology
    treatment_capabilities: emergency_stabilization, critical_care,
                           surgery_general, orthopedic_surgery, dialysis,
                           obstetric_care, paediatric_care,
                           specialist_consultation
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

SYNTHETIC_DATA_NOTE = (
    "Synthetic demonstration data - not a real hospital and not real "
    "current availability."
)

EMERGENCY_LEVELS = ("full", "basic", "none")
ICU_LEVELS = ("available", "limited", "none")
CAPACITY_LEVELS = ("open", "limited", "full")
AVAILABILITY_LEVELS = ("open", "diverting", "closed")

DIAGNOSTIC_LABELS = {
    "basic_labs": "Basic laboratory tests",
    "ecg": "ECG / cardiac monitoring",
    "imaging_xray": "X-ray imaging",
    "ultrasound": "Ultrasound imaging",
    "ct_scan": "CT scan",
    "pathology": "Pathology / histopathology",
}

TREATMENT_LABELS = {
    "emergency_stabilization": "Emergency stabilization",
    "critical_care": "Critical care (ICU-level treatment)",
    "surgery_general": "General surgery",
    "orthopedic_surgery": "Orthopedic surgery",
    "dialysis": "Dialysis",
    "obstetric_care": "Obstetric / delivery care",
    "paediatric_care": "Paediatric care",
    "specialist_consultation": "Specialist consultation",
}


def diagnostic_label(code: str) -> str:
    return DIAGNOSTIC_LABELS.get(code, code.replace("_", " ").title())


def treatment_label(code: str) -> str:
    return TREATMENT_LABELS.get(code, code.replace("_", " ").title())


@dataclass
class Hospital:
    hospital_id: str
    name: str
    latitude: float
    longitude: float
    specialties: list[str] = field(default_factory=list)
    emergency_capability: str = "none"
    icu_capability: str = "none"
    diagnostics: list[str] = field(default_factory=list)
    treatment_capabilities: list[str] = field(default_factory=list)
    capacity_status: str = "open"
    available_beds: int = 0
    availability_status: str = "open"
    is_synthetic: bool = True
    data_note: str = SYNTHETIC_DATA_NOTE
    # Government-scheme compatibility (Prompt 6). INFORMATIONAL ONLY: these
    # fields are never used in clinical eligibility or hospital ranking.
    # They mirror the hospital_scheme_eligibility relationship for display.
    ayushman_empaneled: bool = False
    ayushman_verification_date: str | None = None
    scheme_supported_specialties: list[str] = field(default_factory=list)
    scheme_supported_packages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Hospital":
        """Build a Hospital from an API/DB row or a plain dict.

        Tolerates JSON-encoded list columns (as stored in SQLite/PostgreSQL).
        """
        def as_list(value: Any) -> list[str]:
            if value is None:
                return []
            if isinstance(value, str):
                try:
                    decoded = json.loads(value)
                    return [str(item) for item in decoded] if isinstance(decoded, list) else []
                except json.JSONDecodeError:
                    return [part.strip() for part in value.split(",") if part.strip()]
            return [str(item) for item in value]

        return cls(
            hospital_id=str(payload["hospital_id"]),
            name=str(payload["name"]),
            latitude=float(payload["latitude"]),
            longitude=float(payload["longitude"]),
            specialties=as_list(payload.get("specialties")),
            emergency_capability=str(payload.get("emergency_capability", "none")),
            icu_capability=str(payload.get("icu_capability", "none")),
            diagnostics=as_list(payload.get("diagnostics")),
            treatment_capabilities=as_list(payload.get("treatment_capabilities")),
            capacity_status=str(payload.get("capacity_status", "open")),
            available_beds=int(payload.get("available_beds", 0) or 0),
            availability_status=str(payload.get("availability_status", "open")),
            is_synthetic=bool(payload.get("is_synthetic", True)),
            data_note=str(payload.get("data_note", SYNTHETIC_DATA_NOTE)),
            ayushman_empaneled=bool(
                payload.get("ayushman_empaneled", payload.get("is_pmjay_empaneled", False))
            ),
            ayushman_verification_date=(
                payload.get("ayushman_verification_date") or payload.get("pmjay_verification_date")
            ),
            scheme_supported_specialties=as_list(
                payload.get("scheme_supported_specialties")
            ),
            scheme_supported_packages=as_list(payload.get("scheme_supported_packages")),
        )


# --------------------------------------------------------------------------- #
# SYNTHETIC demonstration hospitals (6) — deliberately spread across the
# capability matrix so every matching scenario can be exercised:
#   01 full-service general hospital (usually the best match),
#   02 cardiac/trauma specialty centre,
#   03 small district hospital (no ICU),
#   04 multi-specialty centre with limited ICU + limited capacity,
#   05 teaching hospital that is full + diverting (excluded by constraints),
#   06 capable suburban hub far away (weak distance score).
# --------------------------------------------------------------------------- #
SYNTHETIC_HOSPITALS: list[dict[str, Any]] = [
    {
        "hospital_id": "SYN-HOSP-01",
        "name": "City General Hospital (synthetic)",
        "latitude": 23.2605,
        "longitude": 77.4150,
        "specialties": [
            "internal_medicine",
            "cardiology",
            "surgery",
            "orthopedics",
            "pediatrics",
            "obstetrics_gynaecology",
            "neurology",
            "emergency_medicine",
        ],
        "emergency_capability": "full",
        "icu_capability": "available",
        "diagnostics": ["basic_labs", "ecg", "imaging_xray", "ultrasound", "ct_scan", "pathology"],
        "treatment_capabilities": [
            "emergency_stabilization",
            "critical_care",
            "surgery_general",
            "orthopedic_surgery",
            "dialysis",
            "obstetric_care",
            "paediatric_care",
            "specialist_consultation",
        ],
        "capacity_status": "open",
        "available_beds": 12,
        "availability_status": "open",
        "ayushman_empaneled": True,
        "ayushman_verification_date": "2026-09-15",
        "scheme_supported_specialties": [
            "cardiology",
            "surgery",
            "orthopedics",
            "neurology",
            "internal_medicine",
            "pediatrics",
        ],
        "scheme_supported_packages": [
            "Emergency & Polytrauma packages",
            "Cardiac interventional packages",
            "Stroke / neurology packages",
            "General surgical packages",
        ],
    },
    {
        "hospital_id": "SYN-HOSP-02",
        "name": "Heart & Trauma Institute (synthetic)",
        "latitude": 23.2350,
        "longitude": 77.4010,
        "specialties": ["cardiology", "orthopedics", "surgery", "emergency_medicine"],
        "emergency_capability": "full",
        "icu_capability": "available",
        "diagnostics": ["basic_labs", "ecg", "imaging_xray", "ct_scan"],
        "treatment_capabilities": [
            "emergency_stabilization",
            "critical_care",
            "surgery_general",
            "orthopedic_surgery",
            "specialist_consultation",
        ],
        "capacity_status": "open",
        "available_beds": 6,
        "availability_status": "open",
        "ayushman_empaneled": True,
        "ayushman_verification_date": "2026-09-15",
        "scheme_supported_specialties": ["cardiology", "surgery", "orthopedics"],
        "scheme_supported_packages": [
            "Emergency & Polytrauma packages",
            "Cardiac interventional packages",
            "Orthopaedic packages",
        ],
    },
    {
        "hospital_id": "SYN-HOSP-03",
        "name": "District Community Hospital (synthetic)",
        "latitude": 23.1800,
        "longitude": 77.5500,
        "specialties": ["internal_medicine", "pediatrics"],
        "emergency_capability": "basic",
        "icu_capability": "none",
        "diagnostics": ["basic_labs", "imaging_xray"],
        "treatment_capabilities": [
            "emergency_stabilization",
            "paediatric_care",
            "specialist_consultation",
        ],
        "capacity_status": "open",
        "available_beds": 4,
        "availability_status": "open",
        "ayushman_empaneled": False,
        "ayushman_verification_date": None,
        "scheme_supported_specialties": [],
        "scheme_supported_packages": [],
    },
    {
        "hospital_id": "SYN-HOSP-04",
        "name": "Multi-Specialty Care Centre (synthetic)",
        "latitude": 23.2790,
        "longitude": 77.3900,
        "specialties": [
            "internal_medicine",
            "cardiology",
            "neurology",
            "obstetrics_gynaecology",
            "pediatrics",
        ],
        "emergency_capability": "basic",
        "icu_capability": "limited",
        "diagnostics": ["basic_labs", "ecg", "imaging_xray", "ultrasound"],
        "treatment_capabilities": [
            "emergency_stabilization",
            "critical_care",
            "dialysis",
            "obstetric_care",
            "specialist_consultation",
        ],
        "capacity_status": "limited",
        "available_beds": 2,
        "availability_status": "open",
        "ayushman_empaneled": True,
        "ayushman_verification_date": "2026-08-01",
        "scheme_supported_specialties": [
            "cardiology",
            "neurology",
            "internal_medicine",
            "obstetrics_gynaecology",
        ],
        "scheme_supported_packages": [
            "Emergency packages",
            "Stroke / neurology packages",
        ],
    },
    {
        "hospital_id": "SYN-HOSP-05",
        "name": "Sunrise Teaching Hospital (synthetic)",
        "latitude": 23.2210,
        "longitude": 77.4400,
        "specialties": [
            "internal_medicine",
            "cardiology",
            "surgery",
            "orthopedics",
            "pediatrics",
            "obstetrics_gynaecology",
            "neurology",
            "emergency_medicine",
        ],
        "emergency_capability": "full",
        "icu_capability": "available",
        "diagnostics": ["basic_labs", "ecg", "imaging_xray", "ultrasound", "ct_scan", "pathology"],
        "treatment_capabilities": [
            "emergency_stabilization",
            "critical_care",
            "surgery_general",
            "orthopedic_surgery",
            "dialysis",
            "obstetric_care",
            "paediatric_care",
            "specialist_consultation",
        ],
        "capacity_status": "full",
        "available_beds": 0,
        "availability_status": "diverting",
        "ayushman_empaneled": True,
        "ayushman_verification_date": "2026-06-01",
        "scheme_supported_specialties": [
            "cardiology",
            "surgery",
            "orthopedics",
            "neurology",
            "internal_medicine",
            "pediatrics",
        ],
        "scheme_supported_packages": [
            "Emergency & Polytrauma packages",
            "Cardiac interventional packages",
            "General surgical packages",
        ],
    },
    {
        "hospital_id": "SYN-HOSP-06",
        "name": "Suburban Medical Hub (synthetic)",
        "latitude": 23.1500,
        "longitude": 77.3000,
        "specialties": ["internal_medicine", "surgery", "orthopedics"],
        "emergency_capability": "full",
        "icu_capability": "limited",
        "diagnostics": ["basic_labs", "ecg", "imaging_xray", "ultrasound"],
        "treatment_capabilities": [
            "emergency_stabilization",
            "critical_care",
            "surgery_general",
            "specialist_consultation",
        ],
        "capacity_status": "open",
        "available_beds": 8,
        "availability_status": "open",
        "ayushman_empaneled": False,
        "ayushman_verification_date": None,
        "scheme_supported_specialties": [],
        "scheme_supported_packages": [],
    },
]


def synthetic_hospitals() -> list[Hospital]:
    """Fresh Hospital objects for the built-in SYNTHETIC catalogue."""
    return [Hospital.from_dict(payload) for payload in SYNTHETIC_HOSPITALS]


__all__ = [
    "AVAILABILITY_LEVELS",
    "CAPACITY_LEVELS",
    "DIAGNOSTIC_LABELS",
    "EMERGENCY_LEVELS",
    "Hospital",
    "ICU_LEVELS",
    "SYNTHETIC_DATA_NOTE",
    "SYNTHETIC_HOSPITALS",
    "TREATMENT_LABELS",
    "diagnostic_label",
    "synthetic_hospitals",
    "treatment_label",
]
