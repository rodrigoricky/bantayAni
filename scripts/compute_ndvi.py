"""Compute NDVI from Sentinel-2 GeoTIFF bands (B08 NIR, B04 Red)."""
# Requires: rasterio, numpy
# Usage: python compute_ndvi.py --input data/satellite/naga_before_2024-10-15.tif


def calculate_ndvi(nir_band, red_band):
    import numpy as np
    nir = nir_band.astype(float)
    red = red_band.astype(float)
    denominator = nir + red
    ndvi = np.where(denominator != 0, (nir - red) / denominator, 0)
    return np.clip(ndvi, -1, 1)


if __name__ == "__main__":
    print("NDVI computation script — requires rasterio and GeoTIFF input files.")
    print("Demo NDVI values are pre-seeded in database/seed.sql")