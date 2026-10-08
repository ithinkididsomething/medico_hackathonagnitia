"""Initial clinic decision: map urgency (+ clinic capability) to an outcome.

Deliberately modular. The urgency level alone produces the base decision:

    GREEN  -> manage_locally
    ORANGE -> referral_recommended
    RED    -> immediate_referral

`decide(..., context=...)` may carry a `clinic_capability` payload (from
`assess_clinic_capability`). When the configured clinic cannot cover the
case's derived requirements, a GREEN (routine) case is upgraded to
"referral recommended" — with the exact gaps listed in the note. Urgency
ORANGE/RED decisions are unchanged: those cases are referred regardless of
local resources.
"""
from __future__ import annotations

from typing import Any

DECISIONS: dict[str, dict[str, str]] = {
    "GREEN": {
        "code": "manage_locally",
        "label": "Manage locally",
        "note": "Routine demonstration urgency — local management may be appropriate.",
    },
    "ORANGE": {
        "code": "referral_recommended",
        "label": "Referral recommended",
        "note": "Urgent demonstration urgency — consider referral to a higher-level facility.",
    },
    "RED": {
        "code": "immediate_referral",
        "label": "Immediate referral required",
        "note": "Emergency demonstration urgency — arrange immediate referral/escalation.",
    },
}

BASES: dict[str, str] = {
    "urgency_only": "Based on demonstration urgency rules only. Clinic resources "
    "and hospital capability are not yet considered.",
    "urgency_and_clinic": "Based on demonstration urgency rules and the current "
    "clinic's configured capabilities (demo clinic profile).",
}

__all__ = ["DECISIONS", "decide"]


def decide(urgency: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return {code, label, note, urgency, basis} for an urgency level.

    Optional `context["clinic_capability"]` (assess_clinic_capability output)
    is folded into the decision for routine cases the clinic cannot cover.
    """
    if urgency not in DECISIONS:
        raise ValueError(f"Unknown urgency level: {urgency!r}")

    decision = dict(DECISIONS[urgency])
    decision["urgency"] = urgency
    decision["basis"] = BASES["urgency_only"]

    clinic_capability = (context or {}).get("clinic_capability")
    if clinic_capability is not None:
        decision["basis"] = BASES["urgency_and_clinic"]
        missing = list(clinic_capability.get("missing_capabilities") or [])
        can_manage = bool(clinic_capability.get("can_manage_locally"))
        decision["clinic_can_manage"] = can_manage

        if decision["code"] == "manage_locally" and not can_manage:
            gaps = "; ".join(missing) if missing else "configured resource gaps"
            decision["code"] = "referral_recommended"
            decision["label"] = "Referral recommended"
            decision["note"] = (
                "Routine demonstration urgency, but the current clinic's "
                f"configured capabilities do not cover the assessed requirements "
                f"({gaps}) — referral to a better-equipped facility is recommended."
            )
        elif decision["code"] == "manage_locally":
            decision["note"] = (
                "Routine demonstration urgency — local management may be "
                "appropriate; the clinic's configured resources cover the "
                "assessed requirements."
            )
        else:
            decision["note"] = (
                decision["note"]
                + " Hospital capability matching identifies referral candidates "
                "below; clinic resources alone are not sufficient for this case."
            )

    if context:
        decision["context"] = context
    return decision
