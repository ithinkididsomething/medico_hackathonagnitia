"""DEMONSTRATION rules for the urgency classifier.

IMPORTANT: these are synthetic prototype examples, NOT clinically validated
thresholds. They exist only to demonstrate how the rule engine produces
explainable output. Replace or review them with qualified clinical input
before any real-world use.

Each rule: id, condition, severity (GREEN/ORANGE/RED), weight (score),
priority, explanation. Conditions may use dotted paths into the assessment
(e.g. "vitals.oxygen_saturation") and nest with all / any / not.
"""
from __future__ import annotations

DEMO_RULES: list[dict] = [
    # ------------------------------------------------------------------ #
    # RED — demonstration emergency criteria
    # ------------------------------------------------------------------ #
    {
        "id": "demo_emergency_indicator",
        "severity": "RED",
        "weight": 10,
        "priority": 100,
        "condition": {"field": "emergency_indicator", "op": "eq", "value": True},
        "explanation": "Demonstration emergency criterion triggered (explicit emergency indicator entered by staff).",
    },
    {
        "id": "demo_low_oxygen_saturation",
        "severity": "RED",
        "weight": 10,
        "priority": 90,
        "condition": {"field": "vitals.oxygen_saturation", "op": "lt", "value": 90},
        "explanation": "Oxygen saturation below configured demonstration threshold (<90%).",
    },
    {
        "id": "demo_severely_low_blood_pressure",
        "severity": "RED",
        "weight": 10,
        "priority": 85,
        "condition": {
            "any": [
                {"field": "vitals.systolic_bp", "op": "lt", "value": 90},
                {"field": "vitals.diastolic_bp", "op": "lt", "value": 50},
            ]
        },
        "explanation": "Blood pressure below configured demonstration threshold (systolic <90 or diastolic <50 mmHg).",
    },
    {
        "id": "demo_extreme_respiratory_rate",
        "severity": "RED",
        "weight": 10,
        "priority": 80,
        "condition": {
            "any": [
                {"field": "vitals.respiratory_rate", "op": "gt", "value": 30},
                {"field": "vitals.respiratory_rate", "op": "lt", "value": 8},
            ]
        },
        "explanation": "Respiratory rate outside configured demonstration range (8-30 breaths/min).",
    },
    {
        "id": "demo_extreme_heart_rate",
        "severity": "RED",
        "weight": 10,
        "priority": 80,
        "condition": {
            "any": [
                {"field": "vitals.heart_rate", "op": "gt", "value": 150},
                {"field": "vitals.heart_rate", "op": "lt", "value": 40},
            ]
        },
        "explanation": "Heart rate outside configured demonstration range (40-150 bpm).",
    },
    {
        "id": "demo_extreme_temperature",
        "severity": "RED",
        "weight": 10,
        "priority": 75,
        "condition": {
            "any": [
                {"field": "vitals.temperature_c", "op": "gt", "value": 41},
                {"field": "vitals.temperature_c", "op": "lt", "value": 35},
            ]
        },
        "explanation": "Temperature outside configured demonstration range (35-41 °C).",
    },
    {
        "id": "demo_severely_high_blood_pressure",
        "severity": "RED",
        "weight": 10,
        "priority": 70,
        "condition": {
            "any": [
                {"field": "vitals.systolic_bp", "op": "gte", "value": 180},
                {"field": "vitals.diastolic_bp", "op": "gte", "value": 120},
            ]
        },
        "explanation": "Blood pressure at or above configured demonstration threshold (180/120 mmHg or higher).",
    },
    # ------------------------------------------------------------------ #
    # ORANGE — demonstration urgent criteria
    # ------------------------------------------------------------------ #
    {
        "id": "demo_mildly_low_oxygen_saturation",
        "severity": "ORANGE",
        "weight": 5,
        "priority": 60,
        "condition": {
            "all": [
                {"field": "vitals.oxygen_saturation", "op": "gte", "value": 90},
                {"field": "vitals.oxygen_saturation", "op": "lte", "value": 94},
            ]
        },
        "explanation": "Oxygen saturation in configured demonstration band (90-94%).",
    },
    {
        "id": "demo_elevated_respiratory_rate",
        "severity": "ORANGE",
        "weight": 5,
        "priority": 55,
        "condition": {
            "all": [
                {"field": "vitals.respiratory_rate", "op": "gte", "value": 21},
                {"field": "vitals.respiratory_rate", "op": "lte", "value": 30},
            ]
        },
        "explanation": "Respiratory rate in configured demonstration band (21-30 breaths/min).",
    },
    {
        "id": "demo_abnormal_heart_rate",
        "severity": "ORANGE",
        "weight": 5,
        "priority": 55,
        "condition": {
            "any": [
                {
                    "all": [
                        {"field": "vitals.heart_rate", "op": "gte", "value": 111},
                        {"field": "vitals.heart_rate", "op": "lte", "value": 150},
                    ]
                },
                {
                    "all": [
                        {"field": "vitals.heart_rate", "op": "gte", "value": 40},
                        {"field": "vitals.heart_rate", "op": "lte", "value": 50},
                    ]
                },
            ]
        },
        "explanation": "Heart rate in configured demonstration band (40-50 or 111-150 bpm).",
    },
    {
        "id": "demo_borderline_low_blood_pressure",
        "severity": "ORANGE",
        "weight": 5,
        "priority": 55,
        "condition": {
            "any": [
                {
                    "all": [
                        {"field": "vitals.systolic_bp", "op": "gte", "value": 90},
                        {"field": "vitals.systolic_bp", "op": "lte", "value": 100},
                    ]
                },
                {
                    "all": [
                        {"field": "vitals.diastolic_bp", "op": "gte", "value": 50},
                        {"field": "vitals.diastolic_bp", "op": "lte", "value": 60},
                    ]
                },
            ]
        },
        "explanation": "Blood pressure in configured demonstration band (systolic 90-100 or diastolic 50-60 mmHg).",
    },
    {
        "id": "demo_high_fever",
        "severity": "ORANGE",
        "weight": 5,
        "priority": 50,
        "condition": {"field": "vitals.temperature_c", "op": "gte", "value": 39.5},
        "explanation": "Temperature at or above configured demonstration threshold (39.5 °C or higher).",
    },
]

RULES_SOURCE = "demonstration"
RULES_DISCLAIMER = (
    "Prototype demonstration rules using synthetic example thresholds. "
    "Not clinically validated. Any output must be reviewed by a qualified "
    "healthcare professional."
)
