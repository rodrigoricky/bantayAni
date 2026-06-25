export const CLAIM_PREFILL_KEY = 'bantay_ani_claim_prefill';

export function saveClaimPrefill(data) {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(CLAIM_PREFILL_KEY, JSON.stringify({
    rsbsa_number: data.rsbsa_number,
    disaster_date: data.disaster_date || '2024-10-23',
    damage_type: data.damage_type || 'flood',
    claimed_area_hectares: data.area_hectares ?? data.claimed_area_hectares,
    farmer_name: data.farmer_name,
    parcel_id: data.parcel_id,
    autostart: true,
  }));
}

export function consumeClaimPrefill() {
  if (typeof window === 'undefined') return null;
  const raw = sessionStorage.getItem(CLAIM_PREFILL_KEY);
  if (!raw) return null;
  sessionStorage.removeItem(CLAIM_PREFILL_KEY);
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}