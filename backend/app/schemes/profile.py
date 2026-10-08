"""Benefits profile normalisation + privacy guard (Prompt 6).

The clinic records ONLY the minimum data required for scheme matching. This
module enforces a strict whitelist:

  * Unknown keys are dropped.
  * Sensitive personal identifiers (Aadhaar, name, phone, email, address,
    date-of-birth) are REJECTED with a ValueError so callers surface a 422,
    never silently persisted. This prototype must never ask for or store
    Aadhaar unless an authorised real integration exists - it does not.
"""
from __future__ import annotations

from typing import Any, final

# Fields the prototype is allowed to accept for scheme matching.
@final
class ProfileFields:
    STATE = "state"
    DISTRICT = "district"
    LOCALITY_TYPE = "locality_type"  # rural | urban
    SOCIOECONOMIC_CATEGORY = "socioeconomic_category"  # bpl | priority_household | general | unknown
    AYUSHMAN_CARD_STATUS = "ayushman_card_status"  # yes | no | unknown
    AYUSHMAN_STATUS = "ayushman_status"  # verified | not_verified | not_available | unknown
    PREGNANT = "pregnant"  # bool | None
    DISABILITY = "disability"  # bool | None
    WORKER_CATEGORY = "worker_category"
    HAS_BPL_RATION_CARD = "has_bpl_ration_card"  # bool | None
    EXISTING_HEALTH_SCHEMES = "existing_health_schemes"  # list[str]


ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        ProfileFields.STATE,
        ProfileFields.DISTRICT,
        ProfileFields.LOCALITY_TYPE,
        ProfileFields.SOCIOECONOMIC_CATEGORY,
        ProfileFields.AYUSHMAN_CARD_STATUS,
        ProfileFields.AYUSHMAN_STATUS,
        ProfileFields.PREGNANT,
        ProfileFields.DISABILITY,
        ProfileFields.WORKER_CATEGORY,
        ProfileFields.HAS_BPL_RATION_CARD,
        ProfileFields.EXISTING_HEALTH_SCHEMES,
    }
)

# Keys that must NEVER be accepted, even if a client sends them.
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "aadhaar",
        "aadhaar_number",
        "uidai",
        "name",
        "full_name",
        "phone",
        "mobile",
        "email",
        "contact",
        "address",
        "dob",
        "date_of_birth",
        "pan",
        "bank_account",
        "account_number",
    }
)

LOCALITY_TYPES: frozenset[str] = frozenset({"rural", "urban"})
SOCIOECONOMIC_CATEGORIES: frozenset[str] = frozenset(
    {"bpl", "priority_household", "general", "unknown"}
)


def normalize_benefits_profile(raw: Any) -> dict[str, Any]:
    """Validate and normalise a benefits profile payload.

    Raises
    ------
    ValueError
        If a sensitive personal-identifier key is present, or an enum-style
        value is not in its allowed set.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("benefits_profile must be an object")

    # 1) Hard reject sensitive personal identifiers before anything else.
    lowered = {str(k).strip().lower(): v for k, v in raw.items()}
    sensitive_hit = SENSITIVE_KEYS.intersection(lowered)
    if sensitive_hit:
        raise ValueError(
            "Sensitive personal information (e.g. Aadhaar, name, contact) is "
            "not accepted by this prototype and never stored."
        )

    # 2) Whitelist allowed keys with canonical spacing/case.
    profile: dict[str, Any] = {}
    for key, value in raw.items():
        normalized_key = str(key).strip().replace("_", " ").replace("-", " ").lower()
        normalized_key = normalized_key.replace(" ", "_")
        if normalized_key not in ALLOWED_KEYS:
            continue  # drop unknown keys silently

        if value is None:
            profile[normalized_key] = None
            continue

        if normalized_key in (ProfileFields.LOCALITY_TYPE,):
            value = str(value).strip().lower()
            if value not in LOCALITY_TYPES:
                raise ValueError(f"locality_type must be one of {sorted(LOCALITY_TYPES)}")
            profile[normalized_key] = value
            continue

        if normalized_key == ProfileFields.SOCIOECONOMIC_CATEGORY:
            value = str(value).strip().lower()
            if value not in SOCIOECONOMIC_CATEGORIES:
                raise ValueError(
                    "socioeconomic_category must be one of "
                    f"{sorted(SOCIOECONOMIC_CATEGORIES)}"
                )
            profile[normalized_key] = value
            continue

        if normalized_key in (ProfileFields.AYUSHMAN_CARD_STATUS,):
            from .catalog import AYUSHMAN_CARD_STATUSES

            value = str(value).strip().lower()
            if value not in AYUSHMAN_CARD_STATUSES:
                raise ValueError(
                    "ayushman_card_status must be one of "
                    f"{sorted(AYUSHMAN_CARD_STATUSES)}"
                )
            profile[normalized_key] = value
            continue

        if normalized_key == ProfileFields.AYUSHMAN_STATUS:
            from .catalog import AYUSHMAN_STATUSES

            value = str(value).strip().lower()
            if value not in AYUSHMAN_STATUSES:
                raise ValueError(
                    "ayushman_status must be one of "
                    f"{sorted(AYUSHMAN_STATUSES)}"
                )
            profile[normalized_key] = value
            continue

        if normalized_key == ProfileFields.WORKER_CATEGORY:
            value = str(value).strip()
            profile[normalized_key] = value or None
            continue

        if normalized_key == ProfileFields.EXISTING_HEALTH_SCHEMES:
            if isinstance(value, (list, tuple)):
                profile[normalized_key] = [str(x).strip() for x in value if str(x).strip()]
            else:
                profile[normalized_key] = [str(value).strip()] if str(value).strip() else []
            continue

        if normalized_key in (ProfileFields.PREGNANT, ProfileFields.DISABILITY,
                              ProfileFields.HAS_BPL_RATION_CARD):
            profile[normalized_key] = _coerce_bool(value, normalized_key) if value is not None else None
            continue

        # scalar free string (state, district)
        profile[normalized_key] = str(value).strip()

    return profile


def _coerce_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value in (0, 1):
            return bool(value)
        raise ValueError(f"{field} must be a boolean")
    text = str(value).strip().lower()
    if text in ("true", "yes", "1", "y"):
        return True
    if text in ("false", "no", "0", "n"):
        return False
    raise ValueError(f"{field} must be a boolean")


def profile_completeness(profile: dict[str, Any]) -> tuple[int, int]:
    """Return (filled, total) counts for provided non-null, non-empty values."""
    total = len(ALLOWED_KEYS)
    filled = 0
    for key in ALLOWED_KEYS:
        value = profile.get(key)
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        filled += 1
    return filled, total