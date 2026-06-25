def classify_health_status(ndvi_value):
    if ndvi_value is None:
        return "UNKNOWN", "#6b7280"
    ndvi = float(ndvi_value)
    if ndvi >= 0.6:
        return "HEALTHY", "#22c55e"
    elif ndvi >= 0.4:
        return "WATCH", "#eab308"
    else:
        return "CRITICAL", "#ef4444"


def calculate_ndvi(nir, red):
    if red + nir == 0:
        return 0.0
    return (nir - red) / (nir + red)


def classify_ndvi_label(ndvi_value):
    status, _ = classify_health_status(ndvi_value)
    labels = {
        "HEALTHY": "healthy vegetation",
        "WATCH": "moderate vegetation stress",
        "CRITICAL": "severe damage or water cover",
        "UNKNOWN": "unknown",
    }
    return labels.get(status, "unknown")