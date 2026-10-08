"""Rule/scoring engine.

A rule is a structured definition:

    {
      "id": "short-id",
      "name": "Human name (optional)",
      "condition": {"field": "age", "op": "gte", "value": 65},
      "weight": 5,
      "priority": 10,
      "explanation": "Why this rule fired, in plain language."
    }

Conditions may also be nested with "all" / "any" / "not", and "op" supports
eq, ne, gt, gte, lt, lte, in, not_in, contains, exists.

The engine is intentionally empty of application rules: the real rule set is
supplied later (by the caller, a config file, or the database).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping

__all__ = [
    "Rule",
    "RuleEngine",
    "RuleError",
    "RuleResult",
    "EvaluationResult",
    "OPERATORS",
    "evaluate_condition",
]


class RuleError(ValueError):
    """Raised for malformed rules, conditions or inputs."""


def _contains(haystack: Any, needle: Any) -> bool:
    try:
        return needle in haystack
    except TypeError:
        return False


OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "in": lambda a, b: a in (b or []),
    "not_in": lambda a, b: a not in (b or []),
    "contains": _contains,
    "exists": lambda a, b: (a is not None) if b else (a is None),
}


def _lookup(data: Mapping[str, Any], path: str) -> Any:
    """Read a possibly dotted path ("patient.age") from the input."""
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def evaluate_condition(condition: Any, data: Mapping[str, Any]) -> bool:
    """Evaluate a (possibly nested) condition against structured input.

    Unknown fields never trigger a rule; malformed conditions raise RuleError.
    """
    if callable(condition):
        return bool(condition(data))
    if not isinstance(condition, Mapping):
        raise RuleError(f"Condition must be a mapping or callable, got {condition!r}")

    if "all" in condition:
        return all(evaluate_condition(c, data) for c in condition["all"])
    if "any" in condition:
        return any(evaluate_condition(c, data) for c in condition["any"])
    if "not" in condition:
        return not evaluate_condition(condition["not"], data)

    field_path = condition.get("field")
    if not field_path:
        raise RuleError("Condition needs 'field', or a nested 'all' / 'any' / 'not'")

    op = condition.get("op", "eq")
    comparator = OPERATORS.get(op)
    if comparator is None:
        raise RuleError(f"Unknown operator {op!r}. Known: {sorted(OPERATORS)}")

    try:
        return bool(comparator(_lookup(data, str(field_path)), condition.get("value")))
    except (TypeError, ValueError):
        # Comparing incompatible types (e.g. None > 5) simply does not trigger.
        return False


@dataclass(frozen=True)
class Rule:
    id: str
    condition: Any
    weight: float = 1.0
    priority: int = 0
    explanation: str = ""
    name: str = ""
    severity: str = ""  # optional classification label (e.g. GREEN/ORANGE/RED)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], fallback_id: str = "") -> "Rule":
        if not isinstance(payload, Mapping):
            raise RuleError(f"Rule must be a mapping, got {payload!r}")
        if "condition" not in payload:
            raise RuleError("Rule is missing 'condition'")

        rule_id = str(payload.get("id") or fallback_id or "")
        if not rule_id:
            raise RuleError("Rule needs an 'id'")

        try:
            weight = float(payload.get("weight", 1.0))
            priority = int(payload.get("priority", 0))
        except (TypeError, ValueError) as exc:
            raise RuleError(f"Rule '{rule_id}': weight/priority must be numeric") from exc

        return cls(
            id=rule_id,
            condition=payload["condition"],
            weight=weight,
            priority=priority,
            explanation=str(payload.get("explanation", "")),
            name=str(payload.get("name", "")),
            severity=str(payload.get("severity", "")),
        )


@dataclass
class RuleResult:
    rule_id: str
    name: str
    triggered: bool
    score: float
    weight: float
    priority: int
    explanation: str
    severity: str = ""


@dataclass
class EvaluationResult:
    total_score: float
    scores: dict[str, float]
    triggered: list[str]
    explanations: list[str]
    details: list[RuleResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["details"] = [asdict(d) for d in self.details]
        return payload


class RuleEngine:
    """Evaluates a set of rules against structured input."""

    def __init__(self, rules: list[Rule] | None = None) -> None:
        self.rules: list[Rule] = list(rules or [])

    @classmethod
    def from_dicts(cls, payloads: list[Mapping[str, Any]]) -> "RuleEngine":
        rules = [
            Rule.from_dict(p, fallback_id=f"rule_{index + 1}")
            for index, p in enumerate(payloads)
        ]
        return cls(rules)

    def evaluate(self, data: Mapping[str, Any]) -> EvaluationResult:
        if not isinstance(data, Mapping):
            raise RuleError("Engine input must be a mapping of structured data")

        details: list[RuleResult] = []
        for rule in self.rules:
            triggered = evaluate_condition(rule.condition, data)
            details.append(
                RuleResult(
                    rule_id=rule.id,
                    name=rule.name,
                    triggered=triggered,
                    score=float(rule.weight) if triggered else 0.0,
                    weight=float(rule.weight),
                    priority=rule.priority,
                    explanation=rule.explanation,
                    severity=rule.severity,
                )
            )

        # Highest priority first, stable within equal priority.
        details.sort(key=lambda d: (-d.priority, d.rule_id))

        triggered_details = [d for d in details if d.triggered]
        explanations = [
            f"{d.rule_id}: {d.explanation or 'triggered'} (+{d.score:g})"
            for d in triggered_details
        ]

        return EvaluationResult(
            total_score=round(sum(d.score for d in details), 6),
            scores={d.rule_id: d.score for d in details},
            triggered=[d.rule_id for d in triggered_details],
            explanations=explanations,
            details=details,
        )
