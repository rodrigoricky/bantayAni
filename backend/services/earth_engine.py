"""Google Earth Engine initialization with graceful demo fallback."""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

EE_AVAILABLE = False
_ee = None


def initialize_earth_engine():
    global EE_AVAILABLE, _ee

    try:
        import ee as earth_engine

        _ee = earth_engine
    except ImportError:
        logger.warning("earthengine-api not installed. Using demo satellite mode.")
        return False

    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    backend_root = Path(__file__).resolve().parent.parent
    if not creds_path:
        creds_path = str(backend_root / "credentials" / "earth-engine-key.json")
    elif not Path(creds_path).is_absolute():
        creds_path = str(backend_root / creds_path)

    project = os.getenv("GOOGLE_EE_PROJECT", "")
    try:
        if creds_path and Path(creds_path).exists():
            with open(creds_path) as f:
                import json
                key_data = json.load(f)
            if not project:
                project = key_data.get("project_id", "")
            credentials = _ee.ServiceAccountCredentials(
                email=key_data.get("client_email"),
                key_file=creds_path,
            )
            _ee.Initialize(credentials, project=project or None)
        else:
            _ee.Initialize(project=project or None)

        EE_AVAILABLE = True
        logger.info("Earth Engine initialized successfully (project=%s)", project)
        return True
    except Exception as exc:
        EE_AVAILABLE = False
        logger.warning("Earth Engine initialization failed: %s. Using demo mode.", exc)
        return False


def get_ee():
    return _ee if EE_AVAILABLE else None


def is_ee_available():
    return EE_AVAILABLE