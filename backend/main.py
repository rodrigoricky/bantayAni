import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from api import auth, farms, claims, reports, satellite, chat, notifications, verify
from services.earth_engine import initialize_earth_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from middleware.error_handler import (
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

load_dotenv(Path(__file__).resolve().parent / ".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.earth_engine_enabled = False

    from utils.database import is_demo_mode, ensure_farms_data_integrity
    if is_demo_mode():
        if not ensure_farms_data_integrity():
            logger.critical("Demo farm data is corrupted and could not be restored from backup")

    try:
        import os
        from pathlib import Path

        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        if credentials_path and not Path(credentials_path).is_absolute():
            credentials_path = str(Path(__file__).resolve().parent / credentials_path)

        if not credentials_path:
            logger.warning("⚠️  GOOGLE_APPLICATION_CREDENTIALS not set. Using demo mode.")
        elif not Path(credentials_path).exists():
            logger.error("❌ Credentials file not found: %s", credentials_path)
        else:
            if initialize_earth_engine():
                logger.info("✅ Earth Engine initialized successfully")
                app.state.earth_engine_enabled = True
            else:
                logger.warning("⚠️  Earth Engine unavailable. Using demo mode.")
    except Exception as exc:
        logger.error("❌ Earth Engine initialization failed: %s", exc)
        app.state.earth_engine_enabled = False

    app.state.satellite_cache = {}
    if app.state.earth_engine_enabled:
        import threading

        def _warm_cache():
            try:
                from services.satellite_service import get_sentinel_imagery, NAGA_CENTER
                lat, lng = NAGA_CENTER
                for warmup_date in ("2024-10-14", "2024-11-01"):
                    try:
                        result = get_sentinel_imagery(lat, lng, warmup_date, buffer_km=10.0)
                        app.state.satellite_cache[f"{lat}_{lng}_{warmup_date}"] = result
                    except Exception:
                        pass
                logger.info("Satellite tile cache warmed for Naga City (%d entries)", len(app.state.satellite_cache))
            except Exception as exc:
                logger.warning("Satellite cache warmup skipped: %s", exc)

        threading.Thread(target=_warm_cache, daemon=True).start()

    yield


app = FastAPI(
    title="Bantay Ani API",
    description="Satellite crop monitoring and insurance claims verification",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(farms.router, prefix="/api/farms", tags=["Farms"])
app.include_router(claims.router, prefix="/api/claims", tags=["Claims"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(satellite.router, prefix="/api/satellite", tags=["Satellite"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(verify.router, prefix="/api/verify", tags=["Verification"])


@app.get("/api/health")
def health_check():
    from utils.database import is_demo_mode
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "mode": "demo" if is_demo_mode() else "production",
        },
        "error": None,
    }