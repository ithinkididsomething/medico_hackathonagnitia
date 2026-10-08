"""Prompt 3: routing, travel-aware ranking, fallback and explanations.

Required scenarios:
  1. successful routing                       -> osrm source + geometry
  2. routing failure                          -> graceful placeholder fallback
  3. multiple hospitals                       -> ranked list with alternatives
  4. nearest hospital lacking capability      -> excluded despite proximity
  5. eligible farther hospital, better match  -> capability outranks distance
  6. primary hospital becoming unavailable    -> fallback triggered
  7. fallback selection                       -> next-best + why-not + detail
  8. no eligible hospital                     -> best_match None + explanation
Plus: clinic location configuration, POST /api/route, and schema back-compat.
"""
import pytest

from app.api.routes import reset_clinic
from app.api.schemas import TravelEstimateOut
from app.maps import MapsServiceError
from app.maps.travel import (
    OSRM_ROUTING_NOTE,
    PLACEHOLDER_NOTE,
    TravelEstimator,
    thin_coordinates,
)
from app.matching import (
    Hospital,
    derive_requirements,
    match_hospitals,
    score_hospital,
)
from app.rules import classify_urgency

CLINIC_LOCATION = (23.2599, 77.4126)


@pytest.fixture(autouse=True)
def _clean_clinic_override():
    reset_clinic()
    yield
    reset_clinic()


def hospital(**overrides) -> Hospital:
    base = {
        "hospital_id": "T-HOSP",
        "name": "Test Hospital",
        "latitude": 23.26,
        "longitude": 77.41,
        "specialties": ["internal_medicine", "cardiology"],
        "emergency_capability": "full",
        "icu_capability": "available",
        "diagnostics": ["basic_labs", "ecg"],
        "treatment_capabilities": ["emergency_stabilization", "critical_care"],
        "capacity_status": "open",
        "available_beds": 10,
        "availability_status": "open",
    }
    base.update(overrides)
    return Hospital(**base)


def emergency_requirements(**overrides):
    assessment = {
        "patient_id": "SYN-REQ",
        "age_years": 60,
        "sex": "male",
        "chief_complaint": "Severe chest pain and collapse",
        "emergency_indicator": True,
        "vitals": {
            "heart_rate": 150,
            "systolic_bp": 86,
            "diastolic_bp": 45,
            "respiratory_rate": 33,
            "oxygen_saturation": 87,
            "temperature_c": 36.0,
        },
        "known_specialty": None,
    }
    urgency = classify_urgency(assessment)
    requirements = derive_requirements(assessment, urgency.level, urgency.score)
    data = requirements.to_dict()
    data.update(overrides)
    return data


def fake_route(origin, destination, profile=None):
    """Deterministic stand-in for the OSRM provider."""
    return {
        "distance_km": 4.2,
        "duration_minutes": 11.5,
        "geometry": {"type": "LineString", "coordinates": [[77.41, 23.26], [77.415, 23.2605]]},
        "coordinates": [
            {"latitude": 23.26, "longitude": 77.41},
            {"latitude": 23.2605, "longitude": 77.415},
        ],
    }


def failing_route(origin, destination, profile=None):
    raise MapsServiceError("Routing request failed: connection refused")


# --------------------------------------------------------------------------- #
# TravelEstimator (Part 2)
# --------------------------------------------------------------------------- #
def test_travel_estimator_successful_routing():
    estimator = TravelEstimator(CLINIC_LOCATION, route_fn=fake_route)
    result = estimator.estimate((23.2605, 77.415))

    assert result["source"] == "osrm"
    assert result["distance_km"] == 4.2
    assert result["travel_minutes"] == 11.5
    assert result["note"] == OSRM_ROUTING_NOTE
    assert result["route_coordinates"] and result["route_coordinates"][0]["latitude"] == 23.26
    assert estimator.routing_attempted == 1
    assert estimator.routing_failures == 0


def test_travel_estimator_routing_failure_falls_back_gracefully():
    estimator = TravelEstimator(CLINIC_LOCATION, route_fn=failing_route)
    result = estimator.estimate((23.2605, 77.415))

    assert result["source"] == "placeholder"
    assert "Placeholder" in result["note"]
    assert "routing unavailable" in result["note"]
    assert result["distance_km"] > 0  # straight-line distance still estimated
    assert result["travel_minutes"] > 0
    assert result["route_coordinates"] is None
    assert estimator.routing_failures == 1


def test_travel_estimator_missing_destination_returns_none():
    estimator = TravelEstimator(CLINIC_LOCATION, route_fn=fake_route)
    assert estimator.estimate(None) is None


def test_travel_estimator_disabled_by_configuration(monkeypatch):
    monkeypatch.setenv("ROUTING_ENABLED", "false")
    estimator = TravelEstimator(CLINIC_LOCATION)  # no custom route_fn
    result = estimator.estimate((23.2605, 77.415))
    assert result["source"] == "placeholder"
    assert "routing disabled" in result["note"]
    assert result["distance_km"] > 0


def test_travel_estimator_estimate_many():
    estimator = TravelEstimator(CLINIC_LOCATION, route_fn=fake_route)
    results = estimator.estimate_many(
        {"A": (23.2605, 77.415), "B": None, "C": (23.235, 77.401)}
    )
    assert set(results) == {"A", "C"}  # B had no coordinates -> skipped
    assert all(r["source"] == "osrm" for r in results.values())


def test_thin_coordinates_caps_payload_size():
    coords = [{"latitude": float(i), "longitude": float(i)} for i in range(500)]
    thinned = thin_coordinates(coords, limit=60)
    assert len(thinned) == 60
    assert thin_coordinates([]) is None
    short = [{"latitude": 1.0, "longitude": 2.0}] * 3
    assert len(thin_coordinates(short)) == 3


# --------------------------------------------------------------------------- #
# Travel-aware scoring (Part 4)
# --------------------------------------------------------------------------- #
def test_scoring_uses_real_routing_travel_information():
    travel = {
        "distance_km": 12.0,
        "travel_minutes": 28.0,
        "source": "osrm",
        "note": OSRM_ROUTING_NOTE,
        "route_coordinates": None,
    }
    scored = score_hospital(
        hospital(), emergency_requirements(), CLINIC_LOCATION, travel_info=travel
    )
    assert scored["travel"]["source"] == "osrm"
    assert scored["travel"]["travel_minutes"] == 28.0
    distance_factor = scored["factor_scores"]["distance"]
    travel_factor = scored["factor_scores"]["travel_time"]
    assert "Road distance" in distance_factor["reason"]
    assert "Estimated travel time" in travel_factor["reason"]
    # 12 km of 50 km reference -> 0.76 ratio; 28 min of 90 -> ~0.689 ratio.
    assert 0 < distance_factor["earned"] < distance_factor["possible"]
    assert 0 < travel_factor["earned"] < travel_factor["possible"]


def test_capability_outranks_proximity_farther_better_match_wins():
    # NEAR hospital: close but only 'limited' ICU and fewer beds.
    near = hospital(
        hospital_id="T-NEAR",
        name="Near But Weaker",
        latitude=23.2605,
        longitude=77.4135,  # ~0.1 km away
        icu_capability="limited",
        available_beds=2,
        capacity_status="limited",
    )
    # FAR hospital: clinically better matched (full ICU, more capacity).
    far = hospital(
        hospital_id="T-FAR",
        name="Far But Complete",
        latitude=23.20,
        longitude=77.35,  # ~10 km away
        icu_capability="available",
        available_beds=14,
    )
    travel_lookup = {
        "T-NEAR": {
            "distance_km": 0.1,
            "travel_minutes": 1.0,
            "source": "osrm",
            "note": OSRM_ROUTING_NOTE,
            "route_coordinates": None,
        },
        "T-FAR": {
            "distance_km": 10.5,
            "travel_minutes": 24.0,
            "source": "osrm",
            "note": OSRM_ROUTING_NOTE,
            "route_coordinates": None,
        },
    }
    result = match_hospitals(
        emergency_requirements(),
        [near, far],
        CLINIC_LOCATION,
        travel_lookup=travel_lookup,
    )
    assert result["best_match"]["hospital"]["hospital_id"] == "T-FAR"
    # Why-not is generated from the scoring data, mentioning capability -
    # even though the recommended hospital is MUCH farther away.
    why_not = result["alternatives"][0]["why_not"]
    assert any("ICU capability scores lower" in r for r in why_not)
    assert any("Simulated capacity scores lower" in r for r in why_not)
    assert not any("Longer estimated travel time" in r for r in why_not)


def test_nearest_hospital_lacking_capability_is_still_excluded():
    # The closest hospital of all, but no cardiology/ICU -> hard constraint.
    nearest = hospital(
        hospital_id="T-CLOSEST",
        name="Closest Clinic Hospital",
        latitude=23.25995,
        longitude=77.41265,  # essentially at the clinic
        specialties=["internal_medicine"],
        icu_capability="none",
        emergency_capability="basic",
        diagnostics=["basic_labs"],
        treatment_capabilities=["emergency_stabilization"],
    )
    capable_far = hospital(
        hospital_id="T-CAPABLE",
        name="Capable Far Hospital",
        latitude=23.15,
        longitude=77.30,
    )
    travel_lookup = {
        "T-CLOSEST": {
            "distance_km": 0.01,
            "travel_minutes": 0.5,
            "source": "osrm",
            "note": OSRM_ROUTING_NOTE,
            "route_coordinates": None,
        },
        "T-CAPABLE": {
            "distance_km": 18.4,
            "travel_minutes": 40.0,
            "source": "osrm",
            "note": OSRM_ROUTING_NOTE,
            "route_coordinates": None,
        },
    }
    result = match_hospitals(
        emergency_requirements(),
        [nearest, capable_far],
        CLINIC_LOCATION,
        travel_lookup=travel_lookup,
    )
    assert result["best_match"]["hospital"]["hospital_id"] == "T-CAPABLE"
    excluded_ids = [e["hospital"]["hospital_id"] for e in result["excluded"]]
    assert "T-CLOSEST" in excluded_ids
    closest = result["excluded"][0]
    assert any("Required specialty not available" in r for r in closest["why_not"])
    assert any("ICU required" in r for r in closest["why_not"])


def test_travel_lookup_missing_entry_uses_placeholder():
    h = hospital()
    scored = score_hospital(h, emergency_requirements(), CLINIC_LOCATION)
    assert scored["travel"]["source"] == "placeholder"
    assert "Placeholder" in scored["travel"]["note"]


# --------------------------------------------------------------------------- #
# Ranking + fallback with travel data (Parts 5-6)
# --------------------------------------------------------------------------- #
def test_multiple_hospitals_ranked_with_travel_and_why_not():
    best = hospital(hospital_id="T-BEST", name="Best Hospital", available_beds=12)
    second = hospital(
        hospital_id="T-SECOND",
        name="Second Hospital",
        latitude=23.20,
        longitude=77.35,
        icu_capability="limited",
        available_beds=8,
    )
    travel_lookup = {
        "T-BEST": {
            "distance_km": 3.0,
            "travel_minutes": 9.0,
            "source": "osrm",
            "note": OSRM_ROUTING_NOTE,
            "route_coordinates": [{"latitude": 23.26, "longitude": 77.41}],
        },
        "T-SECOND": {
            "distance_km": 9.4,
            "travel_minutes": 22.0,
            "source": "osrm",
            "note": OSRM_ROUTING_NOTE,
            "route_coordinates": None,
        },
    }
    result = match_hospitals(
        emergency_requirements(),
        [second, best],
        CLINIC_LOCATION,
        travel_lookup=travel_lookup,
    )
    assert result["best_match"]["hospital"]["hospital_id"] == "T-BEST"
    assert result["best_match"]["travel"]["route_coordinates"]  # geometry for the map
    assert result["travel_estimate_note"] == OSRM_ROUTING_NOTE
    assert result["clinic_location"] == {
        "latitude": CLINIC_LOCATION[0],
        "longitude": CLINIC_LOCATION[1],
    }
    alt = result["alternatives"][0]
    assert alt["why_not"]
    assert any("scores lower" in r for r in alt["why_not"])
    assert any("Longer estimated travel time" in r for r in alt["why_not"])
    assert result["best_match"]["why_not"] == []


def test_primary_unavailable_triggers_fallback_with_detail():
    best = hospital(hospital_id="T-BEST", name="Best Hospital", available_beds=12)
    second = hospital(
        hospital_id="T-SECOND",
        name="Second Hospital",
        latitude=23.20,
        longitude=77.35,
        available_beds=9,
    )
    travel_lookup = {
        "T-BEST": {
            "distance_km": 3.0,
            "travel_minutes": 9.0,
            "source": "osrm",
            "note": OSRM_ROUTING_NOTE,
            "route_coordinates": None,
        },
        "T-SECOND": {
            "distance_km": 9.4,
            "travel_minutes": 22.0,
            "source": "osrm",
            "note": OSRM_ROUTING_NOTE,
            "route_coordinates": None,
        },
    }
    result = match_hospitals(
        emergency_requirements(),
        [best, second],
        CLINIC_LOCATION,
        unavailable_ids=["T-BEST"],
        travel_lookup=travel_lookup,
    )
    assert result["fallback_used"] is True
    assert result["best_match"]["hospital"]["hospital_id"] == "T-SECOND"
    detail = result["fallback_detail"]
    assert detail["primary_name"] == "Best Hospital"
    assert "Unavailable" in detail["primary_status"]
    assert detail["fallback_name"] == "Second Hospital"
    assert "next-best combined capability/travel score" in detail["reason"]
    assert "Cardiology" in detail["reason"] or "cardiology" in detail["reason"].lower()
    assert "Best Hospital" in result["fallback_note"]
    assert result["alternatives"] == []  # only one eligible after the outage
    # Route data for the fallback selection is still provided.
    assert result["best_match"]["travel"]["source"] == "osrm"


def test_no_eligible_hospital_with_travel_lookup():
    weak = hospital(
        specialties=["pediatrics"],
        emergency_capability="none",
        icu_capability="none",
        diagnostics=[],
        treatment_capabilities=[],
    )
    result = match_hospitals(
        emergency_requirements(),
        [weak],
        CLINIC_LOCATION,
        travel_lookup={
            "T-HOSP": {
                "distance_km": 1.0,
                "travel_minutes": 3.0,
                "source": "osrm",
                "note": OSRM_ROUTING_NOTE,
                "route_coordinates": None,
            }
        },
    )
    assert result["best_match"] is None
    assert "No hospital passed the hard capability constraints" in result["summary_explanation"]
    assert result["excluded"][0]["why_not"]  # exclusion reasons double as why-not


def test_excluded_hospitals_have_generated_why_not():
    weak = hospital(
        hospital_id="T-WEAK",
        name="Weak Hospital",
        specialties=["internal_medicine"],  # no cardiology
        icu_capability="none",
    )
    strong = hospital(hospital_id="T-STRONG", name="Strong Hospital")
    result = match_hospitals(
        emergency_requirements(), [weak, strong], CLINIC_LOCATION
    )
    excluded = result["excluded"][0]
    assert excluded["why_not"] == excluded["exclusion_reasons"]
    assert any("Required specialty not available" in r for r in excluded["why_not"])


# --------------------------------------------------------------------------- #
# Clinic location configuration (Part 3)
# --------------------------------------------------------------------------- #
def test_clinic_location_env_override(monkeypatch):
    monkeypatch.setenv("CLINIC_LATITUDE", "28.6139")
    monkeypatch.setenv("CLINIC_LONGITUDE", "77.2090")
    from app.matching import default_clinic

    clinic = default_clinic()
    assert clinic["latitude"] == 28.6139
    assert clinic["longitude"] == 77.2090


def test_assess_clinic_capability_exposes_coordinates():
    from app.matching import DEFAULT_CLINIC, assess_clinic_capability

    result = assess_clinic_capability(
        {"required_specialty": "internal_medicine"}, DEFAULT_CLINIC
    )
    assert result["clinic"]["latitude"] == DEFAULT_CLINIC["latitude"]
    assert result["clinic"]["longitude"] == DEFAULT_CLINIC["longitude"]


# --------------------------------------------------------------------------- #
# API: route endpoint + clinic location + travel-aware match (Parts 2-4)
# --------------------------------------------------------------------------- #
def test_route_endpoint_successful(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.get_route", fake_route)
    response = client.post(
        "/api/route",
        json={
            "origin": {"latitude": 23.2599, "longitude": 77.4126},
            "destination": {"latitude": 23.2605, "longitude": 77.415},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["distance_km"] == 4.2
    assert body["duration_minutes"] == 11.5
    assert body["source"] == "osrm"
    assert body["coordinates"]


def test_route_endpoint_routing_failure_returns_502(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.get_route", failing_route)
    response = client.post(
        "/api/route",
        json={
            "origin": {"latitude": 23.2599, "longitude": 77.4126},
            "destination": {"latitude": 23.2605, "longitude": 77.415},
        },
    )
    assert response.status_code == 502
    assert "Routing request failed" in response.json()["detail"]


def test_route_endpoint_rejects_missing_coordinates(client):
    response = client.post(
        "/api/route",
        json={"origin": {"latitude": 23.2599}, "destination": {"latitude": 23.26}},
    )
    assert response.status_code == 422


def test_clinic_patch_updates_location_and_match_uses_it(client, monkeypatch):
    monkeypatch.setenv("ROUTING_ENABLED", "true")
    monkeypatch.setattr("app.maps.travel.get_route", fake_route)

    patched = client.patch(
        "/api/clinics/current",
        json={"latitude": 23.2350, "longitude": 77.4010},
    )
    assert patched.status_code == 200
    profile = client.get("/api/clinics/current").json()
    assert profile["latitude"] == 23.2350
    assert profile["longitude"] == 77.4010

    body = client.post(
        "/api/referrals/match",
        json={
            "assessment": {
                "patient_id": "SYN-LOC",
                "age_years": 55,
                "sex": "other",
                "chief_complaint": "Severe chest pain",
                "emergency_indicator": True,
                "vitals": {
                    "heart_rate": 150,
                    "systolic_bp": 86,
                    "diastolic_bp": 45,
                    "respiratory_rate": 32,
                    "oxygen_saturation": 87,
                    "temperature_c": 35.8,
                },
            }
        },
    ).json()
    assert body["clinic_location"] == {"latitude": 23.2350, "longitude": 77.4010}
    best = body["best_match"]
    assert best["travel"]["source"] == "osrm"  # provider was patched + enabled
    assert best["travel"]["distance_km"] == 4.2
    assert body["travel_estimate_note"] == OSRM_ROUTING_NOTE


def test_api_match_uses_fresh_routes_for_fallback_selection(client, monkeypatch):
    calls = []

    def counting_route(origin, destination, profile=None):
        calls.append((origin, destination))
        return fake_route(origin, destination, profile)

    monkeypatch.setenv("ROUTING_ENABLED", "true")
    monkeypatch.setattr("app.maps.travel.get_route", counting_route)

    body = client.post(
        "/api/referrals/match",
        json={
            "assessment": {
                "patient_id": "SYN-FB",
                "age_years": 55,
                "sex": "other",
                "chief_complaint": "Severe chest pain",
                "emergency_indicator": True,
                "vitals": {
                    "heart_rate": 150,
                    "systolic_bp": 86,
                    "diastolic_bp": 45,
                    "respiratory_rate": 32,
                    "oxygen_saturation": 87,
                    "temperature_c": 35.8,
                },
            },
            "unavailable_hospital_ids": ["SYN-HOSP-01"],
        },
    ).json()
    assert body["fallback_used"] is True
    assert body["best_match"]["hospital"]["hospital_id"] == "SYN-HOSP-02"
    assert "City General Hospital" in body["fallback_detail"]["primary_name"]
    assert "next-best combined capability/travel score" in body["fallback_detail"]["reason"]
    assert len(calls) >= 5  # a route was requested for every located hospital


def test_maps_config_reports_routing_state(client):
    body = client.get("/api/maps/config").json()
    assert body["routing_enabled"] is False  # conftest disables live routing
    assert "tile_url" in body and "router_url" in body


# --------------------------------------------------------------------------- #
# Schema back-compat with stored Prompt-2 travel payloads
# --------------------------------------------------------------------------- #
def test_legacy_prompt2_travel_payload_still_validates():
    legacy = TravelEstimateOut(
        distance_km=0.3,
        travel_minutes_placeholder=0.7,
        note=PLACEHOLDER_NOTE,
    )
    assert legacy.travel_minutes is None
    assert legacy.source == "placeholder"
    assert legacy.route_coordinates is None
