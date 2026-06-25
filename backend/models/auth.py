from enum import Enum

from pydantic import BaseModel, Field
from typing import Any, Dict, Optional


class UserRole(str, Enum):
    MAO = "MAO"
    DA_REGIONAL = "DA_REGIONAL"
    PCIC = "PCIC"
    ADMIN = "ADMIN"


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    password: str = Field(..., min_length=6, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    municipality_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role_data: Optional[Dict[str, Any]] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse