"""Hospital <-> government-scheme compatibility (Prompt 6, Part 8).

INFORMATIONAL ONLY. This data never influences clinical eligibility or the
hospital ranking; it is attached to display results after ranking is computed.
Empanelment flags come from the prototype catalogue (seeded into the
``hospital_scheme_eligibility`` table) and are labelled as such.
"""
from __future__ import annotations

from typing import Any

from .catalog import HOSPITAL_SCHEME_COMPAT


def hospital_scheme_compatibility(
    hospital_id: str,
    hospital_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return informational scheme compatibility for a hospital.

    Falls back to the hospital's own informational fields when present (used
    when the hospital comes from the synthetic catalogue), otherwise the
    prototype compatibility table.
    """
    entry = HOSPITAL_SCHEME_COMPAT.get(hospital_id)
    if entry is None:
        return {
            "hospital_id": hospital_id,
            "scheme_id": None,
            "empaneled_any": False,
            "compatible": [],
            "data_note": "No scheme-compatibility record in the prototype catalogue for this hospital.",
            "source": "prototype-configuration",
        }

    payload = hospital_payload or {}
    flags: dict[str, Any] = {
        "hospital_id": hospital_id,
        "scheme_id": entry.get("scheme_id"),
        "empaneled_any": bool(entry.get("empaneled")),
        "empaneled": bool(entry.get("empaneled")),
        "specialty_codes": entry.get("specialty_codes") or [],
        "packages": entry.get("packages") or [],
        "verification_date": entry.get("verification_date"),
        "source": entry.get("source") or "prototype-configuration",
        "notes": entry.get("notes"),
    }

    # Surface the hospital's own informational flags where they exist.
    if payload.get("ayushman_empaneled") is not None:
        flags["empaneled_any"] = bool(payload.get("ayushman_empaneled"))
        flags["empaneled"] = bool(payload.get("ayushman_empaneled"))
    if payload.get("ayushman_verification_date"):
        flags["verification_date"] = payload.get("ayushman_verification_date")

    compatible = []
    if flags["empaneled_any"]:
        compatible.append(
            {
                "scheme_id": entry["scheme_id"] if entry["scheme_id"] is not None else "ab_pmjay",
                "name": "Ayushman Bharat PM-JAY (and state AB implementation)",
                "covered": True,
                "specialty_codes": flags["specialty_codes"],
                "packages": flags["packages"],
                "verification_date": flags["verification_date"],
                "source": flags["source"],
                "notes": flags["notes"],
            }
        )

    flags["compatible"] = compatible
    flags["data_note"] = (
        "Empanelment is PROTOTYPE configuration for demonstration - confirm "
        "empaneplment on the PM-JAY hospital list before relying on it."
    )
    return flags