"""Lightweight field-edge snapping helpers for polygon placement."""

import math


def snap_to_nearest_edge(lng: float, lat: float, edges: list, max_distance_m: float = 20.0):
    """Snap a point to the nearest edge if within max_distance_m."""
    if not edges:
        return lng, lat

    best = (lng, lat)
    best_dist = max_distance_m

    for edge in edges:
        ex, ey = edge
        dist_m = _haversine_m(lat, lng, ey, ex)
        if dist_m < best_dist:
            best_dist = dist_m
            best = (ex, ey)

    return best


def generate_demo_field_edges(center_lat: float, center_lng: float, radius_deg: float):
    """Generate synthetic field boundary edges around a center point."""
    edges = []
    for i in range(16):
        angle = (i / 16) * 2 * math.pi
        edges.append((
            center_lng + radius_deg * math.cos(angle),
            center_lat + radius_deg * math.sin(angle),
        ))
    return edges


def _haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))