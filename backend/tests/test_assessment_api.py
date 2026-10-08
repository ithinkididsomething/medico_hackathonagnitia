"""End-to-end assessment API tests: three severities + invalid input handling."""


def payload(**overrides):
    body = {
        "patient_id": "SYN-100",
        "age_years": 35,
        "sex": "male",
        "chief_complaint": "Synthetic test case for automated testing",
        "vitals": {
            "heart_rate": 75,
            "systolic_bp": 118,
            "diastolic_bp": 76,
            "respiratory_rate": 16,
            "oxygen_saturation": 98,
            "temperature_c": 36.8,
        },
        "clinical_findings": "Synthetic findings",
        "illness_details": "Synthetic details",
        "known_specialty": None,
        "emergency_indicator": False,
    }
    for key, value in overrides.items():
        if key == "vitals":
            body["vitals"].update(value)
        else:
            body[key] = value
    return body


def test_normal_synthetic_case(client):
    response = client.post("/api/assessments", json=payload())

    assert response.status_code == 201
    body = response.json()
    assert body["urgency"]["level"] == "GREEN"
    assert body["urgency"]["label"] == "Routine"
    assert body["decision"]["code"] == "manage_locally"
    assert body["decision"]["label"] == "Manage locally"
    assert body["assessment"]["patient_id"] == "SYN-100"


def test_urgent_synthetic_case(client):
    response = client.post(
        "/api/assessments",
        json=payload(vitals={"oxygen_saturation": 92, "respiratory_rate": 24}),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["urgency"]["level"] == "ORANGE"
    assert body["decision"]["code"] == "referral_recommended"
    assert body["urgency"]["explanations"]
    assert "Not clinically validated" in body["urgency"]["disclaimer"]


def test_emergency_synthetic_case(client):
    response = client.post(
        "/api/assessments",
        json=payload(emergency_indicator=True, vitals={"oxygen_saturation": 88}),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["urgency"]["level"] == "RED"
    assert body["decision"]["code"] == "immediate_referral"
    assert len(body["urgency"]["explanations"]) >= 2
    fired = [d for d in body["urgency"]["rule_details"] if d["triggered"]]
    assert all(d["severity"] in {"RED", "ORANGE"} for d in fired)


def test_assessment_is_persisted(client):
    created = client.post("/api/assessments", json=payload()).json()

    fetched = client.get(f"/api/assessments/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["urgency"]["level"] == "GREEN"
    assert fetched.json()["assessment"] == created["assessment"]

    listed = client.get("/api/assessments")
    assert listed.status_code == 200
    assert any(item["id"] == created["id"] for item in listed.json())

    assert client.get("/api/assessments/999999").status_code == 404


def test_invalid_payloads_are_rejected(client):
    cases = {
        "missing patient id": {"patient_id": None},
        "bad patient id (spaces)": {"patient_id": "P 1"},
        "negative age": {"age_years": -5},
        "absurd age": {"age_years": 999},
        "heart rate too high": {"vitals": {"heart_rate": 500}},
        "heart rate too low": {"vitals": {"heart_rate": 5}},
        "oxygen saturation >100": {"vitals": {"oxygen_saturation": 120}},
        "temperature impossible": {"vitals": {"temperature_c": 99}},
        "respiratory rate absurd": {"vitals": {"respiratory_rate": 400}},
        "systolic below diastolic": {"vitals": {"systolic_bp": 60, "diastolic_bp": 90}},
        "short complaint": {"chief_complaint": "x"},
        "invalid sex": {"sex": "unspecified"},
    }
    for label, patch in cases.items():
        body = payload()
        if "patient_id" in patch and patch["patient_id"] is None:
            body.pop("patient_id")
        else:
            for key, value in patch.items():
                if key == "vitals":
                    body["vitals"].update(value)
                else:
                    body[key] = value
        response = client.post("/api/assessments", json=body)
        assert response.status_code == 422, f"{label} should be rejected"
        detail = response.json()["detail"]
        assert isinstance(detail, list) and detail, f"{label}: clear errors expected"
        assert all("msg" in item and "loc" in item for item in detail)


def test_missing_vitals_rejected(client):
    body = payload()
    body.pop("vitals")
    response = client.post("/api/assessments", json=body)
    assert response.status_code == 422


def test_no_pii_fields_accepted_or_required(client):
    body = payload(
        patient_name="Should Not Appear",
        phone="555-0100",
    )
    response = client.post("/api/assessments", json=body)
    # Extra keys are ignored by pydantic; nothing is stored under them.
    assert response.status_code == 201
    assert "patient_name" not in response.json()["assessment"]
    assert "phone" not in response.json()["assessment"]
