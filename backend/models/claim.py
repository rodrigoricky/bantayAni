from pydantic import BaseModel, Field
from typing import List, Optional


class ClaimVerificationRequest(BaseModel):
    rsbsa_number: str = Field(..., pattern=r"^RSBSA-[A-Z0-9-]+$")
    disaster_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    damage_type: str = Field(..., pattern=r"^(flood|drought|typhoon|pest|disease|other)$")
    claimed_area_hectares: float = Field(..., gt=0, le=1000)


class SatelliteAnalysis(BaseModel):
    before_date: str
    after_date: str
    ndvi_before: float
    ndvi_after: float
    ndvi_change: float
    damage_percentage: float
    before_image_url: str
    after_image_url: str


class FraudIndicator(BaseModel):
    type: str
    severity: str
    description: str


class ClaimVerificationResponse(BaseModel):
    claim_id: str
    claim_number: str
    parcel_id: str
    farmer_name: str
    rsbsa_number: str
    disaster_date: str
    damage_type: str
    claimed_area_hectares: float
    satellite_analysis: SatelliteAnalysis
    status: str
    ai_recommendation: str
    fraud_indicators: List[FraudIndicator] = []
    created_at: str


class ClaimListItem(BaseModel):
    id: str
    claim_number: str
    farmer_name: str
    rsbsa_number: str
    municipality: str
    crop_type: str
    disaster_date: str
    damage_type: str
    damage_percentage: Optional[float] = None
    status: str
    filed_date: str
    verified_at: Optional[str] = None


class PaginationInfo(BaseModel):
    total_count: int
    limit: int
    offset: int
    has_more: bool


class ClaimListResponse(BaseModel):
    claims: List[ClaimListItem]
    pagination: PaginationInfo


class ReportRequest(BaseModel):
    claim_id: str


class ClaimRejectRequest(BaseModel):
    reason: str = Field(..., min_length=20)


class ClaimFlagRequest(BaseModel):
    reason: str = Field(..., min_length=1)