"""Rural Diagnostic Risk & Systemic Healthcare Constraints knowledge layer (Prompt 8)."""
from __future__ import annotations

from .builder import build_knowledge_dataset, compute_metadata, write_artifacts
from .loader import (
    get_all_conditions,
    get_condition_by_id,
    get_injury_risks,
    get_referral_context_notices,
    get_systemic_drivers,
    load_knowledge_dataset,
    query_conditions_by_resource,
    query_mimics,
    reset_cache,
)
from .schema import (
    ConditionRecord,
    ContextRelevance,
    DiagnosticConfusionEntry,
    EVIDENCE_STATUSES,
    InjuryDiagnosticRisk,
    RELATIONSHIP_TYPES,
    RURAL_RELEVANCE_LEVELS,
    RuralContext,
    SourceRef,
    SystemicDriver,
)
from .validator import validate_dataset

__all__ = [
    "ConditionRecord",
    "ContextRelevance",
    "DiagnosticConfusionEntry",
    "EVIDENCE_STATUSES",
    "InjuryDiagnosticRisk",
    "RELATIONSHIP_TYPES",
    "RURAL_RELEVANCE_LEVELS",
    "RuralContext",
    "SourceRef",
    "SystemicDriver",
    "build_knowledge_dataset",
    "compute_metadata",
    "get_all_conditions",
    "get_condition_by_id",
    "get_injury_risks",
    "get_referral_context_notices",
    "get_systemic_drivers",
    "load_knowledge_dataset",
    "query_conditions_by_resource",
    "query_mimics",
    "reset_cache",
    "validate_dataset",
    "write_artifacts",
]
