"""OpenStreetMap / routing integration.

Public interface:
    geocode(query)                     -> [{latitude, longitude, display_name, ...}]
    haversine_km(a, b)                 -> float (no network)
    total_distance_km(points)          -> float (no network)
    get_route(origin, dest)            -> {distance_km, duration_minutes, geometry, coordinates}
    route_waypoints(points)            -> same shape, through several locations
    estimate_travel_time(origin, dest) -> minutes (float)
    MapsServiceError                   -> raised on external service failures
"""
from .errors import MapsServiceError
from .geo import EARTH_RADIUS_KM, haversine_km, total_distance_km
from .geocode import geocode
from .routing import estimate_travel_time, get_route, route_waypoints

__all__ = [
    "EARTH_RADIUS_KM",
    "MapsServiceError",
    "estimate_travel_time",
    "geocode",
    "get_route",
    "haversine_km",
    "route_waypoints",
    "total_distance_km",
]
