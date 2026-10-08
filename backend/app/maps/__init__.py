"""OpenStreetMap / routing integration.

Public interface:
    geocode(query)                     -> [{latitude, longitude, display_name, ...}]
    haversine_km(a, b)                 -> float (no network)
    total_distance_km(points)          -> float (no network)
    get_route(origin, dest)            -> {distance_km, duration_minutes, geometry, coordinates}
    route_waypoints(points)            -> same shape, through several locations
    estimate_travel_time(origin, dest) -> minutes (float)
    TravelEstimator(origin)            -> graceful travel estimates (routing + fallback)
    MapsServiceError                   -> raised on external service failures
"""
from .errors import MapsServiceError
from .geo import EARTH_RADIUS_KM, haversine_km, total_distance_km
from .geocode import geocode
from .routing import estimate_travel_time, get_route, route_waypoints
from .travel import (
    OSRM_ROUTING_NOTE,
    PLACEHOLDER_NOTE,
    PLACEHOLDER_SPEED_KMH,
    TravelEstimator,
    thin_coordinates,
)

__all__ = [
    "EARTH_RADIUS_KM",
    "MapsServiceError",
    "OSRM_ROUTING_NOTE",
    "PLACEHOLDER_NOTE",
    "PLACEHOLDER_SPEED_KMH",
    "TravelEstimator",
    "estimate_travel_time",
    "geocode",
    "get_route",
    "haversine_km",
    "route_waypoints",
    "thin_coordinates",
    "total_distance_km",
]
