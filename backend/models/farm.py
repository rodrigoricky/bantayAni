from pydantic import BaseModel, Field
from typing import List, Optional, Any


class FarmParcel(BaseModel):
    id: str
    rsbsa_number: str
    farmer_name: str
    crop_type: str
    area_hectares: float
    latitude: float
    longitude: float
    polygon: List[List[float]]
    is_insured: bool = False
    latest_ndvi: Optional[float] = None
    ndvi_date: Optional[str] = None
    status: str
    status_color: str


class MunicipalityInfo(BaseModel):
    id: str
    name: str
    total_farms: int
    total_area_hectares: float


class FarmStats(BaseModel):
    healthy_count: int
    watch_count: int
    critical_count: int


class FarmListResponse(BaseModel):
    municipality: MunicipalityInfo
    farms: List[FarmParcel]
    stats: FarmStats


class NDVIHistoryItem(BaseModel):
    date: str
    ndvi: float
    status: str
    image_url: Optional[str] = None


class RecentClaim(BaseModel):
    claim_number: str
    disaster_date: str
    damage_type: str
    damage_percentage: Optional[float] = None
    status: str
    filed_date: str


class FarmDetailResponse(BaseModel):
    farm: dict
    ndvi_history: List[NDVIHistoryItem]
    recent_claims: List[RecentClaim]


class AddFarmRequest(BaseModel):
    farmer_name: str
    rsbsa_number: str
    municipality_id: str
    crop_type: str
    area_hectares: float = Field(gt=0)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    polygon: Optional[List[List[float]]] = None
    insured: bool = False