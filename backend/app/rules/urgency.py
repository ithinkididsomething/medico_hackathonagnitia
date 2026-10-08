"""Urgency classification on top of the generic rule engine.

Takes a structured patient assessment, evaluates a rule set (demonstration
rules by default) and returns:

    level (GREEN / ORANGE / RED), score, triggered rules, explanations
    and per-rule details.

Classification: the highest severity among triggered rules wins; GREEN when
nothing triggers. The score is the sum of triggered rule weights and is
reported as supporting detail (urgency is severity-driven, not score-driven).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from .demo_rules import DEMO_RULES, RULES_DISCLAIMER, RULES_SOURCE
from .engine import RuleEngine, RuleError

URGENCY_LEVELS = ("GREEN", "ORANGE", "RED")
URGENCY_LABELS = {"GREEN": "Routine", "ORANGE": "Urgent", "RED": "Emergency"}
_RANK = {"GREEN": 0, "ORANGE": 1, "RED": 2}

__all__ = [
    "URGENCY_LEVELS",
    "URGENCY_LABELS",
    "RULES_DISCLAIMER",
    "RULES_SOURCE",
    "UrgencyResult",
    "classify_urgency",
]


@dataclass
class UrgencyResult:
    level: str
    label: str
    score: float
    triggered: list[str] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)
    rule_details: list[dict[str, Any]] = field(default_factory=list)
    rules_source: str = RULES_SOURCE
    disclaimer: str = RULES_DISCLAIMER

    @property
    def is_emergency(self) -> bool:
        return self.level == "RED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_urgency(
    assessment: Mapping[str, Any],
    rules: list[Mapping[str, Any]] | None = None,
) -> UrgencyResult:
    """Evaluate an assessment and return an explainable urgency classification.

    `rules` overrides the built-in demonstration rule set (kept empty of any
    real clinical logic on purpose).
    """
    payloads = list(rules) if rules is not None else DEMO_RULES
    engine = RuleEngine.from_dicts(payloads)
    evaluation = engine.evaluate(assessment)

    severity_by_id = {rule.id: (rule.severity or "GREEN") for rule in engine.rules}

    level = "GREEN"
    for rule_id in evaluation.triggered:
        severity = severity_by_id.get(rule_id, "GREEN")
        if _RANK[severity] > _RANK[level]:
            level = severity

    triggered_details = [d for d in evaluation.details if d.triggered]
    explanations = [d.explanation for d in triggered_details if d.explanation]

    # Ordered: severity desc, then the engine's priority ordering.
    ordered = sorted(
        evaluation.details,
        key=lambda d: (-_RANK.get(severity_by_id.get(d.rule_id, "GREEN"), 0), -d.priority),
    )
    rule_details = [
        {
            "rule_id": d.rule_id,
            "severity": severity_by_id.get(d.rule_id, "GREEN"),
            "triggered": d.triggered,
            "score": d.score,
            "weight": d.weight,
            "explanation": d.explanation,
        }
        for d in ordered
    ]

    if rules is None:
        source, disclaimer = RULES_SOURCE, RULES_DISCLAIMER
    else:
        source, disclaimer = "caller-supplied", "Caller-supplied rules; not clinically validated."

    return UrgencyResult(
        level=level,
        label=URGENCY_LABELS[level],
        score=evaluation.total_score,
        triggered=[d.rule_id for d in triggered_details],
        explanations=explanations,
        rule_details=rule_details,
        rules_source=source,
        disclaimer=disclaimer,
    )


def _validate_levels() -> None:  # pragma: no cover - defensive self-check
    if set(URGENCY_LABELS) != set(URGENCY_LEVELS):
        raise RuleError("Urgency levels and labels are out of sync")
