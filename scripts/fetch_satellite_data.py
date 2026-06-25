"""Fetch Sentinel-2 imagery from Google Earth Engine for Naga City, Camarines Sur."""
# Requires: earthengine-api
# AOI: Naga City rice farms (13.62°N, 123.19°E)
# Dates: 2024-10-15 (before), 2024-10-25 (after Typhoon Kristine)


def fetch_sentinel2():
    print("Google Earth Engine fetch script.")
    print("Demo satellite data is pre-loaded in data/farms.json and database/seed.sql")
    print("To fetch live data:")
    print("  1. Authenticate: earthengine authenticate")
    print("  2. Set AOI bounding box around Naga City")
    print("  3. Filter: S2_SR_HARMONIZED, cloud_cover < 30%")
    print("  4. Export B04 (Red) and B08 (NIR) bands as GeoTIFF")


if __name__ == "__main__":
    fetch_sentinel2()