"""Hospital/clinic/matching API tests (Parts 2-6) over HTTP."""
import pytest

from app.api.routes import reset_clinic


def payload(**overrides):
    body = {
        "patient_id": "SYN-200",
        "age_years": 50,
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
        "known_specialty": None,
        "emergency_indicator": False,
    }
    for key, value in overrides.items():
        if key == "vitals":
            body["vitals"].update(value)
        else:
            body[key] = value
    return body


@pytest.fixture(autouse=True)
def _clean_clinic_override():
    """Keep the process-local clinic override from leaking between tests."""
    reset_clinic()
    yield
    reset_clinic()


# --------------------------------------------------------------------------- #
# Hospital catalogue (Part 2)
# --------------------------------------------------------------------------- #
def test_hospitals_endpoint_returns_labelled_synthetic_data(client):
    response = client.get("/api/hospitals")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 5
    assert "SYNTHETIC" in body["data_disclaimer"]
    for hospital in body["hospitals"]:
        assert hospital["is_synthetic"] is True
        assert "synthetic" in hospital["data_note"].lower()
        assert set(hospital) >= {
            "hospital_id",
            "name",
            "latitude",
            "longitude",
            "specialties",
            "emergency_capability",
            "icu_capability",
            "diagnostics",
            "treatment_capabilities",
            "capacity_status",
            "available_beds",
            "availability_status",
        }


def test_health_reports_new_version(client):
    body = client.get("/api/health").json()
    assert body["version"] == "0.7.0"


# --------------------------------------------------------------------------- #
# Clinic profile (Part 1)
# --------------------------------------------------------------------------- #
def test_default_clinic_profile(client):
    body = client.get("/api/clinics/current").json()
    assert body["source"] == "default"
    assert "emergency_stabilization" in body["capabilities"]
    assert "icu" not in body["capabilities"]  # demo clinic has no ICU
    assert body["capability_labels"]["icu"] == "ICU access"


def test_patch_and_reset_clinic_capabilities(client):
    patched = client.patch(
        "/api/clinics/current",
        json={"capabilities": ["emergency_stabilization", "icu"], "specialties": ["cardiology"]},
    )
    assert patched.status_code == 200
    assert patched.json()["clinic"]["capabilities"] == ["emergency_stabilization", "icu"]

    profile = client.get("/api/clinics/current").json()
    assert profile["source"] == "override"
    assert "icu" in profile["capabilities"]

    reset = client.delete("/api/clinics/current")
    assert reset.status_code == 200
    assert client.get("/api/clinics/current").json()["source"] == "default"


# --------------------------------------------------------------------------- #
# Assessment integration (Parts 1-5)
# --------------------------------------------------------------------------- #
def test_green_assessment_includes_capability_but_no_hospital_matches(client):
    body = client.post("/api/assessments", json=payload()).json()
    assert body["urgency"]["level"] == "GREEN"
    assert body["decision"]["code"] == "manage_locally"
    assert body["clinic_capability"]["can_manage_locally"] is True
    assert body["requirements"]["required_specialty"] == "internal_medicine"
    assert body["hospital_matches"] is None  # no referral needed -> no matching


def test_orange_assessment_includes_hospital_matches(client):
    body = client.post(
        "/api/assessments",
        json=payload(vitals={"oxygen_saturation": 92, "respiratory_rate": 24}),
    ).json()
    assert body["urgency"]["level"] == "ORANGE"
    assert body["decision"]["code"] == "referral_recommended"
    matches = body["hospital_matches"]
    assert matches is not None
    assert matches["best_match"] is not None
    best = matches["best_match"]
    assert best["total_score"] > 0
    assert best["reasons"]
    assert matches["data_disclaimer"]


def test_red_assessment_immediate_referral_with_full_matching(client):
    body = client.post(
        "/api/assessments",
        json=payload(
            emergency_indicator=True,
            chief_complaint="Severe chest pain and collapse",
            vitals={"oxygen_saturation": 87, "systolic_bp": 86, "heart_rate": 152},
        ),
    ).json()
    assert body["urgency"]["level"] == "RED"
    assert body["decision"]["code"] == "immediate_referral"
    matches = body["hospital_matches"]
    assert matches["best_match"] is not None
    # Best match must satisfy the hard constraints for this case.
    hospital = matches["best_match"]["hospital"]
    assert "cardiology" in hospital["specialties"]
    assert hospital["emergency_capability"] == "full"
    assert hospital["icu_capability"] != "none"
    assert hospital["availability_status"] == "open"
    assert hospital["capacity_status"] != "full"
    # Weak hospitals are excluded with explanations.
    excluded_ids = [e["hospital"]["hospital_id"] for e in matches["excluded"]]
    assert "SYN-HOSP-03" in excluded_ids  # no cardiology, no ICU
    assert "SYN-HOSP-05" in excluded_ids  # diverting + full capacity
    for entry in matches["excluded"]:
        assert entry["exclusion_reasons"]
        assert entry["explanation"]


def test_stored_assessment_returns_persisted_matches(client):
    created = client.post(
        "/api/assessments",
        json=payload(vitals={"oxygen_saturation": 92}),
    ).json()
    fetched = client.get(f"/api/assessments/{created['id']}").json()
    assert fetched["hospital_matches"] is not None
    assert (
        fetched["hospital_matches"]["best_match"]["hospital"]["hospital_id"]
        == created["hospital_matches"]["best_match"]["hospital"]["hospital_id"]
    )
    assert fetched["clinic_capability"] == created["clinic_capability"]


def test_clinic_capability_flip_changes_decision_and_still_matches(client):
    # Strip the clinic of everything -> even a routine case needs referral.
    client.patch(
        "/api/clinics/current",
        json={"capabilities": [], "specialties": []},
    )
    body = client.post("/api/assessments", json=payload()).json()
    assert body["urgency"]["level"] == "GREEN"
    assert body["decision"]["code"] == "referral_recommended"
    assert body["clinic_capability"]["can_manage_locally"] is False
    assert body["hospital_matches"] is not None  # referral -> matching ran


# --------------------------------------------------------------------------- #
# Match endpoint (Parts 3-6)
# --------------------------------------------------------------------------- #
def test_match_endpoint_with_inline_assessment(client):
    response = client.post(
        "/api/referrals/match",
        json={"assessment": payload(vitals={"oxygen_saturation": 92})},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["best_match"] is not None
    assert body["requirements"]["needs_emergency"] == "basic"
    assert set(body["weights"]) == {
        "specialty_match",
        "emergency_capability",
        "icu_capability",
        "diagnostics_match",
        "treatment_match",
        "capacity",
        "distance",
        "travel_time",
    }
    assert body["travel_estimate_note"]
    assert "Placeholder" in body["travel_estimate_note"]


def test_match_endpoint_with_stored_assessment_id(client):
    created = client.post(
        "/api/assessments",
        json=payload(emergency_indicator=True, vitals={"oxygen_saturation": 87}),
    ).json()
    response = client.post("/api/referrals/match", json={"assessment_id": created["id"]})
    assert response.status_code == 200
    assert response.json()["best_match"] is not None


def test_match_endpoint_requires_assessment_input(client):
    response = client.post("/api/referrals/match", json={})
    assert response.status_code == 422


def test_match_endpoint_unknown_assessment_404(client):
    response = client.post("/api/referrals/match", json={"assessment_id": 999999})
    assert response.status_code == 404


def test_match_endpoint_rejects_bad_weights(client):
    response = client.post(
        "/api/referrals/match",
        json={
            "assessment": payload(vitals={"oxygen_saturation": 92}),
            "weights": {"not_a_factor": 10},
        },
    )
    assert response.status_code == 422


def test_match_endpoint_fallback_via_unavailable_top_hospital(client):
    # City General (SYN-HOSP-01) is the usual best match for RED chest pain.
    response = client.post(
        "/api/referrals/match",
        json={
            "assessment": payload(
                emergency_indicator=True,
                chief_complaint="Severe chest pain",
                vitals={"oxygen_saturation": 87, "systolic_bp": 86},
            ),
            "unavailable_hospital_ids": ["SYN-HOSP-01"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["fallback_used"] is True
    assert body["best_match"]["hospital"]["hospital_id"] == "SYN-HOSP-02"
    assert "City General Hospital" in body["fallback_note"]  # named, not just id
    assert "Fallback applied" in body["summary_explanation"]


def test_match_endpoint_respects_clinic_override_for_distance(client):
    # Move the clinic far away -> distance factor decays for every hospital.
    far = client.post(
        "/api/referrals/match",
        json={"assessment": payload(vitals={"oxygen_saturation": 92})},
    ).json()
    client.patch(
        "/api/clinics/current",
        json={"capabilities": [], "specialties": []},
    )
    # PATCH does not change coordinates (kept from the default profile).
    near = client.post(
        "/api/referrals/match",
        json={"assessment": payload(vitals={"oxygen_saturation": 92})},
    ).json()
    assert far["best_match"]["travel"]["distance_km"] == near["best_match"]["travel"]["distance_km"]

