import logging
import os
import re

import httpx

from utils.ndvi import classify_ndvi_label

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

CHAT_SYSTEM_RULES = """You are BantayAni Auto, a farm monitoring assistant for Philippine MAOs.

STYLE RULES (strict):
- Reply in English only. Never use Tagalog or Filipino.
- Informational replies: under 80 words.
- Analytical replies (NDVI, claims): under 120 words.
- Never use em dashes.
- Never use semicolons.
- Max 15 words per sentence.
- Be short and direct.
- Lists: numbered, max 4 items.
- Do not repeat what the user already said.
- No disclaimers or "please note" phrases.
- End with one clear next step or question, not a summary.

Use only provided municipality data. Never invent NDVI values or claim numbers.

CLAIM FILING: You can file claims in this app. Never tell users to use the PCIC portal or MAO office instead.
If they ask to file, generate, or create a claim, say you found the farmer and ask them to confirm in the card below."""


def format_chat_response(response: str, max_words: int = 150) -> str:
    """Post-process LLM output for demo-friendly concise replies."""
    if not response:
        return response

    cleaned = response.replace("—", ", ").replace(";", ".")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    words = cleaned.split()
    if len(words) > max_words:
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        trimmed = []
        count = 0
        for sentence in sentences:
            sentence_words = sentence.split()
            if count + len(sentence_words) > max_words:
                break
            trimmed.append(sentence)
            count += len(sentence_words)
        cleaned = " ".join(trimmed).strip() if trimmed else " ".join(words[:max_words])
        if not cleaned.endswith("?"):
            cleaned = f"{cleaned} Want more details?"

    return cleaned.strip()


def call_deepseek(messages: list, max_tokens: int = 400) -> str:
    """Call DeepSeek chat completions API."""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not configured")

    response = httpx.post(
        DEEPSEEK_API_URL,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"].strip()
    if messages and messages[0].get("role") == "system":
        return format_chat_response(content)
    return content


def generate_damage_assessment(
    farmer_name: str,
    crop_type: str,
    damage_type: str,
    disaster_date: str,
    before_date: str,
    after_date: str,
    ndvi_before: float,
    ndvi_after: float,
    damage_pct: float,
    status: str,
    fraud_indicators: list,
) -> str:
    if DEEPSEEK_API_KEY:
        try:
            prompt = f"""You are an agricultural insurance claim analyst. Based on satellite imagery analysis, generate a professional 2-sentence recommendation.

Claim Details:
- Farmer: {farmer_name}
- Crop: {crop_type}
- Disaster Type: {damage_type}
- Disaster Date: {disaster_date}

Satellite Analysis:
- NDVI Before ({before_date}): {ndvi_before:.3f} ({classify_ndvi_label(ndvi_before)})
- NDVI After ({after_date}): {ndvi_after:.3f} ({classify_ndvi_label(ndvi_after)})
- Calculated Damage: {damage_pct:.1f}%

Fraud Indicators: {len(fraud_indicators)} detected
Status: {status}

Provide a professional recommendation for insurance approval or denial. Be concise and data-driven."""

            return call_deepseek(
                [{"role": "user", "content": prompt}],
                max_tokens=150,
            )
        except Exception as exc:
            logger.warning("DeepSeek damage assessment failed: %s", exc)

    return _fallback_recommendation(damage_pct, damage_type, status, fraud_indicators)


def generate_claim_assessment(verification_data: dict) -> str:
    """Generate a single-turn DeepSeek assessment narrative with template fallback."""
    sat = verification_data.get("satellite_analysis") or {}
    ndvi_before = sat.get("ndvi_before")
    ndvi_after = sat.get("ndvi_after")
    damage_pct = sat.get("damage_percentage", 0)
    is_significant = verification_data.get("is_significant_change", True)

    if DEEPSEEK_API_KEY:
        try:
            system_prompt = (
                "You are an agricultural insurance satellite analyst. Write a professional damage "
                "assessment in 100 words or fewer. Use specific NDVI values in the explanation. "
                "Explain what the values mean for the specific crop type. Explain whether satellite "
                "evidence supports or does not support the claim. Avoid generic language like "
                "'significant decline' when values show otherwise. If NDVI values are both near zero "
                "or show less than 0.08 points of change, explain that no significant crop damage "
                "was detected, not that crops are recovering."
            )
            user_prompt = f"""Generate an agricultural damage assessment for this claim:

Farmer: {verification_data.get('farmer_name', 'Unknown')}
Crop: {verification_data.get('crop_type', 'Unknown')}
Damage type: {verification_data.get('damage_type', 'unknown')}
Disaster date: {verification_data.get('disaster_date', 'N/A')}
NDVI before: {ndvi_before}
NDVI after: {ndvi_after}
Damage percentage: {damage_pct}%
NDWI before/after: {sat.get('ndwi_before')} / {sat.get('ndwi_after')}
LST before/after (°C): {sat.get('lst_celsius_before')} / {sat.get('lst_celsius_after')}
Status: {verification_data.get('status')}
Significant change detected: {is_significant}
Rejection reason (if any): {verification_data.get('rejection_reason', 'None')}"""

            return call_deepseek(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=200,
            )
        except Exception as exc:
            logger.warning("DeepSeek claim assessment failed, using template fallback: %s", exc)

    from services.ai_templates import select_ai_recommendation
    return select_ai_recommendation(
        damage_type=verification_data.get("damage_type", ""),
        damage_pct=damage_pct,
        status=verification_data.get("status", "PENDING"),
        ndvi_before=ndvi_before or 0,
        ndvi_after=ndvi_after or 0,
        fraud_indicators=verification_data.get("fraud_indicators", []),
        is_significant=is_significant,
    )


def _fallback_recommendation(damage_pct, damage_type, status, fraud_indicators):
    if status == "APPROVED":
        if damage_pct >= 70:
            return (
                f"Severe crop damage confirmed via satellite analysis. NDVI dropped significantly, "
                f"consistent with {damage_type} event. Recommend full insurance payout for affected area."
            )
        return (
            f"Satellite verification confirms {damage_pct:.1f}% crop damage consistent with reported {damage_type}. "
            f"Recommend approval for insurance payout."
        )
    if status == "FLAGGED":
        return (
            f"Satellite analysis shows {damage_pct:.1f}% damage with {len(fraud_indicators)} anomalies detected. "
            f"Field investigation recommended before approval."
        )
    reason = fraud_indicators[0]["description"] if fraud_indicators else "Satellite evidence contradicts claimed damage."
    return f"Claim rejected. Satellite evidence contradicts claimed damage. {reason}"