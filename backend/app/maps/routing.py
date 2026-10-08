"""Routing via OSRM (OpenStreetMap-compatible) — routes, distance, travel time.

Provider endpoints come from environment variables (see `.env.example`).
The public OSRM demo server is free and keyless; for production run your own
OSRM instance (or another OSM-compatible engine) and point ROUTER_BASE_URL at it.
"""
from __future__ import annotations

from typing import Sequence

import httpx

from ..config import get_settings
from .errors import MapsServiceError
from .geo import Point

# OSRM expects lon,lat pairs.
Coords = Sequence[float]


def _format_waypoints(points: Sequence[Point]) -> str:
    if len(points) < 2:
        raise MapsServiceError("A route needs at least two locations")
    return ";".join(f"{lon},{lat}" for lat, lon in points)


def _request_route(points: Sequence[Point], profile: str | None) -> dict:
    settings = get_settings()
    profile = profile or settings.router_profile
    path = f"{settings.router_base_url}/route/v1/{profile}/{_format_waypoints(points)}"
    params = {"overview": "full", "geometries": "geojson", "steps": "false"}

    headers = {}
    if settings.routing_api_key:
        headers["Authorization"] = f"Bearer {settings.routing_api_key}"

    try:
        with httpx.Client(timeout=15.0, headers=headers) as client:
            response = client.get(path, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise MapsServiceError(f"Routing request failed: {exc}") from exc
    except ValueError as exc:
        raise MapsServiceError("Router returned a non-JSON response") from exc

    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise MapsServiceError(
            f"Router could not find a route (code={payload.get('code')!r})"
        )

    route = payload["routes"][0]
    geometry = route.get("geometry", {})
    return {
        "distance_km": round(route["distance"] / 1000.0, 3),
        "duration_minutes": round(route["duration"] / 60.0, 2),
        "geometry": geometry,  # GeoJSON LineString (or with overview=full)
        "coordinates": [
            {"latitude": lat, "longitude": lon}
            for lon, lat in geometry.get("coordinates", [])
        ],
    }


def get_route(origin: Point, destination: Point, *, profile: str | None = None) -> dict:
    """Route between two (lat, lon) locations: distance, duration, geometry."""
    return _request_route([origin, destination], profile)


def route_waypoints(points: Sequence[Point], *, profile: str | None = None) -> dict:
    """Route through multiple locations in order (same shape as get_route)."""
    return _request_route(list(points), profile)


def estimate_travel_time(origin: Point, destination: Point, *, profile: str | None = None) -> float:
    """Estimated travel time in minutes between two locations."""
    return get_route(origin, destination, profile=profile)["duration_minutes"]
