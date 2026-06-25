from fastapi import APIRouter, HTTPException, Request, status
import os

from models.auth import LoginRequest
from services.auth_service import (
    authenticate_user,
    check_login_rate_limit,
    clear_login_attempts,
    create_access_token,
    record_failed_login,
    sanitize_user_for_response,
)
from services.role_service import get_role_data

router = APIRouter()
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))


@router.post("/login")
def login(request_body: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    check_login_rate_limit(client_ip)

    user = authenticate_user(request_body.email, request_body.password)
    if not user:
        record_failed_login(client_ip, request_body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    clear_login_attempts(client_ip)
    token = create_access_token(user)
    role_data = get_role_data(user)
    safe_user = sanitize_user_for_response(user)
    safe_user["role_data"] = role_data

    return {
        "success": True,
        "data": {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": JWT_EXPIRATION_HOURS * 3600,
            "user": safe_user,
        },
        "error": None,
    }