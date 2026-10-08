from app.maps import MapsServiceError, haversine_km, total_distance_km
from app.maps.routing import _format_waypoints


def test_haversine_one_degree_latitude():
    # One degree of latitude is ~111.19 km everywhere.
    assert abs(haversine_km((0, 0), (1, 0)) - 111.19) < 0.1


def test_haversine_zero_for_same_point():
    assert haversine_km((28.6, 77.2), (28.6, 77.2)) == 0.0


def test_total_distance_multi_stop():
    points = [(0, 0), (0, 1), (0, 2)]
    assert abs(total_distance_km(points) - 2 * 111.19) < 0.2
    assert total_distance_km([(0, 0)]) == 0.0


def test_route_waypoint_formatting():
    # OSRM wants lon,lat pairs separated by ';'.
    assert _format_waypoints([(28.6, 77.2), (19.0, 72.8)]) == "77.2,28.6;72.8,19.0"


def test_route_needs_two_points():
    try:
        _format_waypoints([(28.6, 77.2)])
    except MapsServiceError:
        pass
    else:
        raise AssertionError("expected MapsServiceError")
