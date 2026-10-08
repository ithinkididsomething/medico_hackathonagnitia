from app.rules import RuleEngine, RuleError


def make_engine():
    return RuleEngine.from_dicts(
        [
            {
                "id": "senior",
                "condition": {"field": "age", "op": "gte", "value": 65},
                "weight": 5,
                "priority": 10,
                "explanation": "Patient is a senior citizen.",
            },
            {
                "id": "urgent",
                "condition": {
                    "any": [
                        {"field": "symptoms", "op": "contains", "value": "chest pain"},
                        {"field": "triage", "op": "eq", "value": "emergency"},
                    ]
                },
                "weight": 10,
                "priority": 20,
                "explanation": "Urgent case detected.",
            },
            {
                "id": "insurance",
                "condition": {"field": "insurance", "op": "eq", "value": True},
                "weight": 2,
                "explanation": "Insurance on file.",
            },
        ]
    )


def test_engine_scores_and_triggers():
    result = make_engine().evaluate({"age": 70, "symptoms": "mild chest pain"})

    assert result.total_score == 15  # 5 (senior) + 10 (urgent)
    assert set(result.triggered) == {"senior", "urgent"}
    assert result.scores["insurance"] == 0.0
    # Highest priority rule is reported first.
    assert result.triggered[0] == "urgent"


def test_explanations_are_human_readable():
    result = make_engine().evaluate({"age": 30, "triage": "emergency"})

    assert result.explanations == ["urgent: Urgent case detected. (+10)"]
    assert result.total_score == 10


def test_empty_input_scores_zero():
    result = make_engine().evaluate({})

    assert result.total_score == 0.0
    assert result.triggered == []


def test_malformed_rule_rejected():
    try:
        RuleEngine.from_dicts([{"id": "broken", "weight": 3}])
    except RuleError as exc:
        assert "condition" in str(exc)
    else:
        raise AssertionError("expected RuleError")


def test_result_serialises_to_dict():
    payload = make_engine().evaluate({"age": 65}).to_dict()

    assert payload["total_score"] == 5
    assert payload["scores"]["senior"] == 5
    assert payload["triggered"] == ["senior"]
    assert isinstance(payload["details"], list)
