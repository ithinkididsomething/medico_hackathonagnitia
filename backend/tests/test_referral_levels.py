"""Rural health referral levels (Prompt 7): unit + API tests.

Covers all four levels, the emergency-override safety rule, workflow
integration (L3/L4 enter matching, L1 never creates an emergency referral),
backend-generated explanations, and persistence with referral records.
"""
import pytest

from app.api.routes import reset_clinic
from app.matching import derive_requirements
from app.rules import calculate_referral_level, classify_urgency


@pytest.fixture(autouse=True)
def _clean_clinic_override():
    reset_clinic()
    yield
    reset_clinic()


def assessment(complaint, age_years=30, emergency_indicator=False, **vitals):
    body = {
        "patient_id": "SYN-700",
        "age_years": age_years,
        "sex": "male",
        "chief_complaint": complaint,
        "vitals": {
            "heart_rate": 75,
            "systolic_bp": 118,
            "diastolic_bp": 76,
            "respiratory_rate": 16,
            "oxygen_saturation": 98,
            "temperature_c": 36.8,
        },
        "clinical_findings": None,
        "illness_details": None,
        "known_specialty": None,
        "emergency_indicator": emergency_indicator,
    }
    body["vitals"].update(vitals)
    return body


def level_of(complaint, **kwargs):
    body = assessment(complaint, **kwargs)
    urgency = classify_urgency(body)
    requirements = derive_requirements(body, urgency.level, urgency.score)
    return calculate_referral_level(body, urgency, requirements), urgency


# --------------------------------------------------------------------------- #
# All four levels
# --------------------------------------------------------------------------- #
def test_mild_presentation_is_level_1():
    level, urgency = level_of("Common cold with mild headache and mild muscle pain")
    assert urgency.level == "GREEN"
    assert level["level"] == 1
    assert level["name"] == "Home Care / Observe"
    assert level["referral_recommended"] is False
    assert level["emergency_transport"] is False
    assert level["needs_hospital_matching"] is False


def test_non_emergency_examination_case_is_level_2():
    level, urgency = level_of("Persistent fever with suspected urinary infection")
    assert urgency.level == "GREEN"
    assert level["level"] == 2
    assert level["name"] == "Local Clinic / PHC"
    assert "rl_clinic_evaluation" in level["triggered_rules"]
    assert level["referral_recommended"] is False


def test_fracture_is_level_3():
    level, urgency = level_of("Fall from bicycle with suspected fracture of forearm")
    assert level["level"] == 3
    assert level["name"] == "Urgent Referral"
    assert "rl_fracture" in level["triggered_rules"]
    assert level["referral_recommended"] is True
    assert level["emergency_transport"] is False
    assert level["needs_hospital_matching"] is True


def test_animal_bite_is_level_3():
    level, urgency = level_of("Dog bite on the leg with a deep wound")
    assert level["level"] == 3
    assert "rl_animal_bite" in level["triggered_rules"]


def test_critical_emergency_is_level_4():
    level, urgency = level_of(
        "Severe chest pain and collapse", oxygen_saturation=87
    )
    assert urgency.level == "RED"
    assert level["level"] == 4
    assert level["name"] == "Emergency / Big Hospital"
    assert level["emergency_transport"] is True
    assert level["referral_recommended"] is True


def test_seizure_keywords_is_level_4():
    level, _ = level_of("Sudden seizure with convulsions lasting two minutes")
    assert level["level"] == 4
    assert "rl_seizure" in level["triggered_rules"]


# --------------------------------------------------------------------------- #
# Safety priority: emergencies are never downgraded
# --------------------------------------------------------------------------- #
def test_emergency_indicator_overrides_mild_symptoms():
    level, urgency = level_of("Mild headache only", emergency_indicator=True)
    assert urgency.level == "RED"
    assert level["level"] == 4


def test_orange_urgency_never_downgrades_to_level_1_or_2():
    level, urgency = level_of("Common cold", oxygen_saturation=92)
    assert urgency.level == "ORANGE"
    assert level["level"] >= 3


def test_red_vitals_never_downgrade_despite_mild_complaint():
    level, urgency = level_of("Mild cold symptoms", oxygen_saturation=85)
    assert urgency.level == "RED"
    assert level["level"] == 4


def test_explanation_corresponds_to_triggered_rules():
    level, _ = level_of("Fall from bicycle with suspected fracture of forearm")
    for rule_id in level["triggered_rules"]:
        assert rule_id in level["reason"]
    assert "Suggested Level 3" in level["reason"]
    assert "based on entered information" in level["reason"]


def test_level_payload_carries_safety_wording():
    level, _ = level_of("Common cold")
    assert "not a diagnosis" in level["disclaimer"].lower() or "decision-support" in level["disclaimer"].lower()
    assert "Suggested" in level["reason"] or "suggested" in level["reason"]


# --------------------------------------------------------------------------- #
# API integration: assessment responses, workflow, persistence
# --------------------------------------------------------------------------- #
def _payload(complaint, **kwargs):
    body = assessment(complaint, **kwargs)
    body["patient_id"] = "SYN-701"
    return body


def test_assessment_response_includes_referral_level(client):
    response = client.post(
        "/api/assessments", json=_payload("Persistent fever for three days")
    )
    assert response.status_code == 201
    body = response.json()
    assert body["referral_level"]["level"] == 2
    assert body["referral_level"]["name"] == "Local Clinic / PHC"
    assert body["referral_level"]["action"]
    assert body["referral_level"]["reason"]

    fetched = client.get(f"/api/assessments/{body['id']}").json()
    assert fetched["referral_level"] == body["referral_level"]


def test_level_3_enters_hospital_referral_workflow(client):
    # A clinic that cannot cover the case escalates a GREEN L3 case to a
    # referral decision, which then runs the existing hospital matching.
    client.patch("/api/clinics/current", json={"capabilities": [], "specialties": []})
    created = client.post(
        "/api/assessments",
        json=_payload("Fall with suspected fracture of the forearm"),
    ).json()
    assert created["referral_level"]["level"] == 3
    assert created["decision"]["code"] == "referral_recommended"
    assert created["hospital_matches"] is not None
    assert created["hospital_matches"]["best_match"] is not None


def test_level_4_enters_emergency_hospital_matching(client):
    created = client.post(
        "/api/assessments",
        json=_payload(
            "Severe chest pain and collapse", oxygen_saturation=87
        ),
    ).json()
    assert created["referral_level"]["level"] == 4
    assert created["decision"]["code"] == "immediate_referral"
    assert created["hospital_matches"]["best_match"] is not None


def test_level_1_does_not_create_emergency_referral(client):
    created = client.post(
        "/api/assessments", json=_payload("Common cold with mild headache")
    ).json()
    assert created["referral_level"]["level"] == 1
    assert created["decision"]["code"] == "manage_locally"
    assert created["hospital_matches"] is None
    # A referral record requires a referral decision — L1 cannot create one.
    denied = client.post("/api/referrals", json={"assessment_id": created["id"]})
    assert denied.status_code == 422


def test_referral_record_persists_referral_level(client):
    created = client.post(
        "/api/assessments",
        json=_payload("Dog bite on the leg", oxygen_saturation=92),
    ).json()
    assert created["referral_level"]["level"] == 3

    referral = client.post(
        "/api/referrals", json={"assessment_id": created["id"]}
    ).json()
    summary = referral["summary"]
    assert summary["referral_level"]["level"] == 3
    assert summary["referral_level_name"] == "Urgent Referral"
    assert summary["referral_level_action"] == created["referral_level"]["action"]
    assert summary["referral_level_reason"] == created["referral_level"]["reason"]
    assert summary["referral_level_rules"] == created["referral_level"]["triggered_rules"]

    text = client.get(f"/api/referrals/{referral['referral_id']}/summary.txt").json()
    assert "Suggested Referral Level:" in text["text"]
    assert "Level 3 — Urgent Referral" in text["text"]
    assert "Recommended Action:" in text["text"]
    assert "Reason:" in text["text"]
