"""Clinic resource/capability assessment (Part 1 of the referral flow).

Each clinic declares a configurable set of capabilities and specialties.
Given the derived case requirements, `assess_clinic_capability(...)` decides
whether the current clinic can *potentially* manage the case locally, and
explains exactly which requirements are met and which are missing.

IMPORTANT: demonstration logic only. "Can manage locally" means the clinic's
configured resources cover the derived requirements - it is NOT a clinical
judgement about the patient.
"""
from __future__ import annotations

from typing import Any, Mapping

from ..config import get_settings
from .catalog import diagnostic_label, treatment_label

CLINIC_DISCLAIMER = (
    "Capability check based on configured clinic resources and demonstration "
    "requirement rules. Not a clinical judgement - review by a qualified "
    "healthcare professional is required."
)

# Coarse, configurable capability vocabulary for clinics.
CAPABILITY_LABELS = {
    "emergency_stabilization": "Emergency stabilization",
    "icu": "ICU access",
    "basic_diagnostics": "Basic diagnostics",
    "imaging": "Imaging",
    "laboratory": "Laboratory",
    "surgery": "Surgery",
    "dialysis": "Dialysis",
    "specialist_consultation": "Specialist availability",
}

SPECIALTY_LABELS = {
    "internal_medicine": "Internal medicine",
    "cardiology": "Cardiology",
    "surgery": "Surgery",
    "orthopedics": "Orthopedics",
    "pediatrics": "Pediatrics",
    "obstetrics_gynaecology": "Obstetrics & gynaecology",
    "neurology": "Neurology",
    "emergency_medicine": "Emergency medicine",
    "other": "Other",
}

# Fine-grained requirement codes -> the coarse clinic capability that covers
# them. Configurable mapping; unknown codes require themselves.
REQUIREMENT_TO_CLINIC_CAPABILITY: dict[str, str] = {
    "basic_labs": "laboratory",
    "pathology": "laboratory",
    "ecg": "basic_diagnostics",
    "imaging_xray": "imaging",
    "ultrasound": "imaging",
    "ct_scan": "imaging",
    "emergency_stabilization": "emergency_stabilization",
    "critical_care": "icu",
    "surgery_general": "surgery",
    "orthopedic_surgery": "surgery",
    "dialysis": "dialysis",
    "obstetric_care": "specialist_consultation",
    "paediatric_care": "specialist_consultation",
    "specialist_consultation": "specialist_consultation",
}

# Default demonstration clinic: a primary-care style clinic with basic
# resources but no ICU and no surgery. Location/coordinates are overridable
# via CLINIC_LATITUDE / CLINIC_LONGITUDE; capabilities via PATCH /api/clinics/current.
DEFAULT_CLINIC: dict[str, Any] = {
    "clinic_id": "CLINIC-DEMO-01",
    "name": "Model Primary Clinic (demo)",
    "latitude": 23.2599,
    "longitude": 77.4126,
    "capabilities": [
        "emergency_stabilization",
        "basic_diagnostics",
        "laboratory",
        "imaging",
        "specialist_consultation",
    ],
    "specialties": ["internal_medicine", "pediatrics"],
}


def capability_label(code: str) -> str:
    return CAPABILITY_LABELS.get(code, code.replace("_", " ").title())


def specialty_label(code: str) -> str:
    return SPECIALTY_LABELS.get(code, code.replace("_", " ").title())


def default_clinic() -> dict[str, Any]:
    """Demo clinic profile with the location taken from configuration.

    CLINIC_LATITUDE / CLINIC_LONGITUDE (or a later admin setting) control
    where the clinic sits for routing - no browser geolocation involved.
    """
    settings = get_settings()
    clinic = dict(DEFAULT_CLINIC)
    clinic["latitude"] = settings.clinic_latitude
    clinic["longitude"] = settings.clinic_longitude
    return clinic


def _requirement_capability(code: str) -> str:
    return REQUIREMENT_TO_CLINIC_CAPABILITY.get(code, code)


def assess_clinic_capability(
    requirements: Mapping[str, Any],
    clinic: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare case requirements against a clinic's configured resources.

    Returns a dict:
        clinic                  - the profile that was evaluated (no secrets)
        can_manage_locally      - True when every requirement is covered
        met_requirements        - human-readable met items (for chips)
        missing_capabilities    - human-readable gaps (hard gaps block local care)
        reasons                 - plain-language explanation of the verdict
        disclaimer
    """
    profile = clinic or DEFAULT_CLINIC
    capabilities = set(profile.get("capabilities") or [])
    specialties = set(profile.get("specialties") or [])

    required_specialty = requirements.get("required_specialty")
    needs_emergency = str(requirements.get("needs_emergency") or "none")
    needs_icu = bool(requirements.get("needs_icu"))
    required_diagnostics = list(requirements.get("required_diagnostics") or [])
    required_treatment = list(requirements.get("required_treatment") or [])

    met: list[str] = []
    missing: list[str] = []
    reasons: list[str] = []

    # Specialty coverage.
    if required_specialty:
        label = specialty_label(required_specialty)
        if required_specialty in specialties:
            met.append(f"Specialty: {label}")
            reasons.append(f"Required specialty available at the clinic ({label}).")
        else:
            missing.append(f"Specialty: {label}")
            reasons.append(f"Required specialty not offered by this clinic ({label}).")

    # Emergency capability (coarse check; the level is recorded in the reason).
    if needs_emergency != "none":
        label = capability_label("emergency_stabilization")
        if "emergency_stabilization" in capabilities:
            met.append(label)
            reasons.append(
                f"Emergency capability requirement met ({needs_emergency} level "
                "configured at the clinic)."
            )
        else:
            missing.append(label)
            reasons.append(
                f"Case requires {needs_emergency} emergency capability, which this "
                "clinic does not offer."
            )

    # ICU access.
    if needs_icu:
        label = capability_label("icu")
        if "icu" in capabilities:
            met.append(label)
            reasons.append("ICU access requirement met.")
        else:
            missing.append(label)
            reasons.append("Case likely needs ICU-level care; this clinic has no ICU access.")

    # Diagnostics.
    for code in required_diagnostics:
        needed = _requirement_capability(code)
        label = f"Diagnostics: {diagnostic_label(code)}"
        if needed in capabilities:
            met.append(label)
        else:
            missing.append(label)
            reasons.append(
                f"Required diagnostic not available at this clinic "
                f"({diagnostic_label(code)} needs '{capability_label(needed)}')."
            )

    # Treatments.
    for code in required_treatment:
        needed = _requirement_capability(code)
        label = f"Treatment: {treatment_label(code)}"
        if needed in capabilities:
            met.append(label)
        else:
            missing.append(label)
            reasons.append(
                f"Required treatment capability not available at this clinic "
                f"({treatment_label(code)} needs '{capability_label(needed)}')."
            )

    can_manage = not missing
    if can_manage:
        reasons.append(
            "All derived requirements are covered by the clinic's configured "
            "resources - local management may be possible."
        )
    else:
        reasons.append(
            f"{len(missing)} requirement(s) not covered by this clinic - "
            "referral to a better-equipped facility is recommended."
        )

    return {
        "clinic": {
            "clinic_id": profile.get("clinic_id"),
            "name": profile.get("name"),
            "latitude": profile.get("latitude"),
            "longitude": profile.get("longitude"),
            "capabilities": sorted(capabilities),
            "specialties": sorted(specialties),
        },
        "can_manage_locally": can_manage,
        "met_requirements": met,
        "missing_capabilities": missing,
        "reasons": reasons,
        "disclaimer": CLINIC_DISCLAIMER,
    }


__all__ = [
    "CAPABILITY_LABELS",
    "CLINIC_DISCLAIMER",
    "DEFAULT_CLINIC",
    "REQUIREMENT_TO_CLINIC_CAPABILITY",
    "SPECIALTY_LABELS",
    "assess_clinic_capability",
    "capability_label",
    "default_clinic",
    "specialty_label",
]
