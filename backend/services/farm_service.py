import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from utils.database import execute_query, is_demo_mode, _load_demo_data, _demo_write_lock
from utils.ndvi import classify_health_status

logger = logging.getLogger(__name__)

MUNICIPALITY_ID_CONFIG = {
    "camarines-naga": {"parcel_prefix": "NAGA", "rsbsa_region": "NAG", "rsbsa_year": 2024},
    "camarines-pili": {"parcel_prefix": "PILI", "rsbsa_region": "PIL", "rsbsa_year": 2024},
    "camarines-iriga": {"parcel_prefix": "IRIGA", "rsbsa_region": "IRI", "rsbsa_year": 2024},
}

def _municipality_config(municipality_id: str) -> dict:
    from utils.database import resolve_municipality_id
    municipality_id = resolve_municipality_id(municipality_id)
    if municipality_id in MUNICIPALITY_ID_CONFIG:
        return MUNICIPALITY_ID_CONFIG[municipality_id]
    code = municipality_id.split("-")[-1].upper()[:4]
    return {"parcel_prefix": code, "rsbsa_region": code[:3], "rsbsa_year": datetime.now().year}


def _parse_id_suffix(value: str) -> int | None:
    if not value:
        return None
    match = re.search(r"-(\d+)$", value.strip())
    return int(match.group(1)) if match else None


def _existing_farms_for_municipality(municipality_id: str) -> list:
    from utils.database import resolve_municipality_id
    municipality_id = resolve_municipality_id(municipality_id)
    if is_demo_mode():
        data = _load_demo_data()
        return [f for f in data.get("farms", []) if f.get("municipality_id") == municipality_id]
    rows = execute_query(
        "SELECT id, rsbsa_number FROM farm_parcels WHERE municipality_id = %s",
        (municipality_id,),
        fetch_all=True,
    )
    return rows or []


def _next_parcel_id(municipality_id: str, existing_ids: set | None = None) -> str:
    config = _municipality_config(municipality_id)
    prefix = config["parcel_prefix"]
    farms = _existing_farms_for_municipality(municipality_id)
    used = existing_ids or set()
    suffixes = []
    for farm in farms:
        suffix = _parse_id_suffix(farm.get("id", ""))
        if suffix is not None:
            suffixes.append(suffix)
        used.add(farm.get("id"))
    next_num = (max(suffixes) if suffixes else 0) + 1
    while True:
        candidate = f"{prefix}-{str(next_num).zfill(3)}"
        if candidate not in used:
            return candidate
        next_num += 1


def get_next_rsbsa_number(municipality_id: str) -> str:
    config = _municipality_config(municipality_id)
    region = config["rsbsa_region"]
    year = config["rsbsa_year"]
    farms = _existing_farms_for_municipality(municipality_id)
    suffixes = []
    for farm in farms:
        rsbsa = farm.get("rsbsa_number", "")
        if rsbsa:
            suffix = _parse_id_suffix(rsbsa)
            if suffix is not None:
                suffixes.append(suffix)
    next_num = (max(suffixes) if suffixes else 0) + 1
    return f"RSBSA-{region}-{year}-{str(next_num).zfill(5)}"

_ndvi_refresh_status: dict = {}


TYPHOON_KRISTINE_DATE = "2024-10-22"


def _ndvi_for_date(parcel_id: str, satellite_date: str | None, polygon=None, lat=None, lng=None):
    if not satellite_date:
        return None, None, None

    logger.info("Looking up NDVI for parcel %s on satellite_date %s", parcel_id, satellite_date)

    record = execute_query(
        """
        SELECT ndvi_value, capture_date, health_status FROM satellite_imagery
        WHERE parcel_id = %s AND capture_date = %s
        """,
        (parcel_id, satellite_date),
        fetch_one=True,
    )
    if record:
        capture = record["capture_date"]
        if hasattr(capture, "isoformat"):
            capture = capture.isoformat()
        health = record.get("health_status")
        return float(record["ndvi_value"]), str(capture)[:10], health

    return None, None, None


def _status_for_satellite_date(ndvi, satellite_date: str, seeded_health: str | None = None):
    """Classify parcel color for a selected satellite date."""
    if ndvi is None:
        return "UNKNOWN", "#9CA3AF"
    if seeded_health == "healthy":
        return "HEALTHY", "#22c55e"
    target = str(satellite_date)[:10]
    if target < TYPHOON_KRISTINE_DATE and float(ndvi) >= 0.55:
        return "HEALTHY", "#22c55e"
    return classify_health_status(ndvi)


def _get_ndvi_trend(parcel_id: str):
    records = execute_query(
        """
        SELECT ndvi_value FROM satellite_imagery
        WHERE parcel_id = %s
        ORDER BY capture_date DESC
        LIMIT 2
        """,
        (parcel_id,),
        fetch_all=True,
    )
    if not records or len(records) < 2:
        return None
    latest = float(records[0]["ndvi_value"])
    previous = float(records[1]["ndvi_value"])
    return round(latest - previous, 3)


def get_municipality_ndvi_status(municipality_id: str) -> dict:
    """Return background NDVI refresh status for a municipality."""
    from utils.database import resolve_municipality_id
    municipality_id = resolve_municipality_id(municipality_id)
    status = _ndvi_refresh_status.get(municipality_id)
    if not status:
        return {"status": "idle", "updated_at": None, "farms_updated": 0}
    return {
        "status": status.get("status", "idle"),
        "updated_at": status.get("updated_at"),
        "farms_updated": status.get("farms_updated", 0),
    }


def start_background_ndvi_refresh(municipality_id: str, farms: list):
    """
    After list response is returned, refresh NDVI sequentially for each farm.
    Skips if a refresh is already in progress for this municipality.
    """
    from utils.database import resolve_municipality_id
    municipality_id = resolve_municipality_id(municipality_id)

    current = _ndvi_refresh_status.get(municipality_id, {})
    if current.get("status") == "updating":
        logger.info("NDVI refresh already running for municipality %s", municipality_id)
        return

    if not farms:
        return

    def _refresh():
        from services.satellite_service import compute_ndvi_for_location

        _ndvi_refresh_status[municipality_id] = {
            "status": "updating",
            "updated_at": None,
            "farms_updated": 0,
        }
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        updated = 0

        for farm in farms:
            polygon = farm.get("polygon")
            if not polygon or len(polygon) < 3:
                continue
            try:
                lat = float(farm["latitude"])
                lng = float(farm["longitude"])
                ndvi = compute_ndvi_for_location(lat, lng, polygon, start_date, end_date)
                if isinstance(ndvi, (int, float)):
                    updated += 1
                    _ndvi_refresh_status[municipality_id]["farms_updated"] = updated
                    status, _ = classify_health_status(ndvi)
                    if status == "CRITICAL":
                        from services.notification_service import notify_regional_critical_farm
                        notify_regional_critical_farm(
                            farm_id=farm.get("id", ""),
                            farmer_name=farm.get("farmer_name", "Farmer"),
                            municipality_name=municipality_id.replace("-", " ").title(),
                            ndvi=ndvi,
                        )
            except Exception as exc:
                logger.warning(
                    "Background NDVI refresh failed for farm %s: %s",
                    farm.get("id"), exc,
                )

        _ndvi_refresh_status[municipality_id] = {
            "status": "updated",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "farms_updated": updated,
        }
        logger.info(
            "Background NDVI refresh complete for %s: %d/%d farms updated",
            municipality_id, updated, len(farms),
        )

    threading.Thread(target=_refresh, daemon=True, name=f"ndvi-refresh-{municipality_id}").start()


def get_farms_by_municipality(municipality_id: str, status_filter=None, crop_type=None, limit=100, satellite_date=None):
    from utils.database import resolve_municipality_id
    municipality_id = resolve_municipality_id(municipality_id)
    if satellite_date:
        logger.info("Fetching farms for municipality %s with satellite_date %s", municipality_id, satellite_date)
    if is_demo_mode():
        data = _load_demo_data()
        municipality = next(
            (m for m in data.get("municipalities", [data["municipality"]]) if m["id"] == municipality_id),
            None,
        )
        if municipality is None:
            municipality = data["municipality"] if data["municipality"]["id"] == municipality_id else None
        if municipality is None:
            return None
        farms_raw = execute_query(
            """
            SELECT fp.id, fp.rsbsa_number, fp.farmer_name, fp.crop_type,
                   fp.area_hectares, fp.latitude, fp.longitude, fp.polygon,
                   fp.is_insured,
                   latest_sat.ndvi_value AS latest_ndvi,
                   latest_sat.capture_date AS ndvi_date,
                   latest_sat.image_url
            FROM farm_parcels fp
            LEFT JOIN LATERAL (
                SELECT ndvi_value, capture_date, image_url
                FROM satellite_imagery
                WHERE parcel_id = fp.id
                ORDER BY capture_date DESC
                LIMIT 1
            ) latest_sat ON true
            WHERE fp.municipality_id = %s
            ORDER BY fp.id
            """,
            (municipality_id,),
            fetch_all=True,
        )
    else:
        municipality = execute_query(
            "SELECT * FROM municipalities WHERE id = %s",
            (municipality_id,),
            fetch_one=True,
        )
        if not municipality:
            return None

        farms_raw = execute_query(
            """
            SELECT fp.id, fp.rsbsa_number, fp.farmer_name, fp.crop_type,
                   fp.area_hectares, fp.latitude, fp.longitude, fp.polygon,
                   fp.is_insured,
                   latest_sat.ndvi_value AS latest_ndvi,
                   latest_sat.capture_date AS ndvi_date,
                   latest_sat.image_url
            FROM farm_parcels fp
            LEFT JOIN LATERAL (
                SELECT ndvi_value, capture_date, image_url
                FROM satellite_imagery
                WHERE parcel_id = fp.id
                ORDER BY capture_date DESC
                LIMIT 1
            ) latest_sat ON true
            WHERE fp.municipality_id = %s
            ORDER BY fp.id
            LIMIT %s
            """,
            (municipality_id, limit),
            fetch_all=True,
        )

    if municipality is None:
        return None

    farms = []
    stats = {"healthy_count": 0, "watch_count": 0, "critical_count": 0}
    ndvi_sources = set()

    prepared = []
    for farm in farms_raw or []:
        polygon = farm.get("polygon")
        if isinstance(polygon, str):
            import json
            polygon = json.loads(polygon)
        prepared.append({**farm, "polygon": polygon})

    ndvi_results = {}
    if satellite_date and prepared:
        from services.satellite_service import get_scan_cache

        cached_records = get_scan_cache(municipality_id, satellite_date) or []
        cache_by_parcel = {r["parcel_id"]: r for r in cached_records}

        def _compute_one(farm):
            parcel_id = farm["id"]
            cached = cache_by_parcel.get(parcel_id)
            if cached:
                return parcel_id, float(cached["ndvi_value"]), str(cached["capture_date"])[:10], cached.get("health_status")
            ndvi, capture, health = _ndvi_for_date(parcel_id, satellite_date)
            return parcel_id, ndvi, capture, health

        with ThreadPoolExecutor(max_workers=min(4, len(prepared))) as pool:
            futures = [pool.submit(_compute_one, farm) for farm in prepared]
            for future in as_completed(futures):
                try:
                    parcel_id, ndvi, capture, health = future.result()
                    ndvi_results[parcel_id] = (ndvi, capture, health)
                except Exception as exc:
                    logger.warning("Parallel NDVI lookup failed: %s", exc)

    for farm in prepared:
        polygon = farm["polygon"]
        latest_ndvi = None
        ndvi_date = None
        ndvi_source = "earth-engine"

        seeded_health = None
        if satellite_date:
            cached = ndvi_results.get(farm["id"])
            if cached and cached[0] is not None:
                latest_ndvi, ndvi_date = cached[0], cached[1]
                seeded_health = cached[2] if len(cached) > 2 else None
                ndvi_source = "cached"
            else:
                latest_ndvi = None
                ndvi_date = None
                ndvi_source = "unavailable"
        elif farm.get("latest_ndvi") is not None:
            latest_ndvi = float(farm["latest_ndvi"])
            ndvi_date = farm.get("ndvi_date")
            ndvi_source = "cached"

        ndvi_sources.add(ndvi_source)
        if satellite_date and latest_ndvi is None:
            status, color = "UNKNOWN", "#9CA3AF"
        else:
            status, color = _status_for_satellite_date(
                latest_ndvi, satellite_date, seeded_health,
            ) if satellite_date else classify_health_status(latest_ndvi)
        if status_filter and status != status_filter:
            continue
        if crop_type and farm.get("crop_type") != crop_type:
            continue

        if hasattr(ndvi_date, "isoformat"):
            ndvi_date = ndvi_date.isoformat()

        is_insured = farm.get("is_insured", farm.get("insured", False))
        farm_entry = {
            "id": farm["id"],
            "rsbsa_number": farm["rsbsa_number"],
            "farmer_name": farm["farmer_name"],
            "crop_type": farm["crop_type"],
            "area_hectares": float(farm["area_hectares"]),
            "latitude": float(farm["latitude"]),
            "longitude": float(farm["longitude"]),
            "polygon": polygon,
            "is_insured": bool(is_insured),
            "latest_ndvi": latest_ndvi,
            "ndvi_date": str(ndvi_date) if ndvi_date else None,
            "ndvi_trend": None,
            "status": status,
            "health_status": "unknown" if status == "UNKNOWN" else status,
            "status_color": color,
            "ndvi_source": ndvi_source,
        }
        farms.append(farm_entry)

        if status == "HEALTHY":
            stats["healthy_count"] += 1
        elif status == "WATCH":
            stats["watch_count"] += 1
        elif status == "CRITICAL":
            stats["critical_count"] += 1

    total_area = sum(f["area_hectares"] for f in farms)

    is_date_scanned = False
    if satellite_date:
        from services.satellite_service import is_date_scanned as scan_cache_hit
        is_date_scanned = scan_cache_hit(municipality_id, satellite_date)

    return {
        "municipality": {
            "id": municipality["id"],
            "name": municipality["name"],
            "total_farms": len(farms),
            "total_area_hectares": float(municipality.get("total_area_hectares") or total_area),
            "latitude": float(municipality.get("latitude") or 13.6218),
            "longitude": float(municipality.get("longitude") or 123.1948),
        },
        "farms": farms[:limit],
        "stats": stats,
        "ndvi_source": "earth-engine" if ndvi_sources == {"earth-engine"} else ("mixed" if ndvi_sources else "unavailable"),
        "is_date_scanned": is_date_scanned,
        "satellite_date": satellite_date,
    }


def get_farm_detail(parcel_id: str):
    farm = execute_query(
        """
        SELECT fp.*, m.name as municipality_name, m.province
        FROM farm_parcels fp
        JOIN municipalities m ON fp.municipality_id = m.id
        WHERE fp.id = %s
        """,
        (parcel_id,),
        fetch_one=True,
    )
    if not farm:
        return None

    ndvi_records = execute_query(
        """
        SELECT capture_date, ndvi_value, image_url
        FROM satellite_imagery
        WHERE parcel_id = %s
        ORDER BY capture_date DESC
        LIMIT 10
        """,
        (parcel_id,),
        fetch_all=True,
    )

    claims = execute_query(
        """
        SELECT claim_number, disaster_date, damage_type, damage_percentage, status, filed_date
        FROM claims
        WHERE parcel_id = %s
        ORDER BY filed_date DESC
        LIMIT 5
        """,
        (parcel_id,),
        fetch_all=True,
    )

    polygon = farm.get("polygon")
    if isinstance(polygon, str):
        import json
        polygon = json.loads(polygon)

    planting_date = farm.get("planting_date")
    harvest_date = farm.get("expected_harvest_date")
    if hasattr(planting_date, "isoformat"):
        planting_date = planting_date.isoformat()
    if hasattr(harvest_date, "isoformat"):
        harvest_date = harvest_date.isoformat()

    ndvi_history = []
    for record in ndvi_records or []:
        status, _ = classify_health_status(record["ndvi_value"])
        capture_date = record["capture_date"]
        if hasattr(capture_date, "isoformat"):
            capture_date = capture_date.isoformat()
        ndvi_history.append({
            "date": str(capture_date),
            "ndvi": float(record["ndvi_value"]),
            "status": status,
            "image_url": record.get("image_url"),
        })

    recent_claims = []
    for claim in claims or []:
        disaster_date = claim["disaster_date"]
        filed_date = claim["filed_date"]
        if hasattr(disaster_date, "isoformat"):
            disaster_date = disaster_date.isoformat()
        if hasattr(filed_date, "isoformat"):
            filed_date = filed_date.isoformat()
        recent_claims.append({
            "claim_number": claim["claim_number"],
            "disaster_date": str(disaster_date),
            "damage_type": claim["damage_type"],
            "damage_percentage": float(claim["damage_percentage"]) if claim.get("damage_percentage") is not None else None,
            "status": claim["status"],
            "filed_date": str(filed_date),
        })

    latest_ndvi = ndvi_history[0]["ndvi"] if ndvi_history else None
    latest_status = ndvi_history[0]["status"] if ndvi_history else "WATCH"

    return {
        "farm": {
            "id": farm["id"],
            "rsbsa_number": farm["rsbsa_number"],
            "farmer_name": farm["farmer_name"],
            "municipality": {
                "id": farm["municipality_id"],
                "name": farm["municipality_name"],
                "province": farm["province"],
            },
            "crop_type": farm["crop_type"],
            "area_hectares": float(farm["area_hectares"]),
            "latitude": float(farm["latitude"]),
            "longitude": float(farm["longitude"]),
            "polygon": polygon,
            "planting_date": str(planting_date) if planting_date else None,
            "expected_harvest_date": str(harvest_date) if harvest_date else None,
            "latest_ndvi": latest_ndvi,
            "status": latest_status,
            "is_insured": bool(farm.get("is_insured", farm.get("insured", False))),
            "insured": bool(farm.get("is_insured", farm.get("insured", False))),
        },
        "ndvi_history": ndvi_history,
        "recent_claims": recent_claims,
    }


def add_farm_parcel(farm_data: dict):
    from utils.polygon_placement import find_agricultural_location, generate_field_polygon
    from utils.database import resolve_municipality_id

    municipality_id = resolve_municipality_id(farm_data["municipality_id"])

    if farm_data.get("latitude") is None or farm_data.get("longitude") is None:
        mun = execute_query(
            "SELECT latitude, longitude FROM municipalities WHERE id = %s",
            (municipality_id,),
            fetch_one=True,
        )
        if mun:
            mun_coords = (float(mun["latitude"]), float(mun["longitude"]))
            location = find_agricultural_location(
                mun_coords,
                farm_data["area_hectares"],
                farm_data["crop_type"],
                municipality_id,
            )
            farm_data["latitude"] = location["latitude"]
            farm_data["longitude"] = location["longitude"]

    if not farm_data.get("polygon"):
        farm_data["polygon"] = generate_field_polygon(
            farm_data["latitude"],
            farm_data["longitude"],
            farm_data["area_hectares"],
            farm_data["crop_type"],
        )

    import json
    import copy
    from utils.database import _atomic_save_demo_data

    def _create_record(existing_ids: set | None = None):
        parcel_id = _next_parcel_id(municipality_id, existing_ids)
        rsbsa_number = farm_data["rsbsa_number"]

        farms = _existing_farms_for_municipality(municipality_id)
        if any(f.get("id") == parcel_id for f in farms):
            logger.warning("Parcel ID collision detected for %s — retrying", parcel_id)
            parcel_id = _next_parcel_id(municipality_id, (existing_ids or set()) | {parcel_id})
        if any(f.get("rsbsa_number") == rsbsa_number for f in farms):
            logger.warning("RSBSA collision detected for %s — generating next available", rsbsa_number)
            rsbsa_number = get_next_rsbsa_number(municipality_id)

        logger.info("Creating farm parcel %s with RSBSA %s for municipality %s", parcel_id, rsbsa_number, municipality_id)

        polygon = farm_data["polygon"]
        polygon_db = polygon if isinstance(polygon, str) else json.dumps(polygon)

        record = {
            "id": parcel_id,
            "rsbsa_number": rsbsa_number,
            "farmer_name": farm_data["farmer_name"],
            "municipality_id": municipality_id,
            "crop_type": farm_data["crop_type"],
            "area_hectares": farm_data["area_hectares"],
            "latitude": farm_data["latitude"],
            "longitude": farm_data["longitude"],
            "polygon": farm_data["polygon"],
            "insured": farm_data.get("insured", False),
            "is_insured": farm_data.get("insured", False),
        }

        if is_demo_mode():
            with _demo_write_lock:
                data = _load_demo_data()
                data["farms"].append(copy.deepcopy(record))
                mun_id = municipality_id
                total = len([f for f in data["farms"] if f["municipality_id"] == mun_id])
                if data["municipality"]["id"] == mun_id:
                    data["municipality"]["total_farms"] = total
                for mun in data.get("municipalities", []):
                    if mun["id"] == mun_id:
                        mun["total_farms"] = total
                _atomic_save_demo_data(data)
        else:
            execute_query(
                """
                INSERT INTO farm_parcels (
                    id, rsbsa_number, farmer_name, municipality_id, crop_type,
                    area_hectares, latitude, longitude, polygon, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE')
                """,
                (
                    parcel_id,
                    rsbsa_number,
                    farm_data["farmer_name"],
                    municipality_id,
                    farm_data["crop_type"],
                    farm_data["area_hectares"],
                    farm_data["latitude"],
                    farm_data["longitude"],
                    polygon_db,
                ),
            )

        return parcel_id, rsbsa_number

    parcel_id, rsbsa_number = _create_record()

    return {
        "parcel_id": parcel_id,
        "rsbsa_number": rsbsa_number,
        "message": "Farm parcel added successfully",
    }


def update_farm_parcel(parcel_id: str, farm_data: dict):
    import json

    polygon = farm_data.get("polygon")
    if polygon and not isinstance(polygon, str):
        polygon = json.dumps(polygon)

    execute_query(
        """
        UPDATE farm_parcels SET
            farmer_name = %s,
            rsbsa_number = %s,
            crop_type = %s,
            area_hectares = %s,
            latitude = %s,
            longitude = %s,
            polygon = %s
        WHERE id = %s
        """,
        (
            farm_data["farmer_name"],
            farm_data["rsbsa_number"],
            farm_data["crop_type"],
            farm_data["area_hectares"],
            farm_data["latitude"],
            farm_data["longitude"],
            polygon,
            parcel_id,
        ),
    )

    if is_demo_mode():
        from utils.database import update_demo_farm
        update_demo_farm(parcel_id, farm_data)

    return {"parcel_id": parcel_id, "message": "Farm parcel updated successfully"}


def get_regional_health(municipalities: list):
    results = []
    region_totals = {
        "total_farms": 0,
        "healthy_count": 0,
        "watch_count": 0,
        "critical_count": 0,
        "total_area_hectares": 0.0,
    }

    for mun in municipalities:
        mun_id = mun["id"] if isinstance(mun, dict) else mun
        mun_name = mun.get("name") if isinstance(mun, dict) else mun_id
        data = get_farms_by_municipality(mun_id)
        if data:
            stats = data["stats"]
            total_farms = len(data["farms"])
            total_area = data.get("total_area_hectares") or sum(
                f["area_hectares"] for f in data["farms"]
            )
            province = data["municipality"].get("province")
            latitude = data["municipality"].get("latitude")
            longitude = data["municipality"].get("longitude")
        else:
            stats = {"healthy_count": 0, "watch_count": 0, "critical_count": 0}
            total_farms = 0
            total_area = 0.0
            province = mun.get("province") if isinstance(mun, dict) else None
            latitude = mun.get("latitude") if isinstance(mun, dict) else None
            longitude = mun.get("longitude") if isinstance(mun, dict) else None

        critical_pct = (stats["critical_count"] / total_farms * 100) if total_farms else 0
        results.append({
            "id": mun_id,
            "name": mun_name,
            "province": province,
            "latitude": latitude,
            "longitude": longitude,
            "total_farms": total_farms,
            "total_area_hectares": round(total_area, 2),
            "stats": stats,
            "critical_pct": round(critical_pct, 1),
            "health_score": round(
                (stats["healthy_count"] * 100 + stats["watch_count"] * 50) / total_farms, 1
            ) if total_farms else 0,
        })

        region_totals["total_farms"] += total_farms
        region_totals["healthy_count"] += stats["healthy_count"]
        region_totals["watch_count"] += stats["watch_count"]
        region_totals["critical_count"] += stats["critical_count"]
        region_totals["total_area_hectares"] += total_area

    results.sort(key=lambda m: m["health_score"])
    region_totals["total_area_hectares"] = round(region_totals["total_area_hectares"], 2)

    return {
        "municipalities": results,
        "totals": region_totals,
    }