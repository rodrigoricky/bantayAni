"""Predefined AI assessment templates for claim verification."""


def select_ai_recommendation(
    damage_type: str,
    damage_pct: float,
    status: str,
    ndvi_before: float,
    fraud_indicators: list,
    ndvi_after: float | None = None,
    is_significant: bool = True,
) -> str:
    damage_type_lower = (damage_type or "").lower()
    ndvi_after = ndvi_after if ndvi_after is not None else ndvi_before
    ndvi_diff = abs((ndvi_before or 0) - (ndvi_after or 0))

    if not is_significant or ndvi_diff < 0.08:
        return (
            f"No big NDVI change for this period. "
            f"NDVI went from {ndvi_before:.3f} to {ndvi_after:.3f}. "
            f"This looks like normal crop variation, not disaster damage."
        )

    if ndvi_before < 0.15 and ndvi_after < 0.15:
        return (
            f"Both readings are very low (before {ndvi_before:.3f}, after {ndvi_after:.3f}). "
            f"The parcel may be bare land or built-up area. Please verify on the ground."
        )

    if ndvi_before < 0.35:
        return (
            f"Pre-event NDVI was already low at {ndvi_before:.3f}. "
            f"Some stress may predate the claimed disaster. Field check recommended."
        )

    if status == "REJECTED" or damage_pct < 20:
        return (
            f"Satellite shows only {damage_pct:.1f}% loss, below the 20% payout threshold. "
            f"Ask the farmer if damage was limited to one section of the field."
        )

    if status == "FLAGGED" or (20 <= damage_pct <= 70):
        return (
            f"Partial damage detected at {damage_pct:.1f}%. "
            f"NDVI dropped from {ndvi_before:.3f} to {ndvi_after:.3f}. "
            f"Adjuster visit recommended before final approval."
        )

    if damage_pct > 70:
        if damage_type_lower in ("flood", "typhoon"):
            return (
                f"Severe flood damage confirmed. NDVI fell from {ndvi_before:.3f} to {ndvi_after:.3f}. "
                f"Pattern matches submergence across the parcel. Recommend expedited payout."
            )
        if damage_type_lower == "drought":
            return (
                f"Drought stress confirmed. NDVI declined steadily to {ndvi_after:.3f}. "
                f"Field-wide pattern supports the farmer's reported timeline."
            )
        if damage_type_lower in ("pest", "disease"):
            return (
                f"Patchy NDVI loss suggests biological stress. "
                f"Damage estimate is {damage_pct:.1f}%. Field sampling still recommended."
            )
        return (
            f"Severe crop loss at {damage_pct:.1f}%. "
            f"NDVI dropped from {ndvi_before:.3f} to {ndvi_after:.3f}. Recommend approval."
        )

    return (
        f"Verification complete. Review NDVI {ndvi_before:.3f} to {ndvi_after:.3f} "
        f"before your final decision."
    )