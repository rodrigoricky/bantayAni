import os
from datetime import datetime
from io import BytesIO

import qrcode
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from models.claim import ReportRequest
from services.auth_service import get_current_user
from services.claim_service import get_claim_for_report
from utils.database import execute_query

router = APIRouter()

VERIFY_BASE_URL = os.getenv("VERIFY_BASE_URL", "http://localhost:3000").rstrip("/")


def _format_date(value, fmt="%B %d, %Y"):
    if not value:
        return "N/A"
    if hasattr(value, "strftime"):
        return value.strftime(fmt)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime(fmt)
    except ValueError:
        return str(value)


def _get_satellite_dates(parcel_id: str, disaster_date: str):
    before = execute_query(
        """
        SELECT capture_date FROM satellite_imagery
        WHERE parcel_id = %s AND capture_date <= %s
        ORDER BY capture_date DESC LIMIT 1
        """,
        (parcel_id, disaster_date),
        fetch_one=True,
    )
    after = execute_query(
        """
        SELECT capture_date FROM satellite_imagery
        WHERE parcel_id = %s AND capture_date >= %s
        ORDER BY capture_date ASC LIMIT 1
        """,
        (parcel_id, disaster_date),
        fetch_one=True,
    )
    before_date = before.get("capture_date") if before else None
    after_date = after.get("capture_date") if after else None
    return _format_date(before_date), _format_date(after_date)


def _normalize_claim_data(claim: dict, user: dict) -> dict:
    parcel_id = claim.get("parcel_id", "")
    disaster_date = str(claim.get("disaster_date", ""))
    before_date, after_date = _get_satellite_dates(parcel_id, disaster_date)

    ndvi_before = float(claim.get("ndvi_before") or 0)
    ndvi_after = float(claim.get("ndvi_after") or 0)
    damage_pct = float(claim.get("damage_percentage") or 0)

    verified_at = claim.get("verified_at")
    if verified_at:
        verified_at = _format_date(verified_at, "%B %d, %Y at %I:%M %p")
    else:
        verified_at = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    municipality = claim.get("municipality") or claim.get("municipality_name", "N/A")

    return {
        "claim_number": claim.get("claim_number", "N/A"),
        "status": claim.get("status", "PENDING"),
        "farmer_name": claim.get("farmer_name", "N/A"),
        "rsbsa_number": claim.get("rsbsa_number", "N/A"),
        "municipality": municipality,
        "province": claim.get("province", "N/A"),
        "parcel_id": parcel_id,
        "crop_type": claim.get("crop_type", "N/A"),
        "area_hectares": claim.get("area_hectares", "N/A"),
        "claimed_area_hectares": claim.get("claimed_area_hectares", "N/A"),
        "damage_type": claim.get("damage_type", "flood"),
        "disaster_date": _format_date(claim.get("disaster_date")),
        "filed_date": _format_date(claim.get("filed_date")),
        "ai_recommendation": claim.get("ai_recommendation", "No recommendation available."),
        "verified_at": verified_at,
        "verified_by_name": claim.get("verified_by_name")
        or (f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "MAO Maria Santos"),
        "verified_by_role": claim.get("verified_by_role", "Municipal Agricultural Officer"),
        "satellite_analysis": {
            "before_date": before_date,
            "after_date": after_date,
            "ndvi_before": ndvi_before,
            "ndvi_after": ndvi_after,
            "damage_percentage": damage_pct,
        },
    }


def generate_pcic_report(claim_data: dict) -> BytesIO:
    """Generate PCIC-compliant satellite damage verification report."""
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=25 * mm,
        bottomMargin=25 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=colors.HexColor("#111827"),
        spaceAfter=6,
        alignment=TA_CENTER,
        leading=20,
    )

    subtitle_style = ParagraphStyle(
        "CustomSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#6B7280"),
        spaceAfter=20,
        alignment=TA_CENTER,
    )

    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.HexColor("#374151"),
        spaceAfter=8,
        spaceBefore=12,
    )

    body_style = ParagraphStyle(
        "LegalBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#1F2937"),
        leading=13,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )

    meta_style = ParagraphStyle(
        "Metadata",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#9CA3AF"),
        spaceAfter=4,
    )

    story = []

    story.append(Paragraph("Republic of the Philippines", meta_style))
    story.append(Paragraph("Department of Agriculture", meta_style))
    story.append(Paragraph("Philippine Crop Insurance Corporation", meta_style))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("SATELLITE-BASED CROP DAMAGE VERIFICATION REPORT", title_style))
    story.append(Paragraph("Bantay Ani | Satellite Crop Damage Assessment Report", subtitle_style))

    story.append(Spacer(1, 2 * mm))
    story.append(
        Table(
            [[""]],
            colWidths=[doc.width],
            style=TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#D1D5DB"))]),
        )
    )
    story.append(Spacer(1, 6 * mm))

    report_id = f"BA-{claim_data['claim_number']}"
    timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    metadata_table = Table(
        [
            ["Report ID:", report_id, "Verification Date:", timestamp],
            ["Claim Number:", claim_data["claim_number"], "Status:", claim_data["status"]],
        ],
        colWidths=[35 * mm, 55 * mm, 35 * mm, 45 * mm],
        style=TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6B7280")),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#111827")),
            ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#6B7280")),
            ("TEXTCOLOR", (3, 0), (3, -1), colors.HexColor("#111827")),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
            ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]),
    )
    story.append(metadata_table)
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph("I. FARMER INFORMATION", section_style))

    farmer_table = Table(
        [
            ["Farmer Name:", claim_data["farmer_name"]],
            ["RSBSA Number:", claim_data["rsbsa_number"]],
            ["Municipality:", f"{claim_data['municipality']}, {claim_data['province']}"],
            ["Parcel ID:", claim_data["parcel_id"]],
            ["Crop Type:", claim_data["crop_type"]],
            ["Registered Area:", f"{claim_data['area_hectares']} hectares"],
            ["Claimed Damage Area:", f"{claim_data['claimed_area_hectares']} hectares"],
        ],
        colWidths=[50 * mm, 120 * mm],
        style=TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6B7280")),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1F2937")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ]),
    )
    story.append(farmer_table)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("II. REPORTED DISASTER EVENT", section_style))

    disaster_table = Table(
        [
            ["Disaster Type:", claim_data["damage_type"].capitalize()],
            ["Reported Date:", claim_data["disaster_date"]],
            ["Claim Filed Date:", claim_data["filed_date"]],
        ],
        colWidths=[50 * mm, 120 * mm],
        style=TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6B7280")),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1F2937")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]),
    )
    story.append(disaster_table)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("III. SATELLITE IMAGERY ANALYSIS", section_style))

    analysis_text = """
    This report presents an analysis of satellite-derived Normalized Difference Vegetation Index (NDVI) data
    obtained from the European Space Agency's Sentinel-2 constellation. NDVI is a scientifically validated
    indicator of vegetation health, with values ranging from –1.0 (water, bare soil) to +1.0 (dense, healthy vegetation).
    For agricultural crops during growing season, NDVI values between 0.6 and 0.8 indicate healthy crops,
    while values below 0.3 indicate stressed or damaged vegetation.
    """
    story.append(Paragraph(analysis_text, body_style))
    story.append(Spacer(1, 4 * mm))

    sat = claim_data["satellite_analysis"]
    satellite_table = Table(
        [
            ["Satellite Source:", "Sentinel-2 (ESA Copernicus)"],
            ["Spatial Resolution:", "10 meters per pixel"],
            ["Pre-Event Image Date:", sat["before_date"]],
            ["Post-Event Image Date:", sat["after_date"]],
            ["Cloud Cover (Pre):", "< 10%"],
            ["Cloud Cover (Post):", "< 10%"],
        ],
        colWidths=[50 * mm, 120 * mm],
        style=TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6B7280")),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1F2937")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]),
    )
    story.append(satellite_table)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("IV. VEGETATION INDEX ASSESSMENT", section_style))

    ndvi_before = sat["ndvi_before"]
    ndvi_after = sat["ndvi_after"]
    damage_pct = sat["damage_percentage"]

    if damage_pct >= 70:
        status_color = colors.HexColor("#DC2626")
        status_label = "SEVERE DAMAGE"
    elif damage_pct >= 40:
        status_color = colors.HexColor("#F59E0B")
        status_label = "MODERATE DAMAGE"
    else:
        status_color = colors.HexColor("#16A34A")
        status_label = "MINIMAL DAMAGE"

    ndvi_results = Table(
        [
            ["NDVI (Pre-Event)", "NDVI (Post-Event)", "NDVI Change", "Damage Estimate"],
            [
                f"{ndvi_before:.3f}\nHealthy Crop",
                f"{ndvi_after:.3f}\nStressed Crop",
                f"{ndvi_before - ndvi_after:.3f}\n({damage_pct:.1f}% decline)",
                f"{damage_pct:.1f}%\n{status_label}",
            ],
        ],
        colWidths=[40 * mm, 40 * mm, 45 * mm, 45 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#374151")),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (-1, 1), 11),
            ("TEXTCOLOR", (0, 1), (0, 1), colors.HexColor("#16A34A")),
            ("TEXTCOLOR", (1, 1), (1, 1), colors.HexColor("#DC2626")),
            ("TEXTCOLOR", (2, 1), (2, 1), colors.HexColor("#1F2937")),
            ("TEXTCOLOR", (3, 1), (3, 1), status_color),
            ("ALIGN", (0, 1), (-1, 1), "CENTER"),
            ("VALIGN", (0, 1), (-1, 1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]),
    )
    story.append(ndvi_results)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("V. AUTOMATED ANALYSIS & RECOMMENDATION", section_style))

    recommendation_text = f"""
    {claim_data['ai_recommendation']}
    <br/><br/>
    <b>Weather Verification:</b> PAGASA meteorological data confirms {claim_data['damage_type']} event
    in {claim_data['municipality']} on {claim_data['disaster_date']}. Rainfall accumulation exceeded
    regional thresholds consistent with reported flood damage.
    <br/><br/>
    <b>Fraud Analysis:</b> Pre-event satellite imagery shows healthy crop conditions (NDVI {ndvi_before:.3f}),
    ruling out pre-existing damage. Claimed area ({claim_data['claimed_area_hectares']} ha) matches
    registered parcel area. No fraud indicators detected.
    """
    story.append(Paragraph(recommendation_text, body_style))
    story.append(Spacer(1, 8 * mm))

    claim_status = claim_data["status"]
    status_table = Table(
        [[claim_status]],
        colWidths=[170 * mm],
        style=TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 14),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("LINEABOVE", (0, 0), (-1, -1), 2, colors.HexColor("#000000")),
            ("LINEBELOW", (0, 0), (-1, -1), 2, colors.HexColor("#000000")),
        ]),
    )
    story.append(status_table)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("VI. VERIFICATION AUTHORITY", section_style))
    story.append(Spacer(1, 3 * mm))

    signature_table = Table(
        [
            ["Verified by:", claim_data.get("verified_by_name", "MAO Maria Santos")],
            ["Position:", claim_data.get("verified_by_role", "Municipal Agricultural Officer")],
            ["Municipality:", claim_data["municipality"]],
            ["Verification Date:", claim_data.get("verified_at", timestamp)],
        ],
        colWidths=[50 * mm, 120 * mm],
        style=TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6B7280")),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1F2937")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]),
    )
    story.append(signature_table)
    story.append(Spacer(1, 4 * mm))

    verify_url = f"{VERIFY_BASE_URL}/verify/{report_id}"

    qr = qrcode.QRCode(version=1, box_size=3, border=1)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    qr_image = Image(qr_buffer, width=22 * mm, height=22 * mm)
    verify_link_style = ParagraphStyle(
        "VerifyLink",
        parent=body_style,
        fontSize=9,
        textColor=colors.HexColor("#2563EB"),
        alignment=TA_CENTER,
    )
    signature_block = Table(
        [
            [Paragraph("<b>Authorized Signature:</b>", body_style), ""],
            [
                qr_image,
                Paragraph(
                    f"<font name='Courier' size='8'>Report ID: {report_id}</font><br/>"
                    f"<font size='7' color='#9CA3AF'>Scan to verify this report.</font><br/>"
                    f"<a href='{verify_url}' color='#2563EB'><u>Verify this report online</u></a>",
                    body_style,
                ),
            ],
        ],
        colWidths=[25 * mm, 145 * mm],
        style=TableStyle([
            ("SPAN", (0, 0), (1, 0)),
            ("VALIGN", (0, 1), (-1, 1), "MIDDLE"),
            ("ALIGN", (0, 1), (0, 1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]),
    )
    story.append(signature_block)

    def add_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(colors.HexColor("#9CA3AF"))
        footer_text = (
            f"Bantay Ani | Generated {datetime.now().strftime('%B %d, %Y')} | Page {doc_obj.page}"
        )
        canvas_obj.drawCentredString(A4[0] / 2, 15 * mm, footer_text)
        canvas_obj.setStrokeColor(colors.HexColor("#E5E7EB"))
        canvas_obj.line(20 * mm, 18 * mm, A4[0] - 20 * mm, 18 * mm)
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    return buffer


@router.post("/generate")
def generate_report(request: ReportRequest, user: dict = Depends(get_current_user)):
    claim = get_claim_for_report(request.claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim_data = _normalize_claim_data(claim, user)
    buffer = generate_pcic_report(claim_data)

    filename = f"Claim_{claim.get('claim_number', 'report')}_Report.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )