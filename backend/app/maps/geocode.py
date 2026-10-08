"""Geocoding via Nominatim (OpenStreetMap) — converts addresses to coordinates.

Endpoint/credentials come from environment variables (see `.env.example`).
Nominatim's public instance is free but requires a descriptive User-Agent and
light usage; for heavier traffic run your own instance and point
GEOCODER_BASE_URL at it.
"""
from __future__ import annotations

import httpx

from ..config import get_settings
from .errors import MapsServiceError


def geocode(query: str, *, limit: int = 5) -> list[dict]:
    """Resolve a free-form address/place name to coordinates.

    Returns a list of {latitude, longitude, display_name, ...}; empty if not found.
    """
    if not query or not query.strip():
        raise MapsServiceError("Geocoding query must not be empty")

    settings = get_settings()
    try:
        with httpx.Client(timeout=10.0, headers={"User-Agent": settings.user_agent}) as client:
            response = client.get(
                f"{settings.geocoder_base_url}/search",
                params={"q": query, "format": "jsonv2", "limit": limit},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise MapsServiceError(f"Geocoding request failed: {exc}") from exc
    except ValueError as exc:
        raise MapsServiceError("Geocoder returned a non-JSON response") from exc

    return [
        {
            "latitude": float(item["lat"]),
            "longitude": float(item["lon"]),
            "display_name": item.get("display_name", ""),
            "type": item.get("type"),
            "category": item.get("category"),
        }
        for item in payload
        if "lat" in item and "lon" in item
    ]
