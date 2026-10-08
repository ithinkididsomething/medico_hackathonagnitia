"""Curated prototype registry of government healthcare schemes (Prompt 6).

This is a SMALL, configuration-style dataset for the demo. It is derived from
official public information (National Health Authority / PM-JAY, Ministry of
Health & Family Welfare / NHM, Ministry of Women & Child Development, and the
Madhya Pradesh health department) and is explicitly labelled `is_prototype`.

RULES WE FOLLOW:
  * Every scheme carries `official_url` / `source_url` pointing at official
    government domains — never blogs or unofficial articles.
  * `verified_at` / `last_checked` record when this prototype copy was last
    reviewed; the UI always reminds staff to confirm with the authority.
  * No scheme ever claims confirmed eligibility — the engine only ever returns
    "potentially relevant / potentially eligible" and flags verification.
  * Ayushman card status is recorded from bearer-provided/clinic inputs or an
    authorised source; the prototype NEVER fabricates card numbers or claims
    coverage on its own.

Maternity note (source: National Health Mission): pregnancy/delivery is NOT
covered by the AB PM-JAY core package, but JSY / JSSK / PMMVY and related
neonatal packages are the relevant maternal-benefit pathways, so pregnancy
situations match those schemes instead.
"""
from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------- #
# Status vocabularies
# --------------------------------------------------------------------------- #
AYUSHMAN_CARD_STATUSES = ("yes", "no", "unknown")

# Part 3 statuses (recorded from bearer/clinic input, never invented).
AYUSHMAN_STATUSES = ("verified", "not_verified", "not_available", "unknown")

AYUSHMAN_STATUS_LABELS = {
    "verified": "Card verified",
    "not_verified": "Card not verified",
    "not_available": "Card not available",
    "unknown": "Eligibility unknown",
}

# Generic statuses allowed on patient_scheme_status rows.
SCHEME_STATUSES = (
    "verified",
    "not_verified",
    "not_available",
    "unknown",
    "applied",
    "active",
    "denied",
    "expired",
    "not_relevant",
)

SITUATION_LABELS = {
    "emergency": "Emergency / urgent hospitalization",
    "critical_care": "Critical care / ICU-level care",
    "trauma": "Major trauma / accident",
    "maternity": "Pregnancy / obstetric care",
    "newborn": "Newborn / neonatal care",
    "pediatric": "Pediatric care (age under 18)",
    "senior_care": "Senior citizen (age 70+)",
    "chronic_care": "Chronic / long-term care",
    "low_income": "Low-income / vulnerable household",
    "hospitalization": "Hospital-level care",
    "community_care": "Community / outpatient-level care",
}

SCHEME_MATCH_DISCLAIMER = (
    "Potentially eligible / potentially relevant - NOT a confirmed eligibility "
    "determination. Final eligibility, coverage and empanelment must be verified "
    "through the appropriate official government system or authorized scheme "
    "authority before any benefit decision is made."
)

BENEFITS_PROFILE_PRIVACY_NOTE = (
    "Only information needed for scheme matching is collected. No Aadhaar "
    "number, name or contact details are requested or stored anywhere in this "
    "prototype. Clip can use synthetic clinic-assigned patient identifiers only."
)

SCHEME_DATA_NOTE = (
    "All scheme information in this application is prototype configuration "
    "based on official public sources. It is NOT live government data and must "
    "be confirmed via the listed official source before use."
)

# --------------------------------------------------------------------------- #
# Document checklist catalogue (Part 10). Schemes reference these codes.
# --------------------------------------------------------------------------- #
DOCUMENT_CATALOG: dict[str, dict[str, str]] = {
    "identity": {
        "label": "Identity document",
        "notes": "Government photo identity document as recognised by the scheme (e.g. Voter ID, driving licence).",
    },
    "ayushman_card": {
        "label": "Ayushman (AB PM-JAY) card / e-card",
        "notes": "Printed Ayushman card or the PM-JAY beneficiary e-card / Ayushman app record.",
    },
    "ration_card_or_beneficiary_list": {
        "label": "Ration (priority/BPL) card or PM-JAY beneficiary list confirmation",
        "notes": "Socio-economic category proof or a confirmed match in the SECC/NFSA beneficiary database.",
    },
    "bpl_ration_card": {
        "label": "BPL / priority-household ration card",
        "notes": "Used by schemes such as JSY and PMMVY to demonstrate the socio-economic category.",
    },
    "medical_referral": {
        "label": "Medical / referral documents",
        "notes": "Referral letter, prescriptions and prior medical records relevant to the case.",
    },
    "mcp_card": {
        "label": "MCP / mother & child tracking card",
        "notes": "Mother and Child Protection card showing pregnancy registration and antenatal visits.",
    },
    "maternity_evidence": {
        "label": "Pregnancy / maternity evidence",
        "notes": "LMP date, antenatal check-up records or a clinician-confirmed pregnancy.",
    },
    "bank_account": {
        "label": "Bank / Post Office account details (for DBT)",
        "notes": "Required where the scheme pays cash benefits by Direct Benefit Transfer (e.g. PMMVY).",
    },
    "job_card_evidence": {
        "label": "Work/Job card evidence (where claimed)",
        "notes": "e.g. MGNREGA job card, e-Shram card or other category-supporting card when offered.",
    },
}

SOURCES: list[dict[str, Any]] = [
    {
        "source_id": "pmjay.gov.in",
        "source_name": "Ayushman Bharat PM-JAY official portal - National Health Authority",
        "source_url": "https://pmjay.gov.in",
        "source_type": "official",
        "region": "India (Central)",
        "last_checked": "2026-09-30",
        "notes": "Authoritative AB PM-JAY scheme information, empanelled hospital lists and beneficiary details.",
    },
    {
        "source_id": "nha.gov.in",
        "source_name": "National Health Authority (NHA)",
        "source_url": "https://nha.gov.in",
        "source_type": "official",
        "region": "India (Central)",
        "last_checked": "2026-09-30",
        "notes": "NHA implements AB PM-JAY and the senior-citizen (Vay Vandana) expansion.",
    },
    {
        "source_id": "beneficiary.nha.gov.in",
        "source_name": "PM-JAY beneficiary portal (NHA)",
        "source_url": "https://beneficiary.nha.gov.in",
        "source_type": "official",
        "region": "India (Central)",
        "last_checked": "2026-09-30",
        "notes": "Online beneficiary/Ayushman Vay Vandana eligibility and cover verification; toll-free 14555.",
    },
    {
        "source_id": "nhm.gov.in",
        "source_name": "National Health Mission (MoHFW)",
        "source_url": "https://nhm.gov.in",
        "source_type": "official",
        "region": "India (Central)",
        "last_checked": "2026-09-30",
        "notes": "JSY, JSSK and RBSK programme pages - official maternal and child health benefit information.",
    },
    {
        "source_id": "wcd.gov.in",
        "source_name": "Ministry of Women & Child Development - PMMVY",
        "source_url": "https://wcd.gov.in",
        "source_type": "official",
        "region": "India (Central)",
        "last_checked": "2026-09-30",
        "notes": "Official PMMVY scheme information; beneficiary portal at https://pmmvy.wcd.gov.in.",
    },
    {
        "source_id": "health.mp.gov.in",
        "source_name": "Madhya Pradesh Health Department (official portal)",
        "source_url": "https://health.mp.gov.in",
        "source_type": "official",
        "region": "Madhya Pradesh (State)",
        "last_checked": "2026-09-30",
        "notes": "State-level health programmes and implementation of Ayushman Bharat in Madhya Pradesh.",
    },
]

# --------------------------------------------------------------------------- #
# Curated scheme dataset. Keys mirror the government_schemes table columns so
# the same payload seeds the database and drives the matching engine.
# --------------------------------------------------------------------------- #
SCHEMES: list[dict[str, Any]] = [
    {
        "scheme_id": "ab_pmjay",
        "name": "Ayushman Bharat - Pradhan Mantri Jan Arogya Yojana (AB PM-JAY)",
        "short_name": "AB PM-JAY",
        "government_level": "central",
        "state": None,
        "department": "National Health Authority (Ministry of Health & Family Welfare)",
        "description": (
            "World's largest publicly funded health assurance scheme. Provides "
            "cashless secondary and tertiary hospitalisation cover of up to "
            "Rs 5,00,000 per family per year through a network of empanelled "
            "hospitals for eligible beneficiary families identified from the "
            "SECC/NFSA database."
        ),
        "target_beneficiary_category": (
            "Economically vulnerable families per the SECC/NFSA deprivation list; "
            "all citizens aged 70+ under the Ayushman Vay Vandana expansion; "
            "ASHAs/AWWs/AWHs and their families."
        ),
        "age_min": 0,
        "age_max": 120,
        "clinical_categories": [
            "emergency",
            "critical_care",
            "trauma",
            "cardiovascular",
            "neurology",
            "oncology",
            "renal",
            "orthopaedics",
            "paediatrics",
            "general_hospitalisation",
        ],
        "coverage_type": "Hospitalisation (secondary & tertiary care packages)",
        "benefit_type": "Cashless treatment cover up to Rs 5,00,000 per family per year",
        "situations": ["emergency", "critical_care", "trauma", "chronic_care", "pediatric", "hospitalization", "senior_care"],
        "eligibility_rules": [
            {
                "condition": {
                    "any": [
                        {"field": "situations", "op": "contains", "value": "emergency"},
                        {"field": "situations", "op": "contains", "value": "critical_care"},
                        {"field": "situations", "op": "contains", "value": "trauma"},
                        {"field": "situations", "op": "contains", "value": "hospitalization"},
                    ]
                },
                "explanation": (
                    "The case points to hospital-level care, which AB PM-JAY "
                    "Health Benefit Packages cover for eligible beneficiaries."
                ),
                "priority": 10,
            },
            {
                "condition": {"field": "age_years", "op": "gte", "value": 70},
                "explanation": (
                    "Senior citizen aged 70+ - potentially eligible under the "
                    "Ayushman Vay Vandana expansion irrespective of income."
                ),
                "priority": 9,
            },
        ],
        "documents": ["identity", "ayushman_card", "ration_card_or_beneficiary_list", "medical_referral"],
        "application_verification_method": (
            "Verify via the PM-JAY beneficiary portal (beneficiary.nha.gov.in) or "
            "toll-free 14555, or confirm at any empanelled hospital before admission."
        ),
        "official_url": "https://pmjay.gov.in",
        "source_name": "National Health Authority / PM-JAY official portal",
        "source_url": "https://pmjay.gov.in",
        "verified_at": "2026-09-30",
        "last_checked": "2026-09-30",
        "active": True,
        "is_prototype": True,
        "version": "prototype-v1",
        "effective_from": "2018-09-23",
        "effective_until": None,
        "benefit_notes": [
            "Cashless treatment for eligible Health Benefit Packages (secondary & tertiary hospitalisation).",
            "Cover of up to Rs 5,00,000 per family per year for eligible beneficiary families.",
            "Senior citizens aged 70+ receive a dedicated Ayushman Vay Vandana cover.",
            "Pregnancy/maternity itself is NOT covered by the AB PM-JAY core package; related neonatal packages may apply.",
        ],
        "exclusions_notice": (
            "Maternity/pregnancy care is not covered under the AB PM-JAY core "
            "benefit. Actual coverage depends on the empanelled hospital and the "
            "specific Health Benefit Package; always confirm on the PM-JAY portal."
        ),
    },
    {
        "scheme_id": "pmjay_senior_vay_vandana",
        "name": "Ayushman Bharat PM-JAY - Senior Citizen (Ayushman Vay Vandana)",
        "short_name": "Ayushman Vay Vandana",
        "government_level": "central",
        "state": None,
        "department": "National Health Authority (Ministry of Health & Family Welfare)",
        "description": (
            "Government of India expansion of AB PM-JAY (announced 29-Oct-2024) "
            "covering ALL citizens aged 70 years and above with up to Rs 5,00,000 "
            "per year, irrespective of socio-economic status."
        ),
        "target_beneficiary_category": "All senior citizens aged 70 years and above",
        "age_min": 70,
        "age_max": 120,
        "clinical_categories": ["emergency", "critical_care", "cardiovascular", "orthopaedics", "renal", "oncology", "general_hospitalisation"],
        "coverage_type": "Hospitalisation (secondary & tertiary care packages)",
        "benefit_type": "Rs 5,00,000 per year free health cover (family basis or top-up)",
        "situations": ["senior_care", "emergency", "critical_care", "chronic_care", "hospitalization"],
        "eligibility_rules": [
            {
                "condition": {"field": "age_years", "op": "gte", "value": 70},
                "explanation": "Patient is 70 or older - potentially eligible for the Vay Vandana cover.",
                "priority": 20,
            }
        ],
        "documents": ["identity", "ayushman_card", "medical_referral"],
        "application_verification_method": (
            "Registration/verification at empanelled hospitals, the Ayushman app, "
            "beneficiary.nha.gov.in, toll-free 14555 or missed call 1800110770."
        ),
        "official_url": "https://pmjay.gov.in",
        "source_name": "National Health Authority / PM-JAY official portal",
        "source_url": "https://pmjay.gov.in",
        "verified_at": "2026-09-30",
        "last_checked": "2026-09-30",
        "active": True,
        "is_prototype": True,
        "version": "prototype-v1",
        "effective_from": "2024-10-29",
        "effective_until": None,
        "benefit_notes": [
            "All senior citizens aged 70+ are covered regardless of income (subject to scheme rules).",
            "Existing PM-JAY families get an additional top-up cover for the 70+ member.",
        ],
        "exclusions_notice": "Coverage is subject to the official NHA implementation guidelines; confirm before use.",
    },
    {
        "scheme_id": "jsy",
        "name": "Janani Suraksha Yojana (JSY)",
        "short_name": "JSY",
        "government_level": "central",
        "state": None,
        "department": "National Health Mission (Ministry of Health & Family Welfare)",
        "description": (
            "Conditional cash-transfer scheme promoting institutional delivery "
            "among poor pregnant women. Cash assistance is paid on delivery at a "
            "health institution (amounts vary by state under the national minimum)."
        ),
        "target_beneficiary_category": "Pregnant women from low-income (BPL/eligible) households, prioritising institutional delivery",
        "age_min": 15,
        "age_max": 55,
        "clinical_categories": ["maternity", "obstetrics"],
        "coverage_type": "Cash assistance (conditional, on institutional delivery)",
        "benefit_type": "Cash assistance for institutional delivery plus ASHA-linked support",
        "situations": ["maternity"],
        "eligibility_rules": [
            {
                "condition": {"field": "situations", "op": "contains", "value": "maternity"},
                "explanation": "Pregnancy/obstetric case - JSY targets institutional delivery among eligible women.",
                "priority": 10,
            },
            {
                "condition": {"any": [{"field": "benefits_profile.socioeconomic_category", "op": "in", "value": ["bpl", "priority_household"]}]},
                "explanation": "Socio-economic category recorded as BPL/priority - a common JSY target group.",
                "priority": 9,
            },
        ],
        "documents": ["bpl_ration_card", "identity", "mcp_card", "maternity_evidence", "bank_account"],
        "application_verification_method": (
            "Application through the ASHA worker/health facility; cash released per JSY guidelines on verified institutional delivery."
        ),
        "official_url": "https://nhm.gov.in",
        "source_name": "National Health Mission (MoHFW) - JSY page",
        "source_url": "https://nhm.gov.in",
        "verified_at": "2026-09-30",
        "last_checked": "2026-09-30",
        "active": True,
        "is_prototype": True,
        "version": "prototype-v1",
        "effective_from": "2005-04-12",
        "effective_until": None,
        "benefit_notes": [
            "Cash assistance for institutional delivery, with a special focus on low-performing states.",
            "Delivered as a conditional cash transfer; eligibility and amounts follow official JSY guidelines.",
        ],
        "exclusions_notice": "Not a pilot-fabricated benefit; amounts and eligibility must be confirmed per state JSY guidelines.",
    },
    {
        "scheme_id": "pmmvy",
        "name": "Pradhan Mantri Matru Vandana Yojana (PMMVY)",
        "short_name": "PMMVY",
        "government_level": "central",
        "state": None,
        "department": "Ministry of Women & Child Development",
        "description": (
            "Maternity benefit scheme providing cash incentive (Rs 5,000 for the "
            "first child; Rs 6,000 under Mission Shakti for a second girl child) "
            "by Direct Benefit Transfer to eligible pregnant/lactating women."
        ),
        "target_beneficiary_category": "Pregnant/lactating women 18-55 from socially/educationally disadvantaged sections (excl. regular govt/PSU employees)",
        "age_min": 18,
        "age_max": 55,
        "clinical_categories": ["maternity"],
        "coverage_type": "Cash incentive (DBT)",
        "benefit_type": "Direct Benefit Transfer cash incentive for condition fulfilment (ANC + birth/immunisation)",
        "situations": ["maternity", "low_income"],
        "eligibility_rules": [
            {
                "condition": {"field": "situations", "op": "contains", "value": "maternity"},
                "explanation": "Pregnancy/obstetric case - PMMVY targets eligible pregnant women.",
                "priority": 10,
            },
            {
                "condition": {"field": "benefits_profile.socioeconomic_category", "op": "in", "value": ["bpl", "priority_household"]},
                "explanation": "Socio-economic category recorded as BPL/priority - a typical PMMVY target group.",
                "priority": 9,
            },
        ],
        "documents": ["identity", "mcp_card", "maternity_evidence", "bpl_ration_card", "bank_account", "job_card_evidence"],
        "application_verification_method": (
            "Application via the Anganwadi worker/ASHA or the official portal (pmmvy.wcd.gov.in); payout in DBT."
        ),
        "official_url": "https://wcd.gov.in",
        "source_name": "Ministry of Women & Child Development - PMMVY",
        "source_url": "https://pmmvy.wcd.gov.in",
        "verified_at": "2026-09-30",
        "last_checked": "2026-09-30",
        "active": True,
        "is_prototype": True,
        "version": "prototype-v1",
        "effective_from": "2017-01-01",
        "effective_until": None,
        "benefit_notes": [
            "Cash incentive of Rs 5,000 for the first living child (in instalments).",
            "Rs 6,000 for a second child where the child is a girl under Mission Shakti.",
            "Paid by Direct Benefit Transfer; Aadhaar-based validation happens at the portal - never in this prototype.",
        ],
        "exclusions_notice": "Excludes women in regular government/PSU employment; eligibility verified via the official portal.",
    },
    {
        "scheme_id": "jssk",
        "name": "Janani Shishu Suraksha Karyakram (JSSK)",
        "short_name": "JSSK",
        "government_level": "central",
        "state": None,
        "department": "National Health Mission (Ministry of Health & Family Welfare)",
        "description": (
            "Guarantees free and cashless delivery (including C-section), free "
            "drugs, diagnostics, diet, blood and free transport for pregnant women "
            "and for sick newborns up to one year in public health institutions."
        ),
        "target_beneficiary_category": "All pregnant women delivering in public institutions + sick newborns/infants (up to 1 year)",
        "age_min": 0,
        "age_max": 120,
        "clinical_categories": ["maternity", "newborn", "paediatrics"],
        "coverage_type": "Free/cashless care in public institutions",
        "benefit_type": "Free drugs, consumables, diagnostics, diet, blood, transport and user-charge exemption",
        "situations": ["maternity", "newborn", "pediatric"],
        "eligibility_rules": [
            {
                "condition": {"any": [
                    {"field": "situations", "op": "contains", "value": "maternity"},
                    {"field": "situations", "op": "contains", "value": "newborn"},
                ]},
                "explanation": "Maternity/newborn case - JSSK entitles free care for delivery and sick newborns in public facilities.",
                "priority": 10,
            }
        ],
        "documents": ["identity", "mcp_card", "maternity_evidence", "medical_referral"],
        "application_verification_method": "Automatic entitlement at empanelled public health institutions at the point of care.",
        "official_url": "https://nhm.gov.in",
        "source_name": "National Health Mission (MoHFW) - JSSK page",
        "source_url": "https://nhm.gov.in",
        "verified_at": "2026-09-30",
        "last_checked": "2026-09-30",
        "active": True,
        "is_prototype": True,
        "version": "prototype-v1",
        "effective_from": "2011-06-01",
        "effective_until": None,
        "benefit_notes": [
            "Free and cashless delivery including C-section in public institutions.",
            "Free care for sick newborns up to 30 days (expanded to sick infants up to one year).",
            "Free transport, drugs, diagnostics, blood and diet during stay.",
        ],
        "exclusions_notice": "Entitlement is tied to care in public health institutions; confirm the facility qualifies.",
    },
    {
        "scheme_id": "rbsk",
        "name": "Rashtriya Bal Swasthya Karyakram (RBSK)",
        "short_name": "RBSK",
        "government_level": "central",
        "state": None,
        "department": "National Health Mission (Ministry of Health & Family Welfare)",
        "description": (
            "Child health screening programme screening children 0-18 years for "
            "32 health conditions (Diseases, Deficiencies, Defects and "
            "Developmental delays) with referral to District Early Intervention "
            "Centres for management."
        ),
        "target_beneficiary_category": "Children aged 0-18 years (schools + community anganwadi/health facility screening)",
        "age_min": 0,
        "age_max": 18,
        "clinical_categories": ["paediatrics", "child_health"],
        "coverage_type": "Health screening + referral pathway",
        "benefit_type": "Free screening for 32 child-health conditions and referral for management",
        "situations": ["pediatric"],
        "eligibility_rules": [
            {
                "condition": {"field": "situations", "op": "contains", "value": "pediatric"},
                "explanation": "Patient is under 18 - RBSK screens children 0-18 for early-detected conditions.",
                "priority": 10,
            }
        ],
        "documents": ["identity", "medical_referral"],
        "application_verification_method": "Screening through schools/anganwadi/health facilities; referral to the District Early Intervention Centre.",
        "official_url": "https://nhm.gov.in",
        "source_name": "National Health Mission (MoHFW) - RBSK",
        "source_url": "https://nhm.gov.in",
        "verified_at": "2026-09-30",
        "last_checked": "2026-09-30",
        "active": True,
        "is_prototype": True,
        "version": "prototype-v1",
        "effective_from": "2013-02-07",
        "effective_until": None,
        "benefit_notes": [
            "Early screening of 32 diseases, deficiencies, defects and developmental delays.",
            "Referral to District Early Intervention Centres (DEIC) for confirmation and management.",
        ],
        "exclusions_notice": "Screening is a health-system pathway - availability in Madhya Pradesh is via public facilities.",
    },
    {
        "scheme_id": "mp_ayushman_state",
        "name": "Ayushman Bharat - Madhya Pradesh State Implementation (AB-MP)",
        "short_name": "AB-MP",
        "government_level": "state",
        "state": "Madhya Pradesh",
        "department": "Madhya Pradesh Health Department (State Health Agency)",
        "description": (
            "State-level implementation of Ayushman Bharat in Madhya Pradesh, "
            "including state-defined Health Benefit Package flexibilities, "
            "empanelled hospital network within the state, and state-specific "
            "top-ups/rollout. The system is designed to accommodate this "
            "state-specific pathway (Prototype configuration)."
        ),
        "target_beneficiary_category": "State beneficiaries under AB PM-JAY within Madhya Pradesh, plus state-defined coverage groups",
        "age_min": 0,
        "age_max": 120,
        "clinical_categories": ["emergency", "critical_care", "trauma", "general_hospitalisation"],
        "coverage_type": "Hospitalisation under the state AB network",
        "benefit_type": "State-linked AB PM-JAY hospitalisation coverage & empanelled-network access",
        "situations": ["emergency", "critical_care", "trauma", "hospitalization", "chronic_care"],
        "eligibility_rules": [
            {
                "condition": {
                    "any": [
                        {"field": "situations", "op": "contains", "value": "emergency"},
                        {"field": "situations", "op": "contains", "value": "hospitalization"},
                        {"field": "situations", "op": "contains", "value": "critical_care"},
                    ]
                },
                "explanation": "Hospital-level care in Madhya Pradesh - the state AB implementation is the relevant pathway.",
                "priority": 8,
            }
        ],
        "documents": ["identity", "ayushman_card", "ration_card_or_beneficiary_list", "medical_referral"],
        "application_verification_method": (
            "Confirm coverage/empanelment via the MP health department and the national beneficiary portal (beneficiary.nha.gov.in)."
        ),
        "official_url": "https://health.mp.gov.in",
        "source_name": "Madhya Pradesh Health Department (official portal)",
        "source_url": "https://health.mp.gov.in",
        "verified_at": "2026-09-30",
        "last_checked": "2026-09-30",
        "active": True,
        "is_prototype": True,
        "version": "prototype-v1",
        "effective_from": "2018-09-25",
        "effective_until": None,
        "benefit_notes": [
            "State-level access to AB PM-JAY coverage through the Madhya Pradesh empanelled network.",
            "Designed as the configurable state implementation anchor for future MP-specific rules.",
        ],
        "exclusions_notice": "State rules are represented as demonstration configuration; verify with the MP health department.",
    },
    {
        "scheme_id": "mp_108_ambulance",
        "name": "Madhya Pradesh Emergency Ambulance Assistance (Dial 108)",
        "short_name": "108 Ambulance (MP)",
        "government_level": "state",
        "state": "Madhya Pradesh",
        "department": "Madhya Pradesh Health Department / National Health Mission (MP)",
        "description": (
            "Emergency patient transport assistance in Madhya Pradesh (Dial 108 "
            "ambulance network). Free/govt-facilitated emergency transport is a "
            "benefit pathway commonly available at the point of care."
        ),
        "target_beneficiary_category": "Members of the public requiring emergency transport in Madhya Pradesh",
        "age_min": 0,
        "age_max": 120,
        "clinical_categories": ["emergency", "trauma", "transport"],
        "coverage_type": "Emergency transport service",
        "benefit_type": "Emergency ambulance transport (subject to availability and local programme rules)",
        "situations": ["emergency", "trauma"],
        "eligibility_rules": [
            {
                "condition": {"any": [
                    {"field": "situations", "op": "contains", "value": "emergency"},
                    {"field": "situations", "op": "contains", "value": "trauma"},
                ]},
                "explanation": "Emergency/trauma case - emergency transport assistance is relevant at the point of care.",
                "priority": 6,
            }
        ],
        "documents": ["identity"],
        "application_verification_method": "Contact the MP emergency response line (108) / local helpline; availability is simulated in this prototype, not real-time.",
        "official_url": "https://health.mp.gov.in",
        "source_name": "Madhya Pradesh Health Department (official portal)",
        "source_url": "https://health.mp.gov.in",
        "verified_at": "2026-09-30",
        "last_checked": "2026-09-30",
        "active": True,
        "is_prototype": True,
        "version": "prototype-v1",
        "effective_from": "2020-01-01",
        "effective_until": None,
        "benefit_notes": [
            "Emergency patient transport support during emergency/trauma situations in Madhya Pradesh.",
        ],
        "exclusions_notice": "Ambulance availability is SIMULATED (not real-time); always confirm with the local emergency response line.",
    },
]

# --------------------------------------------------------------------------- #
# Hospital -> scheme empanelment compatibility (Part 8). INFORMATIONAL ONLY:
# never feeds the clinical eligibility/safety hierarchy or the hospital rank.
# Mirrors the hospital_scheme_eligibility table that is seeded at startup.
# --------------------------------------------------------------------------- #
HOSPITAL_SCHEME_COMPAT: dict[str, dict[str, Any]] = {
    "SYN-HOSP-01": {
        "scheme_id": "ab_pmjay",
        "empaneled": True,
        "specialty_codes": ["cardiology", "surgery", "orthopedics", "neurology", "internal_medicine", "pediatrics"],
        "packages": [
            "Emergency & Polytrauma packages",
            "Cardiac interventional packages",
            "Stroke / neurology packages",
            "General surgical packages",
        ],
        "verification_date": "2026-09-15",
        "source": "prototype-configuration",
        "notes": "Synthetic empanelment flag for demonstration only - confirm on the PM-JAY empanelled hospital list.",
    },
    "SYN-HOSP-02": {
        "scheme_id": "ab_pmjay",
        "empaneled": True,
        "specialty_codes": ["cardiology", "surgery", "orthopedics"],
        "packages": ["Emergency & Polytrauma packages", "Cardiac interventional packages", "Orthopaedic packages"],
        "verification_date": "2026-09-15",
        "source": "prototype-configuration",
        "notes": "Synthetic empanelment flag for demonstration only.",
    },
    "SYN-HOSP-03": {
        "scheme_id": "ab_pmjay",
        "empaneled": False,
        "specialty_codes": [],
        "packages": [],
        "verification_date": None,
        "source": "prototype-configuration",
        "notes": "Not flagged as empanelled in this prototype catalogue.",
    },
    "SYN-HOSP-04": {
        "scheme_id": "ab_pmjay",
        "empaneled": True,
        "specialty_codes": ["cardiology", "neurology", "internal_medicine", "obstetrics_gynaecology"],
        "packages": ["Emergency packages", "Stroke / neurology packages"],
        "verification_date": "2026-08-01",
        "source": "prototype-configuration",
        "notes": "Synthetic empanelment flag for demonstration only.",
    },
    "SYN-HOSP-05": {
        "scheme_id": "ab_pmjay",
        "empaneled": True,
        "specialty_codes": ["cardiology", "surgery", "orthopedics", "neurology", "pediatrics"],
        "packages": ["Emergency & Polytrauma packages", "Cardiac interventional packages", "General surgical packages"],
        "verification_date": "2026-06-01",
        "source": "prototype-configuration",
        "notes": "Empanelled but excluded for this case by simulated capacity/availability.",
    },
    "SYN-HOSP-06": {
        "scheme_id": "ab_pmjay",
        "empaneled": False,
        "specialty_codes": [],
        "packages": [],
        "verification_date": None,
        "source": "prototype-configuration",
        "notes": "Not flagged as empanelled in this prototype catalogue.",
    },
}

SCHEME_CATALOG_META = {
    "count": len(SCHEMES),
    "sources_count": len(SOURCES),
    "document_codes": sorted(DOCUMENT_CATALOG),
    "design_state": "Madhya Pradesh",
    "note": SCHEME_DATA_NOTE,
}