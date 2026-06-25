import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from services.auth_service import check_municipality_access, get_current_user
from fastapi.responses import StreamingResponse
from io import BytesIO

from services.satellite_service import (
    get_available_sentinel_dates,
    get_sentinel_imagery,
    get_ndvi_tiles_for_date,
    get_sentinel1_flood_tile_url,
    start_ndvi_scan_job,
    get_ndvi_scan_status,
)
from services import sentinel_hub_service
from utils.database import execute_query, is_demo_mode

router = APIRouter()

DEMO_AVAILABLE_DATES = [
    {"date": "2024-09-01", "cloud_cover": 3.2},
    {"date": "2024-09-05", "cloud_cover": 4.1},
    {"date": "2024-09-10", "cloud_cover": 2.8},
    {"date": "2024-09-15", "cloud_cover": 5.5},
    {"date": "2024-09-20", "cloud_cover": 3.9},
    {"date": "2024-09-25", "cloud_cover": 4.6},
    {"date": "2024-10-01", "cloud_cover": 6.2},
    {"date": "2024-10-05", "cloud_cover": 5.0},
    {"date": "2024-10-10", "cloud_cover": 7.1},
    {"date": "2024-10-15", "cloud_cover": 8.0},
    {"date": "2024-10-20", "cloud_cover": 6.8},
    {"date": "2024-10-22", "cloud_cover": 4.5},
    {"date": "2024-10-25", "cloud_cover": 8.2},
    {"date": "2024-10-30", "cloud_cover": 7.4},
    {"date": "2024-11-01", "cloud_cover": 5.3},
    {"date": "2024-11-05", "cloud_cover": 6.1},
    {"date": "2024-11-10", "cloud_cover": 4.9},
    {"date": "2024-11-15", "cloud_cover": 7.8},
    {"date": "2024-11-20", "cloud_cover": 5.6},
    {"date": "2024-11-25", "cloud_cover": 6.4},
]


def _filter_demo_dates(start_date: str, end_date: str) -> list:
    return [
        d for d in DEMO_AVAILABLE_DATES
        if start_date <= d["date"] <= end_date
    ]


class ComputeNdviRequest(BaseModel):
    parcel_id: str
    date: str


class ScanNdviRequest(BaseModel):
    municipality_id: str
    satellite_date: str


@router.get("/available-dates")
def available_dates(
    latitude: float = Query(13.6192),
    longitude: float = Query(123.1814),
    start_date: str = Query("2024-09-01"),
    end_date: str = Query("2024-12-31"),
    current_user: dict = Depends(get_current_user),
):
    try:
        if is_demo_mode() or os.environ.get("DATABASE_URL", "demo") == "demo":
            dates = _filter_demo_dates(start_date, end_date)
        else:
            dates = get_available_sentinel_dates(latitude, longitude, start_date, end_date)
        return {
            "success": True,
            "data": {
                "available_dates": dates,
                "total_count": len(dates),
            },
            "error": None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch satellite dates: {str(e)}")


@router.get("/imagery")
def imagery(
    latitude: float = Query(...),
    longitude: float = Query(...),
    date: str = Query(...),
    buffer_km: float = Query(5.0),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = get_sentinel_imagery(latitude, longitude, date, buffer_km)
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch imagery: {str(e)}")


@router.get("/ndvi-tiles")
def ndvi_tiles(
    request: Request,
    latitude: float = Query(13.6192),
    longitude: float = Query(123.1814),
    date: str = Query(...),
    buffer_km: float = Query(10.0),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = get_ndvi_tiles_for_date(latitude, longitude, date)
        if not result:
            result = get_sentinel_imagery(latitude, longitude, date, buffer_km)
            tile_url = result["tile_url"]
            bounds = result.get("bounds")
            source = result.get("source", "earth-engine")
            actual_date = result["actual_date"]
        else:
            tile_url = result["tile_url"]
            bounds = result.get("bounds")
            source = result.get("source", "earth-engine")
            actual_date = result.get("actual_date", date)

        expires_at = (datetime.utcnow() + timedelta(days=3)).isoformat() + "Z"
        return {
            "success": True,
            "data": {
                "tile_url": tile_url,
                "actual_date": actual_date,
                "cloud_cover": 0.0,
                "source": source,
                "expires_at": expires_at,
                "bounds": bounds,
            },
            "error": None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch NDVI tiles: {str(e)}")


@router.get("/sentinel-dates")
def sentinel_dates(
    lat: float = Query(13.6192),
    lng: float = Query(123.1814),
    start_date: str = Query("2024-09-01"),
    end_date: str = Query("2024-12-31"),
    current_user: dict = Depends(get_current_user),
):
    try:
        if is_demo_mode() or os.environ.get("DATABASE_URL", "demo") == "demo":
            dates = _filter_demo_dates(start_date, end_date)
        else:
            dates = sentinel_hub_service.get_available_dates(lat, lng, start_date, end_date)
        return {"success": True, "data": {"available_dates": dates, "total_count": len(dates)}, "error": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Sentinel Hub dates: {str(e)}")


@router.post("/scan-ndvi", status_code=202)
def scan_ndvi(body: ScanNdviRequest, current_user: dict = Depends(get_current_user)):
    check_municipality_access(current_user, body.municipality_id)
    try:
        result = start_ndvi_scan_job(body.municipality_id, body.satellite_date)
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NDVI scan failed: {str(e)}")


@router.get("/scan-status/{job_id}")
def scan_status(job_id: str, current_user: dict = Depends(get_current_user)):
    from services.claim_service import get_claim_verify_status

    job = get_ndvi_scan_status(job_id) or get_claim_verify_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    return {"success": True, "data": job, "error": None}


@router.post("/compute-ndvi")
def compute_ndvi(body: ComputeNdviRequest, current_user: dict = Depends(get_current_user)):
    farm = execute_query(
        "SELECT id, polygon FROM farm_parcels WHERE id = %s",
        (body.parcel_id,),
        fetch_one=True,
    )
    if not farm:
        raise HTTPException(status_code=404, detail="Farm parcel not found")

    import json
    polygon = farm.get("polygon")
    if isinstance(polygon, str):
        polygon = json.loads(polygon)

    if sentinel_hub_service.is_live_mode():
        result = sentinel_hub_service.compute_ndvi_for_polygon(polygon, body.date)
        if result:
            return {"success": True, "data": result, "error": None}

    from services.farm_service import _ndvi_for_date
    ndvi, capture, _health = _ndvi_for_date(body.parcel_id, body.date)
    if ndvi is None:
        raise HTTPException(status_code=404, detail="NDVI unavailable for this date")
    return {
        "success": True,
        "data": {"ndvi": ndvi, "actual_date": capture, "source": "estimated"},
        "error": None,
    }


@router.get("/sar-tiles")
def sar_tiles(
    latitude: float = Query(13.6192),
    longitude: float = Query(123.1814),
    start_date: str = Query("2024-10-01"),
    end_date: str = Query("2024-11-15"),
    current_user: dict = Depends(get_current_user),
):
    """Flood detection tiles from Sentinel-1 SAR (VV < -15 dB)."""
    try:
        result = get_sentinel1_flood_tile_url(latitude, longitude, start_date, end_date)
        if not result:
            raise HTTPException(
                status_code=404,
                detail="No Sentinel-1 SAR flood imagery available for this location and date range",
            )
        expires_at = (datetime.utcnow() + timedelta(days=3)).isoformat() + "Z"
        return {
            "success": True,
            "data": {
                "tile_url": result["tile_url"],
                "bounds": result.get("bounds"),
                "source": result.get("source", "sentinel-1"),
                "vv_threshold_db": result.get("vv_threshold_db", -15),
                "start_date": start_date,
                "end_date": end_date,
                "expires_at": expires_at,
            },
            "error": None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch SAR flood tiles: {str(e)}")


@router.get("/sentinel-image")
def sentinel_image(
    lat: float = Query(...),
    lng: float = Query(...),
    date: str = Query(...),
    type: str = Query("true-color"),
    buffer_km: float = Query(0.5),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = sentinel_hub_service.get_sentinel_image_png(lat, lng, date, type, buffer_km=buffer_km)
        return StreamingResponse(
            BytesIO(result["png_bytes"]),
            media_type="image/png",
            headers={
                "X-Image-Source": result.get("source", "unknown"),
                "X-Requested-Date": result.get("requested_date", date),
                "X-Actual-Date": result.get("actual_date", date),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Sentinel imagery unavailable: {str(e)}")