import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from utils.database import execute_query

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
security = HTTPBearer()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()
if not JWT_SECRET_KEY or JWT_SECRET_KEY in ("dev-secret-key", "change-me-in-production"):
    raise RuntimeError(
        "JWT_SECRET_KEY must be set in environment variables. Refusing to start with default secret."
    )
if len(JWT_SECRET_KEY) < 32:
    logger.critical(
        "JWT_SECRET_KEY is only %d characters; use at least 32 characters for production security.",
        len(JWT_SECRET_KEY),
    )

_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_BLOCKED_IPS: dict[str, float] = {}
_MAX_FAILED_ATTEMPTS = 5
_ATTEMPT_WINDOW_SECONDS = 5 * 60
_BLOCK_DURATION_SECONDS = 15 * 60
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user: dict) -> str:
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        "user_id": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "municipality_id": user.get("municipality_id"),
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


LEGACY_EMAIL_ALIASES = {
    "mao.kibawe@da.gov.ph": "mao.naga@da.gov.ph",
}


def check_login_rate_limit(client_ip: str) -> None:
    """Raise 429 if the client IP is temporarily blocked after repeated failures."""
    now = time.time()
    blocked_until = _BLOCKED_IPS.get(client_ip)
    if blocked_until and now < blocked_until:
        retry_after = int(blocked_until - now)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )
    if blocked_until and now >= blocked_until:
        _BLOCKED_IPS.pop(client_ip, None)
        _LOGIN_ATTEMPTS.pop(client_ip, None)


def record_failed_login(client_ip: str, email: str) -> None:
    """Track a failed login attempt and block the IP after repeated failures."""
    logger.warning("Failed login attempt for email=%s from ip=%s", email, client_ip)
    now = time.time()
    attempts = [ts for ts in _LOGIN_ATTEMPTS.get(client_ip, []) if now - ts < _ATTEMPT_WINDOW_SECONDS]
    attempts.append(now)
    _LOGIN_ATTEMPTS[client_ip] = attempts
    if len(attempts) >= _MAX_FAILED_ATTEMPTS:
        _BLOCKED_IPS[client_ip] = now + _BLOCK_DURATION_SECONDS
        logger.warning(
            "Login rate limit triggered for ip=%s after %d failed attempts",
            client_ip,
            len(attempts),
        )


def clear_login_attempts(client_ip: str) -> None:
    _LOGIN_ATTEMPTS.pop(client_ip, None)
    _BLOCKED_IPS.pop(client_ip, None)


def sanitize_user_for_response(user: dict) -> dict:
    """Return user fields safe for API responses (never includes password_hash)."""
    return {
        "id": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "municipality_id": user.get("municipality_id"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
    }


def authenticate_user(email: str, password: str) -> Optional[dict]:
    email = LEGACY_EMAIL_ALIASES.get(email.lower(), email)
    user = execute_query(
        "SELECT * FROM users WHERE LOWER(email) = LOWER(%s)",
        (email,),
        fetch_one=True,
    )
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )
        from utils.database import resolve_municipality_id
        return {
            "id": user_id,
            "email": payload.get("email"),
            "role": payload.get("role"),
            "municipality_id": resolve_municipality_id(payload.get("municipality_id")),
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def check_municipality_access(user: dict, municipality_id: str):
    from utils.database import resolve_municipality_id
    municipality_id = resolve_municipality_id(municipality_id)
    user_mun = resolve_municipality_id(user.get("municipality_id"))
    if user["role"] in ("DA_REGIONAL", "PCIC", "ADMIN"):
        return
    if user["role"] == "MAO" and user_mun != municipality_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this municipality",
        )