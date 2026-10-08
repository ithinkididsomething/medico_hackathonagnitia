"""Initial clinic decision: map urgency to a manage/referral recommendation.

Deliberately modular: for now the decision follows the urgency level alone.
`decide(..., context=...)` accepts a context so later prompts can incorporate
clinic resources and hospital capability without changing callers.
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
}

__all__ = ["DECISIONS", "decide"]


def decide(urgency: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return {code, label, note, urgency, basis} for an urgency level."""
    if urgency not in DECISIONS:
        raise ValueError(f"Unknown urgency level: {urgency!r}")

    decision = dict(DECISIONS[urgency])
    decision["urgency"] = urgency
    # Reserved for later prompts: clinic resources / hospital capability.
    decision["basis"] = BASES["urgency_only"]
    if context:
        decision["context"] = context
    return decision
