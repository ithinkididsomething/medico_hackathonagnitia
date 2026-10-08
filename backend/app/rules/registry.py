"""Application rule registry.

The final business rules are NOT defined here yet — add them once the
product requirements are known, e.g.:

    DEFAULT_RULES: list[dict] = [
        {"id": "...", "condition": {...}, "weight": 5, "priority": 1,
         "explanation": "..."},
    ]

Until then the API accepts rules per-request, and an empty list means
"nothing to score" (total score 0).
"""
from __future__ import annotations

DEFAULT_RULES: list[dict] = []
