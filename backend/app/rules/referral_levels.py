"""Rural health referral levels (Prompt 7).

Four configurable, decision-support levels that sit UNDER the existing safety
hierarchy — they never override urgency or clinical rules:

    Critical safety rule  ->  Urgency classification  ->  Referral level
        ->  Condition-specific hospital matching  ->  Availability / travel ranking

The level is derived from (a) the urgency classification as a FLOOR that can
never be lowered, (b) the Prompt-5 derived case requirements as a second
floor, and (c) configurable demonstration keyword rules evaluated with the
same condition engine. The highest applicable level always wins, so a
critical emergency can never be downgraded because a symptom looks mild.

IMPORTANT: prototype demonstration categories only — not clinically validated,
not a substitute for professional judgment. Production use requires review by
qualified healthcare professionals.
"""
from __future__ import annotations

from typing import Any, Mapping

from .engine import RuleEngine

REFERRAL_LEVELS: dict[int, dict[str, Any]] = {
    1: {
        "name": "Home Care / Observe",
        "short_name": "Home / Observe",
        "tagline": "Low urgency",
        "description": (
            "Mild, uncomplicated symptoms based on the entered information."
        ),
        "action": (
            "Rest, fluids, basic supportive care and monitor symptoms. "
            "Seek care if symptoms worsen or danger signs appear."
        ),
        "examples": [
            "Common cold",
            "Mild headache",
            "Mild muscle pain",
            "Minor superficial wound",
            "Mild diarrhea without dehydration",
        ],
        "referral_recommended": False,
        "emergency_transport": False,
    },
    2: {
        "name": "Local Clinic / PHC",
        "short_name": "Clinic / PHC",
        "tagline": "Needs medical evaluation",
        "description": (
            "Needs examination or treatment but no immediate danger signs "
            "based on the entered information."
        ),
        "action": (
            "Visit the local clinic / PHC for examination, testing and treatment."
        ),
        "examples": [
            "Persistent fever",
            "Suspected uncomplicated malaria/dengue",
            "UTI symptoms",
            "Moderate diarrhea",
            "Skin infection",
            "Minor burns",
            "Simple wound",
            "Stable asthma symptoms",
        ],
        "referral_recommended": False,
        "emergency_transport": False,
    },
    3: {
        "name": "Urgent Referral",
        "short_name": "Urgent Referral",
        "tagline": "Higher-level evaluation",
        "description": (
            "Potentially serious presentation needing higher-level evaluation "
            "based on the entered information."
        ),
        "action": (
            "Higher-level evaluation is recommended. Initial "
            "assessment/stabilization at a clinic or PHC may be appropriate "
            "when safe, followed by CHC/hospital referral when required."
        ),
        "examples": [
            "Suspected severe infection",
            "Pneumonia with breathing difficulty",
            "Significant dehydration",
            "Fracture",
            "Deep wound",
            "Animal bite",
            "Persistent abdominal pain",
            "Pregnancy complications",
        ],
        "referral_recommended": True,
        "emergency_transport": False,
    },
    4: {
        "name": "Emergency / Big Hospital",
        "short_name": "Emergency Hospital",
        "tagline": "Immediate care",
        "description": (
            "Life-threatening or specialist/emergency presentation based on "
            "the entered information."
        ),
        "action": (
            "Immediate emergency referral/ambulance. Do not delay emergency "
            "care for routine clinic treatment."
        ),
        "examples": [
            "Severe breathing difficulty",
            "Unconsciousness",
            "Shock",
            "Severe bleeding",
            "Concerning chest pain",
            "Stroke symptoms",
            "Severe burns",
            "Major trauma",
            "Seizures",
            "Severe poisoning",
            "Complicated childbirth",
        ],
        "referral_recommended": True,
        "emergency_transport": True,
    },
}

REFERRAL_LEVEL_SOURCE = "demonstration"
REFERRAL_LEVEL_DISCLAIMER = (
    "Suggested referral level is a prototype decision-support recommendation "
    "based on entered information only. It is not a diagnosis, is not "
    "clinically validated, and must be reviewed by a qualified healthcare "
    "professional. Emergency decisions must follow applicable local clinical "
    "protocols."
)

# Floors derived from the existing classifications. These can only raise the
# level — nothing in this module may lower them (safety priority).
_URGENCY_FLOOR = {"GREEN": 1, "ORANGE": 3, "RED": 4}

# Demonstration keyword rules (configurable prototype data). Each rule carries
# a target level; the maximum triggered target wins. Text fields are matched
# case-insensitively against complaint + findings + illness details.
DEMO_REFERRAL_LEVEL_RULES: list[dict[str, Any]] = [
    # -- Level 4: life-threatening / emergency presentations -----------------
    {
        "id": "rl_unconscious",
        "target_level": 4,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in ("unconscious", "unresponsive", "coma", "fainted and not waking")
            ]
        },
        "explanation": "Entered information mentions unconsciousness/unresponsiveness.",
    },
    {
        "id": "rl_seizure",
        "target_level": 4,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in ("seizure", "convulsion", "epileptic fit", "fits")
            ]
        },
        "explanation": "Entered information mentions seizures/convulsions.",
    },
    {
        "id": "rl_severe_bleeding",
        "target_level": 4,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in (
                    "severe bleeding",
                    "bleeding heavily",
                    "heavy bleeding",
                    "blood loss",
                    "hemorrhage",
                    "haemorrhage",
                )
            ]
        },
        "explanation": "Entered information mentions severe bleeding/blood loss.",
    },
    {
        "id": "rl_shock",
        "target_level": 4,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in ("shock", "clammy and pale", "cold sweat with low pulse")
            ]
        },
        "explanation": "Entered information mentions shock.",
    },
    {
        "id": "rl_stroke_signs",
        "target_level": 4,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in (
                    "stroke",
                    "slurred speech",
                    "facial droop",
                    "face droop",
                    "one-sided weakness",
                    "one sided weakness",
                    "paralysis",
                )
            ]
        },
        "explanation": "Entered information mentions stroke-like signs.",
    },
    {
        "id": "rl_severe_breathing",
        "target_level": 4,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in (
                    "severe breathing difficulty",
                    "cannot breathe",
                    "can't breathe",
                    "gasping",
                    "choking",
                    "blue lips",
                    "turning blue",
                )
            ]
        },
        "explanation": "Entered information mentions severe breathing difficulty.",
    },
    {
        "id": "rl_major_trauma_burn",
        "target_level": 4,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in (
                    "major trauma",
                    "severe burn",
                    "severe burns",
                    "burn over large",
                    "crush injury",
                    "road traffic accident",
                    "road accident",
                )
            ]
        },
        "explanation": "Entered information mentions major trauma or severe burns.",
    },
    {
        "id": "rl_poisoning",
        "target_level": 4,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in ("poisoning", "poison", "snakebite", "snake bite", "overdose")
            ]
        },
        "explanation": "Entered information mentions poisoning/snakebite/overdose.",
    },
    {
        "id": "rl_obstetric_emergency",
        "target_level": 4,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in (
                    "complicated childbirth",
                    "obstructed labour",
                    "obstructed labor",
                    "heavy bleeding in pregnancy",
                    "bleeding in pregnancy",
                    "eclampsia",
                    "severe pre-eclampsia",
                )
            ]
        },
        "explanation": "Entered information mentions an obstetric emergency.",
    },
    {
        "id": "rl_chest_pain",
        "target_level": 4,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in (
                    "chest pain",
                    "pressure in chest",
                    "heart attack",
                    "myocardial infarction",
                )
            ]
        },
        "explanation": (
            "Entered information mentions chest pain — treated as potentially "
            "life-threatening until ruled out by a professional."
        ),
    },
    # -- Level 3: potentially serious, higher-level evaluation ---------------
    {
        "id": "rl_fracture",
        "target_level": 3,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in ("fracture", "broken bone", "suspected break", "deformity after injury")
            ]
        },
        "explanation": "Entered information mentions a possible fracture.",
    },
    {
        "id": "rl_animal_bite",
        "target_level": 3,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in ("animal bite", "dog bite", "cat bite", "monkey bite", "bite wound")
            ]
        },
        "explanation": "Entered information mentions an animal bite.",
    },
    {
        "id": "rl_dehydration",
        "target_level": 3,
        "condition": {
            "all": [
                {
                    "any": [
                        {"field": "presentation_text", "op": "contains", "value": kw}
                        for kw in (
                            "dehydration",
                            "dehydrated",
                            "sunken eyes",
                            "no urine",
                            "unable to drink",
                        )
                    ]
                },
                {
                    "not": {
                        "any": [
                            {"field": "presentation_text", "op": "contains", "value": kw}
                            for kw in ("without dehydration", "no dehydration", "no signs of dehydration")
                        ]
                    }
                },
            ]
        },
        "explanation": "Entered information mentions significant dehydration signs.",
    },
    {
        "id": "rl_pneumonia_breathing",
        "target_level": 3,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in (
                    "pneumonia",
                    "breathing difficulty",
                    "difficulty breathing",
                    "shortness of breath",
                    "short of breath",
                    "wheezing with fever",
                )
            ]
        },
        "explanation": "Entered information mentions pneumonia or breathing difficulty.",
    },
    {
        "id": "rl_abdominal_pain",
        "target_level": 3,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in (
                    "persistent abdominal pain",
                    "severe abdominal pain",
                    "acute abdomen",
                    "rigid abdomen",
                )
            ]
        },
        "explanation": "Entered information mentions persistent/severe abdominal pain.",
    },
    {
        "id": "rl_pregnancy_complication",
        "target_level": 3,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in (
                    "pregnancy complication",
                    "labour pain",
                    "labor pain",
                    "water broke",
                    "leaking fluid in pregnancy",
                    "reduced fetal movement",
                    "swelling in pregnancy with headache",
                )
            ]
        },
        "explanation": "Entered information mentions a pregnancy complication.",
    },
    {
        "id": "rl_deep_wound_infection",
        "target_level": 3,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in (
                    "deep wound",
                    "deep cut",
                    "severe infection",
                    "spreading redness",
                    "pus with fever",
                    "high fever with rash",
                )
            ]
        },
        "explanation": "Entered information mentions a deep wound or severe infection.",
    },
    # -- Level 2: needs examination, no immediate danger signs ---------------
    {
        "id": "rl_clinic_evaluation",
        "target_level": 2,
        "condition": {
            "any": [
                {"field": "presentation_text", "op": "contains", "value": kw}
                for kw in (
                    "fever",
                    "malaria",
                    "dengue",
                    "urinary",
                    "burning urination",
                    "uti ",
                    "diarrhea",
                    "diarrhoea",
                    "skin infection",
                    "boil",
                    "abscess",
                    "burn",
                    "wound",
                    "asthma",
                    "ear pain",
                    "sore throat",
                    "cough",
                    "vomiting",
                    "persistent headache",
                )
            ]
        },
        "explanation": "Entered information describes symptoms needing clinic/PHC examination.",
    },
]

__all__ = [
    "DEMO_REFERRAL_LEVEL_RULES",
    "REFERRAL_LEVEL_DISCLAIMER",
    "REFERRAL_LEVEL_SOURCE",
    "REFERRAL_LEVELS",
    "ReferralLevelResult",
    "build_referral_level_context",
    "calculate_referral_level",
]


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())
    return {}


def build_referral_level_context(
    assessment: Mapping[str, Any],
    urgency: Any,
    requirements: Any | None = None,
) -> dict[str, Any]:
    """Combined context the referral-level rules evaluate against."""
    urgency_dict = _as_dict(urgency)
    context = dict(assessment)
    text_parts = [
        str(assessment.get("chief_complaint") or ""),
        str(assessment.get("clinical_findings") or ""),
        str(assessment.get("illness_details") or ""),
    ]
    context["presentation_text"] = " ".join(text_parts).lower()
    context["urgency"] = {
        "level": urgency_dict.get("level", "GREEN"),
        "score": urgency_dict.get("score", 0.0),
    }
    context["emergency_indicator"] = bool(assessment.get("emergency_indicator", False))
    if requirements is not None:
        context["requirements"] = _as_dict(requirements)
    return context


class ReferralLevelResult(dict):
    """Dict subclass so callers can use it as a plain JSON-able payload."""


def calculate_referral_level(
    assessment: Mapping[str, Any],
    urgency: Any,
    requirements: Any | None = None,
    clinic_capability: Any | None = None,
    rules: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Classify a case into referral levels 1-4 (never downgrading safety).

    Priority: critical/RED signals -> urgency floor -> requirements floor ->
    keyword rules. The returned level is the maximum across all floors and
    triggered demonstration rules.
    """
    urgency_dict = _as_dict(urgency)
    urgency_level = str(urgency_dict.get("level", "GREEN")).upper()
    rule_details = list(urgency_dict.get("rule_details") or [])
    red_triggered = [
        d.get("rule_id", "")
        for d in rule_details
        if isinstance(d, Mapping) and d.get("triggered") and d.get("severity") == "RED"
    ]
    explicit_emergency = bool((assessment or {}).get("emergency_indicator", False))

    # Floor 1: urgency classification (+ explicit emergency flag as backstop).
    urgency_floor = _URGENCY_FLOOR.get(urgency_level, 1)
    if explicit_emergency:
        urgency_floor = max(urgency_floor, 4)

    # Floor 2: Prompt-5 derived requirements (capability-first signals).
    requirements_floor = 1
    requirements_dict = _as_dict(requirements) if requirements is not None else {}
    if requirements_dict.get("needs_icu"):
        requirements_floor = 4
    elif str(requirements_dict.get("needs_emergency", "none")) == "full":
        requirements_floor = 4
    elif str(requirements_dict.get("needs_emergency", "none")) == "basic":
        requirements_floor = max(requirements_floor, 3)

    # A routine case the local clinic cannot cover still needs a clinic/PHC
    # visit (possibly a better-equipped one) — floor 2, never a downgrade.
    capability_dict = _as_dict(clinic_capability) if clinic_capability is not None else {}
    clinic_gap = capability_dict.get("can_manage_locally") is False

    context = build_referral_level_context(assessment, urgency, requirements)
    payloads = list(rules) if rules is not None else DEMO_REFERRAL_LEVEL_RULES
    engine = RuleEngine.from_dicts(
        [
            {
                "id": str(rule.get("id", f"rule_{index + 1}")),
                "condition": rule.get("condition"),
                "weight": 0,
                "priority": int(rule.get("target_level", 1)),
                "explanation": str(rule.get("explanation", "")),
            }
            for index, rule in enumerate(payloads)
        ]
    )
    evaluation = engine.evaluate(context)
    triggered_targets: list[tuple[str, int, str]] = []
    for detail in evaluation.details:
        if not detail.triggered:
            continue
        target = next(
            (
                int(rule.get("target_level", 1))
                for rule in payloads
                if str(rule.get("id")) == detail.rule_id
            ),
            1,
        )
        triggered_targets.append((detail.rule_id, target, detail.explanation))

    rule_floor = max((target for _, target, _ in triggered_targets), default=1)
    clinic_floor = 2 if clinic_gap and urgency_level == "GREEN" else 1
    level = max(urgency_floor, requirements_floor, rule_floor, clinic_floor)
    level = min(max(level, 1), 4)

    meta = REFERRAL_LEVELS[level]
    source = (
        REFERRAL_LEVEL_SOURCE if rules is None else "caller-supplied"
    )

    # Backend-generated reason: only from inputs that actually fired.
    reason_parts: list[str] = []
    if red_triggered or explicit_emergency or urgency_level == "RED":
        reason_parts.append(
            "emergency urgency classification (RED)"
            + (
                f" — triggered: {', '.join(red_triggered)}"
                if red_triggered
                else (" — explicit emergency indicator" if explicit_emergency else "")
            )
        )
    elif urgency_level == "ORANGE":
        reason_parts.append("urgent classification (ORANGE)")
    if requirements_floor >= 3:
        reason_parts.append(
            "derived case requirements call for "
            + ("ICU/full emergency capability" if requirements_floor == 4 else "emergency capability")
        )
    for rule_id, _, explanation in sorted(triggered_targets, key=lambda t: -t[1]):
        reason_parts.append(f"{rule_id}: {explanation or 'matched demonstration criteria'}")
    if clinic_gap and level == 2 and urgency_level == "GREEN":
        reason_parts.append(
            "the current clinic profile does not cover the assessed requirements"
        )
    if not reason_parts:
        reason_parts.append(
            "no urgent or emergency criteria were triggered by the entered information"
        )

    triggered_ids = sorted({rule_id for rule_id, _, _ in triggered_targets})
    if red_triggered:
        triggered_ids = sorted(set(triggered_ids) | set(red_triggered))

    return ReferralLevelResult(
        {
            "level": level,
            "name": meta["name"],
            "short_name": meta["short_name"],
            "tagline": meta["tagline"],
            "description": meta["description"],
            "action": meta["action"],
            "examples": list(meta["examples"]),
            "reason": (
                f"Suggested Level {level} — {meta['name']} based on entered information: "
                + "; ".join(reason_parts)
                + "."
            ),
            "triggered_rules": triggered_ids,
            "referral_recommended": bool(meta["referral_recommended"]),
            "emergency_transport": bool(meta["emergency_transport"]),
            "needs_hospital_matching": level >= 3,
            "rules_source": source,
            "disclaimer": REFERRAL_LEVEL_DISCLAIMER,
        }
    )
