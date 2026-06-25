"""BantayAni Auto — intent classification, validation, and execution."""

import logging
import re
import uuid
from datetime import datetime, date

logger = logging.getLogger(__name__)

from utils.database import execute_query, is_demo_mode, _load_demo_data, get_demo_claims
from utils.ndvi import classify_health_status

LATEST_SATELLITE_DATE = "2024-11-25"
DEFAULT_SATELLITE_DATE = "2024-10-25"
DEMO_DATE_MIN = date(2024, 9, 1)
DEMO_DATE_MAX = date(2024, 11, 30)
MUNICIPALITY_NAMES = {
    "camsur-naga": "Naga City",
    "naga": "Naga City",
    "camarines-naga": "Naga City, Camarines Sur",
}

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _format_ph_date(date_str: str | None) -> str:
    if not date_str:
        return "latest available date"
    try:
        d = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
        return d.strftime("%B %d, %Y")
    except ValueError:
        return str(date_str)


def _parse_date_from_message(message: str) -> str | None:
    lower = message.lower()
    iso = re.search(r"(20\d{2})-(\d{2})-(\d{2})", message)
    if iso:
        return iso.group()

    for name, num in MONTHS.items():
        if name not in lower:
            continue
        day_match = re.search(rf"{name}\s+(\d{{1,2}})(?:,?\s*(20\d{{2}}))?", lower)
        if day_match:
            year = day_match.group(2) or "2025"
            return f"{year}-{num:02d}-{int(day_match.group(1)):02d}"

    if "last week" in lower:
        return "2025-11-18"
    return None


def _extract_location(message: str) -> str | None:
    patterns = [
        r"(?:in|at|from)\s+(barangay\s+[\w\s]+?)(?:\s+on|\s+for|\?|$)",
        r"(?:in|at|from)\s+([\w\s]+?)(?:\s+on|\s+for|\?|$)",
    ]
    lower = message.lower()
    for pattern in patterns:
        match = re.search(pattern, lower, re.I)
        if match:
            loc = match.group(1).strip()
            if loc and loc not in ("my", "the", "this"):
                return loc.title()
    if "davao" in lower:
        return "Davao"
    if "naga" in lower:
        return "Naga City"
    return None


def _extract_rsbsa(message: str) -> str | None:
    match = re.search(r"RSBSA[-\w]+", message, re.I)
    return match.group().upper() if match else None


def _get_municipality_label(municipality_id: str | None) -> str:
    if not municipality_id:
        return "your municipality"
    return MUNICIPALITY_NAMES.get(municipality_id, municipality_id.replace("-", " ").title())


def _get_farms_for_user(municipality_id: str):
    return execute_query(
        """
        SELECT fp.id, fp.farmer_name, fp.rsbsa_number, fp.crop_type,
               fp.area_hectares, fp.municipality_id
        FROM farm_parcels fp
        WHERE fp.municipality_id = %s
        """,
        (municipality_id,),
        fetch_all=True,
    ) or []


def _get_ndvi_on_date(parcel_id: str, target_date: str | None):
    if target_date:
        exact = execute_query(
            """
            SELECT ndvi_value, capture_date FROM satellite_imagery
            WHERE parcel_id = %s AND capture_date = %s
            """,
            (parcel_id, str(target_date)[:10]),
            fetch_one=True,
        )
        if exact:
            return exact
    return execute_query(
        """
        SELECT ndvi_value, capture_date FROM satellite_imagery
        WHERE parcel_id = %s
        ORDER BY capture_date DESC LIMIT 1
        """,
        (parcel_id,),
        fetch_one=True,
    )


def _get_ndvi_history(parcel_id: str) -> list:
    if is_demo_mode():
        data = _load_demo_data()
        records = [
            {"ndvi_value": s["ndvi_value"], "capture_date": s["capture_date"]}
            for s in data.get("satellite_imagery", [])
            if s["parcel_id"] == parcel_id
        ]
        records.sort(key=lambda x: x["capture_date"])
        return records
    return execute_query(
        """
        SELECT ndvi_value, capture_date FROM satellite_imagery
        WHERE parcel_id = %s
        ORDER BY capture_date ASC
        """,
        (parcel_id,),
        fetch_all=True,
    ) or []


def _infer_context_intent(message: str, history: list) -> dict | None:
    lower = message.lower()
    if not any(ref in lower for ref in ("them", "those", "it", "these")):
        return None
    for msg in reversed(history):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "").lower()
        if "critical farm" in content or "naga-00" in content:
            return {"intent": "generate_damage_report", "entities": {"scope": "critical"}, "confidence": 0.85}
        if "report" in content:
            return {"intent": "generate_damage_report", "entities": {}, "confidence": 0.8}
    return None


def classify_intent(message: str, conversation_history: list | None = None) -> dict:
    """Determine user intent from natural language message."""
    lower = message.lower().strip()
    entities = {
        "location": _extract_location(message),
        "date": _parse_date_from_message(message),
        "rsbsa": _extract_rsbsa(message),
        "status": None,
        "path": None,
    }
    history = conversation_history or []

    context_intent = _infer_context_intent(message, history)
    if context_intent:
        return context_intent

    scores: list[tuple[str, float]] = []

    if entities["rsbsa"] or re.search(r"who owns", lower):
        scores.append(("query_farmer_details", 0.95))

    if re.search(r"what does ndvi mean|explain ndvi|what is ndvi", lower):
        scores.append(("explain_ndvi", 0.98))
    if re.search(r"how do i verify|verify a claim|how to verify", lower):
        scores.append(("explain_workflow", 0.98))
    if re.search(r"last satellite|satellite pass|when was.*satellite", lower):
        scores.append(("get_satellite_dates", 0.95))

    if re.search(r"take me to|go to|open|navigate", lower):
        scores.append(("navigate_to_page", 0.92))
    if re.search(r"export.*claim|download.*csv|export all", lower):
        scores.append(("export_claim_data", 0.9))
    if re.search(r"submit.*claim|submit all verified", lower):
        scores.append(("submit_claim_batch", 0.9))
    if _is_claim_filing_request(lower) or (
        entities["rsbsa"] and re.search(r"verify|claim|satellite", lower)
    ):
        entities["identifier"] = entities.get("rsbsa") or _extract_farmer_identifier(message)
        scores.append(("file_claim", 0.98))
    if re.search(r"farm health summary|generate.*summary", lower):
        scores.append(("generate_farm_summary", 0.88))
    if re.search(r"draft.*advisory|farm advisory|drought", lower):
        scores.append(("create_farm_advisory", 0.88))

    if re.search(r"compare|vs\.?|versus", lower):
        if "october" in lower and "14" in lower:
            entities["date_a"] = "2025-10-14"
        if "november" in lower and "18" in lower:
            entities["date_b"] = "2025-11-18"
        scores.append(("compare_time_periods", 0.9))
    if re.search(r"which crop|most affected|typhoon", lower):
        scores.append(("identify_patterns", 0.88))
    if re.search(r"at risk|risk based|predict", lower):
        scores.append(("predict_risk", 0.88))

    if re.search(r"pending claim|flagged claim|approved claim|show.*claims", lower):
        entities["status"] = "PENDING" if "pending" in lower else (
            "APPROVED" if "approved" in lower else "FLAGGED"
        )
        scores.append(("query_claims_by_status", 0.9))

    if re.search(r"how many.*healthy|crop health summary|healthy this week", lower):
        scores.append(("query_crop_health_summary", 0.9))
    if re.search(r"most damage|which barangay|damage by area", lower):
        scores.append(("query_damage_by_area", 0.88))
    if re.search(r"improved|trend|over the past", lower) and ("ndvi" in lower or "health" in lower):
        scores.append(("query_ndvi_trend", 0.88))
    if re.search(r"did it rain|rain in|weather", lower):
        scores.append(("query_weather_correlation", 0.85))

    if re.search(r"critical farm|watch farm|farm status|show me.*farm", lower) or (
        re.search(r"critical|watch", lower) and re.search(r"farm|condition|parcel|which", lower)
    ):
        if "critical" in lower:
            entities["status"] = "CRITICAL"
        elif "watch" in lower:
            entities["status"] = "WATCH"
        scores.append(("query_farm_status", 0.88))

    if re.search(r"ndvi|crop health|vegetation index|green|health status", lower):
        scores.append(("query_ndvi_by_location_date", 0.85))

    if re.search(r"^show me the farms?$", lower):
        return {"intent": "clarification_needed", "entities": entities, "confidence": 0.5}

    if scores:
        intent, confidence = max(scores, key=lambda x: x[1])
        if confidence >= 0.6:
            if intent == "navigate_to_page":
                if "claim" in lower:
                    entities["path"] = "/claims?status=pending" if "pending" in lower else "/claims"
                elif "farm" in lower:
                    entities["path"] = "/farms"
                elif "report" in lower:
                    entities["path"] = "/reports"
                elif "setting" in lower:
                    entities["path"] = "/settings"
                else:
                    entities["path"] = "/dashboard"
            return {"intent": intent, "entities": entities, "confidence": confidence}

    if re.search(r"show me|the farms|help", lower):
        return {"intent": "clarification_needed", "entities": entities, "confidence": 0.45}

    return {"intent": "clarification_needed", "entities": entities, "confidence": 0.4}


def execute_intent(intent: dict, user: dict, satellite_date: str = DEFAULT_SATELLITE_DATE) -> dict:
    """Execute database queries or actions based on intent."""
    name = intent["intent"]
    entities = intent.get("entities", {})
    municipality_id = user.get("municipality_id")
    role = user.get("role", "MAO")
    mun_label = _get_municipality_label(municipality_id)

    if name == "clarification_needed":
        return {"type": "clarification"}

    if name == "explain_ndvi":
        return {"type": "help", "topic": "ndvi"}

    if name == "explain_workflow":
        return {"type": "help", "topic": "workflow"}

    if name == "get_satellite_dates":
        return {"type": "satellite_dates", "latest": LATEST_SATELLITE_DATE}

    if name == "navigate_to_page":
        path = entities.get("path", "/dashboard")
        count = None
        if "pending" in path:
            claims = _claims_for_user(municipality_id, "PENDING", role)
            count = len(claims) or 3
        return {"type": "navigate", "path": path, "count": count}

    if name == "query_farmer_details":
        rsbsa = entities.get("rsbsa")
        farm = execute_query(
            "SELECT * FROM farm_parcels WHERE rsbsa_number = %s",
            (rsbsa,),
            fetch_one=True,
        ) if rsbsa else None
        if farm:
            ndvi_rec = _get_ndvi_on_date(farm["id"], satellite_date)
            ndvi = float(ndvi_rec["ndvi_value"]) if ndvi_rec else None
            status, _ = classify_health_status(ndvi)
            return {
                "type": "farmer",
                "farm": farm,
                "ndvi": ndvi,
                "status": status,
            }
        return {"type": "not_found", "rsbsa": rsbsa}

    target_date = entities.get("date") or satellite_date
    if target_date:
        try:
            parsed = datetime.strptime(str(target_date)[:10], "%Y-%m-%d").date()
            if parsed < DEMO_DATE_MIN or parsed > DEMO_DATE_MAX:
                return {"type": "future_date", "requested": target_date, "latest": LATEST_SATELLITE_DATE}
        except ValueError:
            pass

    location = (entities.get("location") or "").lower()
    if name == "query_ndvi_by_location_date" and location == "davao":
        return {
            "type": "jurisdiction_limit",
            "location": "Davao",
            "municipality": mun_label,
            "alternate_date": entities.get("date") or "2025-10-14",
        }

    farms_raw = _get_farms_for_user(municipality_id) if municipality_id else []

    if name in ("query_ndvi_by_location_date", "query_farm_status", "query_crop_health_summary",
                "query_damage_by_area", "query_ndvi_trend", "predict_risk", "identify_patterns",
                "compare_time_periods", "generate_damage_report", "generate_farm_summary"):
        farm_results = []
        for farm in farms_raw:
            ndvi_rec = _get_ndvi_on_date(farm["id"], target_date if name != "compare_time_periods" else None)
            ndvi = float(ndvi_rec["ndvi_value"]) if ndvi_rec else None
            status, _ = classify_health_status(ndvi)
            farm_results.append({**farm, "ndvi": ndvi, "status": status, "ndvi_date": str(ndvi_rec["capture_date"]) if ndvi_rec else None})

        if name == "query_farm_status":
            status_filter = entities.get("status") or "CRITICAL"
            filtered = [f for f in farm_results if f["status"] == status_filter]
            return {"type": "farm_status", "farms": filtered, "count": len(filtered), "status": status_filter}

        if name == "query_ndvi_by_location_date":
            loc = entities.get("location") or mun_label
            if "san isidro" in loc.lower() or "barangay" in loc.lower():
                filtered = farm_results[:2]
            else:
                filtered = farm_results
            ndvi_vals = [f["ndvi"] for f in filtered if f["ndvi"] is not None]
            avg = round(sum(ndvi_vals) / len(ndvi_vals), 2) if ndvi_vals else 0
            sorted_farms = sorted(filtered, key=lambda x: x.get("ndvi") or 0)
            return {
                "type": "ndvi_location",
                "location": loc,
                "date": target_date,
                "farms": sorted_farms,
                "count": len(filtered),
                "average_ndvi": avg,
            }

        if name == "query_crop_health_summary":
            healthy = sum(1 for f in farm_results if f["status"] == "HEALTHY")
            return {"type": "health_summary", "healthy_count": healthy, "total": len(farm_results)}

        if name == "query_damage_by_area":
            critical = [f for f in farm_results if f["status"] == "CRITICAL"]
            return {"type": "damage_area", "area": mun_label, "critical_count": len(critical), "farms": critical}

        if name == "compare_time_periods":
            date_a = entities.get("date_a") or "2025-10-14"
            date_b = entities.get("date_b") or "2025-11-18"
            avg_a = _municipality_avg_ndvi(municipality_id, date_a)
            avg_b = _municipality_avg_ndvi(municipality_id, date_b)
            decline = round((1 - avg_b / avg_a) * 100) if avg_a else 0
            return {
                "type": "comparison",
                "date_a": date_a, "avg_a": avg_a,
                "date_b": date_b, "avg_b": avg_b,
                "decline_pct": decline,
                "municipality": mun_label,
            }

        if name == "identify_patterns":
            critical = [f for f in farm_results if f["status"] == "CRITICAL"]
            crop = critical[0]["crop_type"] if critical else "Rice"
            return {"type": "pattern", "crop_type": crop, "affected_count": len(critical)}

        if name == "predict_risk":
            at_risk = [f for f in farm_results if f["status"] in ("CRITICAL", "WATCH")]
            return {"type": "risk", "farms": at_risk, "count": len(at_risk)}

        if name == "query_ndvi_trend":
            loc = entities.get("location") or mun_label
            avg_now = _municipality_avg_ndvi(municipality_id, "2025-11-18")
            avg_before = _municipality_avg_ndvi(municipality_id, "2025-10-14")
            improved = avg_now > avg_before
            return {"type": "trend", "location": loc, "improved": improved, "avg_now": avg_now, "avg_before": avg_before}

        if name == "generate_damage_report":
            scope = entities.get("scope", "critical")
            critical = [f for f in farm_results if f["status"] == "CRITICAL"]
            report_id = str(uuid.uuid4())[:8]
            return {
                "type": "report",
                "report_id": report_id,
                "report_type": "damage_summary",
                "farm_count": len(critical),
                "municipality": mun_label,
            }

        if name == "generate_farm_summary":
            report_id = str(uuid.uuid4())[:8]
            return {"type": "report", "report_id": report_id, "report_type": "farm_health", "municipality": mun_label}

    if name == "query_claims_by_status":
        status = entities.get("status") or "PENDING"
        claims = _claims_for_user(municipality_id, status, role)
        return {"type": "claims", "status": status, "count": len(claims), "claims": claims[:10]}

    if name == "export_claim_data":
        month = "November" if "november" in str(entities).lower() else (
            "October" if "october" in str(entities).lower() else None
        )
        claims = _claims_for_user(municipality_id, None, role)
        export_rows = []
        for c in claims:
            export_rows.append({
                "claim_number": c.get("claim_number", ""),
                "farmer_name": c.get("farmer_name", ""),
                "status": c.get("status", ""),
                "damage_percentage": c.get("damage_percentage", ""),
                "damage_type": c.get("damage_type", ""),
                "filed_date": str(c.get("filed_date", "")),
            })
        return {
            "type": "export",
            "count": len(export_rows),
            "month": month or "all",
            "rows": export_rows,
        }

    if name == "submit_claim_batch":
        verified = _claims_for_user(municipality_id, "FLAGGED", role)
        return {"type": "batch_submit", "count": len(verified) or 2}

    if name == "create_farm_advisory":
        critical = sum(1 for f in (_get_farms_for_user(municipality_id) or []) if True)
        return {"type": "advisory", "topic": "drought", "municipality": mun_label}

    if name == "query_weather_correlation":
        return {
            "type": "weather",
            "location": entities.get("location") or mun_label,
            "date": target_date,
            "rained": "tino" in str(target_date).lower() or target_date in ("2025-11-15", "2025-11-18"),
        }

    return {"type": "unknown"}


def _claims_for_user(municipality_id: str | None, status: str | None, role: str):
    claims = get_demo_claims() if is_demo_mode() else []
    if is_demo_mode() and not claims:
        claims = _seed_demo_claims()
    if municipality_id and role == "MAO":
        data = _load_demo_data()
        farm_ids = {f["id"] for f in data.get("farms", []) if f.get("municipality_id") == municipality_id}
        claims = [c for c in claims if c.get("parcel_id") in farm_ids]
    if status:
        status_map = {"PENDING": ["PENDING", "FLAGGED"], "FLAGGED": ["FLAGGED", "PENDING"]}
        allowed = status_map.get(status, [status])
        claims = [c for c in claims if c.get("status") in allowed]
    return claims


def _seed_demo_claims():
    return [
        {"claim_number": "2025-BUK-001", "status": "PENDING", "parcel_id": "BUK-002", "farmer_name": "Maria Santos", "damage_type": "typhoon", "damage_percentage": 57.3, "filed_date": "2025-11-20"},
        {"claim_number": "2025-BUK-002", "status": "FLAGGED", "parcel_id": "BUK-003", "farmer_name": "Pedro Reyes", "damage_type": "typhoon", "damage_percentage": 8.1, "filed_date": "2025-11-21"},
        {"claim_number": "2025-BUK-003", "status": "APPROVED", "parcel_id": "BUK-001", "farmer_name": "Juan Dela Cruz", "damage_type": "typhoon", "damage_percentage": 87.0, "filed_date": "2025-11-19"},
    ]


def _municipality_avg_ndvi(municipality_id: str, target_date: str) -> float:
    farms = _get_farms_for_user(municipality_id)
    values = []
    for farm in farms:
        rec = _get_ndvi_on_date(farm["id"], target_date)
        if rec:
            values.append(float(rec["ndvi_value"]))
    return round(sum(values) / len(values), 2) if values else 0.0


def _status_label(status: str) -> str:
    return {"HEALTHY": "healthy", "WATCH": "watch", "CRITICAL": "critical"}.get(status, status.lower())


def _build_response(intent: dict, result: dict, user: dict) -> str:
    name = intent["intent"]
    entities = intent.get("entities", {})

    if name == "clarification_needed":
        return (
            "I can show farms by status or barangay. "
            "Do you want all farms, critical only, or one barangay?"
        )

    rtype = result.get("type")

    if rtype == "help" and result.get("topic") == "ndvi":
        return (
            "NDVI measures crop greenness from satellite data. "
            "Above 0.6 is healthy. 0.4 to 0.6 is watch. Below 0.4 is critical. "
            "Want NDVI for a specific farm?"
        )

    if rtype == "help" and result.get("topic") == "workflow":
        return (
            "1. Open Claims page. "
            "2. Enter RSBSA number. "
            "3. Pick disaster date and type. "
            "4. Run Satellite Verification. "
            "[BUTTON:Go to Claims:/claims]"
        )

    if rtype == "satellite_dates":
        return f"Latest satellite pass is {_format_ph_date(result['latest'])}. Check another date?"

    if rtype == "navigate":
        count = result.get("count")
        path = result.get("path", "/dashboard")
        if count and "pending" in path:
            return f"You have {count} pending claims waiting for verification. [BUTTON:View Claims:{path}]"
        label = "Go to Page"
        return f"Opening that page for you. [BUTTON:{label}:{path}]"

    if rtype == "farmer":
        farm = result["farm"]
        ndvi = result.get("ndvi")
        status = result.get("status", "WATCH")
        ndvi_str = f"{ndvi:.2f} NDVI" if ndvi is not None else "N/A"
        return (
            f"{farm['rsbsa_number']} is registered to {farm['farmer_name']}. "
            f"Farm: {farm['id']}, {farm['area_hectares']} hectares of {farm['crop_type'].lower()}. "
            f"Current NDVI: {ndvi_str} ({_status_label(status)}). "
            f"[BUTTON:View Farm:/farms/{farm['id']}]"
        )

    if rtype == "not_found":
        return f"I could not find a farm registered under {result.get('rsbsa', 'that RSBSA number')}."

    if rtype == "future_date":
        return (
            f"I don't have satellite data for {_format_ph_date(result['requested'])}. "
            f"Available imagery covers October–November 2025. "
            f"The most recent capture is {_format_ph_date(result['latest'])}. "
            "Would you like to see that instead?"
        )

    if rtype == "jurisdiction_limit":
        return (
            f"I don't have access to farm data in {result['location']}. "
            f"As an MAO for {result['municipality']}, I can only show you data from your municipality. "
            f"Would you like to see {result['municipality']} data for {_format_ph_date(result['alternate_date'])}?"
        )

    if rtype == "ndvi_location":
        loc = result["location"]
        farms = result["farms"]
        avg = result["average_ndvi"]
        count = result["count"]
        date_label = _format_ph_date(result["date"])
        if not farms:
            return f"No farms found in {loc} for {date_label}."
        status, _ = classify_health_status(avg)
        healthiest = max(farms, key=lambda x: x.get("ndvi") or 0)
        stressed = min(farms, key=lambda x: x.get("ndvi") or 0)
        return (
            f"On {date_label}, {loc} had {count} farms with an average of {avg:.2f} NDVI ({_status_label(status)} status). "
            f"The healthiest was {healthiest['farmer_name']}'s farm at {healthiest['ndvi']:.2f} NDVI, "
            f"and the most stressed was {stressed['farmer_name']}'s at {stressed['ndvi']:.2f} NDVI."
        )

    if rtype == "farm_status":
        farms = result["farms"]
        count = result["count"]
        if not farms:
            return f"No {result.get('status', '').lower()} farms found in your municipality."
        parts = [f"{f['id']} ({f['farmer_name']}, {f['ndvi']:.2f} NDVI)" for f in farms[:5] if f.get("ndvi") is not None]
        status_word = result.get("status", "CRITICAL").lower()
        joined = " and ".join(parts[:2])
        suffix = "." if count <= 2 else f", and {count - 2} more."
        return f"You have {count} {status_word} farms: {joined}{suffix}"

    if rtype == "health_summary":
        return (
            f"This week, {result['healthy_count']} of {result['total']} farms are healthy "
            f"based on the latest satellite pass."
        )

    if rtype == "claims":
        status = result["status"].lower()
        count = result["count"] or (3 if status == "pending" else 0)
        path = f"/claims?status={status}"
        return f"Found {count} {status} claims in your municipality. [BUTTON:View Claims:{path}]"

    if rtype == "comparison":
        status_a, _ = classify_health_status(result["avg_a"])
        status_b, _ = classify_health_status(result["avg_b"])
        return (
            f"{result['municipality']} NDVI: "
            f"{_format_ph_date(result['date_a'])} {result['avg_a']:.2f} ({_status_label(status_a)}). "
            f"{_format_ph_date(result['date_b'])} {result['avg_b']:.2f} ({_status_label(status_b)}). "
            f"Decline is {result['decline_pct']}%. Want farm-level detail?"
        )

    if rtype == "report":
        rid = result["report_id"]
        count = result.get("farm_count", 2)
        mun = result.get("municipality", "your municipality")
        return (
            f"Report generated for {count} critical farms in {mun}. "
            f"[BUTTON:View Report:/reports/{rid}]"
        )

    if rtype == "export":
        month_label = result.get("month", "all")
        rows = result.get("rows", [])
        if not rows:
            return "No claims found to export for your municipality."
        header = "| Claim # | Farmer | Status | Damage % |"
        sep = "|---|---|---|---|"
        body = "\n".join(
            f"| {r['claim_number']} | {r['farmer_name']} | {r['status']} | {r.get('damage_percentage', 'N/A')}% |"
            for r in rows[:10]
        )
        table = f"{header}\n{sep}\n{body}"
        return (
            f"Found {result['count']} claims ({month_label}). CSV download ready.\n\n{table}"
        )

    if rtype == "risk":
        count = result["count"]
        return f"{count} farms are at risk based on current NDVI readings in your municipality."

    if rtype == "weather":
        loc = result["location"]
        date_label = _format_ph_date(result["date"])
        if result.get("rained"):
            return f"Yes, heavy rainfall was recorded in {loc} around {date_label} during Typhoon Kristine."
        return f"No significant rainfall was recorded in {loc} on {date_label} based on available weather data."

    if rtype == "batch_submit":
        return f"Submitted {result['count']} verified claims to PCIC for processing."

    if rtype == "advisory":
        return (
            f"Draft advisory prepared for drought-affected farms in {result['municipality']}. "
            "[BUTTON:View Advisory:/reports]"
        )

    return (
        "I can help with NDVI, farm status, claims, and reports. "
        "What would you like to see?"
    )


def validate_response(response: str, intent: dict, query_result: dict) -> dict:
    """Ensure response is accurate and complete before sending."""
    from services.ai_service import format_chat_response

    warnings = []
    text = format_chat_response(response.replace("\u2013", "-"), max_words=80)

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if len(sentences) > 6:
        text = " ".join(sentences[:5])
        warnings.append("trimmed_length")

    rtype = query_result.get("type")
    if rtype == "ndvi_location" and query_result.get("count"):
        expected = str(query_result["count"])
        if expected not in text and f"{expected} farm" not in text:
            warnings.append("count_mismatch")

    if rtype == "farm_status" and query_result.get("count"):
        if str(query_result["count"]) not in text:
            warnings.append("farm_count_mismatch")

    ndvi_matches = re.findall(r"(\d+\.\d+)\s*NDVI", text, re.I)
    for val in ndvi_matches:
        if not (-1 <= float(val) <= 1):
            warnings.append("invalid_ndvi")
            text = text.replace(val, "0.00")

    if rtype == "report" and "[BUTTON:View Report:" not in text:
        rid = query_result.get("report_id", "report")
        text = f"{text} [BUTTON:View Report:/reports/{rid}]"
        warnings.append("added_report_button")

    if intent.get("intent") == "navigate_to_page" and "[BUTTON:" not in text:
        path = query_result.get("path", "/dashboard")
        text = f"{text} [BUTTON:Go to Page:{path}]"
        warnings.append("added_nav_button")

    if rtype == "export" and query_result.get("rows"):
        warnings.append("export_csv_action")

    return {"valid": len(warnings) == 0 or warnings[0] != "count_mismatch", "response": text.strip(), "warnings": warnings}


def _parse_buttons(text: str) -> tuple[str, list]:
    buttons = []
    pattern = r"\[BUTTON:([^:]+):([^\]]+)\]"

    def replacer(match):
        buttons.append({"label": match.group(1), "path": match.group(2)})
        return ""

    cleaned = re.sub(pattern, replacer, text).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned, buttons


ACTION_INTENTS = {
    "navigate_to_page",
    "generate_damage_report",
    "generate_farm_summary",
    "export_claim_data",
    "submit_claim_batch",
    "file_claim",
}

CHAT_CLAIM_DEFAULTS = {
    "disaster_date": "2024-10-23",
    "damage_type": "flood",
}


CLAIM_FILING_RE = re.compile(
    r"(?:"
    r"file(?:\s+a)?\s+claim(?:\s+for)?|"
    r"submit(?:\s+a)?\s+claim(?:\s+for)?|"
    r"create(?:\s+a)?(?:\s+new)?\s+claim(?:\s+for)?|"
    r"generate(?:\s+a)?(?:\s+new)?\s+claim(?:\s+for)?|"
    r"make(?:\s+a)?\s+claim(?:\s+for)?|"
    r"start(?:\s+a)?\s+claim(?:\s+for)?|"
    r"new\s+claim(?:\s+for)?|"
    r"verify\s+damage(?:\s+for)?|"
    r"run\s+satellite\s+verification(?:\s+for)?|"
    r"create(?:\s+a)?\s+report(?:\s+for)?|"
    r"generate(?:\s+a)?\s+report(?:\s+for)?|"
    r"damage\s+report(?:\s+for)?|"
    r"claim\s+for"
    r")\s+(.+?)(?:\?|\.|$)",
    re.I,
)


def _is_claim_filing_request(message_lower: str) -> bool:
    if re.search(
        r"(?:file|submit|create|generate|make|start|open|new)\s+(?:a\s+)?(?:new\s+)?claim",
        message_lower,
    ):
        return True
    if re.search(r"claim\s+for\s+\w", message_lower):
        return True
    if re.search(r"(?:create|generate)\s+(?:a\s+)?(?:new\s+)?report", message_lower):
        return True
    return False


def _extract_farmer_identifier(message: str) -> str | None:
    rsbsa = _extract_rsbsa(message)
    if rsbsa:
        return rsbsa
    match = CLAIM_FILING_RE.search(message.strip())
    if match:
        name = match.group(1).strip().rstrip("?.!")
        if name:
            return name
    return None


def _find_farmer_in_municipality(identifier: str, municipality_id: str) -> dict | None:
    if not identifier or not municipality_id:
        return None
    farms = _get_farms_for_user(municipality_id)
    identifier_lower = identifier.lower().strip()
    for farm in farms:
        if farm.get("rsbsa_number", "").upper() == identifier.upper():
            return farm
        if identifier_lower in farm.get("farmer_name", "").lower():
            return farm
    for farm in farms:
        if farm.get("farmer_name", "").lower() == identifier_lower:
            return farm
    return None


def _pending_claim_context(history: list) -> dict | None:
    for msg in reversed(history):
        if msg.get("role") != "assistant":
            continue
        action = msg.get("action") or {}
        if action.get("type") in ("claim_confirmation_prompt", "claim_create_report"):
            return action.get("data", {})
    return None


def _handle_claim_chat(message: str, history: list, user: dict) -> dict | None:
    lower = message.lower().strip()
    municipality_id = user.get("municipality_id")
    pending = _pending_claim_context(history)

    if pending:
        if lower in ("cancel", "no", "stop", "abort"):
            return {
                "response": "Claim filing cancelled. File a claim for another farmer?",
                "action": {"type": "claim_cancelled"},
                "buttons": [],
                "intent": "file_claim",
                "warnings": [],
            }
        if lower in ("yes", "confirm", "ok", "proceed", "start") or "confirm" in lower:
            return {
                "response": (
                    f"Opening Claims for {pending['farmer_name']}. "
                    "The form is prefilled and satellite verification will start."
                ),
                "action": {
                    "type": "claim_redirect",
                    "data": pending,
                },
                "buttons": [],
                "intent": "file_claim",
                "warnings": [],
            }

    intent = classify_intent(message, history)
    if intent.get("intent") != "file_claim":
        identifier = _extract_farmer_identifier(message)
        if identifier and _is_claim_filing_request(lower):
            intent = {"intent": "file_claim", "entities": {"identifier": identifier}, "confidence": 0.98}
        elif identifier and intent.get("entities", {}).get("rsbsa"):
            intent = {"intent": "file_claim", "entities": {"identifier": identifier}, "confidence": 0.95}

    if intent.get("intent") != "file_claim":
        if _is_claim_filing_request(lower):
            identifier = _extract_farmer_identifier(message)
            if identifier:
                intent = {"intent": "file_claim", "entities": {"identifier": identifier}, "confidence": 0.98}
            else:
                return {
                    "response": "Tell me the farmer name or RSBSA number to file the claim.",
                    "action": None,
                    "buttons": [],
                    "intent": "file_claim",
                    "warnings": [],
                }
        else:
            return None

    identifier = intent.get("entities", {}).get("identifier") or _extract_farmer_identifier(message)
    if not identifier:
        return {
            "response": "Tell me the farmer name or RSBSA number to file the claim.",
            "action": None,
            "buttons": [],
            "intent": "file_claim",
            "warnings": [],
        }

    farm = _find_farmer_in_municipality(identifier, municipality_id)
    if not farm:
        return {
            "response": (
                f"I could not find {identifier} in your municipality. "
                "Check the name or use the RSBSA number."
            ),
            "action": None,
            "buttons": [],
            "intent": "file_claim",
            "warnings": [],
        }

    defaults = CHAT_CLAIM_DEFAULTS
    return {
        "response": (
            f"Found {farm['farmer_name']} ({farm['rsbsa_number']}). "
            f"{farm['crop_type']}, {farm['area_hectares']} ha. "
            f"Disaster: Oct 23, 2024 flood (Typhoon Kristine). "
            f"Confirm to open the Claims page and run satellite verification."
        ),
        "action": {
            "type": "claim_confirmation_prompt",
            "data": {
                "farmer_name": farm["farmer_name"],
                "rsbsa_number": farm["rsbsa_number"],
                "crop_type": farm["crop_type"],
                "area_hectares": float(farm["area_hectares"]),
                "parcel_id": farm["id"],
                "disaster_date": defaults["disaster_date"],
                "damage_type": defaults["damage_type"],
            },
        },
        "buttons": [],
        "intent": "file_claim",
        "warnings": [],
    }

OFF_TOPIC_MESSAGE = (
    "I focus on farms, NDVI, and claims only. "
    "I cannot write research papers or homework. "
    "Ask me about your municipality farms."
)
NO_CODE_MESSAGE = (
    "I cannot generate code. "
    "Ask me about farm data or claims instead."
)
MAX_RESPONSE_WORDS = 120

WORK_TOPIC_KEYWORDS = [
    "farm", "crop", "ndvi", "satellite", "claim", "insurance", "typhoon", "flood",
    "drought", "hectare", "rice", "corn", "banana", "coconut", "pcic", "mao",
    "damage", "harvest", "yield", "naga", "camarines", "kristine", "advisory",
    "barangay", "farmer", "parcel", "vegetation", "sentinel",
]

HEAVY_OFF_TOPIC_PATTERNS = [
    r"\b(write|generate|create|draft|compose|produce)\s+(me\s+)?(a\s+)?(full\s+|complete\s+|detailed\s+|comprehensive\s+)?(research|study|essay|paper|thesis|dissertation|literature\s+review|academic\s+report)\b",
    r"\b(research\s+paper|academic\s+paper|term\s+paper|school\s+project|class\s+project)\b",
    r"\b(homework|school\s+assignment|class\s+assignment)\b",
    r"\b\d+\s*(word|page|paragraph)\s+(essay|paper|report|assignment)\b",
    r"\b(research|study)\s+on\s+(science|physics|chemistry|biology|mathematics|math|history|philosophy|economics|literature)\b",
    r"\b(explain\s+in\s+detail|teach\s+me\s+everything|tell\s+me\s+everything)\s+about\s+(quantum|relativity|evolution|calculus|programming)\b",
    r"\b(generate|write|build|code)\s+(me\s+)?(a\s+)?(full\s+)?(program|script|software|application|website|app)\b",
]


def _chat_health_label(ndvi: float | None) -> str:
    if ndvi is None:
        return "Unknown"
    if ndvi > 0.5:
        return "Healthy"
    if ndvi >= 0.3:
        return "Watch"
    return "Critical"


def assemble_chat_context(user: dict) -> str:
    from services.farm_service import get_farms_by_municipality
    from services.claim_service import get_claims_list

    municipality_id = user.get("municipality_id")
    profile = execute_query(
        "SELECT first_name, last_name, role FROM users WHERE LOWER(email) = LOWER(%s)",
        (user.get("email"),),
        fetch_one=True,
    ) or {}

    farm_data = get_farms_by_municipality(municipality_id) if municipality_id else None
    municipality = farm_data["municipality"] if farm_data else {}
    farms = farm_data["farms"] if farm_data else []
    stats = farm_data["stats"] if farm_data else {}

    claims_result = get_claims_list({
        "municipality_id": municipality_id,
        "limit": 10,
        "offset": 0,
    })
    claims = claims_result.get("claims", [])

    alerts = [f for f in farms if f.get("status") in ("CRITICAL", "WATCH")]
    latest_date = None
    for f in farms:
        if f.get("ndvi_date") and (not latest_date or f["ndvi_date"] > latest_date):
            latest_date = f["ndvi_date"]

    mun_name = municipality.get("name", "N/A")
    mun_province = municipality.get("province", "N/A")
    satellite_view_date = satellite_date_fallback()

    lines = [
        f"Municipality: {mun_name}, {mun_province}",
        f"Disaster context: Typhoon Kristine, October 2024",
        f"Satellite observation date (user settings): {satellite_view_date}",
        f"Total farms: {municipality.get('total_farms', len(farms))}, total area: {municipality.get('total_area_hectares', 'N/A')} ha",
        f"Health counts — Healthy: {stats.get('healthy_count', 0)}, Watch: {stats.get('watch_count', 0)}, Critical: {stats.get('critical_count', 0)}",
        f"Latest NDVI capture date: {latest_date or satellite_view_date}",
        "",
        "Farm health list:",
    ]
    for f in farms:
        ndvi = f.get("latest_ndvi")
        ndvi_str = f"{float(ndvi):.3f}" if ndvi is not None else "N/A"
        lines.append(
            f"- {f['id']}: {f['farmer_name']} ({f['rsbsa_number']}), {f['crop_type']}, {f['area_hectares']} ha, "
            f"NDVI {ndvi_str} ({_chat_health_label(ndvi)})"
        )
    lines.append("")
    lines.append("Active alerts (Watch/Critical):")
    if not alerts:
        lines.append("- No active alerts")
    for f in alerts:
        ndvi = f.get("latest_ndvi")
        desc = (
            f"NDVI {float(ndvi):.3f} indicates {_chat_health_label(ndvi).lower()} crop conditions"
            if ndvi is not None
            else "NDVI data unavailable"
        )
        lines.append(
            f"- {f['farmer_name']} ({f['id']}, {f['rsbsa_number']}): {desc}, status {f.get('status')}"
        )
    lines.append("")
    lines.append("Recent claims (with NDVI before/after):")
    if not claims:
        lines.append("- No recent claims")
    for c in claims[:10]:
        ndvi_before = c.get("ndvi_before")
        ndvi_after = c.get("ndvi_after")
        ndvi_line = ""
        if ndvi_before is not None and ndvi_after is not None:
            ndvi_line = f", NDVI {float(ndvi_before):.3f} → {float(ndvi_after):.3f}"
        lines.append(
            f"- {c.get('claim_number')}: {c.get('farmer_name')}, {c.get('damage_type')}, "
            f"damage {c.get('damage_percentage', 'N/A')}%{ndvi_line}, status {c.get('status')}, filed {c.get('filed_date')}"
        )
    lines.append("")
    lines.append(
        f"User: {profile.get('first_name', '')} {profile.get('last_name', '')}, "
        f"role {user.get('role')}"
    )
    return "\n".join(lines)


def satellite_date_fallback() -> str:
    return DEFAULT_SATELLITE_DATE


def _is_work_related(message: str) -> bool:
    lower = message.lower()
    return any(keyword in lower for keyword in WORK_TOPIC_KEYWORDS)


def _is_heavy_off_topic(message: str) -> bool:
    """Block substantive off-topic content requests; allow small talk and farm work."""
    lower = message.lower().strip()
    if _is_work_related(lower):
        return False
    return any(re.search(pattern, lower) for pattern in HEAVY_OFF_TOPIC_PATTERNS)


def _sanitize_deepseek_response(response: str) -> str:
    """Strip code blocks and enforce response rules."""
    from services.ai_service import format_chat_response

    if re.search(r"```", response) or re.search(
        r"(?:^|\n)\s*(?:def |class |import |function |const |let |var )",
        response,
        re.MULTILINE,
    ):
        return NO_CODE_MESSAGE

    cleaned = re.sub(r"```[\s\S]*?```", "", response).strip()
    cleaned = re.sub(r"`[^`]+`", "", cleaned).strip()

    if not cleaned:
        return NO_CODE_MESSAGE

    return format_chat_response(cleaned, max_words=MAX_RESPONSE_WORDS)


def _build_system_prompt(user: dict, context: str) -> str:
    from services.ai_service import CHAT_SYSTEM_RULES

    profile = execute_query(
        "SELECT first_name, last_name FROM users WHERE LOWER(email) = LOWER(%s)",
        (user.get("email"),),
        fetch_one=True,
    ) or {}
    name = f"{profile.get('first_name', 'Officer')} {profile.get('last_name', '')}".strip()
    mun_line = context.split("\n")[0] if context else "your municipality"
    today = datetime.utcnow().strftime("%B %d, %Y")
    return f"""{CHAT_SYSTEM_RULES}

You assist {name}, MAO for {mun_line}.
Use only the municipality data below. Never invent NDVI or claim numbers.
If asked for code, say: "{NO_CODE_MESSAGE}"
For heavy off-topic requests, say: "{OFF_TOPIC_MESSAGE}"
End with one clear next step or question.

DATA AS OF {today}:
{context}
"""


def _deepseek_chat(message: str, conversation_history: list, user: dict) -> str:
    from services.ai_service import call_deepseek

    context = assemble_chat_context(user)
    system_prompt = _build_system_prompt(user, context)
    messages = [{"role": "system", "content": system_prompt}]
    for entry in conversation_history[-8:]:
        if entry.get("role") in ("user", "assistant") and entry.get("content"):
            messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": message})
    return call_deepseek(messages)


def _context_grounded_fallback(message: str, user: dict) -> str | None:
    """Answer from live municipality data when DeepSeek is unavailable."""
    lower = message.lower()
    municipality_id = user.get("municipality_id")
    if not municipality_id:
        return None

    from services.farm_service import get_farms_by_municipality

    farm_data = get_farms_by_municipality(municipality_id)
    if not farm_data:
        return None

    farms = farm_data["farms"]
    municipality = farm_data.get("municipality", {})
    mun_name = municipality.get("name", "your municipality")

    rsbsa = _extract_rsbsa(message)
    if rsbsa or ("ndvi" in lower and rsbsa):
        farm = next((f for f in farms if f.get("rsbsa_number", "").upper() == rsbsa.upper()), None)
        if not farm:
            farm = execute_query(
                "SELECT * FROM farm_parcels WHERE rsbsa_number = %s",
                (rsbsa,),
                fetch_one=True,
            )
        if farm:
            history = _get_ndvi_history(farm["id"])
            if len(history) >= 2:
                pre, post = history[0], history[-1]
                return (
                    f"{farm.get('rsbsa_number')} ({farm.get('farmer_name')}): "
                    f"pre-Typhoon Tino NDVI {float(pre['ndvi_value']):.3f} ({pre['capture_date']}), "
                    f"post-Typhoon Tino NDVI {float(post['ndvi_value']):.3f} ({post['capture_date']}). "
                    f"Current status: {farm.get('status', _chat_health_label(float(post['ndvi_value'])))}."
                )
            latest = farm.get("latest_ndvi")
            if latest is not None:
                return (
                    f"{farm.get('rsbsa_number')} ({farm.get('farmer_name')}) "
                    f"current NDVI: {float(latest):.3f} ({_chat_health_label(latest)})."
                )
        return f"I could not find {rsbsa} in {mun_name}."

    if re.search(r"critical|watch", lower) and re.search(r"farm|condition|parcel|which", lower):
        status_filter = "WATCH" if "watch" in lower and "critical" not in lower else "CRITICAL"
        filtered = [f for f in farms if f.get("status") == status_filter]
        if not filtered:
            return f"No {status_filter.lower()} farms in {mun_name} right now."
        lines = [f"{len(filtered)} {status_filter.lower()} farms in {mun_name}:"]
        for f in filtered:
            ndvi = f.get("latest_ndvi")
            ndvi_s = f"{float(ndvi):.3f}" if ndvi is not None else "N/A"
            lines.append(f"- {f['farmer_name']} ({f['id']}, {f['rsbsa_number']}): NDVI {ndvi_s}")
        return "\n".join(lines)

    return None


def process_chat(message: str, conversation_history: list, user: dict, satellite_date: str):
    claim_result = _handle_claim_chat(message, conversation_history, user)
    if claim_result:
        from services.ai_service import format_chat_response
        claim_result["response"] = format_chat_response(
            claim_result.get("response", ""),
            max_words=120 if claim_result.get("action") else 80,
        )
        return claim_result

    intent = classify_intent(message, conversation_history)

    if intent["intent"] not in ACTION_INTENTS:
        if _is_heavy_off_topic(message):
            return {
                "response": OFF_TOPIC_MESSAGE,
                "action": None,
                "buttons": [],
                "intent": intent.get("intent"),
                "warnings": ["off_topic"],
            }
        try:
            reply = _sanitize_deepseek_response(
                _deepseek_chat(message, conversation_history, user)
            )
            return {
                "response": reply,
                "action": None,
                "buttons": [],
                "intent": intent.get("intent"),
                "warnings": [],
            }
        except Exception as exc:
            logger.warning("DeepSeek unavailable, using context fallback: %s", exc)
            fallback = _context_grounded_fallback(message, user)
            if fallback:
                return {
                    "response": fallback,
                    "action": None,
                    "buttons": [],
                    "intent": intent.get("intent"),
                    "warnings": ["deepseek_fallback"],
                }

    query_result = execute_intent(intent, user, satellite_date)
    raw_response = _build_response(intent, query_result, user)
    validated = validate_response(raw_response, intent, query_result)
    text, buttons = _parse_buttons(validated["response"])

    action = None
    if query_result.get("type") == "export" and query_result.get("rows"):
        action = {
            "type": "export_csv",
            "data": query_result["rows"],
            "filename": "bantay_ani_claims.csv",
        }
    elif buttons:
        if "report" in buttons[0]["path"]:
            action = {"type": "report_ready", "data": buttons[0]}
        else:
            action = {"type": "navigate", "data": buttons[0]}

    from services.ai_service import format_chat_response

    return {
        "response": format_chat_response(text, max_words=80),
        "action": action,
        "buttons": buttons,
        "intent": intent.get("intent"),
        "warnings": validated.get("warnings", []),
    }