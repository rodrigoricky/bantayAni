"""Sentinel Hub Process + Statistics API with progressive cloud fallback and demo imagery."""

import logging
import math
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

CLIENT_ID = os.getenv("SENTINEL_HUB_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SENTINEL_HUB_CLIENT_SECRET", "")
TOKEN_URL = "https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token"
PROCESS_URL = "https://services.sentinel-hub.com/api/v1/process"
STATISTICS_URL = "https://services.sentinel-hub.com/api/v1/statistics"
CATALOG_URL = "https://services.sentinel-hub.com/api/v1/catalog/1.0.0/search"

_token_cache = {"token": None, "expires_at": 0}
_ndvi_cache: dict = {}
CLOUD_THRESHOLDS = [20, 40, 60, 80]
DATE_WINDOW_DAYS = 15

PUBLIC_ROOT = Path(__file__).resolve().parent.parent.parent / "frontend" / "public"
PREVIEW_DIR = PUBLIC_ROOT / "satellite-previews"

DISASTER_DATE = "2024-10-22"

DEMO_DATES = [
    {"date": "2024-10-05", "cloud_cover": 5.0},
    {"date": "2024-10-14", "cloud_cover": 8.0},
    {"date": "2024-10-25", "cloud_cover": 8.2},
    {"date": "2024-11-01", "cloud_cover": 12.0},
    {"date": "2024-11-08", "cloud_cover": 15.0},
    {"date": "2024-11-15", "cloud_cover": 9.8},
]

TRUE_COLOR_SCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{
      bands: ["B04", "B03", "B02", "SCL", "dataMask"],
      units: ["REFLECTANCE", "REFLECTANCE", "REFLECTANCE", "DN", "DN"]
    }],
    output: { bands: 4, sampleType: "AUTO" }
  };
}
function isCloud(scl) {
  return scl === 3 || scl === 8 || scl === 9 || scl === 10 || scl === 11;
}
function evaluatePixel(sample) {
  if (sample.dataMask === 0 || isCloud(sample.SCL)) return [0, 0, 0, 0];
  return [3.5 * sample.B04, 3.5 * sample.B03, 3.5 * sample.B02, 1];
}
"""

NDVI_SCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{
      bands: ["B04", "B08", "SCL", "dataMask"],
      units: ["REFLECTANCE", "REFLECTANCE", "DN", "DN"]
    }],
    output: { bands: 4, sampleType: "AUTO" }
  };
}
function isCloud(scl) {
  return scl === 3 || scl === 8 || scl === 9 || scl === 10 || scl === 11;
}
function evaluatePixel(sample) {
  if (sample.dataMask === 0 || isCloud(sample.SCL)) return [0, 0, 0, 0];
  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
  if (ndvi < -1) return [0, 0, 0, 0];
  if (ndvi < 0) return [0.35, 0.2, 0.1, 1];
  if (ndvi < 0.2) return [0.9, 0.82, 0.55, 1];
  if (ndvi < 0.4) return [0.95, 0.85, 0.3, 1];
  if (ndvi < 0.6) return [0.55, 0.85, 0.45, 1];
  return [0.1, 0.55, 0.15, 1];
}
"""

SENTINEL1_SCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{
      bands: ["VV", "VH"],
      units: ["DECIBELS", "DECIBELS"]
    }],
    output: { bands: 3, sampleType: "AUTO" }
  };
}
function evaluatePixel(sample) {
  if (sample.VV === undefined || sample.VH === undefined) return [0, 0, 0];
  let vvNorm = Math.max(0, Math.min(1, (sample.VV + 25) / 25));
  let vhNorm = Math.max(0, Math.min(1, (sample.VH + 30) / 30));
  let flood = sample.VV < -15 ? 1.0 : 0.0;
  return [flood * 0.2 + vvNorm * 0.8, vhNorm * 0.5, flood];
}
"""

NDVI_STATS_SCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{
      bands: ["B04", "B08", "SCL", "dataMask"],
      units: ["REFLECTANCE", "REFLECTANCE", "DN", "DN"]
    }],
    output: { bands: 1, sampleType: "FLOAT32" }
  };
}
function isCloud(scl) {
  return scl === 3 || scl === 8 || scl === 9 || scl === 10 || scl === 11;
}
function evaluatePixel(sample) {
  if (sample.dataMask === 0 || isCloud(sample.SCL)) return [NaN];
  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
  return [ndvi];
}
"""


def is_live_mode() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET)


def _configured():
    return is_live_mode()


def _get_token():
    if not _configured():
        return None
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]
    try:
        with httpx.Client(timeout=30) as client:
            res = client.post(
                TOKEN_URL,
                data={"grant_type": "client_credentials", "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
            )
            res.raise_for_status()
            data = res.json()
            _token_cache["token"] = data["access_token"]
            _token_cache["expires_at"] = now + int(data.get("expires_in", 3600))
            return _token_cache["token"]
    except Exception as exc:
        logger.warning("Sentinel Hub auth failed: %s", exc)
        return None


FARM_LEVEL_BUFFER_KM = 0.5


def _bbox(lat: float, lng: float, buffer_km: float = FARM_LEVEL_BUFFER_KM):
    """Build a square bbox for farm-level imagery (default 0.5 km buffer)."""
    deg = buffer_km / 111.0
    bbox = [lng - deg, lat - deg, lng + deg, lat + deg]
    width_km = (bbox[2] - bbox[0]) * 111.0 * max(abs(math.cos(math.radians(lat))), 0.01)
    height_km = (bbox[3] - bbox[1]) * 111.0
    logger.info(
        "BBox for %s,%s buffer_km=%.2f → [%.6f, %.6f, %.6f, %.6f] (%.2f × %.2f km)",
        lat, lng, buffer_km, *bbox, width_km, height_km,
    )
    return bbox


def _polygon_to_geojson(polygon_coords: list) -> dict:
    """Convert [[lng, lat], ...] farm polygon to GeoJSON."""
    if not polygon_coords:
        return {"type": "Polygon", "coordinates": [[]]}
    ring = [[float(p[0]), float(p[1])] for p in polygon_coords]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _catalog_search(lat: float, lng: float, start_date: str, end_date: str, max_cloud: float = 20.0):
    if not _configured():
        return [d for d in DEMO_DATES if start_date <= d["date"] <= end_date and d["cloud_cover"] < max_cloud]

    token = _get_token()
    if not token:
        return [d for d in DEMO_DATES if start_date <= d["date"] <= end_date]

    body = {
        "collections": ["sentinel-2-l2a"],
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "intersects": {"type": "Point", "coordinates": [lng, lat]},
        "limit": 100,
        "filter": f"eo:cloud_cover < {max_cloud}",
        "filter-lang": "cql2-text",
    }
    try:
        with httpx.Client(timeout=30) as client:
            res = client.post(CATALOG_URL, json=body, headers={"Authorization": f"Bearer {token}"})
            res.raise_for_status()
            features = res.json().get("features", [])
            dates = []
            for f in features:
                dt = f.get("properties", {}).get("datetime", "")[:10]
                cloud = f.get("properties", {}).get("eo:cloud_cover", 0)
                if dt:
                    dates.append({"date": dt, "cloud_cover": float(cloud)})
            dates = sorted({d["date"]: d for d in dates}.values(), key=lambda x: x["date"])
            if dates:
                return dates
    except Exception as exc:
        logger.warning("Sentinel Hub catalog failed (max_cloud=%s): %s", max_cloud, exc)

    return [d for d in DEMO_DATES if start_date <= d["date"] <= end_date and d["cloud_cover"] < max_cloud]


def _find_best_date(lat: float, lng: float, requested_date: str) -> tuple[str, str, float]:
    """Progressive cloud fallback within ±15 days of requested date."""
    target = datetime.strptime(requested_date, "%Y-%m-%d")
    start = (target - timedelta(days=DATE_WINDOW_DAYS)).strftime("%Y-%m-%d")
    end = (target + timedelta(days=DATE_WINDOW_DAYS)).strftime("%Y-%m-%d")

    for max_cloud in CLOUD_THRESHOLDS:
        dates = _catalog_search(lat, lng, start, end, max_cloud=max_cloud)
        if dates:
            nearest = min(
                dates,
                key=lambda d: abs((datetime.strptime(d["date"], "%Y-%m-%d") - target).days),
            )
            logger.info(
                "Selected date %s for request %s (cloud %.1f%%, threshold %s%%)",
                nearest["date"], requested_date, nearest["cloud_cover"], max_cloud,
            )
            return requested_date, nearest["date"], nearest["cloud_cover"]

    if DEMO_DATES:
        nearest = min(DEMO_DATES, key=lambda d: abs((datetime.strptime(d["date"], "%Y-%m-%d") - target).days))
        return requested_date, nearest["date"], nearest["cloud_cover"]

    return requested_date, requested_date, 0.0


def _nearest_low_cloud_date(lat: float, lng: float, requested_date: str):
    _, actual, _ = _find_best_date(lat, lng, requested_date)
    return requested_date, actual


def get_available_dates(lat: float, lng: float, start_date: str, end_date: str):
    return _catalog_search(lat, lng, start_date, end_date, max_cloud=80.0)


def _demo_month_key(date_str: str) -> str | None:
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        if dt.year == 2024 and dt.month == 10:
            return "oct"
        if dt.year == 2024 and dt.month == 11:
            return "nov"
    except ValueError:
        pass
    return None


def _prefetched_demo_bytes(requested_date: str, image_type: str) -> bytes | None:
    month = _demo_month_key(requested_date)
    if not month:
        return None
    suffix = "rgb" if image_type == "true-color" else "ndvi"
    path = PREVIEW_DIR / f"kibawe_{month}_{suffix}.png"
    if path.exists():
        logger.info("Serving prefetched demo image %s for date %s", path.name, requested_date)
        return path.read_bytes()
    return None


def _demo_image_bytes(date: str | None = None):
    preview_dirs = [PREVIEW_DIR, PUBLIC_ROOT / "images" / "satellite"]
    candidates = []
    for directory in preview_dirs:
        if not directory.exists():
            continue
        candidates.extend(directory.glob("*.png"))
        candidates.extend(directory.glob("*.jpg"))
    if date:
        month = _demo_month_key(date)
        if month:
            for suffix in ("rgb", "ndvi"):
                p = PREVIEW_DIR / f"kibawe_{month}_{suffix}.png"
                if p.exists():
                    return p.read_bytes()
        dated = [p for p in candidates if date in p.name]
        if dated:
            candidates = dated
    if not candidates:
        return None
    with open(sorted(candidates)[0], "rb") as f:
        return f.read()


def _is_image_invalid(content: bytes) -> bool:
    """True when image is black, flat gray, or too small to display."""
    if not content or len(content) < 500:
        return True
    try:
        from PIL import Image
        import io
        import statistics

        img = Image.open(io.BytesIO(content)).convert("L")
        pixels = list(img.getdata())
        if not pixels:
            return True
        mean = sum(pixels) / len(pixels)
        std = statistics.pstdev(pixels) if len(pixels) > 1 else 0.0
        if mean < 10 or std < 5:
            return True

        rgba = Image.open(io.BytesIO(content)).convert("RGBA")
        rgba_pixels = list(rgba.getdata())
        dark = sum(
            1 for r, g, b, a in rgba_pixels
            if a < 10 or (r < 20 and g < 20 and b < 20)
        )
        return (dark / len(rgba_pixels)) >= 0.95
    except Exception:
        return True


def _static_preview_bytes(requested_date: str, image_type: str) -> bytes | None:
    """Date-aware static preview: pre-disaster vs post-disaster imagery."""
    try:
        target = datetime.strptime(str(requested_date)[:10], "%Y-%m-%d")
        disaster = datetime.strptime(DISASTER_DATE, "%Y-%m-%d")
        is_pre = target < disaster
    except ValueError:
        is_pre = True

    suffix = "rgb" if image_type == "true-color" else "ndvi"
    month = "oct" if is_pre else "nov"
    path = PREVIEW_DIR / f"kibawe_{month}_{suffix}.png"
    if path.exists():
        logger.info("Serving date-aware static preview %s for %s", path.name, requested_date)
        return path.read_bytes()

    label = "before" if is_pre else "after"
    for name in (f"NAGA-001_{label}.png", f"BUK-001_{label}.png"):
        candidate = PREVIEW_DIR / name
        if candidate.exists():
            logger.info("Serving static preview %s for %s", name, requested_date)
            return candidate.read_bytes()
    return _demo_image_bytes(requested_date)


def _earth_engine_thumbnail(lat: float, lng: float, image_type: str) -> bytes | None:
    try:
        from services.earth_engine import get_ee, is_ee_available
        ee = get_ee()
        if not is_ee_available() or ee is None:
            return None
        bbox = _bbox(lat, lng, FARM_LEVEL_BUFFER_KM)
        region = ee.Geometry.Rectangle([bbox[0], bbox[1], bbox[2], bbox[3]])
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(region)
            .filterDate("2024-09-01", "2024-12-31")
            .sort("CLOUDY_PIXEL_PERCENTAGE")
            .first()
        )
        image = ee.Image(collection)
        if image_type == "ndvi":
            thumb = image.normalizedDifference(["B8", "B4"]).visualize(min=0, max=0.8, palette=["brown", "yellow", "green"])
        else:
            thumb = image.select(["B4", "B3", "B2"]).visualize(min=0, max=3000)
        url = thumb.getThumbURL({"dimensions": 256, "region": region, "format": "png"})
        with httpx.Client(timeout=60) as client:
            res = client.get(url)
            res.raise_for_status()
            return res.content
    except Exception as exc:
        logger.warning("Earth Engine thumbnail fallback failed: %s", exc)
        return None


def _post_sentinel_hub(token: str, body: dict) -> bytes:
    with httpx.Client(timeout=60) as client:
        res = client.post(
            PROCESS_URL,
            json=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        logger.info(
            "Sentinel Hub response: status=%s bytes=%d",
            res.status_code, len(res.content or b""),
        )
        if res.status_code >= 500:
            res.raise_for_status()
        res.raise_for_status()
        return res.content


def _process_image(token: str, lat: float, lng: float, actual_date: str, image_type: str, buffer_km: float, max_cloud: float):
    target = datetime.strptime(actual_date, "%Y-%m-%d")
    evalscript = TRUE_COLOR_SCRIPT if image_type == "true-color" else NDVI_SCRIPT
    body = {
        "input": {
            "bounds": {"bbox": _bbox(lat, lng, buffer_km), "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {
                        "from": (target - timedelta(days=14)).strftime("%Y-%m-%dT00:00:00Z"),
                        "to": (target + timedelta(days=14)).strftime("%Y-%m-%dT23:59:59Z"),
                    },
                    "maxCloudCoverage": int(max_cloud),
                    "mosaickingOrder": "mostRecent",
                },
            }],
        },
        "output": {"width": 512, "height": 512, "responses": [{"identifier": "default", "format": {"type": "image/png"}}]},
        "evalscript": evalscript,
    }
    logger.info(
        "Sentinel Hub request: POST %s lat=%s lng=%s date=%s type=%s",
        PROCESS_URL, lat, lng, actual_date, image_type,
    )

    last_exc = None
    for attempt in range(2):
        try:
            content = _post_sentinel_hub(token, body)
            if not _is_image_invalid(content):
                return content
            logger.warning("Sentinel Hub image invalid for %s,%s on %s", lat, lng, actual_date)
            return None
        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            last_exc = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if attempt == 0 and (isinstance(exc, httpx.TimeoutException) or (status and status >= 500)):
                logger.warning("Sentinel Hub attempt %d failed, retrying in 2s: %s", attempt + 1, exc)
                time.sleep(2)
                continue
            raise
        except Exception as exc:
            last_exc = exc
            raise
    if last_exc:
        raise last_exc
    return None


def _fetch_imagery_with_fallback(
    lat: float,
    lng: float,
    requested_date: str,
    actual_date: str,
    image_type: str,
    buffer_km: float,
    token: str | None = None,
) -> dict | None:
    """Try Sentinel Hub, then Earth Engine, then static preview."""
    if token:
        for max_cloud in CLOUD_THRESHOLDS:
            try:
                content = _process_image(token, lat, lng, actual_date, image_type, buffer_km, max_cloud)
                if content and not _is_image_invalid(content):
                    return {
                        "png_bytes": content,
                        "source": "sentinel-hub",
                        "requested_date": requested_date,
                        "actual_date": actual_date,
                    }
            except Exception as exc:
                logger.warning("Sentinel Hub process failed (cloud %s%%): %s", max_cloud, exc)

    ee_bytes = _earth_engine_thumbnail(lat, lng, image_type)
    if ee_bytes and not _is_image_invalid(ee_bytes):
        logger.info("Using Earth Engine thumbnail fallback for %s,%s", lat, lng)
        return {
            "png_bytes": ee_bytes,
            "source": "earth-engine",
            "requested_date": requested_date,
            "actual_date": actual_date,
        }

    static = _static_preview_bytes(requested_date, image_type)
    if static and not _is_image_invalid(static):
        return {
            "png_bytes": static,
            "source": "static-preview",
            "requested_date": requested_date,
            "actual_date": actual_date,
        }
    return None


def get_sentinel1_image(
    lat: float,
    lng: float,
    date: str,
    buffer_km: float = FARM_LEVEL_BUFFER_KM,
):
    """Fetch Sentinel-1 GRD SAR image (VV/VH) for farm-level flood monitoring."""
    if buffer_km != FARM_LEVEL_BUFFER_KM:
        buffer_km = FARM_LEVEL_BUFFER_KM
        logger.info("Enforcing farm-level buffer_km=%.1f for Sentinel-1 image", buffer_km)

    logger.info(
        "Fetching Sentinel-1 SAR for date: %s, location: %s,%s, buffer_km: %s",
        date, lat, lng, buffer_km,
    )

    requested_date, actual_date, cloud_cover = _find_best_date(lat, lng, date)

    if _configured():
        token = _get_token()
        if token:
            target = datetime.strptime(actual_date, "%Y-%m-%d")
            body = {
                "input": {
                    "bounds": {
                        "bbox": _bbox(lat, lng, buffer_km),
                        "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                    },
                    "data": [{
                        "type": "sentinel-1-grd",
                        "dataFilter": {
                            "timeRange": {
                                "from": (target - timedelta(days=3)).strftime("%Y-%m-%dT00:00:00Z"),
                                "to": (target + timedelta(days=3)).strftime("%Y-%m-%dT23:59:59Z"),
                            },
                            "polarization": "VV VH",
                            "acquisitionMode": "IW",
                        },
                    }],
                },
                "output": {
                    "width": 512,
                    "height": 512,
                    "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
                },
                "evalscript": SENTINEL1_SCRIPT,
            }
            try:
                with httpx.Client(timeout=60) as client:
                    res = client.post(
                        PROCESS_URL,
                        json=body,
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    )
                    res.raise_for_status()
                    return {
                        "png_bytes": res.content,
                        "source": "sentinel-hub-s1",
                        "requested_date": requested_date,
                        "actual_date": actual_date,
                        "cloud_cover": cloud_cover,
                    }
            except Exception as exc:
                logger.warning("Sentinel-1 Hub process failed: %s", exc)

    raise RuntimeError("Sentinel-1 SAR imagery unavailable")


def get_sentinel_image_png(
    lat: float,
    lng: float,
    date: str,
    image_type: str = "true-color",
    buffer_km: float = FARM_LEVEL_BUFFER_KM,
    force_live: bool = False,
):
    if buffer_km != FARM_LEVEL_BUFFER_KM:
        buffer_km = FARM_LEVEL_BUFFER_KM
        logger.info("Enforcing farm-level buffer_km=%.1f for Sentinel-2 image", buffer_km)

    logger.info(
        "Fetching Sentinel imagery for date: %s, location: %s,%s, type: %s, buffer_km: %s",
        date, lat, lng, image_type, buffer_km,
    )

    prefetched = None if force_live else _prefetched_demo_bytes(date, image_type)
    if prefetched:
        return {
            "png_bytes": prefetched,
            "source": "prefetched-demo",
            "requested_date": date,
            "actual_date": "2025-10-14" if _demo_month_key(date) == "oct" else "2025-11-18",
        }

    requested_date, actual_date, cloud_cover = _find_best_date(lat, lng, date)

    token = _get_token() if _configured() else None
    result = _fetch_imagery_with_fallback(
        lat, lng, requested_date, actual_date, image_type, buffer_km, token=token,
    )
    if result:
        result["cloud_cover"] = cloud_cover
        return result

    static = _static_preview_bytes(date, image_type) or _static_preview_bytes(actual_date, image_type)
    if static:
        return {
            "png_bytes": static,
            "source": "static-preview",
            "requested_date": requested_date,
            "actual_date": actual_date,
            "cloud_cover": cloud_cover,
        }

    raise RuntimeError("Sentinel Hub imagery unavailable")


def save_verification_images(
    parcel_id: str,
    lat: float,
    lng: float,
    before_date: str,
    after_date: str,
    buffer_km: float = FARM_LEVEL_BUFFER_KM,
) -> tuple[str, str]:
    """Fetch and save before/after true-color images for claim verification."""
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    before_path = PREVIEW_DIR / f"{parcel_id}_before.png"
    after_path = PREVIEW_DIR / f"{parcel_id}_after.png"

    try:
        before_result = get_sentinel_image_png(
            lat, lng, before_date, "true-color", buffer_km=buffer_km, force_live=True,
        )
        before_path.write_bytes(before_result["png_bytes"])
    except Exception as exc:
        logger.warning("Failed to save before image for %s: %s", parcel_id, exc)

    try:
        after_result = get_sentinel_image_png(
            lat, lng, after_date, "true-color", buffer_km=buffer_km, force_live=True,
        )
        after_path.write_bytes(after_result["png_bytes"])
    except Exception as exc:
        logger.warning("Failed to save after image for %s: %s", parcel_id, exc)

    return (
        f"/satellite-previews/{parcel_id}_before.png",
        f"/satellite-previews/{parcel_id}_after.png",
    )


def compute_ndvi_for_polygon(polygon_coords: list, date: str, window_days: int = 7) -> dict | None:
    """Compute mean NDVI over a farm polygon via Sentinel Hub Statistics API."""
    if not polygon_coords or len(polygon_coords) < 3:
        return None

    cache_key = f"{hash(str(polygon_coords))}_{date}"
    if cache_key in _ndvi_cache:
        return _ndvi_cache[cache_key]

    if not _configured():
        return None

    token = _get_token()
    if not token:
        return None

    target = datetime.strptime(date[:10], "%Y-%m-%d")
    time_from = (target - timedelta(days=window_days)).strftime("%Y-%m-%dT00:00:00Z")
    time_to = (target + timedelta(days=window_days)).strftime("%Y-%m-%dT23:59:59Z")
    geometry = _polygon_to_geojson(polygon_coords)

    body = {
        "input": {
            "bounds": {
                "geometry": geometry,
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
            },
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {"from": time_from, "to": time_to},
                    "maxCloudCoverage": 80,
                    "mosaickingOrder": "leastCC",
                },
            }],
        },
        "aggregation": {
            "timeRange": {"from": time_from, "to": time_to},
            "aggregationInterval": {"of": "P1D"},
            "evalscript": NDVI_STATS_SCRIPT,
            "resx": "10m",
            "resy": "10m",
        },
        "calculations": {
            "default": {"statistics": ["mean", "sampleCount"]},
        },
    }

    try:
        logger.info("Computing live NDVI for polygon on date %s", date)
        with httpx.Client(timeout=90) as client:
            res = client.post(
                STATISTICS_URL,
                json=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            res.raise_for_status()
            data = res.json()

        mean_values = []
        for entry in data.get("data", []):
            stats = entry.get("outputs", {}).get("default", {}).get("bands", {}).get("B0", {}).get("stats", {})
            mean = stats.get("mean")
            count = stats.get("sampleCount", 0)
            if mean is not None and count and count > 0 and mean == mean:
                mean_values.append(float(mean))

        if not mean_values:
            logger.warning("Statistics API returned no valid NDVI for date %s", date)
            return None

        result = {
            "ndvi": round(sum(mean_values) / len(mean_values), 3),
            "actual_date": date,
            "source": "live",
            "sample_count": len(mean_values),
        }
        _ndvi_cache[cache_key] = result
        logger.info("Live NDVI computed: %.3f for date %s", result["ndvi"], date)
        return result
    except Exception as exc:
        logger.warning("Sentinel Hub Statistics API failed: %s", exc)
        return None


def compute_ndvi_for_date_range(polygon_coords: list, start_date: str, end_date: str) -> dict | None:
    """Compute mean NDVI over a date range (for claim before/after windows)."""
    mid = datetime.strptime(start_date[:10], "%Y-%m-%d") + (
        datetime.strptime(end_date[:10], "%Y-%m-%d") - datetime.strptime(start_date[:10], "%Y-%m-%d")
    ) / 2
    return compute_ndvi_for_polygon(polygon_coords, mid.strftime("%Y-%m-%d"), window_days=max(7, (datetime.strptime(end_date[:10], "%Y-%m-%d") - datetime.strptime(start_date[:10], "%Y-%m-%d")).days // 2))