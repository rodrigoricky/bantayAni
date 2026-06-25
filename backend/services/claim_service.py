import copy
import json
import logging
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path

from utils.database import execute_query, is_demo_mode

logger = logging.getLogger(__name__)

_PREVIEW_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "satellite-previews"


def _resolve_image_url(parcel_id: str, capture_date, direction: str = "before") -> str:
    """Prefer parcel before/after demo assets, then dated previews."""
    before_path = _PREVIEW_DIR / f"{parcel_id}_before.png"
    after_path = _PREVIEW_DIR / f"{parcel_id}_after.png"
    if direction == "before" and before_path.exists():
        return f"/satellite-previews/{parcel_id}_before.png"
    if direction == "after" and after_path.exists():
        return f"/satellite-previews/{parcel_id}_after.png"

    date_str = str(capture_date)[:10]
    try:
        month = int(date_str[5:7])
        if month == 10 and (_PREVIEW_DIR / "kibawe_oct_rgb.png").exists():
            return "/satellite-previews/kibawe_oct_rgb.png"
        if month == 11 and (_PREVIEW_DIR / "kibawe_nov_rgb.png").exists():
            return "/satellite-previews/kibawe_nov_rgb.png"
    except (ValueError, IndexError):
        pass

    preview_name = f"{parcel_id}_{date_str}.png"
    if (_PREVIEW_DIR / preview_name).exists():
        return f"/satellite-previews/{preview_name}"
    return f"/satellite-previews/{preview_name}"
from utils.ndvi import classify_health_status


TYPHOON_REFERENCE_DATE = datetime(2024, 10, 23).date()
NDVI_SIGNIFICANCE_THRESHOLD = 0.08
LOW_VEGETATION_THRESHOLD = 0.15
PCIC_ACTIONABLE_STATUSES = {"PENDING", "SUBMITTED"}

_claim_verify_jobs: dict = {}
_claim_jobs_lock = __import__("threading").Lock()


def _load_satellite_records(parcel_id: str) -> list:
    if is_demo_mode():
        data = _load_demo_data_for_claims()
        return [
            copy.deepcopy(s) for s in data.get("satellite_imagery", [])
            if s["parcel_id"] == parcel_id
            and (s.get("cloud_cover_percentage") or 0) < 30
        ]
    records = execute_query(
        """
        SELECT * FROM satellite_imagery
        WHERE parcel_id = %s
          AND (cloud_cover_percentage IS NULL OR cloud_cover_percentage < 30)
        ORDER BY capture_date ASC
        """,
        (parcel_id,),
        fetch_all=True,
    )
    return records or []


def _load_demo_data_for_claims():
    from utils.database import _load_demo_data
    return _load_demo_data()


def _parse_date(value) -> datetime.date:
    if hasattr(value, "isoformat"):
        return value if hasattr(value, "day") else datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _find_satellite_pair(parcel_id: str, disaster_date: str):
    """Date-aware before/after NDVI lookup based on disaster timing."""
    disaster = _parse_date(disaster_date)
    records = _load_satellite_records(parcel_id)
    if not records:
        return None, None

    before_candidates = [r for r in records if _parse_date(r["capture_date"]) <= disaster]
    after_candidates = [r for r in records if _parse_date(r["capture_date"]) > disaster]

    if before_candidates:
        before_img = max(before_candidates, key=lambda r: r["capture_date"])
    else:
        before_img = min(records, key=lambda r: r["capture_date"])

    if after_candidates:
        if disaster >= TYPHOON_REFERENCE_DATE:
            after_img = max(after_candidates, key=lambda r: r["capture_date"])
        else:
            after_img = min(after_candidates, key=lambda r: r["capture_date"])
    else:
        after_img = max(records, key=lambda r: r["capture_date"])

    return before_img, after_img


def _detect_fraud(farm, claimed_area, ndvi_before, ndvi_after, damage_pct):
    fraud_indicators = []

    if ndvi_before < 0.35:
        fraud_indicators.append({
            "type": "PRE_EXISTING_DAMAGE",
            "severity": "HIGH",
            "description": f"Crop was already stressed (NDVI {ndvi_before:.2f}) before claimed disaster date.",
        })

    if ndvi_after > ndvi_before:
        fraud_indicators.append({
            "type": "NDVI_IMPROVEMENT",
            "severity": "CRITICAL",
            "description": "Satellite shows crop health improved after claimed disaster. Fraudulent claim.",
        })

    if claimed_area > float(farm["area_hectares"]):
        fraud_indicators.append({
            "type": "AREA_MISMATCH",
            "severity": "HIGH",
            "description": f"Claimed {claimed_area} ha exceeds registered farm size {farm['area_hectares']} ha.",
        })

    if damage_pct < 20:
        fraud_indicators.append({
            "type": "EXAGGERATED_CLAIM",
            "severity": "MEDIUM",
            "description": f"Satellite detected only {damage_pct:.1f}% damage, inconsistent with claim.",
        })

    return fraud_indicators


def _determine_status(damage_pct, fraud_indicators, ndvi_before):
    critical_fraud = [f for f in fraud_indicators if f["severity"] == "CRITICAL"]
    if critical_fraud:
        return "REJECTED"
    if ndvi_before < 0.35:
        return "FLAGGED"
    if fraud_indicators:
        return "FLAGGED"
    if damage_pct < 20:
        return "REJECTED"
    if damage_pct <= 50:
        return "FLAGGED"
    return "APPROVED"


def verify_claim_with_satellite(request_data: dict, user: dict):
    from services.satellite_service import compute_multi_index
    from services.sentinel_hub_service import save_verification_images

    farm = execute_query(
        "SELECT * FROM farm_parcels WHERE rsbsa_number = %s",
        (request_data["rsbsa_number"],),
        fetch_one=True,
    )
    if not farm:
        return None, "Farm not found with this RSBSA number"

    claimed_area = float(request_data["claimed_area_hectares"])
    farm_area = float(farm["area_hectares"])
    if claimed_area > farm_area + 0.01:
        return None, (
            f"Claimed area ({claimed_area} ha) exceeds registered farm area "
            f"({farm_area} ha). Maximum allowed is {farm_area + 0.01:.2f} ha."
        )

    disaster_date = request_data["disaster_date"]
    disaster = datetime.strptime(disaster_date, "%Y-%m-%d").date()

    polygon = farm.get("polygon")
    if isinstance(polygon, str):
        polygon = json.loads(polygon)

    if not polygon or len(polygon) < 3:
        return None, "Farm polygon is missing or invalid"

    lat = float(farm["latitude"])
    lng = float(farm["longitude"])

    before_start = (disaster - timedelta(days=45)).isoformat()
    before_end = (disaster - timedelta(days=7)).isoformat()
    after_start = disaster.isoformat()
    after_end = (disaster + timedelta(days=30)).isoformat()

    before_index = compute_multi_index(polygon, before_start, before_end)
    after_index = compute_multi_index(polygon, after_start, after_end)

    if isinstance(before_index, dict) and before_index.get("error") == "no_imagery":
        return None, (
            "No satellite imagery available for the pre-disaster period. "
            f"{before_index.get('reason', 'Verify the farm location and disaster date.')}"
        )
    if isinstance(after_index, dict) and after_index.get("error") == "no_imagery":
        return None, (
            "No satellite imagery available for the post-disaster period. "
            f"{after_index.get('reason', 'Verify the farm location and disaster date.')}"
        )

    if not before_index or not after_index:
        return None, (
            "No satellite imagery available for this farm location and date range. "
            "Verify the disaster date and farm coordinates."
        )

    ndvi_before = before_index.get("ndvi")
    ndvi_after = after_index.get("ndvi")

    if ndvi_before is None or ndvi_after is None:
        return None, (
            "No satellite imagery available for this farm location and date range. "
            "Verify the disaster date and farm coordinates."
        )

    ndvi_source = before_index.get("source", "earth-engine")
    before_date = before_end
    after_date = after_start
    ndvi_diff = abs(ndvi_before - ndvi_after)
    is_significant = ndvi_diff >= NDVI_SIGNIFICANCE_THRESHOLD

    rejection_reason = None
    if ndvi_before < LOW_VEGETATION_THRESHOLD and ndvi_after < LOW_VEGETATION_THRESHOLD:
        rejection_reason = (
            f"The farm location shows very low vegetation density in both pre-event and post-event "
            f"periods (before: {ndvi_before:.3f}, after: {ndvi_after:.3f}). This may indicate the "
            f"area is primarily built-up or bare land rather than active cropland. Field verification "
            f"recommended."
        )
    elif not is_significant:
        rejection_reason = (
            f"Satellite analysis shows no significant vegetation change in the claimed period. "
            f"The NDVI difference of {ndvi_diff:.3f} is within normal agricultural variability "
            f"and does not indicate crop damage."
        )

    if rejection_reason:
        damage_pct = 0.0
        fraud_indicators = []
        status = "REJECTED"
    elif ndvi_before < 0.35:
        return None, (
            f"Pre-event NDVI is too low ({ndvi_before:.2f}), indicating the crop was "
            "already stressed before the claimed disaster date."
        )
    else:
        if ndvi_before > 0:
            damage_pct = ((ndvi_before - ndvi_after) / ndvi_before) * 100
        else:
            damage_pct = 100.0 if ndvi_after < ndvi_before else 0.0
        damage_pct = max(0.0, round(damage_pct, 1))
        fraud_indicators = _detect_fraud(farm, claimed_area, ndvi_before, ndvi_after, damage_pct)
        status = _determine_status(damage_pct, fraud_indicators, ndvi_before)

    before_mid = (disaster - timedelta(days=26)).isoformat()
    after_mid = (disaster + timedelta(days=15)).isoformat()
    before_url, after_url = save_verification_images(
        farm["id"], lat, lng, before_mid, after_mid,
    )

    from services.ai_service import generate_claim_assessment
    ai_recommendation = generate_claim_assessment({
        "farmer_name": farm["farmer_name"],
        "crop_type": farm["crop_type"],
        "damage_type": request_data["damage_type"],
        "disaster_date": disaster_date,
        "status": status,
        "rejection_reason": rejection_reason,
        "is_significant_change": is_significant,
        "fraud_indicators": fraud_indicators,
        "satellite_analysis": {
            "ndvi_before": ndvi_before,
            "ndvi_after": ndvi_after,
            "damage_percentage": damage_pct,
            "ndwi_before": before_index.get("ndwi"),
            "ndwi_after": after_index.get("ndwi"),
            "lst_celsius_before": before_index.get("lst_celsius"),
            "lst_celsius_after": after_index.get("lst_celsius"),
        },
    })

    mun_id = farm["municipality_id"]
    municipality_code = "NAG" if "naga" in mun_id.lower() else mun_id.split("-")[-1].upper()[:3]
    year = datetime.now().year
    claim_number = f"{year}-{municipality_code}-{secrets.token_hex(4).upper()}"

    result = execute_query(
        """
        INSERT INTO claims (
            claim_number, parcel_id, farmer_name, rsbsa_number,
            damage_type, claimed_area_hectares, disaster_date, filed_date,
            ndvi_before, ndvi_after, damage_percentage,
            before_image_url, after_image_url,
            ai_recommendation, status, rejection_reason,
            verified_by_user_id, verified_at
        )
        VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, CURRENT_DATE,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s, NOW()
        )
        RETURNING id
        """,
        (
            claim_number,
            farm["id"],
            farm["farmer_name"],
            farm["rsbsa_number"],
            request_data["damage_type"],
            claimed_area,
            disaster_date,
            ndvi_before,
            ndvi_after,
            damage_pct,
            before_url,
            after_url,
            ai_recommendation,
            status,
            rejection_reason,
            user["id"],
        ),
        fetch_one=True,
    )

    claim_id = str(result["id"]) if result else secrets.token_hex(16)

    import json
    polygon = farm.get("polygon")
    if isinstance(polygon, str):
        polygon = json.loads(polygon)

    return {
        "claim_id": claim_id,
        "claim_number": claim_number,
        "parcel_id": farm["id"],
        "farmer_name": farm["farmer_name"],
        "rsbsa_number": farm["rsbsa_number"],
        "farm": {
            "id": farm["id"],
            "farmer_name": farm["farmer_name"],
            "rsbsa_number": farm["rsbsa_number"],
            "crop_type": farm["crop_type"],
            "area_hectares": float(farm["area_hectares"]),
            "latitude": float(farm["latitude"]),
            "longitude": float(farm["longitude"]),
            "polygon": polygon,
            "is_insured": bool(farm.get("is_insured", farm.get("insured", False))),
        },
        "disaster_date": disaster_date,
        "damage_type": request_data["damage_type"],
        "claimed_area_hectares": claimed_area,
        "satellite_analysis": {
            "before_date": str(before_date),
            "after_date": str(after_date),
            "ndvi_before": ndvi_before,
            "ndvi_after": ndvi_after,
            "ndvi_change": round(ndvi_after - ndvi_before, 3),
            "damage_percentage": damage_pct,
            "before_image_url": before_url,
            "after_image_url": after_url,
            "ndvi_source": ndvi_source,
            "ndwi_before": before_index.get("ndwi"),
            "ndwi_after": after_index.get("ndwi"),
            "lst_celsius_before": before_index.get("lst_celsius"),
            "lst_celsius_after": after_index.get("lst_celsius"),
            "flood_detected_before": before_index.get("flood_detected"),
            "flood_detected_after": after_index.get("flood_detected"),
            "heat_stress_before": before_index.get("heat_stress"),
            "heat_stress_after": after_index.get("heat_stress"),
            "capture_dates_before": before_index.get("capture_dates", []),
            "capture_dates_after": after_index.get("capture_dates", []),
        },
        "status": status,
        "rejection_reason": rejection_reason,
        "is_significant_change": is_significant,
        "ai_recommendation": ai_recommendation,
        "fraud_indicators": fraud_indicators,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }, None


def _claim_verify_steps():
    return [
        "Retrieving pre-event imagery...",
        "Computing before-event NDVI...",
        "Retrieving post-event imagery...",
        "Computing after-event NDVI...",
        "Generating assessment...",
    ]


def _validate_pcic_action_status(claim: dict) -> str | None:
    status = (claim.get("status") or "").upper()
    if status not in PCIC_ACTIONABLE_STATUSES:
        return (
            f"Claim in status {status} cannot be processed. "
            "Only PENDING or SUBMITTED claims are actionable."
        )
    return None


def _update_verify_job(job_id: str, **fields):
    with _claim_jobs_lock:
        job = _claim_verify_jobs.get(job_id)
        if job:
            job.update(fields)
            if "message" in fields:
                job["current_step"] = fields["message"]


def _recommendation_word(status: str) -> str:
    return {
        "APPROVED": "APPROVE",
        "REJECTED": "REJECT",
        "FLAGGED": "FLAG",
    }.get((status or "").upper(), "FLAG")


def _demo_ndvi_pair(parcel_id: str):
    """Oldest and newest NDVI records for a parcel from demo satellite data."""
    from utils.database import _load_demo_data

    data = _load_demo_data()
    records = [
        s for s in data.get("satellite_imagery", [])
        if s["parcel_id"] == parcel_id
    ]
    if not records:
        return None, None
    sorted_records = sorted(records, key=lambda r: r["capture_date"])
    before = sorted_records[0]
    after = sorted_records[-1]
    return before, after


def _demo_step(job_id: str, progress: int, message: str):
    _update_verify_job(
        job_id,
        status="running",
        progress=progress,
        message=message,
        current_step=message,
    )
    time.sleep(0.5)


def _demo_recommendation_from_damage(damage_pct: float) -> str:
    if damage_pct >= 60:
        return "APPROVE"
    if damage_pct >= 30:
        return "FLAG"
    return "REJECT"


def _run_claim_verify_job_demo(job_id: str, request_data: dict, user: dict):
    """Demo claim verification mirroring synchronous logic with progress updates."""
    try:
        _demo_step(job_id, 20, "Looking up farm record")

        farm = execute_query(
            "SELECT * FROM farm_parcels WHERE rsbsa_number = %s",
            (request_data["rsbsa_number"],),
            fetch_one=True,
        )
        if not farm:
            _update_verify_job(
                job_id,
                status="failed",
                progress=0,
                message="Farmer record not found. Check the RSBSA number.",
                error="Farmer record not found. Check the RSBSA number.",
            )
            return

        _demo_step(job_id, 35, "Fetching pre-event image")

        records = sorted(
            _load_satellite_records(farm["id"]),
            key=lambda r: r["capture_date"],
        )
        if records:
            ndvi_before = float(records[0]["ndvi_value"])
            before_date = str(records[0]["capture_date"])[:10]
        else:
            ndvi_before = 0.70
            before_date = "2024-09-01"

        _demo_step(job_id, 50, "Fetching post-event image")

        if len(records) > 1:
            ndvi_after = float(records[-1]["ndvi_value"])
            after_date = str(records[-1]["capture_date"])[:10]
        elif records:
            ndvi_after = 0.12
            after_date = str(records[0]["capture_date"])[:10]
        else:
            ndvi_after = 0.12
            after_date = "2024-11-25"

        _demo_step(job_id, 65, "Analyzing damage")

        damage_pct = max(
            0.0,
            round((ndvi_before - ndvi_after) / ndvi_before * 100, 1),
        ) if ndvi_before > 0 else 0.0

        _demo_step(job_id, 78, "Verifying weather records")

        weather_note = (
            "PAGASA records confirm heavy rainfall 124mm over 48 hours on the reported "
            "disaster date. Flooding consistent with reported damage."
        )

        _demo_step(job_id, 88, "Generating assessment")

        recommendation = _demo_recommendation_from_damage(damage_pct)
        status = {
            "APPROVE": "APPROVED",
            "FLAG": "FLAGGED",
            "REJECT": "REJECTED",
        }[recommendation]

        from services.ai_templates import select_ai_recommendation

        ai_recommendation = select_ai_recommendation(
            damage_type=request_data["damage_type"],
            damage_pct=damage_pct,
            status=status,
            ndvi_before=ndvi_before,
            fraud_indicators=[],
            ndvi_after=ndvi_after,
        )

        _demo_step(job_id, 95, "Saving claim record")

        import uuid

        claim_id = str(uuid.uuid4())
        claim_number = f"2026-NAG-{uuid.uuid4().hex[:8].upper()}"
        claim_record = {
            "id": claim_id,
            "claim_number": claim_number,
            "parcel_id": farm["id"],
            "farmer_name": farm["farmer_name"],
            "rsbsa_number": farm["rsbsa_number"],
            "damage_type": request_data["damage_type"],
            "claimed_area_hectares": float(request_data["claimed_area_hectares"]),
            "disaster_date": request_data["disaster_date"],
            "filed_date": datetime.utcnow().date().isoformat(),
            "ndvi_before": ndvi_before,
            "ndvi_after": ndvi_after,
            "damage_percentage": damage_pct,
            "before_image_url": _resolve_image_url(farm["id"], before_date, "before"),
            "after_image_url": _resolve_image_url(farm["id"], after_date, "after"),
            "ai_recommendation": ai_recommendation,
            "status": "PENDING",
            "rejection_reason": None,
            "verified_by_user_id": user.get("id"),
            "verified_at": datetime.utcnow().isoformat() + "Z",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "weather_note": weather_note,
        }
        from utils.database import add_demo_claim
        add_demo_claim(claim_record)

        result = {
            "claim_id": claim_id,
            "claim_number": claim_number,
            "parcel_id": farm["id"],
            "farmer_name": farm["farmer_name"],
            "rsbsa_number": farm["rsbsa_number"],
            "disaster_date": request_data["disaster_date"],
            "damage_type": request_data["damage_type"],
            "claimed_area_hectares": float(request_data["claimed_area_hectares"]),
            "damage_percentage": damage_pct,
            "recommendation": recommendation,
            "ndvi_before": ndvi_before,
            "ndvi_after": ndvi_after,
            "satellite_analysis": {
                "before_date": before_date,
                "after_date": after_date,
                "ndvi_before": ndvi_before,
                "ndvi_after": ndvi_after,
                "ndvi_change": round(ndvi_before - ndvi_after, 3),
                "damage_percentage": damage_pct,
                "before_image_url": claim_record["before_image_url"],
                "after_image_url": claim_record["after_image_url"],
            },
            "status": status,
            "ai_recommendation": ai_recommendation,
            "created_at": claim_record["created_at"],
        }

        _update_verify_job(
            job_id,
            status="completed",
            progress=100,
            message="Claim verified",
            current_step="Claim verified",
            claim_id=claim_id,
            claim_number=claim_number,
            farmer_name=farm["farmer_name"],
            damage_percentage=damage_pct,
            recommendation=recommendation,
            ndvi_before=ndvi_before,
            ndvi_after=ndvi_after,
            result=result,
        )
    except Exception as exc:
        logger.error("Claim verify job failed: %s", exc)
        _update_verify_job(
            job_id,
            status="failed",
            progress=0,
            message="Verification failed. File the claim manually from the Claims page.",
            error="Verification failed. File the claim manually from the Claims page.",
        )


def _run_claim_verify_job(job_id: str, request_data: dict, user: dict):
    if is_demo_mode():
        _run_claim_verify_job_demo(job_id, request_data, user)
        return

    steps = _claim_verify_steps()
    try:
        for idx, step in enumerate(steps):
            _update_verify_job(
                job_id,
                current_step=step,
                progress=int((idx / len(steps)) * 90),
            )
            time.sleep(1.5)

        result, error = verify_claim_with_satellite(request_data, user)
        if error:
            _update_verify_job(job_id, status="failed", error=error, progress=100)
        else:
            _update_verify_job(
                job_id,
                status="completed",
                progress=100,
                current_step="Verification complete",
                result=result,
            )
    except Exception as exc:
        logger.exception("Claim verify job %s failed", job_id)
        _update_verify_job(job_id, status="failed", error=str(exc), progress=100)


def verify_claim_async(
    rsbsa_number: str,
    disaster_date: str,
    damage_type: str,
    claimed_area: float,
    user: dict,
) -> dict:
    """Start background claim verification and return job metadata."""
    import threading
    import uuid

    job_id = str(uuid.uuid4())
    request_data = {
        "rsbsa_number": rsbsa_number,
        "disaster_date": disaster_date,
        "damage_type": damage_type,
        "claimed_area_hectares": claimed_area,
    }

    with _claim_jobs_lock:
        _claim_verify_jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "progress": 10,
            "message": "Starting verification",
            "current_step": "Starting verification",
            "result": None,
            "error": None,
            "rsbsa_number": rsbsa_number,
        }

    thread = threading.Thread(
        target=_run_claim_verify_job,
        args=(job_id, request_data, user),
        daemon=True,
        name=f"claim-verify-{job_id[:8]}",
    )
    thread.start()

    return {
        "job_id": job_id,
        "status": "running",
        "message": "Starting verification",
        "current_step": "Starting verification",
        "progress": 10,
    }


def get_claim_verify_status(job_id: str) -> dict | None:
    with _claim_jobs_lock:
        job = _claim_verify_jobs.get(job_id)
        return copy.deepcopy(job) if job else None


def get_claims_list(filters: dict):
    municipality_id = filters.get("municipality_id")
    status = filters.get("status")
    date_from = filters.get("disaster_date_from")
    date_to = filters.get("disaster_date_to")
    limit = min(filters.get("limit", 50), 200)
    offset = filters.get("offset", 0)

    if is_demo_mode():
        from utils.database import get_demo_claims, _load_demo_data
        data = _load_demo_data()
        claims = []
        for claim in get_demo_claims():
            farm = next((f for f in data["farms"] if f["id"] == claim.get("parcel_id")), {})
            entry = {
                "id": str(claim.get("id")),
                "claim_number": claim.get("claim_number"),
                "farmer_name": claim.get("farmer_name"),
                "rsbsa_number": claim.get("rsbsa_number"),
                "municipality": data["municipality"]["name"],
                "crop_type": farm.get("crop_type", "Rice"),
                "disaster_date": str(claim.get("disaster_date")),
                "damage_type": claim.get("damage_type"),
                "damage_percentage": claim.get("damage_percentage"),
                "ndvi_before": claim.get("ndvi_before"),
                "ndvi_after": claim.get("ndvi_after"),
                "status": claim.get("status"),
                "filed_date": str(claim.get("filed_date")),
                "verified_at": claim.get("verified_at"),
            }
            if municipality_id and farm.get("municipality_id") != municipality_id:
                continue
            if status and entry["status"] != status:
                continue
            claims.append(entry)
        total = len(claims)
        paginated = claims[offset:offset + limit]
        return {
            "claims": paginated,
            "pagination": {
                "total_count": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total,
            },
        }

    claims = execute_query(
        """
        SELECT
            c.id, c.claim_number, c.farmer_name, c.rsbsa_number,
            m.name AS municipality, fp.crop_type,
            c.disaster_date, c.damage_type, c.damage_percentage,
            c.ndvi_before, c.ndvi_after,
            c.status, c.filed_date, c.verified_at
        FROM claims c
        JOIN farm_parcels fp ON c.parcel_id = fp.id
        JOIN municipalities m ON fp.municipality_id = m.id
        WHERE (%s IS NULL OR fp.municipality_id = %s)
          AND (%s IS NULL OR c.status = %s)
          AND (%s IS NULL OR c.disaster_date >= %s)
          AND (%s IS NULL OR c.disaster_date <= %s)
        ORDER BY c.filed_date DESC
        LIMIT %s OFFSET %s
        """,
        (
            municipality_id, municipality_id,
            status, status,
            date_from, date_from,
            date_to, date_to,
            limit, offset,
        ),
        fetch_all=True,
    )

    count_result = execute_query(
        """
        SELECT COUNT(*) as count FROM claims c
        JOIN farm_parcels fp ON c.parcel_id = fp.id
        WHERE (%s IS NULL OR fp.municipality_id = %s)
          AND (%s IS NULL OR c.status = %s)
          AND (%s IS NULL OR c.disaster_date >= %s)
          AND (%s IS NULL OR c.disaster_date <= %s)
        """,
        (
            municipality_id, municipality_id,
            status, status,
            date_from, date_from,
            date_to, date_to,
        ),
        fetch_one=True,
    )
    total = count_result["count"] if count_result else 0

    formatted = []
    for claim in claims or []:
        disaster_date = claim["disaster_date"]
        filed_date = claim["filed_date"]
        verified_at = claim.get("verified_at")
        if hasattr(disaster_date, "isoformat"):
            disaster_date = disaster_date.isoformat()
        if hasattr(filed_date, "isoformat"):
            filed_date = filed_date.isoformat()
        if verified_at and hasattr(verified_at, "isoformat"):
            verified_at = verified_at.isoformat()

        formatted.append({
            "id": str(claim["id"]),
            "claim_number": claim["claim_number"],
            "farmer_name": claim["farmer_name"],
            "rsbsa_number": claim["rsbsa_number"],
            "municipality": claim["municipality"],
            "crop_type": claim["crop_type"],
            "disaster_date": str(disaster_date),
            "damage_type": claim["damage_type"],
            "damage_percentage": float(claim["damage_percentage"]) if claim.get("damage_percentage") is not None else None,
            "ndvi_before": float(claim["ndvi_before"]) if claim.get("ndvi_before") is not None else None,
            "ndvi_after": float(claim["ndvi_after"]) if claim.get("ndvi_after") is not None else None,
            "status": claim["status"],
            "filed_date": str(filed_date),
            "verified_at": str(verified_at) if verified_at else None,
        })

    return {
        "claims": formatted,
        "pagination": {
            "total_count": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        },
    }


def _build_claim_detail(claim: dict, farm: dict | None, municipality_name: str = "Kibawe") -> dict:
    import json as json_mod

    polygon = farm.get("polygon") if farm else None
    if isinstance(polygon, str):
        polygon = json_mod.loads(polygon)

    before_date = claim.get("before_date") or claim.get("disaster_date")
    after_date = claim.get("after_date") or claim.get("disaster_date")
    if claim.get("before_image_url"):
        for part in str(claim["before_image_url"]).split("_"):
            if part.startswith("2025-"):
                before_date = part.replace(".png", "")
                break
    if claim.get("after_image_url"):
        for part in str(claim["after_image_url"]).split("_"):
            if part.startswith("2025-"):
                after_date = part.replace(".png", "")
                break

    ndvi_before = float(claim["ndvi_before"]) if claim.get("ndvi_before") is not None else 0.0
    ndvi_after = float(claim["ndvi_after"]) if claim.get("ndvi_after") is not None else 0.0
    damage_pct = float(claim["damage_percentage"]) if claim.get("damage_percentage") is not None else 0.0

    parcel_id = claim.get("parcel_id") or (farm.get("id") if farm else None)
    before_url = claim.get("before_image_url") or _resolve_image_url(parcel_id, before_date, "before")
    after_url = claim.get("after_image_url") or _resolve_image_url(parcel_id, after_date, "after")

    fraud_indicators = []
    if farm:
        fraud_indicators = _detect_fraud(
            farm,
            float(claim.get("claimed_area_hectares", 0)),
            ndvi_before,
            ndvi_after,
            damage_pct,
        )

    ndvi_timeline = []
    if parcel_id:
        records = execute_query(
            """
            SELECT capture_date, ndvi_value FROM satellite_imagery
            WHERE parcel_id = %s
            ORDER BY capture_date ASC
            """,
            (parcel_id,),
            fetch_all=True,
        )
        for rec in records or []:
            cap = rec["capture_date"]
            if hasattr(cap, "isoformat"):
                cap = cap.isoformat()[:10]
            ndvi_timeline.append({"date": str(cap), "ndvi": float(rec["ndvi_value"])})

    verified_at = claim.get("verified_at")
    if verified_at and hasattr(verified_at, "isoformat"):
        verified_at = verified_at.isoformat()

    return {
        "claim_id": str(claim.get("id")),
        "claim_number": claim.get("claim_number"),
        "parcel_id": parcel_id,
        "farmer_name": claim.get("farmer_name"),
        "rsbsa_number": claim.get("rsbsa_number"),
        "municipality": municipality_name,
        "disaster_date": str(claim.get("disaster_date")),
        "damage_type": claim.get("damage_type"),
        "claimed_area_hectares": float(claim.get("claimed_area_hectares", 0)),
        "filed_date": str(claim.get("filed_date")),
        "status": claim.get("status"),
        "verified_at": verified_at,
        "rejection_reason": claim.get("rejection_reason"),
        "flag_reason": claim.get("flag_reason"),
        "farm": {
            "id": farm.get("id") if farm else parcel_id,
            "farmer_name": farm.get("farmer_name", claim.get("farmer_name")) if farm else claim.get("farmer_name"),
            "rsbsa_number": farm.get("rsbsa_number", claim.get("rsbsa_number")) if farm else claim.get("rsbsa_number"),
            "crop_type": farm.get("crop_type", "Rice") if farm else "Rice",
            "area_hectares": float(farm.get("area_hectares", 0)) if farm else 0,
            "latitude": float(farm.get("latitude", 13.6192)) if farm else 13.6192,
            "longitude": float(farm.get("longitude", 123.1814)) if farm else 123.1814,
            "polygon": polygon,
            "is_insured": bool(farm.get("is_insured", farm.get("insured", False))) if farm else False,
        } if farm or parcel_id else None,
        "satellite_analysis": {
            "before_date": str(before_date)[:10] if before_date else None,
            "after_date": str(after_date)[:10] if after_date else None,
            "ndvi_before": ndvi_before,
            "ndvi_after": ndvi_after,
            "ndvi_change": round(ndvi_after - ndvi_before, 3),
            "damage_percentage": damage_pct,
            "before_image_url": before_url,
            "after_image_url": after_url,
            "ndvi_source": claim.get("ndvi_source", "estimated"),
        },
        "ndvi_timeline": ndvi_timeline,
        "ai_recommendation": claim.get("ai_recommendation", ""),
        "fraud_indicators": fraud_indicators,
        "created_at": claim.get("created_at"),
    }


def get_claim_detail(claim_id: str):
    if is_demo_mode():
        from utils.database import get_demo_claims, _load_demo_data
        data = _load_demo_data()
        for claim in get_demo_claims():
            if str(claim.get("id")) == str(claim_id):
                farm = next((f for f in data["farms"] if f["id"] == claim.get("parcel_id")), None)
                return _build_claim_detail(claim, farm, data["municipality"]["name"])
        return None

    claim = execute_query(
        """
        SELECT c.*, fp.crop_type, fp.area_hectares, fp.latitude, fp.longitude, fp.polygon,
               m.name as municipality_name
        FROM claims c
        JOIN farm_parcels fp ON c.parcel_id = fp.id
        JOIN municipalities m ON fp.municipality_id = m.id
        WHERE c.id = %s
        """,
        (claim_id,),
        fetch_one=True,
    )
    if not claim:
        return None

    farm = {
        "id": claim["parcel_id"],
        "farmer_name": claim["farmer_name"],
        "rsbsa_number": claim["rsbsa_number"],
        "crop_type": claim.get("crop_type"),
        "area_hectares": claim.get("area_hectares"),
        "latitude": claim.get("latitude"),
        "longitude": claim.get("longitude"),
        "polygon": claim.get("polygon"),
    }
    return _build_claim_detail(claim, farm, claim.get("municipality_name", ""))


def get_claim_for_report(claim_id: str):
    if is_demo_mode():
        from utils.database import get_demo_claims, _load_demo_data
        data = _load_demo_data()
        for claim in get_demo_claims():
            if str(claim.get("id")) == str(claim_id):
                result = copy.deepcopy(claim)
                farm = next((f for f in data["farms"] if f["id"] == claim.get("parcel_id")), {})
                result["crop_type"] = farm.get("crop_type", "Rice")
                result["area_hectares"] = farm.get("area_hectares", 0)
                result["municipality_name"] = data["municipality"]["name"]
                result["province"] = data["municipality"]["province"]
                return result
        return None

    claim = execute_query(
        """
        SELECT c.*, fp.crop_type, fp.area_hectares, m.name as municipality_name, m.province
        FROM claims c
        JOIN farm_parcels fp ON c.parcel_id = fp.id
        JOIN municipalities m ON fp.municipality_id = m.id
        WHERE c.id = %s
        """,
        (claim_id,),
        fetch_one=True,
    )
    return claim


def _parse_report_id(report_id: str) -> str:
    """Extract claim_number from BA-{claim_number} report IDs."""
    normalized = (report_id or "").strip()
    if normalized.upper().startswith("BA-"):
        return normalized[3:]
    return normalized


def get_claim_by_report_id(report_id: str):
    claim_number = _parse_report_id(report_id)
    if not claim_number:
        return None

    if is_demo_mode():
        from utils.database import get_demo_claims, _load_demo_data

        data = _load_demo_data()
        for claim in get_demo_claims():
            if claim.get("claim_number") == claim_number:
                result = copy.deepcopy(claim)
                farm = next((f for f in data["farms"] if f["id"] == claim.get("parcel_id")), {})
                result["crop_type"] = farm.get("crop_type", "Rice")
                result["area_hectares"] = farm.get("area_hectares", 0)
                result["barangay"] = farm.get("barangay", "N/A")
                result["municipality_name"] = data["municipality"]["name"]
                result["province"] = data["municipality"]["province"]

                verified_by_user_id = claim.get("verified_by_user_id")
                verifier = next(
                    (u for u in data.get("users", []) if u.get("id") == verified_by_user_id),
                    None,
                )
                if verifier:
                    result["verified_by_name"] = (
                        f"{verifier.get('first_name', '')} {verifier.get('last_name', '')}".strip()
                    )
                else:
                    result["verified_by_name"] = "Municipal Agricultural Officer"
                return result
        return None

    return execute_query(
        """
        SELECT c.*, fp.crop_type, fp.area_hectares, m.name as municipality_name,
               u.first_name || ' ' || u.last_name as verified_by_name
        FROM claims c
        JOIN farm_parcels fp ON c.parcel_id = fp.id
        JOIN municipalities m ON fp.municipality_id = m.id
        LEFT JOIN users u ON c.verified_by_user_id = u.id
        WHERE c.claim_number = %s
        """,
        (claim_number,),
        fetch_one=True,
    )


def _get_claim_by_id(claim_id: str):
    if is_demo_mode():
        from utils.database import get_demo_claims
        for claim in get_demo_claims():
            if str(claim.get("id")) == str(claim_id):
                return claim
        return None

    return execute_query(
        "SELECT * FROM claims WHERE id = %s",
        (claim_id,),
        fetch_one=True,
    )


def _notify_mao_of_claim_decision(claim_id: str, status: str, reason: str | None = None):
    from services.notification_service import notify_mao_claim_status_change

    claim = _get_claim_by_id(claim_id)
    if not claim:
        return

    parcel_id = claim.get("parcel_id")
    municipality_id = None

    if is_demo_mode():
        data = _load_demo_data_for_claims()
        farm = next((f for f in data.get("farms", []) if f["id"] == parcel_id), None)
        municipality_id = farm.get("municipality_id") if farm else "camarines-naga"
    else:
        farm = execute_query(
            "SELECT municipality_id FROM farm_parcels WHERE id = %s",
            (parcel_id,),
            fetch_one=True,
        )
        municipality_id = farm.get("municipality_id") if farm else None

    notify_mao_claim_status_change(
        claim_id=str(claim_id),
        claim_number=claim.get("claim_number", ""),
        farmer_name=claim.get("farmer_name", ""),
        status=status,
        municipality_id=municipality_id,
        reason=reason,
    )


def _format_claim_action_response(claim: dict):
    return {
        "id": str(claim.get("id")),
        "claim_number": claim.get("claim_number"),
        "farmer_name": claim.get("farmer_name"),
        "rsbsa_number": claim.get("rsbsa_number"),
        "status": claim.get("status"),
        "rejection_reason": claim.get("rejection_reason"),
        "flag_reason": claim.get("flag_reason"),
        "verified_at": claim.get("verified_at"),
        "verified_by_user_id": claim.get("verified_by_user_id"),
    }


def approve_claim(claim_id: str, user_id: str):
    claim = _get_claim_by_id(claim_id)
    if not claim:
        return None, "Claim not found"

    status_error = _validate_pcic_action_status(claim)
    if status_error:
        return None, status_error

    updates = {
        "status": "APPROVED",
        "verified_by_user_id": user_id,
        "verified_at": datetime.utcnow().isoformat() + "Z",
        "rejection_reason": None,
    }

    if is_demo_mode():
        from utils.database import update_demo_claim
        updated = update_demo_claim(claim_id, updates)
        if updated:
            _notify_mao_of_claim_decision(claim_id, "APPROVED")
            return _format_claim_action_response(updated), None
        return None, "Claim not found"

    result = execute_query(
        """
        UPDATE claims
        SET status = 'APPROVED', verified_by_user_id = %s, verified_at = NOW(), rejection_reason = NULL
        WHERE id = %s
        RETURNING *
        """,
        (user_id, claim_id),
        fetch_one=True,
    )
    if not result:
        return None, "Claim not found"
    _notify_mao_of_claim_decision(claim_id, "APPROVED")
    return _format_claim_action_response(result), None


def reject_claim(claim_id: str, reason: str, user_id: str):
    claim = _get_claim_by_id(claim_id)
    if not claim:
        return None, "Claim not found"

    status_error = _validate_pcic_action_status(claim)
    if status_error:
        return None, status_error

    updates = {
        "status": "REJECTED",
        "rejection_reason": reason,
        "verified_by_user_id": user_id,
        "verified_at": datetime.utcnow().isoformat() + "Z",
    }

    if is_demo_mode():
        from utils.database import update_demo_claim
        updated = update_demo_claim(claim_id, updates)
        if updated:
            _notify_mao_of_claim_decision(claim_id, "REJECTED", reason)
            return _format_claim_action_response(updated), None
        return None, "Claim not found"

    result = execute_query(
        """
        UPDATE claims
        SET status = 'REJECTED', rejection_reason = %s, verified_by_user_id = %s, verified_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (reason, user_id, claim_id),
        fetch_one=True,
    )
    if not result:
        return None, "Claim not found"
    _notify_mao_of_claim_decision(claim_id, "REJECTED", reason)
    return _format_claim_action_response(result), None


def flag_claim(claim_id: str, reason: str, user_id: str):
    claim = _get_claim_by_id(claim_id)
    if not claim:
        return None, "Claim not found"

    status_error = _validate_pcic_action_status(claim)
    if status_error:
        return None, status_error

    updates = {
        "status": "FLAGGED",
        "flag_reason": reason,
        "verified_by_user_id": user_id,
        "verified_at": datetime.utcnow().isoformat() + "Z",
    }

    if is_demo_mode():
        from utils.database import update_demo_claim
        updated = update_demo_claim(claim_id, updates)
        if updated:
            _notify_mao_of_claim_decision(claim_id, "FLAGGED", reason)
            return _format_claim_action_response(updated), None
        return None, "Claim not found"

    result = execute_query(
        """
        UPDATE claims
        SET status = 'FLAGGED', flag_reason = %s, verified_by_user_id = %s, verified_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (reason, user_id, claim_id),
        fetch_one=True,
    )
    if not result:
        return None, "Claim not found"
    _notify_mao_of_claim_decision(claim_id, "FLAGGED", reason)
    return _format_claim_action_response(result), None


def reverse_claim_decision(claim_id: str, user_id: str):
    claim = _get_claim_by_id(claim_id)
    if not claim:
        return None, "Claim not found"
    if claim.get("status") != "APPROVED":
        return None, "Only approved claims can be reversed"

    updates = {
        "status": "PENDING",
        "verified_by_user_id": user_id,
        "verified_at": datetime.utcnow().isoformat() + "Z",
    }

    if is_demo_mode():
        from utils.database import update_demo_claim
        updated = update_demo_claim(claim_id, updates)
        if updated:
            return _format_claim_action_response(updated), None
        return None, "Claim not found"

    result = execute_query(
        """
        UPDATE claims
        SET status = 'PENDING', verified_by_user_id = %s, verified_at = NOW()
        WHERE id = %s AND status = 'APPROVED'
        RETURNING *
        """,
        (user_id, claim_id),
        fetch_one=True,
    )
    if not result:
        return None, "Claim not found"
    return _format_claim_action_response(result), None


def submit_claim_to_pcic(claim_id: str):
    if is_demo_mode():
        from utils.database import update_demo_claim
        updated = update_demo_claim(claim_id, {
            "status": "SUBMITTED",
            "submitted_at": datetime.utcnow().isoformat() + "Z",
        })
        if updated:
            _notify_pcic_of_submission(claim_id, updated)
            return {
                "claim_number": updated.get("claim_number"),
                "message": "Claim submitted to PCIC successfully",
            }, None
        return None, "Claim not found"

    result = execute_query(
        """
        UPDATE claims
        SET status = 'SUBMITTED', submitted_at = NOW()
        WHERE id = %s
        RETURNING claim_number, farmer_name, municipality_id
        """,
        (claim_id,),
        fetch_one=True,
    )
    if not result:
        return None, "Claim not found"

    _notify_pcic_of_submission(claim_id, result)
    return {
        "claim_number": result["claim_number"],
        "message": "Claim submitted to PCIC successfully",
    }, None


def _notify_pcic_of_submission(claim_id: str, claim: dict):
    from services.notification_service import notify_pcic_new_claim

    mun = execute_query(
        "SELECT name FROM municipalities WHERE id = %s",
        (claim.get("municipality_id"),),
        fetch_one=True,
    ) if not is_demo_mode() else None
    municipality_name = mun.get("name") if mun else "Naga City"
    if is_demo_mode():
        municipality_name = "Naga City"

    notify_pcic_new_claim(
        claim_id=str(claim_id),
        claim_number=claim.get("claim_number", ""),
        farmer_name=claim.get("farmer_name", "Farmer"),
        municipality_name=municipality_name,
    )


def _estimate_payout_amount(damage_percentage: float | None, crop_type: str = "Rice") -> float:
    base_rate = 25000 if (crop_type or "").lower() == "corn" else 30000
    pct = damage_percentage or 0
    return round(base_rate * (pct / 100), 2)


def get_regional_damage_summary():
    result = get_claims_list({"limit": 200})
    claims = result["claims"]
    by_municipality: dict = {}
    totals = {
        "total_claims": len(claims),
        "pending": 0,
        "approved": 0,
        "rejected": 0,
        "flagged": 0,
        "avg_damage_pct": 0.0,
    }
    damage_values = []

    for claim in claims:
        mun = claim.get("municipality") or "Unknown"
        if mun not in by_municipality:
            by_municipality[mun] = {
                "municipality": mun,
                "claim_count": 0,
                "total_damage_pct": 0.0,
                "approved": 0,
                "pending": 0,
                "flagged": 0,
                "rejected": 0,
            }
        entry = by_municipality[mun]
        entry["claim_count"] += 1
        status = (claim.get("status") or "").upper()
        status_key = status.lower()
        if status_key in ("approved", "pending", "flagged", "rejected"):
            entry[status_key] += 1
        if status in ("PENDING", "SUBMITTED"):
            totals["pending"] += 1
            if status == "SUBMITTED":
                entry["pending"] += 1
        elif status == "APPROVED":
            totals["approved"] += 1
        elif status == "REJECTED":
            totals["rejected"] += 1
        elif status == "FLAGGED":
            totals["flagged"] += 1
        dmg = claim.get("damage_percentage")
        if dmg is not None:
            entry["total_damage_pct"] += float(dmg)
            damage_values.append(float(dmg))

    municipalities = []
    for entry in by_municipality.values():
        count = entry["claim_count"] or 1
        municipalities.append({
            **entry,
            "avg_damage_pct": round(entry["total_damage_pct"] / count, 1) if entry["total_damage_pct"] else 0,
        })

    municipalities.sort(key=lambda m: m["claim_count"], reverse=True)
    if damage_values:
        totals["avg_damage_pct"] = round(sum(damage_values) / len(damage_values), 1)

    return {
        "totals": totals,
        "municipalities": municipalities,
        "recent_claims": claims[:10],
    }


def get_pcic_analytics():
    result = get_claims_list({"limit": 200})
    claims = result["claims"]
    by_status: dict = {}
    by_municipality: dict = {}
    by_damage_type: dict = {}
    damage_values = []

    for claim in claims:
        status = claim.get("status") or "UNKNOWN"
        by_status[status] = by_status.get(status, 0) + 1
        mun = claim.get("municipality") or "Unknown"
        by_municipality[mun] = by_municipality.get(mun, 0) + 1
        dmg_type = (claim.get("damage_type") or "unknown").lower()
        by_damage_type[dmg_type] = by_damage_type.get(dmg_type, 0) + 1
        if claim.get("damage_percentage") is not None:
            damage_values.append(float(claim["damage_percentage"]))

    approved = [c for c in claims if c.get("status") == "APPROVED"]
    total_payout = sum(
        _estimate_payout_amount(c.get("damage_percentage"), c.get("crop_type"))
        for c in approved
    )

    return {
        "total_claims": len(claims),
        "by_status": by_status,
        "by_municipality": [
            {"municipality": k, "count": v}
            for k, v in sorted(by_municipality.items(), key=lambda x: x[1], reverse=True)
        ],
        "by_damage_type": [
            {"damage_type": k, "count": v}
            for k, v in sorted(by_damage_type.items(), key=lambda x: x[1], reverse=True)
        ],
        "avg_damage_pct": round(sum(damage_values) / len(damage_values), 1) if damage_values else 0,
        "approval_rate": round(len(approved) / len(claims) * 100, 1) if claims else 0,
        "total_estimated_payout": round(total_payout, 2),
        "approved_count": len(approved),
    }


def get_pcic_payouts():
    result = get_claims_list({"limit": 200})
    claims = result["claims"]
    payouts = []
    for claim in claims:
        status = claim.get("status")
        if status not in ("APPROVED", "SUBMITTED", "VERIFIED"):
            continue
        amount = _estimate_payout_amount(claim.get("damage_percentage"), claim.get("crop_type"))
        payouts.append({
            "id": claim["id"],
            "claim_number": claim["claim_number"],
            "farmer_name": claim["farmer_name"],
            "municipality": claim["municipality"],
            "crop_type": claim.get("crop_type", "Rice"),
            "damage_percentage": claim.get("damage_percentage"),
            "status": status,
            "filed_date": claim.get("filed_date"),
            "verified_at": claim.get("verified_at"),
            "estimated_payout": amount,
            "payout_status": "PAID" if status == "APPROVED" else "PENDING",
        })

    payouts.sort(key=lambda p: p.get("filed_date") or "", reverse=True)
    total_paid = sum(p["estimated_payout"] for p in payouts if p["payout_status"] == "PAID")
    total_pending = sum(p["estimated_payout"] for p in payouts if p["payout_status"] == "PENDING")

    return {
        "payouts": payouts,
        "summary": {
            "total_records": len(payouts),
            "total_paid": round(total_paid, 2),
            "total_pending": round(total_pending, 2),
        },
    }