"""Hospital capability matching, transparent scoring and fallback (Parts 3/4/6).

Pipeline:

    1. HARD CONSTRAINTS (`check_eligibility`) - a hospital that fails any of
       these is EXCLUDED from the ranking entirely (not merely ranked lower):
         - availability_status must be open (no diverting/closed hospitals),
         - simulated capacity must not be exhausted (capacity_status/beds),
         - required specialty must be offered,
         - required emergency level must be met,
         - ICU must exist when required ('limited' ICU scores lower but passes),
         - every required diagnostic and treatment must be available,
         - hospitals in `unavailable_ids` (simulated live outage) are excluded.
    2. TRAVEL ESTIMATION - road distance/travel time from the clinic via the
       routing provider abstraction (`maps.travel.TravelEstimator`); a
       straight-line placeholder is used whenever routing is unavailable.
    3. TRANSPARENT SCORING (`score_hospital`) - eligible hospitals earn points
       per configurable weight; every factor returns earned/possible/reason.
       Medical capability factors carry ~94 of the 100 weight points - travel
       proximity can only ever fine-tune between clinically suitable options.
    4. RANKING + FALLBACK (`match_hospitals`) - eligible hospitals sorted by
       score; if the would-be top hospital is in the simulated-unavailable set,
       eligibility is re-evaluated, scores/routes already computed for the
       remaining hospitals are reused, and the next eligible hospital is
       recommended with a full explanation (`fallback_detail`, `why_not`).

Score output: total_score (0-100, normalised over applicable factors),
per-factor breakdown, reasons (+points), missing capabilities, exclusions
with reasons, generated "why not" explanations, and a plain-language
recommendation explanation.

IMPORTANT: demonstration logic. "Suitability score" is a capability-match
score for the prototype, NOT a clinical quality rating of the hospital.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from ..maps.geo import haversine_km
from ..maps.travel import OSRM_ROUTING_NOTE, PLACEHOLDER_NOTE, PLACEHOLDER_SPEED_KMH
from .catalog import (
    SYNTHETIC_DATA_NOTE,
    Hospital,
    diagnostic_label,
    treatment_label,
)
from .clinic import specialty_label

WEIGHTS_DISCLAIMER = (
    "Scoring weights are configurable demonstration values. The score "
    "measures capability fit for this case - it is not a clinical quality "
    "ranking and not a distance-only ranking."
)

# Kept for backward compatibility with stored Prompt-2 results.
TRAVEL_PLACEHOLDER_NOTE = PLACEHOLDER_NOTE

# Configurable factor weights (sum need not be 100 - the total is normalised
# over the factors that actually apply). Medical capability dominates: the
# geographic factors (distance + travel_time) together hold at most 6 points
# by default, so proximity can never outrank a better-matched hospital.
DEFAULT_WEIGHTS: dict[str, float] = {
    "specialty_match": 25.0,
    "emergency_capability": 20.0,
    "icu_capability": 15.0,
    "diagnostics_match": 15.0,
    "treatment_match": 10.0,
    "capacity": 9.0,
    "distance": 3.0,
    "travel_time": 3.0,
}

FACTOR_LABELS: dict[str, str] = {
    "specialty_match": "Required specialty",
    "emergency_capability": "Emergency capability",
    "icu_capability": "ICU capability",
    "diagnostics_match": "Required diagnostics",
    "treatment_match": "Treatment capabilities",
    "capacity": "Simulated capacity",
    "distance": "Distance",
    "travel_time": "Estimated travel time",
}

_DISTANCE_REFERENCE_KM = 50.0  # distance score decays linearly to 0 here
_TRAVEL_TIME_REFERENCE_MIN = 90.0  # travel-time score decays to 0 here

TRAVEL_FACTORS = ("distance", "travel_time")


class WeightError(ValueError):
    """Raised for invalid scoring weights."""


def _validate_weights(weights: Mapping[str, float] | None) -> dict[str, float]:
    merged = dict(DEFAULT_WEIGHTS)
    if weights:
        unknown = set(weights) - set(DEFAULT_WEIGHTS)
        if unknown:
            raise WeightError(
                f"Unknown weight factor(s): {sorted(unknown)}. "
                f"Known: {sorted(DEFAULT_WEIGHTS)}"
            )
        for key, value in weights.items():
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise WeightError(f"Weight '{key}' must be numeric") from exc
            if number < 0:
                raise WeightError(f"Weight '{key}' must not be negative")
            merged[key] = number
    return merged


def _as_hospital(hospital: Hospital | Mapping[str, Any]) -> Hospital:
    return hospital if isinstance(hospital, Hospital) else Hospital.from_dict(hospital)


# --------------------------------------------------------------------------- #
# Part 3: HARD CONSTRAINTS
# --------------------------------------------------------------------------- #
def check_eligibility(
    hospital: Hospital | Mapping[str, Any],
    requirements: Mapping[str, Any],
    unavailable_ids: Iterable[str] | None = None,
) -> list[str]:
    """Return exclusion reasons ([] when the hospital passes all constraints)."""
    h = _as_hospital(hospital)
    reasons: list[str] = []

    blocked_ids = set(unavailable_ids or [])
    if h.hospital_id in blocked_ids:
        reasons.append(
            "Hospital marked unavailable in the simulated capacity feed."
        )

    if h.availability_status != "open":
        reasons.append(
            f"Hospital availability status is '{h.availability_status}' "
            "(not open for referrals)."
        )

    if h.capacity_status == "full" or h.available_beds <= 0:
        reasons.append(
            "Simulated capacity exhausted "
            f"(capacity status: {h.capacity_status}, beds: {h.available_beds})."
        )

    required_beds = int(requirements.get("required_beds") or 1)
    if h.available_beds > 0 and h.available_beds < required_beds:
        reasons.append(
            f"Insufficient simulated capacity: {h.available_beds} bed(s) available, "
            f"{required_beds} required."
        )

    required_specialty = requirements.get("required_specialty")
    if required_specialty and required_specialty not in h.specialties:
        reasons.append(
            f"Required specialty not available: "
            f"{specialty_label(str(required_specialty))}."
        )

    needs_emergency = str(requirements.get("needs_emergency") or "none")
    if needs_emergency == "full" and h.emergency_capability != "full":
        reasons.append(
            "Full emergency capability required, but this hospital has "
            f"'{h.emergency_capability}' emergency capability."
        )
    elif needs_emergency == "basic" and h.emergency_capability == "none":
        reasons.append(
            "Basic emergency capability required, but this hospital has none."
        )

    if requirements.get("needs_icu") and h.icu_capability == "none":
        reasons.append("ICU required, but this hospital has no ICU capability.")

    for code in requirements.get("required_diagnostics") or []:
        if code not in h.diagnostics:
            reasons.append(f"Required diagnostic not available: {diagnostic_label(str(code))}.")

    for code in requirements.get("required_treatment") or []:
        if code not in h.treatment_capabilities:
            reasons.append(
                f"Required treatment capability not available: {treatment_label(str(code))}."
            )

    return reasons


def missing_capabilities_of(
    hospital: Hospital | Mapping[str, Any],
    requirements: Mapping[str, Any],
) -> list[str]:
    """Machine-friendly ids of every requirement this hospital fails."""
    h = _as_hospital(hospital)
    missing: list[str] = []

    required_specialty = requirements.get("required_specialty")
    if required_specialty and required_specialty not in h.specialties:
        missing.append(f"specialty:{required_specialty}")

    needs_emergency = str(requirements.get("needs_emergency") or "none")
    if needs_emergency == "full" and h.emergency_capability != "full":
        missing.append("emergency:full")
    elif needs_emergency == "basic" and h.emergency_capability == "none":
        missing.append("emergency:basic")

    if requirements.get("needs_icu") and h.icu_capability == "none":
        missing.append("icu")

    for code in requirements.get("required_diagnostics") or []:
        if code not in h.diagnostics:
            missing.append(f"diagnostics:{code}")

    for code in requirements.get("required_treatment") or []:
        if code not in h.treatment_capabilities:
            missing.append(f"treatment:{code}")

    return missing


# --------------------------------------------------------------------------- #
# Part 4: TRAVEL + TRANSPARENT SCORING
# --------------------------------------------------------------------------- #
def _travel_payload(
    hospital: Hospital,
    clinic_location: tuple[float, float] | None,
    travel_info: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, float, str, float, str]:
    """Return (travel_payload, distance_ratio, distance_reason,
    travel_ratio, travel_reason)."""
    if clinic_location is None:
        note = "Clinic location unknown - travel factors skipped."
        return None, 0.0, note, 0.0, note

    if hospital.latitude is None or hospital.longitude is None:
        note = f"{hospital.name} has no coordinates - travel factors skipped."
        return None, 0.0, note, 0.0, note

    if travel_info is not None:
        distance_km = float(travel_info["distance_km"])
        travel_minutes = float(travel_info["travel_minutes"])
        source = str(travel_info.get("source") or "placeholder")
        note = str(travel_info.get("note") or PLACEHOLDER_NOTE)
        route_coordinates = travel_info.get("route_coordinates")
    else:
        distance_km = haversine_km(
            clinic_location, (hospital.latitude, hospital.longitude)
        )
        travel_minutes = distance_km / PLACEHOLDER_SPEED_KMH * 60.0
        source = "placeholder"
        note = PLACEHOLDER_NOTE
        route_coordinates = None

    distance_ratio = max(0.0, 1.0 - distance_km / _DISTANCE_REFERENCE_KM)
    travel_ratio = max(0.0, 1.0 - travel_minutes / _TRAVEL_TIME_REFERENCE_MIN)

    if source == "osrm":
        distance_reason = (
            f"Road distance from the clinic {distance_km:.1f} km (OSRM routing)."
        )
        travel_reason = (
            f"Estimated travel time {travel_minutes:.0f} min by road (OSRM routing)."
        )
    else:
        distance_reason = (
            f"Straight-line placeholder distance {distance_km:.1f} km "
            "(road routing unavailable)."
        )
        travel_reason = (
            f"Placeholder travel estimate {travel_minutes:.0f} min "
            f"at {PLACEHOLDER_SPEED_KMH:g} km/h (road routing unavailable)."
        )

    payload = {
        "distance_km": round(distance_km, 2),
        "travel_minutes": round(travel_minutes, 1),
        "source": source,
        "note": note,
        "route_coordinates": route_coordinates,
    }
    return payload, distance_ratio, distance_reason, travel_ratio, travel_reason


def score_hospital(
    hospital: Hospital | Mapping[str, Any],
    requirements: Mapping[str, Any],
    clinic_location: tuple[float, float] | None = None,
    weights: Mapping[str, float] | None = None,
    travel_info: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Score one ELIGIBLE hospital; returns breakdown + reasons + explanation.

    `travel_info` is a precomputed estimate (from TravelEstimator) with keys
    distance_km / travel_minutes / source / note / route_coordinates. When it
    is omitted, a straight-line placeholder estimate is computed locally.
    """
    h = _as_hospital(hospital)
    w = _validate_weights(weights)

    factors: dict[str, dict[str, Any]] = {}
    reasons: list[str] = []

    def add_factor(name: str, ratio: float, reason: str) -> None:
        possible = w[name]
        earned = round(possible * max(0.0, min(1.0, ratio)), 2)
        factors[name] = {
            "label": FACTOR_LABELS[name],
            "earned": earned,
            "possible": round(possible, 2),
            "reason": reason,
        }
        if possible > 0:
            reasons.append(f"{reason} (+{earned:g} of {possible:g})")

    # Required specialty.
    required_specialty = requirements.get("required_specialty")
    if required_specialty:
        add_factor(
            "specialty_match",
            1.0,
            f"Required specialty available ({specialty_label(str(required_specialty))}).",
        )

    # Emergency capability.
    needs_emergency = str(requirements.get("needs_emergency") or "none")
    if needs_emergency != "none":
        if h.emergency_capability == "full":
            ratio, note = 1.0, "full"
        else:
            ratio, note = 0.6, "basic"
        add_factor(
            "emergency_capability",
            ratio,
            f"Emergency capability meets the required '{needs_emergency}' level "
            f"(hospital: {note}).",
        )

    # ICU capability.
    if requirements.get("needs_icu"):
        ratio = {"available": 1.0, "limited": 0.5}.get(h.icu_capability, 0.0)
        add_factor(
            "icu_capability",
            ratio,
            f"ICU requirement met (hospital ICU: {h.icu_capability}).",
        )

    # Diagnostics (proportional to how many required diagnostics exist).
    required_diagnostics = list(requirements.get("required_diagnostics") or [])
    if required_diagnostics:
        matched = [c for c in required_diagnostics if c in h.diagnostics]
        add_factor(
            "diagnostics_match",
            len(matched) / len(required_diagnostics),
            f"Required diagnostics available: {len(matched)}/{len(required_diagnostics)}"
            + (f" ({', '.join(diagnostic_label(c) for c in matched)})." if matched else "."),
        )

    # Treatments (proportional).
    required_treatment = list(requirements.get("required_treatment") or [])
    if required_treatment:
        matched = [c for c in required_treatment if c in h.treatment_capabilities]
        add_factor(
            "treatment_match",
            len(matched) / len(required_treatment),
            f"Required treatment capabilities available: "
            f"{len(matched)}/{len(required_treatment)}"
            + (f" ({', '.join(treatment_label(c) for c in matched)})." if matched else "."),
        )

    # Simulated capacity (status + beds, both visible in the reason).
    capacity_ratio = {"open": 1.0, "limited": 0.6}.get(h.capacity_status, 0.0)
    beds_ratio = min(1.0, h.available_beds / 8.0)
    add_factor(
        "capacity",
        0.5 * capacity_ratio + 0.5 * beds_ratio,
        f"Simulated capacity: status '{h.capacity_status}', "
        f"{h.available_beds} bed(s) available.",
    )

    # Distance + estimated travel time (real routing when available).
    travel_payload, d_ratio, d_reason, t_ratio, t_reason = _travel_payload(
        h, clinic_location, travel_info
    )
    add_factor("distance", d_ratio, d_reason)
    add_factor("travel_time", t_ratio, t_reason)

    applicable = sum(f["possible"] for f in factors.values())
    earned_total = sum(f["earned"] for f in factors.values())
    total_score = round(100.0 * earned_total / applicable, 1) if applicable else 0.0

    if travel_payload and travel_payload["source"] == "osrm":
        travel_sentence = (
            f"Estimated travel from the clinic: {travel_payload['travel_minutes']:.0f} min "
            f"over {travel_payload['distance_km']:.1f} km by road."
        )
    elif travel_payload:
        travel_sentence = (
            f"Placeholder travel estimate: {travel_payload['travel_minutes']:.0f} min "
            f"over {travel_payload['distance_km']:.1f} km straight-line "
            "(road routing unavailable)."
        )
    else:
        travel_sentence = "Travel factors skipped (no clinic or hospital coordinates)."

    explanation = (
        f"{h.name} scores {total_score}/100 on capability fit for this case "
        f"({len(factors)} scoring factor(s) applicable). "
        f"Capacity: {h.capacity_status} with {h.available_beds} bed(s); "
        f"availability: {h.availability_status}. {travel_sentence} "
        "Selection is based on transparent capability scores, not simply proximity."
    )

    return {
        "hospital": h.to_dict(),
        "eligible": True,
        "total_score": total_score,
        "factor_scores": factors,
        "reasons": reasons,
        "missing_capabilities": [],
        "exclusion_reasons": [],
        "why_not": [],
        "travel": travel_payload,
        "explanation": explanation,
    }


# --------------------------------------------------------------------------- #
# Part 6: WHY-NOT + RANKING + FALLBACK
# --------------------------------------------------------------------------- #
def _why_not_reasons(
    best: Mapping[str, Any], candidate: Mapping[str, Any]
) -> list[str]:
    """Generate 'why not this hospital' reasons from actual scoring data."""
    reasons: list[str] = []
    best_factors = best.get("factor_scores") or {}
    cand_factors = candidate.get("factor_scores") or {}

    # Capability factors first - clinical fit outranks proximity.
    for name in (
        "specialty_match",
        "emergency_capability",
        "icu_capability",
        "diagnostics_match",
        "treatment_match",
        "capacity",
    ):
        cand = cand_factors.get(name)
        best_f = best_factors.get(name)
        if not cand or not best_f:
            continue
        if cand["earned"] < best_f["earned"]:
            reasons.append(
                f"{cand['label']} scores lower than the recommended hospital "
                f"({cand['earned']:g}/{cand['possible']:g} vs "
                f"{best_f['earned']:g}/{best_f['possible']:g})."
            )

    # Geographic factors - only fine-tuning between suitable options.
    cand_travel = candidate.get("travel") or {}
    best_travel = best.get("travel") or {}
    if cand_travel and best_travel:
        if (cand_travel.get("travel_minutes") or 0) > (
            best_travel.get("travel_minutes") or 0
        ):
            reasons.append(
                f"Longer estimated travel time "
                f"(~{cand_travel['travel_minutes']:.0f} min vs "
                f"~{best_travel['travel_minutes']:.0f} min for the recommended hospital)."
            )
        elif (cand_travel.get("distance_km") or 0) > (
            best_travel.get("distance_km") or 0
        ):
            reasons.append(
                f"Farther from the clinic "
                f"({cand_travel['distance_km']:.1f} km vs "
                f"{best_travel['distance_km']:.1f} km for the recommended hospital)."
            )

    if not reasons:
        reasons.append(
            "Scores lower overall than the recommended hospital "
            f"({candidate.get('total_score', 0):g}/100 vs "
            f"{best.get('total_score', 0):g}/100)."
        )
    reasons.append("Still a suitable alternative if the recommended hospital is unavailable.")
    return reasons


def _fallback_reason_sentence(
    best: Mapping[str, Any], requirements: Mapping[str, Any]
) -> str:
    """One sentence describing why the fallback hospital is a sound choice."""
    hospital = best["hospital"]
    bits: list[str] = []
    specialty = requirements.get("required_specialty")
    if specialty and specialty in hospital.get("specialties", []):
        bits.append(f"provides the required specialty ({specialty_label(str(specialty))})")
    if requirements.get("needs_icu") and hospital.get("icu_capability") != "none":
        bits.append(f"has ICU capability ({hospital['icu_capability']})")
    if str(requirements.get("needs_emergency") or "none") != "none":
        bits.append(
            f"meets the required emergency level ({hospital['emergency_capability']})"
        )
    capability_bits = ", ".join(bits) if bits else "meets the hard capability constraints"
    return (
        f"{hospital['name']} {capability_bits} and has the next-best combined "
        f"capability/travel score ({best['total_score']:g}/100)."
    )


def match_hospitals(
    requirements: Mapping[str, Any],
    hospitals: Sequence[Hospital | Mapping[str, Any]],
    clinic_location: tuple[float, float] | None = None,
    weights: Mapping[str, float] | None = None,
    unavailable_ids: Iterable[str] | None = None,
    travel_lookup: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Rank eligible hospitals, apply hard constraints, and pick with fallback.

    `travel_lookup` maps hospital_id -> precomputed travel estimate (from
    TravelEstimator); when omitted, straight-line placeholder estimates are
    computed from `clinic_location`.

    Returns a MatchResult-style dict: best_match, alternatives, excluded (with
    reasons + missing capabilities + generated "why not" reasons),
    fallback_used/fallback_note/fallback_detail, and a plain-language
    summary_explanation.
    """
    validated_weights = _validate_weights(weights)
    blocked = set(unavailable_ids or [])
    travel_lookup = travel_lookup or {}

    eligible_entries: list[dict[str, Any]] = []
    excluded_entries: list[dict[str, Any]] = []

    for raw in hospitals:
        hospital = _as_hospital(raw)
        # Score against hard constraints EXCEPT the simulated-outage flag so a
        # would-be winner can still be identified for the fallback narrative.
        reasons = check_eligibility(hospital, requirements, unavailable_ids=None)
        if reasons:
            excluded_entries.append(
                {
                    "hospital": hospital.to_dict(),
                    "eligible": False,
                    "total_score": None,
                    "factor_scores": {},
                    "reasons": [],
                    "missing_capabilities": missing_capabilities_of(hospital, requirements),
                    "exclusion_reasons": reasons,
                    "why_not": list(reasons),
                    "travel": None,
                    "explanation": (
                        f"{hospital.name} is not suitable: " + " ".join(reasons)
                    ),
                }
            )
            continue
        eligible_entries.append(
            score_hospital(
                hospital,
                requirements,
                clinic_location,
                validated_weights,
                travel_info=travel_lookup.get(hospital.hospital_id),
            )
        )

    # Simulated live outage: hospitals that pass the static constraints but are
    # currently marked unavailable. Removed from the ranking; may trigger fallback.
    outage_entries = []
    for entry in eligible_entries:
        if entry["hospital"]["hospital_id"] not in blocked:
            continue
        outage_reason = "Hospital marked unavailable in the simulated capacity feed."
        entry = dict(entry)
        entry["eligible"] = False
        entry["exclusion_reasons"] = [outage_reason]
        entry["why_not"] = [outage_reason]
        entry["explanation"] = (
            f"{entry['hospital']['name']} would score "
            f"{entry['total_score']}/100 but is excluded: {outage_reason}"
        )
        outage_entries.append(entry)
    ranked = [e for e in eligible_entries if e["hospital"]["hospital_id"] not in blocked]
    ranked.sort(key=lambda e: (-e["total_score"], e["hospital"]["hospital_id"]))
    excluded_entries.extend(outage_entries)

    best_match = ranked[0] if ranked else None
    alternatives = ranked[1:]

    # Generated "why not" explanations for the runner-up hospitals.
    if best_match is not None:
        for entry in alternatives:
            entry["why_not"] = _why_not_reasons(best_match, entry)

    fallback_used = False
    fallback_note = None
    fallback_detail = None
    if outage_entries and (
        best_match is None
        or max(e["total_score"] for e in outage_entries) > best_match["total_score"]
    ):
        fallback_used = True
        top_outage = max(outage_entries, key=lambda e: e["total_score"])
        outage_name = top_outage["hospital"]["name"]
        if best_match is None:
            fallback_note = (
                f"The previously top-ranked hospital ({outage_name}) "
                "became unavailable in the simulated feed and no other hospital "
                "passed the hard constraints."
            )
        else:
            fallback_note = (
                f"{outage_name} would have ranked first but is "
                "unavailable in the simulated capacity feed - "
                f"{best_match['hospital']['name']} is selected as the next eligible hospital."
            )
        if best_match is not None:
            reason_sentence = _fallback_reason_sentence(best_match, requirements)
        else:
            reason_sentence = "No alternative hospital passed the hard constraints."
        fallback_detail = {
            "primary_hospital_id": top_outage["hospital"]["hospital_id"],
            "primary_name": outage_name,
            "primary_status": "Unavailable (simulated capacity feed)",
            "fallback_hospital_id": (
                best_match["hospital"]["hospital_id"] if best_match else None
            ),
            "fallback_name": (
                best_match["hospital"]["name"] if best_match else None
            ),
            "reason": reason_sentence,
        }

    if best_match is None:
        summary = (
            "No hospital passed the hard capability constraints for this case. "
            f"{len(excluded_entries)} hospital(s) were excluded. "
            + (" ".join(e["explanation"] for e in excluded_entries[:2]))
        ).strip()
    else:
        alt_count = len(alternatives)
        summary = (
            f"{best_match['hospital']['name']} is the best match "
            f"(suitability {best_match['total_score']}/100): "
            + " ".join(best_match["reasons"][:3])
            + f" {alt_count} alternative suitable hospital(s) and "
            f"{len(excluded_entries)} excluded hospital(s) were also evaluated."
        )
        if fallback_used and fallback_note:
            summary += f" Fallback applied: {fallback_note}"

    # Provenance of the travel numbers shown in the ranking.
    sources = {
        str((t or {}).get("source") or "placeholder")
        for t in travel_lookup.values()
    }
    if not travel_lookup:
        travel_estimate_note = PLACEHOLDER_NOTE
    elif sources == {"osrm"}:
        travel_estimate_note = OSRM_ROUTING_NOTE
    elif "osrm" in sources:
        travel_estimate_note = (
            "Most routes used live road routing (OSRM); the rest fell back to "
            "straight-line placeholder estimates because routing was unavailable."
        )
    else:
        travel_estimate_note = PLACEHOLDER_NOTE

    clinic_payload = None
    if clinic_location is not None:
        clinic_payload = {
            "latitude": clinic_location[0],
            "longitude": clinic_location[1],
        }

    return {
        "requirements": dict(requirements),
        "weights": {k: validated_weights[k] for k in DEFAULT_WEIGHTS},
        "clinic_location": clinic_payload,
        "best_match": best_match,
        "alternatives": alternatives,
        "excluded": excluded_entries,
        "evaluated_count": len(hospitals),
        "eligible_count": len(ranked),
        "excluded_count": len(excluded_entries),
        "fallback_used": fallback_used,
        "fallback_note": fallback_note,
        "fallback_detail": fallback_detail,
        "summary_explanation": summary,
        "weights_disclaimer": WEIGHTS_DISCLAIMER,
        "travel_estimate_note": travel_estimate_note,
        "data_disclaimer": (
            f"{SYNTHETIC_DATA_NOTE} Scores reflect capability fit for this case "
            "only - not clinical quality and not real-time traffic."
        ),
    }


__all__ = [
    "DEFAULT_WEIGHTS",
    "FACTOR_LABELS",
    "TRAVEL_FACTORS",
    "TRAVEL_PLACEHOLDER_NOTE",
    "WEIGHTS_DISCLAIMER",
    "WeightError",
    "check_eligibility",
    "match_hospitals",
    "missing_capabilities_of",
    "score_hospital",
]
