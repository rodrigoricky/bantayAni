"""Live Sentinel-2 satellite data via Google Earth Engine."""

import copy
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta

from services.earth_engine import is_ee_available, get_ee

logger = logging.getLogger(__name__)

_tile_cache: dict = {}
_ndvi_cache: dict = {}
CACHE_TTL_SECONDS = 48 * 3600
NDVI_CACHE_TTL_SECONDS = 60 * 60

FLOOD_VV_THRESHOLD_DB = -15
FLOOD_BLUE_PALETTE = ["0000FF", "0066FF", "00CCFF"]


def _ndvi_cache_key(polygon_coords: list, start_date: str, end_date: str) -> str:
    return f"{hash(str(polygon_coords))}_{start_date}_{end_date}"


def get_cached_ndvi(polygon_coords: list, start_date: str, end_date: str):
    key = _ndvi_cache_key(polygon_coords, start_date, end_date)
    entry = _ndvi_cache.get(key)
    if entry and time.time() - entry["cached_at"] < NDVI_CACHE_TTL_SECONDS:
        return entry["ndvi"]
    return None


def set_cached_ndvi(polygon_coords: list, start_date: str, end_date: str, ndvi: float):
    key = _ndvi_cache_key(polygon_coords, start_date, end_date)
    _ndvi_cache[key] = {"ndvi": ndvi, "cached_at": time.time()}


NAGA_CENTER = (13.6192, 123.1814)
NDVI_PALETTE = [
    "#a50026", "#d73027", "#f46d43", "#fdae61", "#fee08b",
    "#ffffbf", "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850", "#006837",
]


def _ee_ready():
    ee = get_ee()
    return is_ee_available() and ee is not None


def _cropland_mask(ee):
    """Mask to cropland (40) and grassland (30) from ESA WorldCover v200."""
    return _land_cover_mask(ee, [30, 40])


def _land_cover_mask(ee, classes: list[int]):
    """Build a boolean mask for the given ESA WorldCover v200 class codes."""
    worldcover = ee.ImageCollection("ESA/WorldCover/v200").first()
    land_cover = worldcover.select("Map")
    mask = None
    for cls in classes:
        cls_mask = land_cover.eq(cls)
        mask = cls_mask if mask is None else mask.Or(cls_mask)
    return mask


def _format_s2_capture_dates(collection, ee) -> list[str]:
    """Extract and format Sentinel-2 capture dates from a collection."""
    try:
        dates_ms = collection.aggregate_array("system:time_start").getInfo()
        if not dates_ms:
            return []
        return sorted({
            datetime.utcfromtimestamp(d / 1000).strftime("%Y-%m-%d")
            for d in dates_ms
        })
    except Exception as exc:
        logger.warning("Failed to extract S2 capture dates: %s", exc)
        return []


def _get_s2_collection(ee, geometry, start_date: str, end_date: str, max_cloud: int = 30):
    return (
        ee.ImageCollection("COPERNICUS/S2_SR")
        .filterDate(start_date, end_date)
        .filterBounds(geometry)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
    )


def _cloud_mask_s2(image):
    """Mask clouds/shadow using Sentinel-2 SCL band (values 3, 8, 9, 10)."""
    scl = image.select("SCL")
    clear = (
        scl.neq(3)
        .And(scl.neq(8))
        .And(scl.neq(9))
        .And(scl.neq(10))
    )
    return image.updateMask(clear)


def _compute_ndvi(image):
    return image.normalizedDifference(["B8", "B4"]).rename("NDVI")


def _compute_ndwi(image):
    return image.normalizedDifference(["B3", "B8"]).rename("NDWI")


def _masked_median_composite(collection, ee):
    cropland = _cropland_mask(ee)
    return (
        collection
        .map(_cloud_mask_s2)
        .map(_compute_ndvi)
        .median()
        .updateMask(cropland)
    )


def _s2_optical_composite(collection, ee):
    """Cloud-masked median composite with cropland mask for index computation."""
    cropland = _cropland_mask(ee)
    return (
        collection
        .map(_cloud_mask_s2)
        .median()
        .updateMask(cropland)
    )


def get_sentinel1_sar_composite(lat: float, lng: float, start_date: str, end_date: str):
    """
    Build a Sentinel-1 SAR composite (VV/VH, IW mode) with focal_median speckle filter.
    Returns an ee.Image or None when unavailable.
    """
    if not _ee_ready():
        return None

    try:
        ee = get_ee()
        point = ee.Geometry.Point([lng, lat])
        collection = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(point)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .select(["VV", "VH"])
        )

        if collection.size().getInfo() == 0:
            logger.warning(
                "No Sentinel-1 SAR imagery for %s,%s between %s and %s",
                lat, lng, start_date, end_date,
            )
            return None

        composite = collection.median()
        return composite.focal_median(50, "circle", "meters")
    except Exception as exc:
        logger.error("Sentinel-1 SAR composite failed: %s", exc)
        return None


def get_sentinel1_flood_tile_url(
    lat: float,
    lng: float,
    start_date: str,
    end_date: str,
) -> dict | None:
    """Generate flood detection tile URL — VV < -15 dB classified as flood (blue palette)."""
    if not _ee_ready():
        return None

    try:
        ee = get_ee()
        buffer = 0.1
        region = ee.Geometry.Rectangle([
            lng - buffer, lat - buffer,
            lng + buffer, lat + buffer,
        ])
        composite = get_sentinel1_sar_composite(lat, lng, start_date, end_date)
        if composite is None:
            return None

        flood = composite.select("VV").lt(FLOOD_VV_THRESHOLD_DB).selfMask()
        map_id = flood.getMapId({"palette": FLOOD_BLUE_PALETTE})

        return {
            "tile_url": map_id["tile_fetcher"].url_format,
            "bounds": region.bounds().getInfo(),
            "source": "sentinel-1",
            "vv_threshold_db": FLOOD_VV_THRESHOLD_DB,
        }
    except Exception as exc:
        logger.error("Sentinel-1 flood tile generation failed: %s", exc)
        return None


def _mean_lst_celsius(ee, geometry, start_date: str, end_date: str) -> float | None:
    """Mean land-surface temperature (°C) from MODIS MOD11A2 over the date range."""
    try:
        lst_collection = (
            ee.ImageCollection("MODIS/061/MOD11A2")
            .filterDate(start_date, end_date)
            .filterBounds(geometry)
            .select("LST_Day_1km")
        )
        if lst_collection.size().getInfo() == 0:
            return None

        lst_kelvin = lst_collection.mean().multiply(0.02)
        stats = lst_kelvin.subtract(273.15).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=1000,
            maxPixels=int(1e9),
        ).getInfo()

        lst_c = stats.get("LST_Day_1km")
        if lst_c is None:
            return None
        return round(float(lst_c), 1)
    except Exception as exc:
        logger.warning("LST computation failed: %s", exc)
        return None


def compute_multi_index(
    polygon_coords: list,
    start_date: str,
    end_date: str,
) -> dict | None:
    """
    Compute NDVI, NDWI, LST, flood and heat-stress flags for a farm polygon.
    Returns ndvi, ndwi, lst_celsius, flood_detected, heat_stress, capture_dates, source.
    """
    if not _ee_ready():
        logger.error("Earth Engine not available for multi-index computation")
        return None

    if not polygon_coords or len(polygon_coords) < 3:
        logger.error("Invalid polygon for multi-index computation")
        return None

    try:
        ee = get_ee()
        geometry = ee.Geometry.Polygon([polygon_coords])
        collection = _get_s2_collection(ee, geometry, start_date, end_date)
        capture_dates = _format_s2_capture_dates(collection, ee)

        if collection.size().getInfo() == 0:
            logger.warning(
                "No Sentinel-2 imagery for multi-index between %s and %s; attempting SAR fallback",
                start_date, end_date,
            )
            lats = [c[1] for c in polygon_coords]
            lngs = [c[0] for c in polygon_coords]
            center_lat = sum(lats) / len(lats)
            center_lng = sum(lngs) / len(lngs)

            sar = get_sentinel1_sar_composite(center_lat, center_lng, start_date, end_date)
            lst_celsius = _mean_lst_celsius(ee, geometry, start_date, end_date)
            flood_detected = False
            if sar is not None:
                flood_stats = sar.select("VV").lt(FLOOD_VV_THRESHOLD_DB).reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geometry,
                    scale=10,
                    maxPixels=int(1e9),
                ).getInfo()
                flood_fraction = flood_stats.get("VV")
                flood_detected = flood_fraction is not None and float(flood_fraction) > 0.1
                logger.info("SAR fallback used for flood detection (fraction=%s)", flood_fraction)

            return {
                "ndvi": None,
                "ndwi": None,
                "lst_celsius": lst_celsius,
                "flood_detected": flood_detected,
                "heat_stress": lst_celsius is not None and lst_celsius > 35,
                "capture_dates": capture_dates,
                "source": "sentinel-1",
            }

        optical = _s2_optical_composite(collection, ee)
        ndvi_img = _compute_ndvi(optical).updateMask(_cropland_mask(ee))
        ndwi_img = _compute_ndwi(optical).updateMask(_cropland_mask(ee))

        ndvi_stats = ndvi_img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=10,
            maxPixels=int(1e9),
        ).getInfo()
        ndwi_stats = ndwi_img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=10,
            maxPixels=int(1e9),
        ).getInfo()

        ndvi = ndvi_stats.get("NDVI")
        ndwi = ndwi_stats.get("NDWI")
        ndvi_val = round(float(ndvi), 3) if ndvi is not None else None
        ndwi_val = round(float(ndwi), 3) if ndwi is not None else None

        lst_celsius = _mean_lst_celsius(ee, geometry, start_date, end_date)
        flood_detected = ndwi_val is not None and ndwi_val > 0.1
        heat_stress = lst_celsius is not None and lst_celsius > 35

        logger.info(
            "Multi-index computed: ndvi=%s ndwi=%s lst=%s captures=%s",
            ndvi_val, ndwi_val, lst_celsius, capture_dates,
        )

        return {
            "ndvi": ndvi_val,
            "ndwi": ndwi_val,
            "lst_celsius": lst_celsius,
            "flood_detected": flood_detected,
            "heat_stress": heat_stress,
            "capture_dates": capture_dates,
            "source": "earth-engine",
        }
    except Exception as exc:
        logger.error("Multi-index computation failed: %s", exc)
        return None


def _try_ndvi_with_mask(collection, ee, geometry, mask):
    """Compute mean NDVI from a collection, optionally applying a land-cover mask."""
    composite = collection.map(_cloud_mask_s2).map(_compute_ndvi).median()
    if mask is not None:
        composite = composite.updateMask(mask)
    stats = composite.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=10,
        maxPixels=int(1e9),
    ).getInfo()
    mean_ndvi = stats.get("NDVI")
    if mean_ndvi is None:
        return None
    return round(float(mean_ndvi), 3)


def _build_no_imagery_error(
    lat: float,
    lng: float,
    start_date: str,
    end_date: str,
    reason: str,
) -> dict:
    return {
        "error": "no_imagery",
        "reason": reason,
        "lat": lat,
        "lng": lng,
        "start_date": start_date,
        "end_date": end_date,
    }


def compute_ndvi_for_location(
    lat: float,
    lng: float,
    polygon_coords: list,
    start_date: str,
    end_date: str,
) -> float | dict | None:
    """
    Single source of truth for NDVI computation over a farm polygon.
    polygon_coords: list of [lng, lat] pairs (Earth Engine order).

    Progressive strategy:
    1. strict cropland mask (30, 40)
    2. vegetated mask (10, 20, 30, 40)
    3. unmasked
    4. widen date range by ±60 days and repeat
    """
    if not _ee_ready():
        logger.error("Earth Engine not available for NDVI computation")
        return None

    if not polygon_coords or len(polygon_coords) < 3:
        logger.error("Invalid polygon for NDVI computation")
        return None

    cached = get_cached_ndvi(polygon_coords, start_date, end_date)
    if cached is not None:
        return cached

    try:
        ee = get_ee()
        geometry = ee.Geometry.Polygon([polygon_coords])
        original_start = datetime.strptime(start_date, "%Y-%m-%d")
        original_end = datetime.strptime(end_date, "%Y-%m-%d")
        widened_start = (original_start - timedelta(days=60)).strftime("%Y-%m-%d")
        widened_end = (original_end + timedelta(days=60)).strftime("%Y-%m-%d")

        date_ranges = [
            (start_date, end_date, "original"),
            (widened_start, widened_end, "widened"),
        ]
        mask_strategies = [
            ("strict_cropland", lambda: _land_cover_mask(ee, [30, 40])),
            ("vegetated", lambda: _land_cover_mask(ee, [10, 20, 30, 40])),
            ("unmasked", lambda: None),
        ]

        last_reason = "No usable Sentinel-2 imagery found for this location and date range."

        for range_start, range_end, range_label in date_ranges:
            for max_cloud in (30, 60):
                collection = _get_s2_collection(ee, geometry, range_start, range_end, max_cloud)
                collection_size = collection.size().getInfo()
                logger.info(
                    "S2 collection size=%d for %s,%s (%s to %s, cloud<%d%%, range=%s)",
                    collection_size,
                    lat,
                    lng,
                    range_start,
                    range_end,
                    max_cloud,
                    range_label,
                )

                if collection_size == 0:
                    last_reason = (
                        f"No Sentinel-2 images with cloud<{max_cloud}% between "
                        f"{range_start} and {range_end}"
                    )
                    if max_cloud == 30:
                        logger.info(
                            "Retrying NDVI lookup for %s,%s with 60%% cloud threshold",
                            lat,
                            lng,
                        )
                        continue
                    break

                capture_dates = _format_s2_capture_dates(collection, ee)
                if capture_dates:
                    logger.info(
                        "S2 capture dates for %s,%s (%s to %s): %s",
                        lat,
                        lng,
                        range_start,
                        range_end,
                        ", ".join(capture_dates),
                    )

                for mask_name, mask_builder in mask_strategies:
                    mask = mask_builder()
                    ndvi = _try_ndvi_with_mask(collection, ee, geometry, mask)
                    if ndvi is not None:
                        logger.info(
                            "NDVI %.3f for %s,%s using %s mask (%s range, cloud<%d%%)",
                            ndvi,
                            lat,
                            lng,
                            mask_name,
                            range_label,
                            max_cloud,
                        )
                        cache_start = range_start if range_label == "original" else start_date
                        cache_end = range_end if range_label == "original" else end_date
                        set_cached_ndvi(polygon_coords, cache_start, cache_end, ndvi)
                        return ndvi

                    last_reason = (
                        f"Sentinel-2 images found but NDVI could not be computed with "
                        f"{mask_name} mask between {range_start} and {range_end}"
                    )

        logger.warning(
            "No Sentinel-2 imagery for %s,%s between %s and %s after progressive masking",
            lat,
            lng,
            start_date,
            end_date,
        )
        sar = get_sentinel1_sar_composite(lat, lng, start_date, end_date)
        if sar is not None:
            logger.info("Sentinel-1 SAR fallback available for %s,%s (NDVI unavailable)", lat, lng)
        return _build_no_imagery_error(lat, lng, start_date, end_date, last_reason)
    except Exception as exc:
        logger.error("NDVI computation failed: %s", exc)
        return _build_no_imagery_error(
            lat,
            lng,
            start_date,
            end_date,
            f"NDVI computation failed: {exc}",
        )


def get_ndvi_map_tile_url(
    lat: float,
    lng: float,
    start_date: str,
    end_date: str,
) -> dict | None:
    """Generate Earth Engine NDVI tile URL for a bounding region."""
    if not _ee_ready():
        return None

    try:
        ee = get_ee()
        buffer = 0.1
        region = ee.Geometry.Rectangle([
            lng - buffer, lat - buffer,
            lng + buffer, lat + buffer,
        ])
        collection = _get_s2_collection(ee, region, start_date, end_date)
        capture_dates = _format_s2_capture_dates(collection, ee)
        if capture_dates:
            logger.info(
                "S2 capture dates for NDVI tiles %s,%s: %s",
                lat, lng, ", ".join(capture_dates),
            )

        if collection.size().getInfo() == 0:
            logger.warning(
                "No Sentinel-2 imagery for NDVI tiles %s,%s; attempting SAR fallback",
                lat, lng,
            )
            sar_tile = get_sentinel1_flood_tile_url(lat, lng, start_date, end_date)
            if sar_tile:
                sar_tile["source"] = "sentinel-1-flood"
                return sar_tile
            return None

        composite = collection.map(_cloud_mask_s2).median().updateMask(_cropland_mask(ee))
        ndvi = _compute_ndvi(composite)
        map_id = ndvi.getMapId({
            "min": -0.2,
            "max": 0.8,
            "palette": NDVI_PALETTE,
        })

        return {
            "tile_url": map_id["tile_fetcher"].url_format,
            "bounds": region.bounds().getInfo(),
            "source": "earth-engine",
            "capture_dates": capture_dates,
        }
    except Exception as exc:
        logger.error("NDVI tile generation failed: %s", exc)
        return None


def get_available_sentinel_dates(
    latitude: float,
    longitude: float,
    start_date: str = "2024-09-01",
    end_date: str = "2024-12-31",
):
    if not _ee_ready():
        return []

    try:
        ee = get_ee()
        point = ee.Geometry.Point([longitude, latitude])
        collection = _get_s2_collection(ee, point, start_date, end_date)

        def get_date(image):
            return ee.Feature(None, {
                "date": image.date().format("YYYY-MM-dd"),
                "cloud_cover": image.get("CLOUDY_PIXEL_PERCENTAGE"),
            })

        dates = collection.map(get_date).getInfo()
        available_dates = [
            {
                "date": f["properties"]["date"],
                "cloud_cover": float(f["properties"]["cloud_cover"]),
            }
            for f in dates.get("features", [])
        ]
        return sorted(available_dates, key=lambda x: x["date"])
    except Exception as exc:
        logger.error("Failed to fetch available dates: %s", exc)
        return []


def _cache_key(latitude: float, longitude: float, date: str, buffer_km: float) -> str:
    return f"{latitude:.4f}_{longitude:.4f}_{date}_{buffer_km}"


def get_cached_imagery(latitude: float, longitude: float, date: str, buffer_km: float = 5.0):
    key = _cache_key(latitude, longitude, date, buffer_km)
    entry = _tile_cache.get(key)
    if entry and time.time() - entry["cached_at"] < CACHE_TTL_SECONDS:
        return entry["data"]
    return None


def get_ndvi_for_parcel(parcel_polygon_coordinates: list, date: str) -> dict:
    """Compute mean NDVI within a farm polygon for the given date."""
    if not parcel_polygon_coordinates or len(parcel_polygon_coordinates) < 3:
        return {"ndvi": None, "actual_date": date, "source": "invalid_polygon"}

    target_date = datetime.strptime(date, "%Y-%m-%d")
    start = (target_date - timedelta(days=7)).strftime("%Y-%m-%d")
    end = (target_date + timedelta(days=7)).strftime("%Y-%m-%d")

    lats = [c[1] for c in parcel_polygon_coordinates]
    lngs = [c[0] for c in parcel_polygon_coordinates]
    center_lat = sum(lats) / len(lats)
    center_lng = sum(lngs) / len(lngs)

    ndvi = compute_ndvi_for_location(
        center_lat, center_lng, parcel_polygon_coordinates, start, end,
    )
    if isinstance(ndvi, dict):
        return {**ndvi, "ndvi": None, "actual_date": date, "source": "unavailable"}
    if ndvi is not None:
        return {"ndvi": ndvi, "actual_date": date, "source": "earth-engine"}

    return {"ndvi": None, "actual_date": date, "source": "unavailable"}


def get_sentinel_imagery(
    latitude: float,
    longitude: float,
    date: str,
    buffer_km: float = 5.0,
):
    """Fetch NDVI tile imagery for map overlay."""
    logger.info(
        "Fetching EE satellite imagery for date: %s, location: %s,%s, buffer_km: %s",
        date, latitude, longitude, buffer_km,
    )
    cached = get_cached_imagery(latitude, longitude, date, buffer_km)
    if cached:
        return cached

    target_date = datetime.strptime(date, "%Y-%m-%d")
    pre_start = (target_date - timedelta(days=20)).strftime("%Y-%m-%d")
    post_end = (target_date + timedelta(days=20)).strftime("%Y-%m-%d")

    tile_result = get_ndvi_map_tile_url(latitude, longitude, pre_start, post_end)
    if not tile_result:
        raise ValueError("No Sentinel-2 imagery available for this date and location")

    result = {
        "requested_date": date,
        "actual_date": date,
        "cloud_cover": 0.0,
        "tile_url": tile_result["tile_url"],
        "source": tile_result.get("source", "earth-engine"),
        "bounds": tile_result.get("bounds"),
    }
    _tile_cache[_cache_key(latitude, longitude, date, buffer_km)] = {
        "data": result,
        "cached_at": time.time(),
    }
    return result


def _save_ndvi_record(parcel_id: str, capture_date: str, ndvi_value: float) -> dict:
    """Persist an NDVI record to production DB or demo satellite_imagery cache."""
    from utils.database import execute_query, is_demo_mode, add_demo_satellite_record

    record = {
        "parcel_id": parcel_id,
        "capture_date": capture_date,
        "ndvi_value": ndvi_value,
        "data_source": "Sentinel-2",
    }

    if is_demo_mode():
        add_demo_satellite_record(record)
        return record

    execute_query(
        """
        INSERT INTO satellite_imagery (parcel_id, capture_date, ndvi_value, data_source)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (parcel_id, capture_date)
        DO UPDATE SET ndvi_value = EXCLUDED.ndvi_value, data_source = EXCLUDED.data_source
        """,
        (parcel_id, capture_date, ndvi_value, "Sentinel-2"),
    )
    return record


_scan_jobs: dict = {}
_scan_jobs_lock = threading.Lock()
_scan_results_cache: dict = {}


def get_scan_cache(municipality_id: str, satellite_date: str) -> list | None:
    """Return cached NDVI scan records for a municipality and date."""
    from utils.database import resolve_municipality_id
    key = f"{resolve_municipality_id(municipality_id)}:{satellite_date}"
    return _scan_results_cache.get(key)


def _get_demo_ndvi_for_date(data: dict, parcel_id: str, satellite_date: str) -> float | None:
    """Read NDVI for a parcel on a specific date from demo satellite_imagery."""
    target = str(satellite_date)[:10]
    exact = next(
        (
            s for s in data.get("satellite_imagery", [])
            if s["parcel_id"] == parcel_id and str(s["capture_date"])[:10] == target
        ),
        None,
    )
    if exact:
        return float(exact["ndvi_value"])
    return None


def _synthetic_ndvi_for_date(data: dict, parcel_id: str, satellite_date: str) -> float:
    """Deterministic NDVI when no exact-date record exists."""
    records = [
        s for s in data.get("satellite_imagery", [])
        if s["parcel_id"] == parcel_id
    ]
    exact = _get_demo_ndvi_for_date(data, parcel_id, satellite_date)
    if exact is not None:
        return exact

    if records:
        values = [float(r["ndvi_value"]) for r in records]
        mean = sum(values) / len(values)
        jitter = ((hash(f"{parcel_id}:{satellite_date}") % 100) - 50) / 1000.0
        return max(0.05, min(0.90, round(mean + jitter, 3)))

    jitter = ((hash(f"{parcel_id}:{satellite_date}") % 40) - 20) / 1000.0
    return max(0.05, min(0.90, round(0.45 + jitter, 3)))


def is_date_scanned(municipality_id: str, satellite_date: str) -> bool:
    """True when scan cache or pre-seeded farms.json records exist for this date."""
    from utils.database import resolve_municipality_id, is_demo_mode, _load_demo_data

    municipality_id = resolve_municipality_id(municipality_id)
    key = f"{municipality_id}:{satellite_date}"
    cached = _scan_results_cache.get(key) or []
    if len(cached) > 0:
        return True

    if is_demo_mode():
        target = str(satellite_date)[:10]
        data = _load_demo_data()
        mun_parcels = {
            f["id"]
            for f in data.get("farms", [])
            if f.get("municipality_id") == municipality_id
        }
        for record in data.get("satellite_imagery", []):
            if (
                record["parcel_id"] in mun_parcels
                and str(record["capture_date"])[:10] == target
            ):
                return True
    return False


def _demo_ndvi_for_scan(data: dict, parcel_id: str, scan_date: str) -> tuple[float, str]:
    """Resolve NDVI and health_status for a parcel on scan_date in demo mode."""
    target = str(scan_date)[:10]
    exact = next(
        (
            s for s in data.get("satellite_imagery", [])
            if s["parcel_id"] == parcel_id and str(s["capture_date"])[:10] == target
        ),
        None,
    )
    if exact:
        ndvi = float(exact["ndvi_value"])
    else:
        records = [s for s in data.get("satellite_imagery", []) if s["parcel_id"] == parcel_id]
        if records:
            mean = sum(float(r["ndvi_value"]) for r in records) / len(records)
        else:
            mean = 0.65
        offset = (hash(parcel_id + scan_date) % 100) / 1000.0
        ndvi = max(0.05, min(0.90, round(mean + offset, 3)))

    if ndvi >= 0.5:
        health = "healthy"
    elif ndvi >= 0.3:
        health = "watch"
    else:
        health = "critical"
    return ndvi, health


def _run_scan_job_demo(job_id: str, municipality_id: str, satellite_date: str, farms: list) -> None:
    """Fast demo-mode NDVI scan with batched persistence and visible progress."""
    import json
    from pathlib import Path
    from utils.database import batch_add_demo_satellite_records, resolve_municipality_id

    municipality_id = resolve_municipality_id(municipality_id)

    def _update_job(**fields):
        with _scan_jobs_lock:
            if job_id not in _scan_jobs:
                return
            _scan_jobs[job_id].update(fields)

    try:
        _update_job(status="running", progress=10, message="Starting scan")

        data_path = Path(__file__).resolve().parent.parent.parent / "data" / "farms.json"
        with open(data_path, encoding="utf-8") as f:
            data = json.load(f)

        mun_farms = [
            f for f in data.get("farms", [])
            if f.get("municipality_id") == municipality_id
        ]
        if not mun_farms:
            mun_farms = farms
        total = max(len(mun_farms), 1)

        _update_job(
            status="running",
            progress=20,
            message=f"Found {len(mun_farms)} farm parcels",
            total_farms=len(mun_farms),
        )

        results_by_parcel: dict = {}
        pending_records: list[dict] = []

        for index, farm in enumerate(mun_farms):
            parcel_id = farm.get("id") or farm.get("parcel_id")
            farmer_name = farm.get("farmer_name", parcel_id)
            ndvi, health = _demo_ndvi_for_scan(data, parcel_id, satellite_date)
            record = {
                "parcel_id": parcel_id,
                "capture_date": satellite_date,
                "ndvi_value": ndvi,
                "health_status": health,
                "data_source": "Sentinel-2",
            }
            results_by_parcel[parcel_id] = record
            pending_records.append(record)

            progress = 20 + int(((index + 1) / total) * 65)
            _update_job(
                status="running",
                progress=progress,
                message=f"Scanning {farmer_name}",
                current_farm=farmer_name,
                completed_farms=index + 1,
            )

        _update_job(status="running", progress=90, message="Saving records")

        cache_key = f"{municipality_id}:{satellite_date}"
        _scan_results_cache[cache_key] = pending_records

        if pending_records:
            batch_add_demo_satellite_records(pending_records)

        _update_job(
            status="completed",
            progress=100,
            message="Scan complete",
            results=results_by_parcel,
            ndvi_records=pending_records,
            scanned_farms=list(results_by_parcel.keys()),
            completed_farms=len(results_by_parcel),
            failed_farms=0,
            current_farm=None,
        )
        logger.info("Demo NDVI scan job %s complete: %d farms", job_id, len(results_by_parcel))
    except Exception as exc:
        logger.error("NDVI scan job %s failed: %s", job_id, exc)
        _update_job(
            status="failed",
            progress=0,
            message="Scan failed. Please try again.",
            error=str(exc),
        )


def _run_scan_job(job_id: str, municipality_id: str, satellite_date: str, farms: list) -> None:
    import os
    from utils.database import is_demo_mode

    if is_demo_mode() or os.environ.get("DATABASE_URL", "demo") in ("demo", "", "none"):
        _run_scan_job_demo(job_id, municipality_id, satellite_date, farms)
        return
    """Background worker: scan farms sequentially and update job state."""
    target = datetime.strptime(satellite_date, "%Y-%m-%d")
    start_date = (target - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = (target + timedelta(days=7)).strftime("%Y-%m-%d")

    scanned: list[str] = []
    failed: list[dict] = []
    results: list[dict] = []

    for farm in farms:
        parcel_id = farm["id"]
        farmer_name = farm.get("farmer_name", parcel_id)

        with _scan_jobs_lock:
            if job_id in _scan_jobs:
                job = _scan_jobs[job_id]
                job["current_farm"] = farmer_name
                total = job.get("total_farms") or len(farms) or 1
                job["progress"] = max(job.get("progress", 0), int((len(scanned) / total) * 90))

        polygon = farm.get("polygon")
        if isinstance(polygon, str):
            import json
            polygon = json.loads(polygon)

        if not polygon or len(polygon) < 3:
            entry = {"farm_id": parcel_id, "reason": "Farm polygon is missing or invalid"}
            failed.append(entry)
            with _scan_jobs_lock:
                if job_id in _scan_jobs:
                    _scan_jobs[job_id]["failed_farms"] = len(failed)
            continue

        try:
            lat = float(farm["latitude"])
            lng = float(farm["longitude"])
            ndvi = compute_ndvi_for_location(lat, lng, polygon, start_date, end_date)

            if isinstance(ndvi, dict):
                entry = {
                    "farm_id": parcel_id,
                    "reason": ndvi.get("reason", "no_imagery"),
                    "error": ndvi.get("error", "no_imagery"),
                }
                failed.append(entry)
                continue

            if ndvi is None:
                failed.append({"farm_id": parcel_id, "reason": "NDVI computation unavailable"})
                continue

            saved = _save_ndvi_record(parcel_id, satellite_date, float(ndvi))
            scanned.append(parcel_id)
            results.append(saved)

            with _scan_jobs_lock:
                if job_id in _scan_jobs:
                    job = _scan_jobs[job_id]
                    job["completed_farms"] = len(scanned)
                    job["results"] = list(results)
                    job["failed_farms"] = len(failed)
                    total = job.get("total_farms") or len(farms) or 1
                    job["progress"] = min(99, int((len(scanned) / total) * 100))
        except Exception as exc:
            logger.warning("NDVI scan failed for farm %s: %s", parcel_id, exc)
            failed.append({"farm_id": parcel_id, "reason": str(exc)})

    with _scan_jobs_lock:
        if job_id not in _scan_jobs:
            return
        job = _scan_jobs[job_id]
        job["status"] = "completed" if scanned else "failed"
        job["progress"] = 100
        job["completed_farms"] = len(scanned)
        job["failed_farms"] = len(failed)
        job["scanned_farms"] = scanned
        job["failed_farm_details"] = failed
        job["ndvi_records"] = results
        job["current_farm"] = None
        if scanned:
            cache_key = f"{municipality_id}:{satellite_date}"
            _scan_results_cache[cache_key] = results
        if not scanned:
            job["error"] = "NDVI scan failed for all farms"
        logger.info(
            "NDVI scan job %s complete: %d scanned, %d failed",
            job_id, len(scanned), len(failed),
        )


def start_ndvi_scan_job(municipality_id: str, satellite_date: str) -> dict:
    """Create a background scan job and return immediately."""
    from utils.database import execute_query, resolve_municipality_id

    municipality_id = resolve_municipality_id(municipality_id)
    farms = execute_query(
        """
        SELECT id, farmer_name, latitude, longitude, polygon
        FROM farm_parcels
        WHERE municipality_id = %s
        ORDER BY id
        """,
        (municipality_id,),
        fetch_all=True,
    ) or []

    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "status": "running",
        "progress": 0,
        "completed_farms": 0,
        "total_farms": len(farms),
        "current_farm": farms[0]["farmer_name"] if farms else None,
        "results": [],
        "failed_farms": 0,
        "failed_farm_details": [],
        "scanned_farms": [],
        "ndvi_records": [],
        "error": None,
        "scan_date": satellite_date,
        "municipality_id": municipality_id,
    }

    with _scan_jobs_lock:
        _scan_jobs[job_id] = job

    if not farms:
        with _scan_jobs_lock:
            _scan_jobs[job_id]["status"] = "failed"
            _scan_jobs[job_id]["error"] = "No farms found for municipality"
        return {"job_id": job_id, "status": "failed", "total_farms": 0}

    thread = threading.Thread(
        target=_run_scan_job,
        args=(job_id, municipality_id, satellite_date, farms),
        daemon=True,
        name=f"ndvi-scan-{job_id[:8]}",
    )
    thread.start()

    return {"job_id": job_id, "status": "started", "total_farms": len(farms)}


def get_ndvi_scan_status(job_id: str) -> dict | None:
    with _scan_jobs_lock:
        job = _scan_jobs.get(job_id)
        return copy.deepcopy(job) if job else None


def scan_municipality_ndvi(municipality_id: str, satellite_date: str) -> dict:
    """Synchronous scan — kept for tests; production uses start_ndvi_scan_job."""
    from utils.database import execute_query, resolve_municipality_id

    municipality_id = resolve_municipality_id(municipality_id)
    farms = execute_query(
        """
        SELECT id, farmer_name, latitude, longitude, polygon
        FROM farm_parcels
        WHERE municipality_id = %s
        ORDER BY id
        """,
        (municipality_id,),
        fetch_all=True,
    ) or []

    job_id = str(uuid.uuid4())
    with _scan_jobs_lock:
        _scan_jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "completed_farms": 0,
            "total_farms": len(farms),
            "results": [],
            "failed_farms": 0,
            "scanned_farms": [],
            "ndvi_records": [],
            "scan_date": satellite_date,
        }
    _run_scan_job(job_id, municipality_id, satellite_date, farms)
    with _scan_jobs_lock:
        job = _scan_jobs.get(job_id, {})
    return {
        "scanned_farms": job.get("scanned_farms", []),
        "failed_farms": job.get("failed_farm_details", []),
        "ndvi_records": job.get("ndvi_records", []),
        "scan_date": satellite_date,
    }


def get_ndvi_tiles_for_date(lat: float, lng: float, date: str) -> dict | None:
    """NDVI tiles for dashboard — pre/post windows around selected date."""
    target = datetime.strptime(date, "%Y-%m-%d")
    if target.month <= 10 and target.year == 2024:
        start = "2024-10-01"
        end = "2024-10-20"
    else:
        start = "2024-10-22"
        end = "2024-11-15"

    tile = get_ndvi_map_tile_url(lat, lng, start, end)
    if not tile:
        tile = get_ndvi_map_tile_url(
            lat, lng,
            (target - timedelta(days=15)).strftime("%Y-%m-%d"),
            (target + timedelta(days=15)).strftime("%Y-%m-%d"),
        )
    if tile:
        tile["actual_date"] = date
        tile["start_date"] = start
        tile["end_date"] = end
    return tile