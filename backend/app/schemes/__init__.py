"""Government Healthcare Schemes & Benefits layer (Prompt 6).

The scheme layer is kept strictly separate from clinical matching: hospital
ranking never changes because of scheme compatibility (clinical safety first).
"""
from __future__ import annotations

from .catalog import (
    AYUSHMAN_CARD_STATUSES,
    AYUSHMAN_STATUSES,
    BENEFITS_PROFILE_PRIVACY_NOTE,
    DOCUMENT_CATALOG,
    HOSPITAL_SCHEME_COMPAT,
    SCHEME_DATA_NOTE,
    SCHEME_MATCH_DISCLAIMER,
    SCHEMES,
    SITUATION_LABELS,
    SOURCES,
    SCHEME_CATALOG_META,
)
from .profile import (
    ALLOWED_KEYS,
    SENSITIVE_KEYS,
    normalize_benefits_profile,
    profile_completeness,
)
from .engine import (
    build_case_context,
    derive_situations,
    match_benefit_schemes,
    benefits_for_assessment,
)
from .hospital import hospital_scheme_compatibility

__all__ = [
    "AYUSHMAN_CARD_STATUSES",
    "AYUSHMAN_STATUSES",
    "BENEFITS_PROFILE_PRIVACY_NOTE",
    "DOCUMENT_CATALOG",
    "HOSPITAL_SCHEME_COMPAT",
    "SCHEME_DATA_NOTE",
    "SCHEME_MATCH_DISCLAIMER",
    "SCHEMES",
    "SITUATION_LABELS",
    "SOURCES",
    "SCHEME_CATALOG_META",
    "ALLOWED_KEYS",
    "SENSITIVE_KEYS",
    "normalize_benefits_profile",
    "profile_completeness",
    "build_case_context",
    "derive_situations",
    "match_benefit_schemes",
    "benefits_for_assessment",
    "hospital_scheme_compatibility",
]