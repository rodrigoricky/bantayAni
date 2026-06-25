import hashlib
import os
from datetime import datetime

from fastapi import APIRouter

from services.claim_service import get_claim_by_report_id

router = APIRouter()

DEFAULT_VERIFY_SECRET = "bantayani-default-verify-secret"


def _mask_farmer_name(full_name: str) -> str:
    parts = (full_name or "").strip().split()
    if not parts:
        return "N/A"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[1][0]}."


def _format_date(value, fmt="%B %d, %Y"):
    if not value:
        return None
    if hasattr(value, "strftime"):
        return value.strftime(fmt)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime(fmt)
    except ValueError:
        return str(value)


def _verified_at_iso(value) -> str:
    if not value:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _compute_report_integrity(claim_id: str, verified_at: str) -> str:
    secret = os.getenv("VERIFY_SECRET", DEFAULT_VERIFY_SECRET)
    payload = f"{claim_id}{verified_at}{secret}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _build_verification_payload(claim: dict) -> dict:
    verified_at_raw = claim.get("verified_at")
    verified_at_iso = _verified_at_iso(verified_at_raw)
    claim_id = str(claim.get("id", ""))

    return {
        "verified": True,
        "claim_number": claim.get("claim_number"),
        "farmer_name": _mask_farmer_name(claim.get("farmer_name", "")),
        "municipality": claim.get("municipality_name") or claim.get("municipality", "N/A"),
        "barangay": claim.get("barangay", "N/A"),
        "crop_type": claim.get("crop_type", "N/A"),
        "area_hectares": float(claim.get("area_hectares") or 0),
        "damage_percentage": float(claim.get("damage_percentage") or 0),
        "status": claim.get("status", "PENDING"),
        "disaster_date": _format_date(claim.get("disaster_date")),
        "verification_date": _format_date(verified_at_raw),
        "verified_by": claim.get("verified_by_name", "Municipal Agricultural Officer"),
        "generated_at": datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC"),
        "report_integrity": _compute_report_integrity(claim_id, verified_at_iso),
    }


@router.get("/{report_id}")
def verify_report(report_id: str):
    claim = get_claim_by_report_id(report_id)
    if not claim:
        return {
            "success": True,
            "data": {"verified": False},
            "error": None,
        }

    return {
        "success": True,
        "data": _build_verification_payload(claim),
        "error": None,
    }