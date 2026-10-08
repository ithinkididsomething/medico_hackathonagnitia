"""Pure geometry helpers — no network, no API keys."""
from __future__ import annotations

import math
from typing import Sequence

EARTH_RADIUS_KM = 6371.0088  # IUGG mean Earth radius

Point = Sequence[float]  # (latitude, longitude)


def haversine_km(a: Point, b: Point) -> float:
    """Great-circle distance in kilometres between two (lat, lon) points."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def total_distance_km(points: Sequence[Point]) -> float:
    """Sum of consecutive great-circle distances for a list of points."""
    if len(points) < 2:
        return 0.0
    return sum(haversine_km(points[i], points[i + 1]) for i in range(len(points) - 1))
