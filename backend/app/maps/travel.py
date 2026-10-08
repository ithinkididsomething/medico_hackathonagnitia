"""Travel estimation with graceful provider fallback (Prompt 3).

`TravelEstimator` wraps the routing provider behind a small abstraction:

  - origin/destination coordinates in, distance + travel time + optional
    route geometry out,
  - real road routing via the OSRM-compatible provider in `routing.py`,
  - automatic FALLBACK to a straight-line (haversine) placeholder estimate
    whenever routing is disabled, unavailable, or fails,
  - never raises for provider/network problems - callers always receive an
    estimate dict with a `source` field ("osrm" or "placeholder").

The routing provider can be replaced or simulated by passing a custom
`route_fn` with the same signature as `routing.get_route`.
"""
from __future__ import annotations

from typing import Callable, Mapping

from ..config import get_settings
from .errors import MapsServiceError
from .geo import Point, haversine_km
from .routing import get_route

# Placeholder assumption used only when live routing is unavailable.
PLACEHOLDER_SPEED_KMH = 25.0

OSRM_ROUTING_NOTE = (
    "Road distance and travel time estimated via OSRM using OpenStreetMap "
    "data. No live traffic."
)

PLACEHOLDER_NOTE = (
    "Placeholder straight-line estimate from the clinic; live road routing "
    "was unavailable or disabled for this request."
)

# Cap the number of geometry points sent to the UI (keeps payloads small).
MAX_ROUTE_POINTS = 60

RouteFn = Callable[..., Mapping]


def thin_coordinates(
    coordinates: list[dict] | None, limit: int = MAX_ROUTE_POINTS
) -> list[dict] | None:
    """Subsample route geometry to at most `limit` {latitude, longitude} points."""
    if not coordinates:
        return None
    if len(coordinates) <= limit:
        return [dict(c) for c in coordinates]
    step = (len(coordinates) - 1) / (limit - 1)
    thinned = [dict(coordinates[round(i * step)]) for i in range(limit)]
    return thinned


class TravelEstimator:
    """Estimate distance/travel-time from one origin to many destinations.

    Each estimate is a dict:
        distance_km      - road distance when routed, else straight-line km
        travel_minutes   - driving estimate when routed, else placeholder
        source           - "osrm" (live routing) or "placeholder"
        note             - plain-language provenance of the numbers
        route_coordinates- thinned GeoJSON-derived polyline, or None
    """

    def __init__(
        self,
        origin: Point | None,
        *,
        route_fn: RouteFn | None = None,
        profile: str | None = None,
    ) -> None:
        self.origin = origin
        self._route_fn = route_fn
        self._profile = profile
        self.routing_attempted = 0
        self.routing_failures = 0

    # -- internals ---------------------------------------------------------- #
    def _call_route_fn(self, destination: Point) -> Mapping:
        fn = self._route_fn or get_route
        if self._profile is not None:
            return fn(self.origin, destination, profile=self._profile)
        return fn(self.origin, destination)

    def _placeholder(self, reason: str) -> dict:
        return {
            "distance_km": None,
            "travel_minutes": None,
            "source": "placeholder",
            "note": f"{PLACEHOLDER_NOTE} ({reason})",
            "route_coordinates": None,
        }

    def _placeholder_with_distance(self, destination: Point, reason: str) -> dict:
        straight_line = haversine_km(self.origin, destination)
        minutes = round(straight_line / PLACEHOLDER_SPEED_KMH * 60.0, 1)
        return {
            "distance_km": round(straight_line, 2),
            "travel_minutes": minutes,
            "source": "placeholder",
            "note": f"{PLACEHOLDER_NOTE} ({reason})",
            "route_coordinates": None,
        }

    # -- public API --------------------------------------------------------- #
    def estimate(self, destination: Point | None) -> dict | None:
        """Estimate travel to one destination; None when coordinates are missing."""
        if destination is None:
            return None
        if self.origin is None:
            return self._placeholder("clinic location unknown")

        settings = get_settings()
        routing_available = self._route_fn is not None or settings.routing_enabled
        if not routing_available:
            return self._placeholder_with_distance(
                destination, "routing disabled by configuration"
            )

        try:
            self.routing_attempted += 1
            route = self._call_route_fn(destination)
        except MapsServiceError as exc:
            self.routing_failures += 1
            return self._placeholder_with_distance(
                destination, f"routing unavailable ({exc})"
            )
        except Exception as exc:  # defensive: never break matching on a router bug
            self.routing_failures += 1
            return self._placeholder_with_distance(
                destination, f"routing error ({exc})"
            )

        return {
            "distance_km": round(float(route["distance_km"]), 2),
            "travel_minutes": round(float(route["duration_minutes"]), 1),
            "source": "osrm",
            "note": OSRM_ROUTING_NOTE,
            "route_coordinates": thin_coordinates(route.get("coordinates")),
        }

    def estimate_many(
        self, destinations: Mapping[str, Point | None]
    ) -> dict[str, dict]:
        """Estimate travel to several destinations keyed by id."""
        results: dict[str, dict] = {}
        for hospital_id, destination in destinations.items():
            estimate = self.estimate(destination)
            if estimate is not None:
                results[hospital_id] = estimate
        return results


__all__ = [
    "MAX_ROUTE_POINTS",
    "OSRM_ROUTING_NOTE",
    "PLACEHOLDER_NOTE",
    "PLACEHOLDER_SPEED_KMH",
    "TravelEstimator",
    "thin_coordinates",
]
