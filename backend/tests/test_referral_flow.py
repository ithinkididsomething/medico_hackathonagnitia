"""End-to-end referral workflow tests (Prompt 4: Parts 3-5).

Covers the three required E2E cases (routine / urgent / emergency) plus:
no suitable hospital, hospital unavailable, routing failure, invalid
assessment, dashboard filtering, and explicit status updates with audit.
"""
import pytest

from app.api.routes import reset_clinic


def payload(**overrides):
    body = {
        "patient_id": "SYN-REF-1",
        "age_years": 50,
        "sex": "male",
        "chief_complaint": "Synthetic referral flow test case",
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


CASE_ROUTINE = {}  # GREEN -> manage locally
CASE_URGENT = {
    "vitals": {"oxygen_saturation": 92, "respiratory_rate": 24},
    "patient_id": "SYN-REF-2",
}
CASE_EMERGENCY = {
    "emergency_indicator": True,
    "chief_complaint": "Severe chest pain and collapse",
    "vitals": {"oxygen_saturation": 87, "systolic_bp": 86, "heart_rate": 152},
    "patient_id": "SYN-REF-3",
}


@pytest.fixture(autouse=True)
def _clean_clinic_override():
    reset_clinic()
    yield
    reset_clinic()


def create_assessment(client, **overrides):
    response = client.post("/api/assessments", json=payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# CASE 1: Routine patient -> managed locally -> no referral record possible
# --------------------------------------------------------------------------- #
def test_case1_routine_manage_locally_cannot_create_referral(client):
    assessment = create_assessment(client, **CASE_ROUTINE)
    assert assessment["urgency"]["level"] == "GREEN"
    assert assessment["decision"]["code"] == "manage_locally"

    response = client.post("/api/referrals", json={"assessment_id": assessment["id"]})
    assert response.status_code == 422
    assert "does not require a referral" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# CASE 2: Urgent patient -> referral -> matching -> ranking -> route -> summary
# --------------------------------------------------------------------------- #
def test_case2_urgent_referral_summary_complete(client):
    assessment = create_assessment(client, **CASE_URGENT)
    assert assessment["decision"]["code"] == "referral_recommended"
    assert assessment["hospital_matches"]["best_match"] is not None

    response = client.post("/api/referrals", json={"assessment_id": assessment["id"]})
    assert response.status_code == 201, response.text
    referral = response.json()

    # Record fields
    assert referral["referral_id"].startswith("REF-")
    assert referral["patient_id"] == "SYN-REF-2"
    assert referral["urgency"] == "ORANGE"
    assert referral["priority"] == "urgent"
    assert referral["status"] == "pending"
    assert referral["recommended_hospital_id"]
    assert referral["recommended_hospital_name"]
    assert referral["status_history"][0]["to_status"] == "pending"

    # Part 2 summary field list
    summary = referral["summary"]
    for field in (
        "patient_id",
        "age_years",
        "sex",
        "chief_complaint",
        "clinical_findings",
        "vitals",
        "urgency",
        "reason_for_referral",
        "required_specialty",
        "required_facilities",
        "recommended_hospital",
        "alternative_hospital",
        "distance_km",
        "estimated_travel_minutes",
        "recommendation_explanation",
    ):
        assert field in summary, f"missing summary field: {field}"
    assert summary["patient_id"] == "SYN-REF-2"
    assert summary["age_years"] == 50
    assert summary["sex"] == "male"
    assert summary["urgency"]["level"] == "ORANGE"
    assert summary["priority"] == "urgent"
    assert set(summary["vitals"]) == {
        "heart_rate",
        "systolic_bp",
        "diastolic_bp",
        "respiratory_rate",
        "oxygen_saturation",
        "temperature_c",
    }
    assert summary["reason_for_referral"]  # generated from requirements/decision
    assert summary["recommended_hospital"]["hospital_id"]
    assert summary["recommended_hospital"]["reasons"]
    assert summary["distance_km"] is not None
    assert summary["estimated_travel_minutes"] is not None
    assert summary["recommendation_explanation"]
    # Routing is disabled in tests -> placeholder source must be explicit.
    assert summary["travel_source"] == "placeholder"
    assert "not clinically validated" in " ".join(summary["disclaimers"]).lower()

    # Detail endpoint returns the same summary + history
    detail = client.get(f"/api/referrals/{referral['referral_id']}").json()
    assert detail["summary"]["referral_id"] == referral["referral_id"]
    assert len(detail["status_history"]) == 1

    # Plain-text summary export
    text = client.get(f"/api/referrals/{referral['referral_id']}/summary.txt").json()
    assert "REFERRAL SUMMARY" in text["text"]
    assert "SYN-REF-2" in text["text"]
    assert summary["recommended_hospital"]["name"] in text["text"]


# --------------------------------------------------------------------------- #
# CASE 3: Emergency -> capability filtering -> travel-aware ranking -> tracking
# --------------------------------------------------------------------------- #
def test_case3_emergency_full_flow_to_completed(client):
    assessment = create_assessment(client, **CASE_EMERGENCY)
    assert assessment["urgency"]["level"] == "RED"
    matches = assessment["hospital_matches"]
    # Capability filtering already excluded incapable hospitals.
    excluded_ids = [e["hospital"]["hospital_id"] for e in matches["excluded"]]
    assert "SYN-HOSP-03" in excluded_ids

    created = client.post("/api/referrals", json={"assessment_id": assessment["id"]})
    assert created.status_code == 201
    referral = created.json()
    assert referral["urgency"] == "RED"
    assert referral["priority"] == "emergency"
    assert referral["recommendation"] == "immediate_referral"
    # Best + alternative both present.
    assert referral["recommended_hospital_id"] == "SYN-HOSP-01"
    assert referral["alternative_hospital_id"] == "SYN-HOSP-02"
    summary = referral["summary"]
    assert summary["alternative_hospital"]["name"]
    # Ranking is travel-aware: travel data present on both entries.
    assert summary["recommended_hospital"]["distance_km"] is not None
    assert summary["alternative_hospital"]["estimated_travel_minutes"] is not None
    # Generated explanations for alternatives ("why ranked lower").
    assert summary["why_alternatives"] or summary["alternative_hospital"]["why_not"]

    ref = referral["referral_id"]

    # Explicit, auditable status journey: pending -> referred -> accepted ->
    # transferred -> completed.
    steps = [
        ("referred", "Sent to hospital"),
        ("accepted", "Hospital accepted"),
        ("transferred", "Patient moved"),
        ("completed", "Episode closed"),
    ]
    for target, note in steps:
        response = client.patch(
            f"/api/referrals/{ref}/status", json={"status": target, "note": note}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == target

    history = client.get(f"/api/referrals/{ref}").json()["status_history"]
    assert [event["to_status"] for event in history] == [
        "pending",
        "referred",
        "accepted",
        "transferred",
        "completed",
    ]
    assert history[1]["note"] == "Sent to hospital"
    assert history[0]["from_status"] is None

    # Terminal state: no further transitions allowed.
    rejected = client.patch(
        f"/api/referrals/{ref}/status", json={"status": "referred"}
    )
    assert rejected.status_code == 409
    assert "Cannot move" in rejected.json()["detail"]


def test_hospital_selection_by_id_picks_alternative(client):
    assessment = create_assessment(client, **CASE_EMERGENCY)
    response = client.post(
        "/api/referrals",
        json={"assessment_id": assessment["id"], "hospital_id": "SYN-HOSP-02"},
    )
    assert response.status_code == 201
    referral = response.json()
    assert referral["recommended_hospital_id"] == "SYN-HOSP-02"
    assert referral["alternative_hospital_id"] == "SYN-HOSP-01"


def test_hospital_selection_rejects_ineligible_hospital(client):
    assessment = create_assessment(client, **CASE_EMERGENCY)
    response = client.post(
        "/api/referrals",
        json={"assessment_id": assessment["id"], "hospital_id": "SYN-HOSP-03"},
    )
    assert response.status_code == 422
    assert "not eligible" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# Edge cases: no suitable hospital, unavailable hospital, invalid input
# --------------------------------------------------------------------------- #
def test_no_suitable_hospital_returns_409_without_fabrication(client, monkeypatch):
    assessment = create_assessment(client, **CASE_EMERGENCY)
    monkeypatch.setattr(
        "app.api.routes.repository.list_hospitals", lambda *a, **k: []
    )
    response = client.post("/api/referrals", json={"assessment_id": assessment["id"]})
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "No suitable facility found based on the currently configured "
        "capabilities and simulated availability."
    )
    # Nothing was fabricated into the dashboard.
    listing = client.get("/api/referrals").json()
    assert listing["count"] == 0


def test_referral_with_unavailable_best_hospital_uses_fallback(client):
    assessment = create_assessment(client, **CASE_EMERGENCY)
    response = client.post(
        "/api/referrals",
        json={
            "assessment_id": assessment["id"],
            "unavailable_hospital_ids": ["SYN-HOSP-01"],
        },
    )
    assert response.status_code == 201
    referral = response.json()
    assert referral["recommended_hospital_id"] == "SYN-HOSP-02"
    assert referral["summary"]["fallback_detail"] is not None
    assert referral["summary"]["fallback_detail"]["primary_hospital_id"] == "SYN-HOSP-01"
    assert "City General Hospital" in referral["summary"]["fallback_detail"]["primary_name"]


def test_referral_with_routing_failure_still_created(client, monkeypatch):
    # ROUTING_ENABLED is false in tests: TravelEstimator must degrade gracefully.
    assessment = create_assessment(client, **CASE_URGENT)
    response = client.post("/api/referrals", json={"assessment_id": assessment["id"]})
    assert response.status_code == 201
    summary = response.json()["summary"]
    assert summary["travel_source"] == "placeholder"
    assert summary["travel_estimate_note"]
    assert summary["distance_km"] is not None  # straight-line distance still given


def test_referral_unknown_assessment_404(client):
    response = client.post("/api/referrals", json={"assessment_id": 999999})
    assert response.status_code == 404


def test_referral_invalid_body_422(client):
    assert client.post("/api/referrals", json={}).status_code == 422
    assessment = create_assessment(client, **CASE_URGENT)
    # patient_id-style injection into other fields must fail validation.
    assert (
        client.post(
            "/api/referrals",
            json={"assessment_id": assessment["id"], "note": "x" * 501},
        ).status_code
        == 422
    )


def test_referral_list_rejects_bad_filters(client):
    assert client.get("/api/referrals?urgency=PURPLE").status_code == 422
    assert client.get("/api/referrals?status=exploded").status_code == 422
    assert client.get("/api/referrals?date_from=09-10-2026").status_code == 422


# --------------------------------------------------------------------------- #
# Dashboard: list, filtering, counts, empty state
# --------------------------------------------------------------------------- #
def test_dashboard_list_and_filters(client):
    # Three referrals: urgent (ORANGE), emergency (RED), plus another urgent.
    urgent = create_assessment(client, **CASE_URGENT)
    emergency = create_assessment(client, **CASE_EMERGENCY)
    urgent2 = create_assessment(
        client,
        **{
            "patient_id": "SYN-REF-4",
            "vitals": {"oxygen_saturation": 93, "respiratory_rate": 25},
        },
    )
    created = []
    for assessment in (urgent, emergency, urgent2):
        response = client.post(
            "/api/referrals", json={"assessment_id": assessment["id"]}
        )
        assert response.status_code == 201
        created.append(response.json())

    everything = client.get("/api/referrals").json()
    assert everything["count"] == 3
    assert everything["counts"]["by_status"]["pending"] == 3
    assert everything["counts"]["by_urgency"]["RED"] == 1
    assert everything["options"]["status"] == [
        "pending",
        "referred",
        "accepted",
        "transferred",
        "completed",
    ]
    # Dashboard row projection (no heavy summary payload in the list).
    for row in everything["referrals"]:
        assert row["summary"] is None
        assert set(row) >= {
            "referral_id",
            "patient_id",
            "urgency",
            "priority",
            "recommendation",
            "status",
            "created_at",
        }

    by_urgency = client.get("/api/referrals?urgency=RED").json()
    assert by_urgency["count"] == 1
    assert by_urgency["referrals"][0]["urgency"] == "RED"
    assert by_urgency["applied_filters"] == {"urgency": "RED"}

    by_recommendation = client.get(
        "/api/referrals?recommendation=referral_recommended"
    ).json()
    assert by_recommendation["count"] == 2

    # Date filters: today only (all three created "now").
    today = urgent["created_at"][:10]
    assert client.get(f"/api/referrals?date_from={today}").json()["count"] == 3
    assert (
        client.get("/api/referrals?date_from=2000-01-01&date_to=2000-01-02").json()[
            "count"
        ]
        == 0
    )

    # Status filter after a transition.
    ref = created[1]["referral_id"]
    client.patch(f"/api/referrals/{ref}/status", json={"status": "referred"})
    assert client.get("/api/referrals?status=pending").json()["count"] == 2
    assert client.get("/api/referrals?status=referred").json()["count"] == 1


def test_dashboard_empty_state_message(client):
    body = client.get("/api/referrals").json()
    assert body["count"] == 0
    assert "No referrals recorded yet" in body["empty_state_message"]

    # Filters active + no matches -> different message.
    body = client.get("/api/referrals?status=completed").json()
    assert "No referrals match the current filters" in body["empty_state_message"]


def test_referral_detail_404(client):
    assert client.get("/api/referrals/REF-NOPE-000000").status_code == 404
    assert (
        client.patch(
            "/api/referrals/999999/status", json={"status": "referred"}
        ).status_code
        == 404
    )


# --------------------------------------------------------------------------- #
# Status transitions: explicit, validated, audited
# --------------------------------------------------------------------------- #
def test_invalid_status_transitions_rejected(client):
    assessment = create_assessment(client, **CASE_URGENT)
    ref = client.post(
        "/api/referrals", json={"assessment_id": assessment["id"]}
    ).json()["referral_id"]

    # pending may only move to referred.
    for bad in ("accepted", "transferred", "completed"):
        response = client.patch(
            f"/api/referrals/{ref}/status", json={"status": bad}
        )
        assert response.status_code == 409, bad
        assert "allowed: referred" in response.json()["detail"]

    # Same status is rejected as non-actionable.
    assert (
        client.patch(f"/api/referrals/{ref}/status", json={"status": "pending"}).status_code
        == 409
    )
    # Unknown status fails schema validation.
    assert (
        client.patch(f"/api/referrals/{ref}/status", json={"status": "archived"}).status_code
        == 422
    )
    # Audit log still shows only the creation event.
    history = client.get(f"/api/referrals/{ref}").json()["status_history"]
    assert len(history) == 1


def test_status_history_persists_across_reads(client):
    assessment = create_assessment(client, **CASE_EMERGENCY)
    ref = client.post(
        "/api/referrals", json={"assessment_id": assessment["id"]}
    ).json()["referral_id"]
    client.patch(
        f"/api/referrals/{ref}/status",
        json={"status": "referred", "note": "ambulance dispatched"},
    )
    detail = client.get(f"/api/referrals/{ref}").json()
    assert detail["status"] == "referred"
    assert detail["updated_at"] >= detail["created_at"]
    event = detail["status_history"][-1]
    assert event["from_status"] == "pending"
    assert event["to_status"] == "referred"
    assert event["note"] == "ambulance dispatched"
    assert event["changed_by"] == "clinic_staff"


def test_referral_ids_are_unique(client):
    first = create_assessment(client, **CASE_URGENT)
    second = create_assessment(
        client, **{"vitals": {"oxygen_saturation": 91}, "patient_id": "SYN-REF-5"}
    )
    ids = set()
    for assessment in (first, second):
        created = client.post(
            "/api/referrals", json={"assessment_id": assessment["id"]}
        ).json()
        ids.add(created["referral_id"])
    assert len(ids) == 2
