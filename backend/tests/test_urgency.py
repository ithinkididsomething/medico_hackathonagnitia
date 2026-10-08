"""Urgency classification + initial clinic decision (demonstration rules)."""
from app.rules import DEMO_RULES, URGENCY_LABELS, classify_urgency, decide


def assessment(**overrides):
    base = {
        "patient_id": "SYN-001",
        "age_years": 40,
        "sex": "female",
        "chief_complaint": "Synthetic test case",
        "vitals": {
            "heart_rate": 72,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "respiratory_rate": 16,
            "oxygen_saturation": 98,
            "temperature_c": 37.0,
        },
        "clinical_findings": None,
        "illness_details": None,
        "known_specialty": None,
        "emergency_indicator": False,
    }
    for key, value in overrides.items():
        if key == "vitals":
            base["vitals"].update(value)
        else:
            base[key] = value
    return base


def test_normal_case_is_green():
    result = classify_urgency(assessment())

    assert result.level == "GREEN"
    assert result.label == "Routine"
    assert result.score == 0
    assert result.triggered == []
    assert result.explanations == []


def test_abnormal_vitals_are_orange():
    result = classify_urgency(
        assessment(vitals={"oxygen_saturation": 92, "heart_rate": 120})
    )

    assert result.level == "ORANGE"
    assert result.label == "Urgent"
    assert result.score > 0
    assert "demo_mildly_low_oxygen_saturation" in result.triggered
    assert any("Oxygen saturation" in text for text in result.explanations)


def test_severe_vitals_are_red_with_explanations():
    result = classify_urgency(assessment(vitals={"oxygen_saturation": 87}))

    assert result.level == "RED"
    assert result.label == "Emergency"
    assert result.triggered == ["demo_low_oxygen_saturation"]
    assert result.explanations == [
        "Oxygen saturation below configured demonstration threshold (<90%)."
    ]


def test_explicit_emergency_indicator_is_red():
    result = classify_urgency(assessment(emergency_indicator=True))

    assert result.level == "RED"
    assert result.triggered[0] == "demo_emergency_indicator"
    assert "Demonstration emergency criterion triggered" in result.explanations[0]


def test_highest_severity_wins():
    # One ORANGE and one RED rule triggered -> RED.
    result = classify_urgency(
        assessment(
            emergency_indicator=True,
            vitals={"oxygen_saturation": 92},
        )
    )

    assert result.level == "RED"
    assert len(result.triggered) >= 2


def test_result_marks_demo_rules_and_disclaims():
    result = classify_urgency(assessment(vitals={"oxygen_saturation": 92}))

    assert result.rules_source == "demonstration"
    assert "Not clinically validated" in result.disclaimer
    assert len(result.rule_details) == len(DEMO_RULES)
    fired = [d for d in result.rule_details if d["triggered"]]
    assert fired and all(d["explanation"] for d in fired)


def test_result_serialises_to_dict():
    payload = classify_urgency(assessment()).to_dict()

    assert payload["level"] == "GREEN"
    assert set(payload) >= {"level", "label", "score", "triggered", "explanations", "rule_details"}


def test_decision_mapping():
    assert decide("GREEN")["code"] == "manage_locally"
    assert decide("ORANGE")["code"] == "referral_recommended"
    assert decide("RED")["code"] == "immediate_referral"
    for level in URGENCY_LABELS:
        decision = decide(level)
        assert decision["urgency"] == level
        assert "not yet considered" in decision["basis"]


def test_unknown_urgency_rejected():
    try:
        decide("BLUE")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
