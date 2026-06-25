from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from models.claim import ClaimVerificationRequest, ClaimRejectRequest, ClaimFlagRequest
from services.auth_service import get_current_user
from services.claim_service import (
    verify_claim_with_satellite,
    verify_claim_async,
    get_claims_list,
    get_claim_detail,
    approve_claim,
    reject_claim,
    flag_claim,
    reverse_claim_decision,
    get_regional_damage_summary,
    get_pcic_analytics,
    get_pcic_payouts,
)

router = APIRouter()


def _require_pcic(user: dict):
    if user.get("role") != "PCIC":
        raise HTTPException(status_code=403, detail="PCIC role required")


def _require_regional(user: dict):
    if user.get("role") not in ("DA_REGIONAL", "ADMIN"):
        raise HTTPException(status_code=403, detail="DA Regional role required")


@router.get("/regional/summary")
def regional_damage_summary(user: dict = Depends(get_current_user)):
    _require_regional(user)
    return {"success": True, "data": get_regional_damage_summary(), "error": None}


@router.get("/pcic/analytics")
def pcic_analytics(user: dict = Depends(get_current_user)):
    _require_pcic(user)
    return {"success": True, "data": get_pcic_analytics(), "error": None}


@router.get("/pcic/payouts")
def pcic_payouts(user: dict = Depends(get_current_user)):
    _require_pcic(user)
    return {"success": True, "data": get_pcic_payouts(), "error": None}


@router.post("/verify")
def verify_claim(request: ClaimVerificationRequest, user: dict = Depends(get_current_user)):
    result, error = verify_claim_with_satellite(request.model_dump(), user)
    if error:
        error_lower = error.lower()
        if "exceeds registered farm area" in error_lower:
            status_code = 422
        elif "pre-event ndvi" in error_lower or "already stressed" in error_lower:
            status_code = 422
        elif "not found" in error_lower:
            status_code = 404
        elif "no satellite imagery" in error_lower or "no_imagery" in error_lower:
            status_code = 404
        else:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=error)

    return {"success": True, "data": result, "error": None}


@router.post("/verify-async")
def verify_claim_async_endpoint(request: ClaimVerificationRequest, user: dict = Depends(get_current_user)):
    """Start background claim verification for chatbot Create Report flow."""
    job = verify_claim_async(
        rsbsa_number=request.rsbsa_number,
        disaster_date=request.disaster_date,
        damage_type=request.damage_type,
        claimed_area=request.claimed_area_hectares,
        user=user,
    )
    return {"success": True, "data": job, "error": None}


@router.get("")
def list_claims(
    municipality_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    disaster_date_from: Optional[str] = Query(None),
    disaster_date_to: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    if user["role"] == "MAO" and not municipality_id:
        municipality_id = user.get("municipality_id")

    result = get_claims_list({
        "municipality_id": municipality_id,
        "status": status,
        "disaster_date_from": disaster_date_from,
        "disaster_date_to": disaster_date_to,
        "limit": limit,
        "offset": offset,
    })

    return {"success": True, "data": result, "error": None}


@router.get("/{claim_id}")
def get_claim(claim_id: str, user: dict = Depends(get_current_user)):
    result = get_claim_detail(claim_id)
    if not result:
        raise HTTPException(status_code=404, detail="Claim not found")
    return {"success": True, "data": result, "error": None}


@router.post("/{claim_id}/submit")
def submit_claim(claim_id: str, user: dict = Depends(get_current_user)):
    from services.claim_service import submit_claim_to_pcic

    result, error = submit_claim_to_pcic(claim_id)
    if error:
        raise HTTPException(status_code=404, detail=error)

    return {"success": True, "data": result, "error": None}


@router.post("/{claim_id}/approve")
def approve_claim_endpoint(claim_id: str, user: dict = Depends(get_current_user)):
    _require_pcic(user)
    result, error = approve_claim(claim_id, user["id"])
    if error:
        raise HTTPException(status_code=404, detail=error)
    return {"success": True, "data": result, "error": None}


@router.post("/{claim_id}/reject")
def reject_claim_endpoint(
    claim_id: str,
    body: ClaimRejectRequest,
    user: dict = Depends(get_current_user),
):
    _require_pcic(user)
    result, error = reject_claim(claim_id, body.reason, user["id"])
    if error:
        raise HTTPException(status_code=404, detail=error)
    return {"success": True, "data": result, "error": None}


@router.post("/{claim_id}/flag")
def flag_claim_endpoint(
    claim_id: str,
    body: ClaimFlagRequest,
    user: dict = Depends(get_current_user),
):
    _require_pcic(user)
    result, error = flag_claim(claim_id, body.reason, user["id"])
    if error:
        raise HTTPException(status_code=404, detail=error)
    return {"success": True, "data": result, "error": None}


@router.post("/{claim_id}/reverse")
def reverse_claim_endpoint(claim_id: str, user: dict = Depends(get_current_user)):
    _require_pcic(user)
    result, error = reverse_claim_decision(claim_id, user["id"])
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"success": True, "data": result, "error": None}