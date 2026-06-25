"""Realistic farm polygon placement on agricultural land (demo + optional Earth Engine)."""

import math
import random

from utils.database import execute_query, is_demo_mode, _load_demo_data


def _existing_farm_centroids(municipality_id: str):
    if is_demo_mode():
        data = _load_demo_data()
        return [
            (float(f["latitude"]), float(f["longitude"]))
            for f in data.get("farms", [])
            if f.get("municipality_id") == municipality_id
        ]

    farms = execute_query(
        "SELECT latitude, longitude FROM farm_parcels WHERE municipality_id = %s",
        (municipality_id,),
        fetch_all=True,
    )
    return [(float(f["latitude"]), float(f["longitude"])) for f in (farms or [])]


def find_agricultural_location(municipality_coords, area_hectares, crop_type, municipality_id=None):
    """Find suitable agricultural coordinates near existing farm clusters."""
    lat, lng = municipality_coords

    try:
        from services.satellite_service import _ee_ready
        from services.earth_engine import get_ee

        if _ee_ready():
            ee = get_ee()
            search_radius = 5000
            point = ee.Geometry.Point([lng, lat])
            search_area = point.buffer(search_radius)
            image = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterBounds(search_area)
                .filterDate("2024-09-01", "2024-10-20")
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
                .sort("CLOUDY_PIXEL_PERCENTAGE")
                .first()
            )
            nir = image.select("B8")
            red = image.select("B4")
            ndvi = nir.subtract(red).divide(nir.add(red))
            agricultural_mask = ndvi.gt(0.4).And(ndvi.lt(0.8))
            sample_points = agricultural_mask.sample(
                region=search_area,
                scale=10,
                numPixels=100,
                seed=random.randint(1, 10000),
            )
            points_list = sample_points.getInfo().get("features", [])
            if points_list:
                selected = random.choice(points_list)
                coords = selected["geometry"]["coordinates"]
                return {"latitude": coords[1], "longitude": coords[0]}
    except Exception:
        pass

    centroids = _existing_farm_centroids(municipality_id) if municipality_id else []
    if centroids:
        base_lat, base_lng = random.choice(centroids)
        return {
            "latitude": base_lat + random.uniform(-0.008, 0.008),
            "longitude": base_lng + random.uniform(-0.008, 0.008),
        }

    return {
        "latitude": lat + random.uniform(-0.015, 0.015),
        "longitude": lng + random.uniform(-0.015, 0.015),
    }


def generate_field_polygon(center_lat, center_lng, area_hectares, crop_type):
    """Generate a realistic field polygon based on crop type and area."""
    return generate_realistic_polygon(center_lat, center_lng, area_hectares, crop_type)


def _rotate_point(lng, lat, center_lng, center_lat, angle_rad):
    dx = lng - center_lng
    dy = lat - center_lat
    cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
    return (
        center_lng + dx * cos_a - dy * sin_a,
        center_lat + dx * sin_a + dy * cos_a,
    )


def generate_realistic_polygon(center_lat, center_lng, area_hectares, crop_type, satellite_image=None):
    """Generate crop-specific polygon with rotation and edge snapping."""
    from utils.edge_detection import generate_demo_field_edges, snap_to_nearest_edge

    side_length_m = (area_hectares * 10000) ** 0.5
    side_length_deg = side_length_m / 111000
    rotation = random.uniform(0, math.pi / 4)
    edges = generate_demo_field_edges(center_lat, center_lng, side_length_deg * 0.6)

    for _ in range(5):
        if crop_type in ("Rice", "Corn"):
            aspect = random.uniform(2.0, 3.0)
            width = side_length_deg / math.sqrt(aspect) * 0.85
            height = width * aspect
            corners = [
                (-width / 2, -height / 2),
                (width / 2, -height / 2),
                (width / 2, height / 2),
                (-width / 2, height / 2),
            ]
            points = []
            for dx, dy in corners:
                lng = center_lng + dx
                lat = center_lat + dy
                lng, lat = _rotate_point(lng, lat, center_lng, center_lat, rotation)
                lng, lat = snap_to_nearest_edge(lng, lat, edges)
                points.append([lng, lat])
            points.append(points[0])
        elif crop_type in ("Banana", "Coconut"):
            radius = side_length_deg / 2
            vertex_count = random.randint(6, 10)
            points = []
            for i in range(vertex_count):
                angle = (i / vertex_count) * 2 * math.pi
                r = radius * random.uniform(0.75, 1.25)
                lng = center_lng + r * math.cos(angle)
                lat = center_lat + r * math.sin(angle)
                lng, lat = snap_to_nearest_edge(lng, lat, edges)
                points.append([lng, lat])
            points.append(points[0])
        else:
            radius = side_length_deg / 2.2
            vertex_count = random.randint(5, 8)
            points = []
            for i in range(vertex_count):
                angle = (i / vertex_count) * 2 * math.pi + rotation
                r = radius * random.uniform(0.7, 1.1)
                lng = center_lng + r * math.cos(angle)
                lat = center_lat + r * math.sin(angle)
                lng, lat = snap_to_nearest_edge(lng, lat, edges)
                points.append([lng, lat])
            points.append(points[0])

        if _polygon_area_ok(points, area_hectares):
            return points

        center_lat += random.uniform(-0.001, 0.001)
        center_lng += random.uniform(-0.001, 0.001)

    return points


def _polygon_area_ok(points, target_hectares):
    if len(points) < 4:
        return False
    area = 0.0
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        area += x1 * y2 - x2 * y1
    area = abs(area) / 2.0
    area_m2 = area * (111000 ** 2)
    target_m2 = target_hectares * 10000
    if target_m2 == 0:
        return True
    deviation = abs(area_m2 - target_m2) / target_m2
    return deviation < 0.15