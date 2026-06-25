#!/usr/bin/env python3
"""Fetch real Sentinel Hub RGB + NDVI images for Kibawe demo (Oct vs Nov 2025)."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

load_dotenv(ROOT / "backend" / ".env")

from services import sentinel_hub_service as sh  # noqa: E402

KIBAWE_LAT = 7.9234
KIBAWE_LNG = 124.6021
OUT_DIR = ROOT / "frontend" / "public" / "satellite-previews"

FETCHES = [
    ("2025-10-14", "oct", "Pre-Typhoon Tino (healthy vegetation)"),
]

NOV_CANDIDATE_DATES = ["2025-11-18", "2025-11-15", "2025-11-08", "2025-11-01"]


def main():
    if not sh.is_live_mode():
        print("ERROR: SENTINEL_HUB_CLIENT_ID and SENTINEL_HUB_CLIENT_SECRET must be set in backend/.env")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for date, month_key, label in FETCHES:
        print(f"\n=== {label} ({date}) ===")
        for image_type, suffix in [("true-color", "rgb"), ("ndvi", "ndvi")]:
            result = sh.get_sentinel_image_png(
                KIBAWE_LAT, KIBAWE_LNG, date, image_type, buffer_km=0.5, force_live=True,
            )
            out_path = OUT_DIR / f"kibawe_{month_key}_{suffix}.png"
            out_path.write_bytes(result["png_bytes"])
            print(f"  Saved {out_path.name} ({len(result['png_bytes'])} bytes, source={result['source']})")

    print("\n=== Post-Typhoon Tino (damage) — November ===")
    best_rgb = None
    best_ndvi = None
    for date in NOV_CANDIDATE_DATES:
        for image_type, suffix in [("true-color", "rgb"), ("ndvi", "ndvi")]:
            result = sh.get_sentinel_image_png(
                KIBAWE_LAT, KIBAWE_LNG, date, image_type, buffer_km=0.5, force_live=True,
            )
            size = len(result["png_bytes"])
            print(f"  {date} {suffix}: {size} bytes (source={result['source']})")
            if suffix == "rgb" and (best_rgb is None or size > best_rgb[0]):
                best_rgb = (size, result["png_bytes"], date)
            if suffix == "ndvi" and (best_ndvi is None or size > best_ndvi[0]):
                best_ndvi = (size, result["png_bytes"], date)

    fallback_rgb = OUT_DIR / "BUK-001_2025-11-18.png"
    if best_rgb and best_rgb[0] > 2000:
        (OUT_DIR / "kibawe_nov_rgb.png").write_bytes(best_rgb[1])
        print(f"  Saved kibawe_nov_rgb.png from {best_rgb[2]} ({best_rgb[0]} bytes)")
    elif fallback_rgb.exists():
        (OUT_DIR / "kibawe_nov_rgb.png").write_bytes(fallback_rgb.read_bytes())
        print(f"  Saved kibawe_nov_rgb.png from fallback {fallback_rgb.name}")

    if best_ndvi and best_ndvi[0] > 1000:
        (OUT_DIR / "kibawe_nov_ndvi.png").write_bytes(best_ndvi[1])
        print(f"  Saved kibawe_nov_ndvi.png from {best_ndvi[2]} ({best_ndvi[0]} bytes)")

    oct_rgb = OUT_DIR / "kibawe_oct_rgb.png"
    nov_rgb = OUT_DIR / "kibawe_nov_rgb.png"
    for parcel in ("BUK-001", "BUK-002", "BUK-003", "BUK-004"):
        if oct_rgb.exists():
            (OUT_DIR / f"{parcel}_before.png").write_bytes(oct_rgb.read_bytes())
        if nov_rgb.exists():
            (OUT_DIR / f"{parcel}_after.png").write_bytes(nov_rgb.read_bytes())
        print(f"  Linked {parcel}_before.png / {parcel}_after.png")

    print("\nDone. Demo imagery ready in frontend/public/satellite-previews/")


if __name__ == "__main__":
    main()