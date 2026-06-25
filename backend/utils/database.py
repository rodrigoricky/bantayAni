import os
import json
import copy
import logging
import shutil
import threading
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "demo")
DEMO_MODE = DATABASE_URL in ("", "demo", "none")

# Legacy municipality ID from pre-Sprint-7 Kibawe demo data
MUNICIPALITY_ALIASES = {
    "bukidnon-kibawe": "camarines-naga",
    "camsur-naga": "camarines-naga",
}


def resolve_municipality_id(municipality_id: str | None) -> str | None:
    if not municipality_id:
        return municipality_id
    return MUNICIPALITY_ALIASES.get(municipality_id, municipality_id)

_demo_data = None
_demo_claims = None
_demo_notifications = None
_demo_write_lock = threading.RLock()
_DEMO_CLAIMS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "demo_claims.json"
_DEMO_NOTIFICATIONS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "notifications.json"


def _load_demo_claims_from_disk():
    global _demo_claims
    if _demo_claims is not None:
        return _demo_claims
    if _DEMO_CLAIMS_PATH.exists():
        try:
            with open(_DEMO_CLAIMS_PATH) as f:
                _demo_claims = json.load(f)
        except (json.JSONDecodeError, OSError):
            _demo_claims = []
    else:
        _demo_claims = []
    return _demo_claims


def _save_demo_claims_to_disk():
    claims = _load_demo_claims_from_disk()
    tmp_path = _DEMO_CLAIMS_PATH.with_suffix(".tmp")
    try:
        with open(tmp_path, "w") as f:
            json.dump(claims, f, indent=2, default=str)
        tmp_path.replace(_DEMO_CLAIMS_PATH)
    except OSError:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


_DEMO_DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "farms.json"
_DEMO_DATA_BACKUP_PATH = _DEMO_DATA_PATH.with_name("farms.json.bak")


def _validate_farms_data(data) -> bool:
    if not isinstance(data, dict):
        return False
    farms = data.get("farms")
    if not isinstance(farms, list):
        return False
    for farm in farms:
        if not isinstance(farm, dict):
            return False
        if not farm.get("id") or not farm.get("farmer_name"):
            return False
    if "satellite_imagery" in data and not isinstance(data["satellite_imagery"], list):
        return False
    return True


def _atomic_save_demo_data(data: dict) -> None:
    """Write farms.json atomically with parse verification and backup."""
    tmp_path = _DEMO_DATA_PATH.with_name("farms.json.tmp")
    with _demo_write_lock:
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())
            with open(tmp_path, encoding="utf-8") as f:
                verified = json.load(f)
            if not _validate_farms_data(verified):
                raise ValueError("Written farms data failed integrity check")
            os.replace(str(tmp_path), str(_DEMO_DATA_PATH))
            global _demo_data
            _demo_data = verified
            shutil.copy2(_DEMO_DATA_PATH, _DEMO_DATA_BACKUP_PATH)
            sat_count = len(verified.get("satellite_imagery", []))
            logger.info(
                "farms.json written and verified — %d farms, %d satellite records.",
                len(verified["farms"]),
                sat_count,
            )
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise


def _read_farms_json_from_path(path: Path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not _validate_farms_data(data):
        raise ValueError(f"Invalid farm data structure in {path}")
    return data


def _load_demo_data(force_reload: bool = False):
    global _demo_data
    if _demo_data is not None and not force_reload:
        return _demo_data

    last_error = None
    for path in (_DEMO_DATA_PATH, _DEMO_DATA_BACKUP_PATH):
        if not path.exists():
            continue
        try:
            data = _read_farms_json_from_path(path)
            _demo_data = data
            if path != _DEMO_DATA_PATH:
                logger.warning("Restored farms.json from backup at %s", path)
                _atomic_save_demo_data(data)
            return _demo_data
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            last_error = exc
            logger.error("Failed to load farm data from %s: %s", path, exc)

    raise RuntimeError(f"Farm data unavailable: {last_error}")


def ensure_farms_data_integrity() -> bool:
    """Startup integrity check with automatic backup restore."""
    try:
        _load_demo_data(force_reload=True)
        farm_count = len(_demo_data.get("farms", []))
        logger.info("farms.json integrity check passed — %d farms", farm_count)
        if _DEMO_DATA_PATH.exists() and not _DEMO_DATA_BACKUP_PATH.exists():
            shutil.copy2(_DEMO_DATA_PATH, _DEMO_DATA_BACKUP_PATH)
            logger.info("Created initial farms.json.bak backup")
        return True
    except Exception as exc:
        logger.critical("farms.json integrity check failed: %s", exc)
        return False


def is_demo_mode():
    return DEMO_MODE


def get_demo_claims():
    return _load_demo_claims_from_disk()


def add_demo_claim(claim):
    claims = _load_demo_claims_from_disk()
    claims.insert(0, claim)
    _save_demo_claims_to_disk()


def update_demo_claim(claim_id: str, updates: dict):
    with _demo_write_lock:
        claims = _load_demo_claims_from_disk()
        for claim in claims:
            if str(claim.get("id")) == str(claim_id):
                claim.update(updates)
                _save_demo_claims_to_disk()
                return copy.deepcopy(claim)
        return None


def _load_demo_notifications_from_disk():
    global _demo_notifications
    if _demo_notifications is not None:
        return _demo_notifications
    if _DEMO_NOTIFICATIONS_PATH.exists():
        try:
            with open(_DEMO_NOTIFICATIONS_PATH) as f:
                _demo_notifications = json.load(f)
        except (json.JSONDecodeError, OSError):
            _demo_notifications = []
    else:
        _demo_notifications = []
    return _demo_notifications


def _save_demo_notifications_to_disk():
    notifications = _load_demo_notifications_from_disk()
    tmp_path = _DEMO_NOTIFICATIONS_PATH.with_suffix(".tmp")
    try:
        with open(tmp_path, "w") as f:
            json.dump(notifications, f, indent=2, default=str)
        tmp_path.replace(_DEMO_NOTIFICATIONS_PATH)
    except OSError:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def get_demo_notifications():
    return _load_demo_notifications_from_disk()


def add_demo_notification(notification):
    notifications = _load_demo_notifications_from_disk()
    notifications.insert(0, notification)
    _save_demo_notifications_to_disk()


def update_demo_notification(notification_id: str, updates: dict):
    notifications = _load_demo_notifications_from_disk()
    for notification in notifications:
        if str(notification.get("id")) == str(notification_id):
            notification.update(updates)
            _save_demo_notifications_to_disk()
            return notification
    return None


def _upsert_satellite_record(data: dict, record: dict) -> dict:
    if "satellite_imagery" not in data:
        data["satellite_imagery"] = []

    parcel_id = record["parcel_id"]
    capture_date = str(record["capture_date"])[:10]
    existing = next(
        (
            item for item in data["satellite_imagery"]
            if item["parcel_id"] == parcel_id and str(item["capture_date"])[:10] == capture_date
        ),
        None,
    )
    safe_record = {
        "parcel_id": parcel_id,
        "capture_date": capture_date,
        "ndvi_value": float(record["ndvi_value"]),
        "data_source": record.get("data_source", "Sentinel-2"),
    }
    if existing:
        existing.update(safe_record)
    else:
        data["satellite_imagery"].append(copy.deepcopy(safe_record))
    return safe_record


def add_demo_satellite_record(record: dict):
    """Update only satellite_imagery entries — never modify farm identity fields."""
    with _demo_write_lock:
        data = _load_demo_data()
        safe_record = _upsert_satellite_record(data, record)
        _atomic_save_demo_data(data)
        return safe_record


def batch_add_demo_satellite_records(records: list) -> list:
    """Persist multiple satellite_imagery entries in one atomic write."""
    if not records:
        return []
    with _demo_write_lock:
        data = _load_demo_data()
        saved = []
        for record in records:
            saved.append(_upsert_satellite_record(data, record))
        _atomic_save_demo_data(data)
        return saved


def add_demo_farm(farm):
    with _demo_write_lock:
        data = _load_demo_data()
        data["farms"].append(copy.deepcopy(farm))
        mun_id = farm.get("municipality_id") or data["municipality"]["id"]
        total = len([f for f in data["farms"] if f["municipality_id"] == mun_id])
        if data["municipality"]["id"] == mun_id:
            data["municipality"]["total_farms"] = total
        for mun in data.get("municipalities", []):
            if mun["id"] == mun_id:
                mun["total_farms"] = total
        _atomic_save_demo_data(data)


def update_demo_farm(parcel_id: str, updates: dict):
    data = _load_demo_data()
    for farm in data["farms"]:
        if farm["id"] == parcel_id:
            farm.update(updates)
            if "polygon" in updates and isinstance(updates["polygon"], str):
                import json
                farm["polygon"] = json.loads(updates["polygon"])
            return farm
    return None


@contextmanager
def get_db_connection():
    if DEMO_MODE:
        yield None
        return

    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    if DEMO_MODE:
        return _execute_demo_query(query, params, fetch_one, fetch_all)

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or ())
            if fetch_one:
                row = cur.fetchone()
                return dict(row) if row else None
            if fetch_all:
                return [dict(row) for row in cur.fetchall()]
            return None


def _execute_demo_query(query, params, fetch_one, fetch_all):
    data = _load_demo_data()
    q = " ".join(query.lower().split())

    if "from users where" in q and "email" in q:
        email = params[0].lower() if params else ""
        for user in data["users"]:
            if user["email"].lower() == email:
                return copy.deepcopy(user) if fetch_one else [copy.deepcopy(user)]
        return None if fetch_one else []

    if (
        "from farm_parcels where id" in q
        or ("from farm_parcels fp" in q and "where fp.id" in q)
        or ("from farm_parcels" in q and "where id =" in q and "municipality_id" not in q.split("where id")[0])
    ):
        parcel_id = params[0]
        for farm in data["farms"]:
            if farm["id"] == parcel_id:
                result = copy.deepcopy(farm)
                mun = next(
                    (m for m in data.get("municipalities", [data["municipality"]])
                     if m["id"] == farm.get("municipality_id")),
                    data["municipality"],
                )
                result["municipality_name"] = mun["name"]
                result["province"] = mun["province"]
                return result if fetch_one else [result]
        return None if fetch_one else []

    if "from farm_parcels where rsbsa_number" in q:
        for farm in data["farms"]:
            if farm["rsbsa_number"] == params[0]:
                return copy.deepcopy(farm) if fetch_one else [copy.deepcopy(farm)]
        return None if fetch_one else []

    if "count(*)" in q and "from farm_parcels" in q:
        municipality_id = params[0] if params else None
        count = len([f for f in data["farms"] if f["municipality_id"] == municipality_id])
        return {"count": count}

    if (
        "from farm_parcels" in q
        and ("where municipality_id" in q or "where fp.municipality_id" in q)
        and "lateral" not in q
        and "count(*)" not in q
    ):
        mun_id = params[0] if params else None
        farms = [
            copy.deepcopy(f) for f in data["farms"]
            if not mun_id or f.get("municipality_id") == mun_id
        ]
        if "select id from farm_parcels" in q:
            farms = [{"id": f["id"]} for f in farms]
        return farms if fetch_all else (farms[0] if farms and fetch_one else None)

    if "from municipalities m" in q and "region" in q:
        ref_id = params[0]
        ref_region = data["municipality"]["region"]
        for mun in data.get("municipalities", []):
            if mun["id"] == ref_id:
                ref_region = mun.get("region", ref_region)
                break
        results = [
            {"id": m["id"], "name": m["name"]}
            for m in data.get("municipalities", [data["municipality"]])
            if m.get("region") == ref_region
        ]
        return results if fetch_all else (results[0] if results and fetch_one else None)

    if "from municipalities where id" in q and "select latitude" in q:
        mun_id = params[0]
        for mun in data.get("municipalities", [data["municipality"]]):
            if mun["id"] == mun_id:
                return copy.deepcopy(mun) if fetch_one else [copy.deepcopy(mun)]
        return None if fetch_one else []

    if "from municipalities where id" in q:
        mun_id = params[0]
        for mun in data.get("municipalities", [data["municipality"]]):
            if mun["id"] == mun_id:
                return copy.deepcopy(mun) if fetch_one else [copy.deepcopy(mun)]
        return None if fetch_one else []

    if "lateral" in q and "farm_parcels" in q:
        municipality_id = params[0]
        farms = []
        for farm in data["farms"]:
            if farm["municipality_id"] != municipality_id:
                continue
            latest = _get_latest_satellite(farm["id"])
            entry = copy.deepcopy(farm)
            entry["is_insured"] = farm.get("is_insured", farm.get("insured", False))
            if latest:
                entry["latest_ndvi"] = latest["ndvi_value"]
                entry["ndvi_date"] = latest["capture_date"]
                if latest.get("image_url"):
                    entry["image_url"] = latest["image_url"]
            farms.append(entry)
        return farms if fetch_all else (farms[0] if farms and fetch_one else None)

    if "insert into satellite_imagery" in q:
        record = {
            "parcel_id": params[0],
            "capture_date": str(params[1]),
            "ndvi_value": float(params[2]),
            "data_source": params[3] if len(params) > 3 else "Sentinel-2",
        }
        add_demo_satellite_record(record)
        return record

    if "from farm_parcels" in q and "where municipality_id" in q and "lateral" not in q:
        municipality_id = params[0]
        farms = [
            copy.deepcopy(farm)
            for farm in data["farms"]
            if farm["municipality_id"] == municipality_id
        ]
        return farms if fetch_all else (farms[0] if farms and fetch_one else None)

    if "from satellite_imagery" in q:
        return _handle_satellite_demo_query(q, params, fetch_one, fetch_all, data)

    if "update claims" in q:
        return _handle_claims_update_demo(q, params)

    if "from claims" in q:
        return _handle_claims_demo_query(q, params, fetch_one, fetch_all, data)

    if "insert into claims" in q:
        return _handle_claim_insert_demo(params)

    if "insert into farm_parcels" in q:
        return {"id": params[0] if params else None}

    if "update farm_parcels set" in q:
        parcel_id = params[-1] if params else None
        if parcel_id:
            updates = {
                "farmer_name": params[0],
                "rsbsa_number": params[1],
                "crop_type": params[2],
                "area_hectares": float(params[3]),
                "latitude": float(params[4]),
                "longitude": float(params[5]),
            }
            import json
            poly = params[6]
            if isinstance(poly, str):
                try:
                    updates["polygon"] = json.loads(poly)
                except json.JSONDecodeError:
                    updates["polygon"] = poly
            else:
                updates["polygon"] = poly
            update_demo_farm(parcel_id, updates)
        return None

    if "count(*)" in q and "from claims" in q:
        return {"count": len(_load_demo_claims_from_disk())}

    return None if fetch_one else ([] if fetch_all else None)


def _get_latest_satellite(parcel_id):
    data = _load_demo_data()
    records = [
        s for s in data.get("satellite_imagery", [])
        if s["parcel_id"] == parcel_id
    ]
    if not records:
        return None
    return max(records, key=lambda x: x["capture_date"])


def _get_satellite_records(parcel_id, before_date=None, after_date=None, disaster_date=None):
    data = _load_demo_data()
    records = [
        copy.deepcopy(s) for s in data.get("satellite_imagery", [])
        if s["parcel_id"] == parcel_id
    ]

    if before_date is not None:
        filtered = [
            r for r in records
            if r["capture_date"] <= before_date
            and (disaster_date is None or r["capture_date"] >= disaster_date)
            and (r.get("cloud_cover_percentage") or 0) < 30
        ]
        if filtered:
            return max(filtered, key=lambda x: x["capture_date"])
        return None

    if after_date is not None:
        filtered = [
            r for r in records
            if r["capture_date"] >= after_date
            and (disaster_date is None or r["capture_date"] <= disaster_date)
            and (r.get("cloud_cover_percentage") or 0) < 30
        ]
        if filtered:
            return min(filtered, key=lambda x: x["capture_date"])
        return None

    records.sort(key=lambda x: x["capture_date"], reverse=True)
    return records


def _handle_claims_update_demo(q: str, params):
    """Persist claim status updates from SQL UPDATE paths in demo mode."""
    q_lower = q.lower()
    claim_id = str(params[-1]) if params else None
    if not claim_id:
        return None

    updates = {}
    if "status = 'approved'" in q_lower or "status='approved'" in q_lower:
        updates["status"] = "APPROVED"
        updates["rejection_reason"] = None
    elif "status = 'rejected'" in q_lower or "status='rejected'" in q_lower:
        updates["status"] = "REJECTED"
        if len(params) >= 2:
            updates["rejection_reason"] = params[0]
    elif "status = 'flagged'" in q_lower or "status='flagged'" in q_lower:
        updates["status"] = "FLAGGED"
        if len(params) >= 2:
            updates["flag_reason"] = params[0]
    elif "status = 'submitted'" in q_lower or "status='submitted'" in q_lower:
        updates["status"] = "SUBMITTED"
    elif "status = 'pending'" in q_lower or "status='pending'" in q_lower:
        updates["status"] = "PENDING"

    if "verified_by_user_id" in q_lower and len(params) >= 2:
        updates["verified_by_user_id"] = params[-2]
    if "verified_at" in q_lower:
        from datetime import datetime
        updates["verified_at"] = datetime.utcnow().isoformat() + "Z"
    if "submitted_at" in q_lower:
        from datetime import datetime
        updates["submitted_at"] = datetime.utcnow().isoformat() + "Z"

    if not updates:
        return None
    return update_demo_claim(claim_id, updates)


def _handle_satellite_demo_query(q, params, fetch_one, fetch_all, data):
    parcel_id = params[0]
    q_lower = q.lower()

    if (
        "capture_date =" in q_lower
        and "satellite_imagery" in q_lower
        and "order by" not in q_lower
    ):
        capture_date = str(params[1])[:10] if len(params) > 1 else None
        if capture_date:
            for record in data.get("satellite_imagery", []):
                if (
                    record["parcel_id"] == parcel_id
                    and str(record["capture_date"])[:10] == capture_date
                ):
                    result = copy.deepcopy(record)
                    if "health_status" not in result:
                        ndvi = float(result.get("ndvi_value", 0))
                        if ndvi >= 0.55 and capture_date < "2024-10-22":
                            result["health_status"] = "healthy"
                        elif ndvi < 0.3:
                            result["health_status"] = "critical"
                        else:
                            result["health_status"] = "watch"
                    return result if fetch_one else [result]
        return None if fetch_one else []

    if "capture_date <=" in q_lower and "order by capture_date desc" in q_lower:
        disaster_date = str(params[1]) if len(params) > 1 else None
        from datetime import datetime, timedelta
        d = datetime.strptime(disaster_date, "%Y-%m-%d").date()
        window_start = (d - timedelta(days=14)).isoformat()
        result = None
        candidates = [
            s for s in data.get("satellite_imagery", [])
            if s["parcel_id"] == parcel_id
            and s["capture_date"] <= disaster_date
            and s["capture_date"] >= window_start
            and (s.get("cloud_cover_percentage") or 0) < 30
        ]
        if candidates:
            result = max(candidates, key=lambda x: x["capture_date"])
        return copy.deepcopy(result) if fetch_one else ([copy.deepcopy(result)] if result else [])

    if "capture_date >=" in q_lower and "order by capture_date asc" in q_lower:
        disaster_date = str(params[1]) if len(params) > 1 else None
        from datetime import datetime, timedelta
        d = datetime.strptime(disaster_date, "%Y-%m-%d").date()
        window_end = (d + timedelta(days=14)).isoformat()
        result = None
        candidates = [
            s for s in data.get("satellite_imagery", [])
            if s["parcel_id"] == parcel_id
            and s["capture_date"] >= disaster_date
            and s["capture_date"] <= window_end
            and (s.get("cloud_cover_percentage") or 0) < 30
        ]
        if candidates:
            result = min(candidates, key=lambda x: x["capture_date"])
        return copy.deepcopy(result) if fetch_one else ([copy.deepcopy(result)] if result else [])

    if "order by capture_date desc" in q_lower:
        records = _get_satellite_records(parcel_id)
        if "limit 2" in q_lower:
            records = records[:2]
        elif "limit 10" in q_lower:
            records = records[:10]
        elif "limit 1" in q_lower:
            records = records[:1]
        return records if fetch_all else (records[0] if records and fetch_one else None)

    if "order by capture_date asc" in q_lower:
        records = sorted(
            [copy.deepcopy(s) for s in data.get("satellite_imagery", []) if s["parcel_id"] == parcel_id],
            key=lambda x: x["capture_date"],
        )
        return records if fetch_all else (records[0] if records and fetch_one else None)

    return None if fetch_one else []


def _handle_claims_demo_query(q, params, fetch_one, fetch_all, data):
    claims = copy.deepcopy(_load_demo_claims_from_disk())

    if "where parcel_id" in q:
        parcel_id = params[0]
        claims = [c for c in claims if c.get("parcel_id") == parcel_id]
        claims = claims[:5]
        return claims if fetch_all else (claims[0] if claims and fetch_one else None)

    if "where c.id" in q or "where id =" in q:
        claim_id = params[0]
        for claim in claims:
            if str(claim.get("id")) == str(claim_id):
                result = copy.deepcopy(claim)
                for farm in data["farms"]:
                    if farm["id"] == claim.get("parcel_id"):
                        result["crop_type"] = farm["crop_type"]
                        result["area_hectares"] = farm["area_hectares"]
                        break
                result["municipality_name"] = data["municipality"]["name"]
                result["province"] = data["municipality"]["province"]
                return result
        return None

    offset = 0
    limit = 50
    if params:
        limit = params[-2] if len(params) >= 2 else 50
        offset = params[-1] if len(params) >= 1 else 0

    paginated = claims[offset:offset + limit]
    return paginated if fetch_all else (paginated[0] if paginated and fetch_one else None)


def _handle_claim_insert_demo(params):
    import uuid
    from datetime import datetime

    claim_id = str(uuid.uuid4())
    claim = {
        "id": claim_id,
        "claim_number": params[0] if len(params) > 0 else f"2024-NAGA-{uuid.uuid4().hex[:8].upper()}",
        "parcel_id": params[1] if len(params) > 1 else "",
        "farmer_name": params[2] if len(params) > 2 else "",
        "rsbsa_number": params[3] if len(params) > 3 else "",
        "damage_type": params[4] if len(params) > 4 else "flood",
        "claimed_area_hectares": float(params[5]) if len(params) > 5 else 0,
        "disaster_date": str(params[6]) if len(params) > 6 else "",
        "filed_date": datetime.now().date().isoformat(),
        "ndvi_before": float(params[7]) if len(params) > 7 else None,
        "ndvi_after": float(params[8]) if len(params) > 8 else None,
        "damage_percentage": float(params[9]) if len(params) > 9 else None,
        "before_image_url": params[10] if len(params) > 10 else "",
        "after_image_url": params[11] if len(params) > 11 else "",
        "ai_recommendation": params[12] if len(params) > 12 else "",
        "status": params[13] if len(params) > 13 else "PENDING",
        "rejection_reason": params[14] if len(params) > 14 else None,
        "verified_by_user_id": params[15] if len(params) > 15 else None,
        "verified_at": datetime.utcnow().isoformat() + "Z",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    add_demo_claim(claim)
    return {"id": claim_id}