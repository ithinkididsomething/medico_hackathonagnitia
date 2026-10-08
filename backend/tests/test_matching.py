"""Capability matching scenarios (Parts 1, 3, 4, 6) — unit level.

Covers every scenario required by the prompt:
  - hospital with missing specialty          -> excluded
  - hospital without required ICU            -> excluded
  - hospital with insufficient capacity      -> excluded
  - fully suitable hospital                  -> best match with factor breakdown
  - multiple suitable hospitals              -> ranked alternatives
  - no suitable hospital                     -> best_match None + explanation
  - fallback when the top hospital is unavailable in the simulated feed
and verifies that every result explains itself.
"""
from app.matching import (
    DEFAULT_CLINIC,
    DEFAULT_WEIGHTS,
    Hospital,
    WeightError,
    assess_clinic_capability,
    check_eligibility,
    derive_requirements,
    match_hospitals,
    missing_capabilities_of,
    score_hospital,
    synthetic_hospitals,
)
from app.rules import classify_urgency, decide

CLINIC_LOCATION = (23.2599, 77.4126)


def hospital(**overrides) -> Hospital:
    """Minimal fully-capable hospital; override fields per scenario."""
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
    """Requirements for a RED chest-pain case (cardiology + ICU + full ER)."""
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


# --------------------------------------------------------------------------- #
# Requirements derivation
# --------------------------------------------------------------------------- #
def test_requirements_red_case_needs_full_er_icu_and_specialty():
    req = emergency_requirements()
    assert req["required_specialty"] == "cardiology"  # keyword hint
    assert req["needs_emergency"] == "full"
    assert req["needs_icu"] is True
    assert "basic_labs" in req["required_diagnostics"]
    assert "ecg" in req["required_diagnostics"]
    assert "emergency_stabilization" in req["required_treatment"]
    assert "critical_care" in req["required_treatment"]  # added because ICU needed
    assert req["explanations"]


def test_requirements_orange_case_needs_basic_emergency():
    assessment = {
        "patient_id": "SYN-REQ2",
        "age_years": 40,
        "sex": "female",
        "chief_complaint": "Mild breathlessness",
        "emergency_indicator": False,
        "vitals": {
            "heart_rate": 118,
            "systolic_bp": 110,
            "diastolic_bp": 70,
            "respiratory_rate": 24,
            "oxygen_saturation": 92,
            "temperature_c": 37.2,
        },
        "known_specialty": None,
    }
    urgency = classify_urgency(assessment)
    assert urgency.level == "ORANGE"
    req = derive_requirements(assessment, urgency.level, urgency.score).to_dict()
    assert req["needs_emergency"] == "basic"
    assert req["needs_icu"] is False
    assert req["required_specialty"] == "internal_medicine"  # default fallback


def test_requirements_staff_specialty_overrides_keyword_hint():
    assessment = {
        "patient_id": "SYN-REQ3",
        "age_years": 50,
        "sex": "other",
        "chief_complaint": "Chest pain reported",
        "emergency_indicator": True,
        "vitals": {
            "heart_rate": 140,
            "systolic_bp": 88,
            "diastolic_bp": 48,
            "respiratory_rate": 32,
            "oxygen_saturation": 88,
            "temperature_c": 36.4,
        },
        "known_specialty": "neurology",
    }
    urgency = classify_urgency(assessment)
    req = derive_requirements(assessment, urgency.level, urgency.score).to_dict()
    assert req["required_specialty"] == "neurology"
    assert any("overrides" in text for text in req["explanations"])


# --------------------------------------------------------------------------- #
# Hard constraints (Part 3)
# --------------------------------------------------------------------------- #
def test_hospital_with_missing_specialty_is_excluded():
    h = hospital(specialties=["internal_medicine"])  # no cardiology
    req = emergency_requirements()

    reasons = check_eligibility(h, req)
    assert any("Required specialty not available" in r for r in reasons)
    assert "specialty:cardiology" in missing_capabilities_of(h, req)

    result = match_hospitals(req, [h], CLINIC_LOCATION)
    assert result["best_match"] is None
    assert result["excluded"][0]["exclusion_reasons"] == reasons


def test_hospital_without_required_icu_is_excluded():
    h = hospital(icu_capability="none")
    req = emergency_requirements()

    reasons = check_eligibility(h, req)
    assert any("ICU required" in r for r in reasons)
    assert "icu" in missing_capabilities_of(h, req)

    result = match_hospitals(req, [h], CLINIC_LOCATION)
    assert result["best_match"] is None


def test_hospital_with_insufficient_capacity_is_excluded():
    full = hospital(hospital_id="T-FULL", capacity_status="full", available_beds=0)
    few = hospital(hospital_id="T-FEW", available_beds=0)

    for h in (full, few):
        reasons = check_eligibility(h, emergency_requirements())
        assert any("capacity" in r.lower() for r in reasons), reasons


def test_diverting_hospital_is_excluded():
    h = hospital(availability_status="diverting")
    reasons = check_eligibility(h, emergency_requirements())
    assert any("availability status" in r for r in reasons)


def test_missing_diagnostic_and_treatment_are_excluded():
    h = hospital(diagnostics=["basic_labs"], treatment_capabilities=["emergency_stabilization"])
    # emergency_stabilization present but critical_care missing (ICU required)
    req = emergency_requirements()
    reasons = check_eligibility(h, req)
    assert any("critical care" in r.lower() for r in reasons), reasons
    missing = missing_capabilities_of(h, req)
    assert "treatment:critical_care" in missing


# --------------------------------------------------------------------------- #
# Scoring (Part 4)
# --------------------------------------------------------------------------- #
def test_fully_suitable_hospital_scores_high_with_full_breakdown():
    h = hospital()
    req = emergency_requirements()
    result = match_hospitals(req, [h], CLINIC_LOCATION)

    best = result["best_match"]
    assert best is not None and best["eligible"] is True
    assert best["total_score"] >= 95
    assert best["missing_capabilities"] == []
    assert best["exclusion_reasons"] == []
    # Every applicable factor is present with earned/possible/reason.
    assert set(best["factor_scores"]) >= {
        "specialty_match",
        "emergency_capability",
        "icu_capability",
        "diagnostics_match",
        "treatment_match",
        "capacity",
        "distance",
    }
    for factor in best["factor_scores"].values():
        assert factor["reason"], "every factor must explain itself"
        assert 0 <= factor["earned"] <= factor["possible"]
    assert best["reasons"] and all("+ " in r or "(+" in r for r in best["reasons"])
    assert "not simply proximity" in best["explanation"]
    assert best["travel"]["distance_km"] >= 0
    assert "Placeholder" in best["travel"]["note"]


def test_score_is_normalised_over_applicable_factors():
    # GREEN routine case: no emergency/ICU/diagnostic/treatment factors apply.
    assessment = {
        "patient_id": "SYN-GREEN",
        "age_years": 30,
        "sex": "female",
        "chief_complaint": "Mild headache",
        "emergency_indicator": False,
        "vitals": {
            "heart_rate": 72,
            "systolic_bp": 118,
            "diastolic_bp": 76,
            "respiratory_rate": 15,
            "oxygen_saturation": 99,
            "temperature_c": 36.7,
        },
        "known_specialty": None,
    }
    urgency = classify_urgency(assessment)
    assert urgency.level == "GREEN"
    req = derive_requirements(assessment, urgency.level).to_dict()
    scored = score_hospital(hospital(), req, CLINIC_LOCATION)
    assert set(scored["factor_scores"]) == {
        "specialty_match",
        "capacity",
        "distance",
        "travel_time",
    }
    assert scored["total_score"] >= 90  # only light distance decay


def test_weights_are_configurable():
    # Limited ICU gives the ICU factor a partial (0.5) ratio, so changing its
    # weight visibly moves the normalised total.
    h = hospital(icu_capability="limited")
    req = emergency_requirements()
    default = match_hospitals(req, [h], CLINIC_LOCATION)["best_match"]["total_score"]
    icu_heavy = match_hospitals(
        req, [h], CLINIC_LOCATION, weights={"icu_capability": 80.0}
    )["best_match"]["total_score"]
    icu_zero = match_hospitals(
        req, [h], CLINIC_LOCATION, weights={"icu_capability": 0.0}
    )["best_match"]["total_score"]
    assert icu_heavy < default < icu_zero
    # Distance can be switched off entirely (placeholder factor).
    no_distance = match_hospitals(
        req, [h], CLINIC_LOCATION, weights={"distance": 0.0}
    )["best_match"]["total_score"]
    assert 0 < no_distance <= 100


def test_invalid_weights_rejected():
    try:
        match_hospitals(emergency_requirements(), [hospital()], weights={"bogus": 5})
    except WeightError:
        pass
    else:
        raise AssertionError("expected WeightError for unknown factor")
    try:
        match_hospitals(emergency_requirements(), [hospital()], weights={"capacity": -1})
    except WeightError:
        pass
    else:
        raise AssertionError("expected WeightError for negative weight")


# --------------------------------------------------------------------------- #
# Ranking + alternatives (multiple suitable hospitals)
# --------------------------------------------------------------------------- #
def test_multiple_suitable_hospitals_ranked_with_alternatives():
    near = hospital(hospital_id="T-NEAR", name="Near Hospital", available_beds=12)
    far = hospital(
        hospital_id="T-FAR",
        name="Far Hospital",
        latitude=23.15,
        longitude=77.30,
        available_beds=12,
    )
    result = match_hospitals(emergency_requirements(), [far, near], CLINIC_LOCATION)

    assert result["eligible_count"] == 2
    assert result["best_match"]["hospital"]["hospital_id"] == "T-NEAR"
    assert len(result["alternatives"]) == 1
    assert result["alternatives"][0]["hospital"]["hospital_id"] == "T-FAR"
    assert result["best_match"]["total_score"] > result["alternatives"][0]["total_score"]
    # Both still explain themselves.
    assert result["alternatives"][0]["reasons"]
    assert "alternative suitable hospital" in result["summary_explanation"]


def test_tie_broken_deterministically_by_hospital_id():
    a = hospital(hospital_id="T-A", name="A")
    b = hospital(hospital_id="T-B", name="B")
    result = match_hospitals(emergency_requirements(), [b, a], CLINIC_LOCATION)
    assert result["best_match"]["hospital"]["hospital_id"] == "T-A"


# --------------------------------------------------------------------------- #
# No suitable hospital
# --------------------------------------------------------------------------- #
def test_no_suitable_hospital_explains_itself():
    weak = hospital(
        specialties=["pediatrics"],
        emergency_capability="none",
        icu_capability="none",
        diagnostics=[],
        treatment_capabilities=[],
    )
    result = match_hospitals(emergency_requirements(), [weak], CLINIC_LOCATION)

    assert result["best_match"] is None
    assert result["alternatives"] == []
    assert result["eligible_count"] == 0
    assert result["excluded_count"] == 1
    assert "No hospital passed the hard capability constraints" in result["summary_explanation"]
    excluded = result["excluded"][0]
    assert excluded["exclusion_reasons"]
    assert excluded["missing_capabilities"]
    assert "not suitable" in excluded["explanation"]


# --------------------------------------------------------------------------- #
# Fallback (Part 6)
# --------------------------------------------------------------------------- #
def test_fallback_selects_next_eligible_when_top_is_unavailable():
    best = hospital(hospital_id="T-BEST", name="Best Hospital", available_beds=12)
    second = hospital(
        hospital_id="T-SECOND",
        name="Second Hospital",
        latitude=23.20,
        longitude=77.35,
        available_beds=9,
    )
    result = match_hospitals(
        emergency_requirements(),
        [best, second],
        CLINIC_LOCATION,
        unavailable_ids=["T-BEST"],
    )

    assert result["fallback_used"] is True
    assert result["best_match"]["hospital"]["hospital_id"] == "T-SECOND"
    assert "Best Hospital" in result["fallback_note"]
    assert "Next eligible" in result["fallback_note"] or "next eligible" in result["fallback_note"]
    assert "Fallback applied" in result["summary_explanation"]
    # The unavailable hospital is still listed as excluded with a clear reason.
    outage = [e for e in result["excluded"] if e["hospital"]["hospital_id"] == "T-BEST"]
    assert outage and "simulated capacity feed" in outage[0]["exclusion_reasons"][0]


def test_no_fallback_flag_when_top_is_available():
    best = hospital(hospital_id="T-BEST", name="Best Hospital")
    second = hospital(hospital_id="T-SECOND", name="Second Hospital", latitude=23.20, longitude=77.35)
    result = match_hospitals(
        emergency_requirements(), [best, second], CLINIC_LOCATION, unavailable_ids=["T-SECOND"]
    )
    assert result["fallback_used"] is False
    assert result["best_match"]["hospital"]["hospital_id"] == "T-BEST"


def test_synthetic_catalogue_passes_expected_shapes():
    hospitals = synthetic_hospitals()
    assert len(hospitals) == 6
    assert all(h.is_synthetic for h in hospitals)
    assert all("synthetic" in h.data_note.lower() for h in hospitals)


# --------------------------------------------------------------------------- #
# Clinic capability + decision flip (Part 1)
# --------------------------------------------------------------------------- #
def test_default_clinic_manages_routine_case():
    assessment = {
        "patient_id": "SYN-CLINIC-1",
        "age_years": 25,
        "sex": "female",
        "chief_complaint": "Mild cold symptoms",
        "emergency_indicator": False,
        "vitals": {
            "heart_rate": 70,
            "systolic_bp": 115,
            "diastolic_bp": 74,
            "respiratory_rate": 14,
            "oxygen_saturation": 99,
            "temperature_c": 36.6,
        },
        "known_specialty": None,
    }
    urgency = classify_urgency(assessment)
    req = derive_requirements(assessment, urgency.level).to_dict()
    capability = assess_clinic_capability(req, DEFAULT_CLINIC)

    assert capability["can_manage_locally"] is True
    assert capability["missing_capabilities"] == []
    assert any("covered" in r for r in capability["reasons"])
    decision = decide(urgency.level, context={"clinic_capability": capability})
    assert decision["code"] == "manage_locally"


def test_clinic_without_capability_flips_routine_case_to_referral():
    stripped = dict(DEFAULT_CLINIC)
    stripped["capabilities"] = []  # no resources at all
    stripped["specialties"] = []

    assessment = {
        "patient_id": "SYN-CLINIC-2",
        "age_years": 25,
        "sex": "female",
        "chief_complaint": "Mild cold symptoms",
        "emergency_indicator": False,
        "vitals": {
            "heart_rate": 70,
            "systolic_bp": 115,
            "diastolic_bp": 74,
            "respiratory_rate": 14,
            "oxygen_saturation": 99,
            "temperature_c": 36.6,
        },
        "known_specialty": None,
    }
    urgency = classify_urgency(assessment)
    assert urgency.level == "GREEN"
    req = derive_requirements(assessment, urgency.level).to_dict()
    capability = assess_clinic_capability(req, stripped)

    assert capability["can_manage_locally"] is False
    assert capability["missing_capabilities"]  # internal medicine + (none emergency)
    decision = decide(urgency.level, context={"clinic_capability": capability})
    assert decision["code"] == "referral_recommended"
    assert "do not cover" in decision["note"]
    assert any(m in decision["note"] for m in capability["missing_capabilities"])


def test_emergency_case_always_refers_even_if_clinic_is_fully_capable():
    rich_clinic = dict(DEFAULT_CLINIC)
    rich_clinic["capabilities"] = [
        "emergency_stabilization",
        "icu",
        "basic_diagnostics",
        "imaging",
        "laboratory",
        "surgery",
        "dialysis",
        "specialist_consultation",
    ]
    rich_clinic["specialties"] = ["internal_medicine", "cardiology", "emergency_medicine"]
    req = emergency_requirements()
    capability = assess_clinic_capability(req, rich_clinic)
    assert capability["can_manage_locally"] is True
    decision = decide("RED", context={"clinic_capability": capability})
    assert decision["code"] == "immediate_referral"
