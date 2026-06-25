import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

logger = logging.getLogger(__name__)

from models.farm import AddFarmRequest
from services.auth_service import get_current_user, check_municipality_access
from services.farm_service import (
    get_farms_by_municipality,
    get_farm_detail,
    add_farm_parcel,
    update_farm_parcel,
    get_regional_health,
    get_municipality_ndvi_status,
    start_background_ndvi_refresh,
    get_next_rsbsa_number,
)
from services.role_service import get_role_data
from utils.database import execute_query

router = APIRouter()


@router.get("/regional/health")
def regional_health(user: dict = Depends(get_current_user)):
    if user["role"] not in ("DA_REGIONAL", "ADMIN"):
        raise HTTPException(status_code=403, detail="DA Regional role required")

    role_data = get_role_data(user)
    municipalities = role_data.get("municipalities", [])
    result = get_regional_health(municipalities)
    return {"success": True, "data": result, "error": None}


@router.get("/next-rsbsa")
def next_rsbsa(
    municipality_id: str = Query(...),
    user: dict = Depends(get_current_user),
):
    check_municipality_access(user, municipality_id)
    next_rsbsa_number = get_next_rsbsa_number(municipality_id)
    return {"success": True, "data": {"rsbsa_number": next_rsbsa_number}, "error": None}


@router.post("/add")
def add_farm(farm_data: AddFarmRequest, user: dict = Depends(get_current_user)):
    check_municipality_access(user, farm_data.municipality_id)

    existing = execute_query(
        "SELECT id FROM farm_parcels WHERE rsbsa_number = %s",
        (farm_data.rsbsa_number,),
        fetch_one=True,
    )
    if existing:
        raise HTTPException(status_code=400, detail="RSBSA number already registered")

    result = add_farm_parcel(farm_data.model_dump())
    return {"success": True, "data": result, "error": None}


@router.get("/municipality/{municipality_id}")
def list_farms_by_municipality(
    municipality_id: str,
    status: Optional[str] = Query(None),
    crop_type: Optional[str] = Query(None),
    satellite_date: Optional[str] = Query(None),
    limit: int = Query(100, le=200),
    user: dict = Depends(get_current_user),
):
    check_municipality_access(user, municipality_id)

    try:
        result = get_farms_by_municipality(municipality_id, status, crop_type, limit, satellite_date)
        if result is None:
            raise HTTPException(status_code=404, detail="Municipality not found")

        if not satellite_date:
            start_background_ndvi_refresh(municipality_id, result.get("farms", []))

        return {"success": True, "data": result, "error": None}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to load farms for municipality %s", municipality_id)
        return {
            "success": False,
            "data": {
                "farms": [],
                "stats": {"healthy_count": 0, "watch_count": 0, "critical_count": 0},
                "municipality": {"id": municipality_id, "name": "Naga City", "total_farms": 0},
                "ndvi_source": "unavailable",
            },
            "error": f"Farm data temporarily unavailable. Reason: {exc}",
        }


@router.get("/municipality/{municipality_id}/ndvi-status")
def municipality_ndvi_status(
    municipality_id: str,
    user: dict = Depends(get_current_user),
):
    check_municipality_access(user, municipality_id)
    status = get_municipality_ndvi_status(municipality_id)
    return {"success": True, "data": status, "error": None}


@router.get("/by-rsbsa/{rsbsa_number}")
def get_farm_by_rsbsa(rsbsa_number: str, user: dict = Depends(get_current_user)):
    farm = execute_query(
        "SELECT * FROM farm_parcels WHERE rsbsa_number = %s",
        (rsbsa_number,),
        fetch_one=True,
    )
    if not farm:
        raise HTTPException(status_code=404, detail="RSBSA number not registered")

    if user["role"] == "MAO":
        check_municipality_access(user, farm["municipality_id"])

    import json
    polygon = farm.get("polygon")
    if isinstance(polygon, str):
        polygon = json.loads(polygon)

    return {
        "success": True,
        "data": {
            "id": farm["id"],
            "rsbsa_number": farm["rsbsa_number"],
            "farmer_name": farm["farmer_name"],
            "crop_type": farm["crop_type"],
            "area_hectares": float(farm["area_hectares"]),
            "latitude": float(farm["latitude"]),
            "longitude": float(farm["longitude"]),
            "polygon": polygon,
            "municipality_id": farm["municipality_id"],
        },
        "error": None,
    }


@router.put("/{parcel_id}")
def update_farm(parcel_id: str, farm_data: AddFarmRequest, user: dict = Depends(get_current_user)):
    existing = execute_query(
        "SELECT municipality_id FROM farm_parcels WHERE id = %s",
        (parcel_id,),
        fetch_one=True,
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Farm not found")

    check_municipality_access(user, existing["municipality_id"])
    result = update_farm_parcel(parcel_id, farm_data.model_dump())
    return {"success": True, "data": result, "error": None}


@router.get("/{parcel_id}")
def get_farm(parcel_id: str, user: dict = Depends(get_current_user)):
    result = get_farm_detail(parcel_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Farm not found")

    if user["role"] == "MAO":
        farm_municipality = result["farm"]["municipality"]["id"]
        check_municipality_access(user, farm_municipality)

    return {"success": True, "data": result, "error": None}