/** Single source of truth for NDVI status colors and classification. */

export const NDVI_THRESHOLDS = {
  HEALTHY: 0.6,
  FAIR: 0.4,
  WATCH: 0.2,
};

const STATUS_PALETTE = {
  CRITICAL: {
    bg: 'bg-red-100',
    text: 'text-red-800',
    border: 'border-red-200',
    dot: 'bg-red-500',
    badge: 'text-red-800 bg-red-100 border-red-200',
    fill: 'rgba(239, 68, 68, 0.45)',
    stroke: '#ef4444',
  },
  WATCH: {
    bg: 'bg-orange-100',
    text: 'text-orange-800',
    border: 'border-orange-200',
    dot: 'bg-orange-500',
    badge: 'text-orange-800 bg-orange-100 border-orange-200',
    fill: 'rgba(249, 115, 22, 0.45)',
    stroke: '#f97316',
  },
  FAIR: {
    bg: 'bg-yellow-100',
    text: 'text-yellow-800',
    border: 'border-yellow-200',
    dot: 'bg-yellow-500',
    badge: 'text-yellow-800 bg-yellow-100 border-yellow-200',
    fill: 'rgba(234, 179, 8, 0.45)',
    stroke: '#eab308',
  },
  HEALTHY: {
    bg: 'bg-green-100',
    text: 'text-green-800',
    border: 'border-green-200',
    dot: 'bg-green-500',
    badge: 'text-green-800 bg-green-100 border-green-200',
    fill: 'rgba(34, 197, 94, 0.45)',
    stroke: '#22c55e',
  },
};

const NO_DATA = {
  bg: 'bg-gray-100',
  text: 'text-gray-500',
  border: 'border-gray-200',
  dot: 'bg-gray-400',
  badge: 'text-gray-500 bg-gray-100 border-gray-200',
  fill: 'rgba(156, 163, 175, 0.45)',
  stroke: '#6b7280',
};

const STATUS_KEYS = new Set(['CRITICAL', 'WATCH', 'FAIR', 'HEALTHY']);

/**
 * Map an NDVI value to a status label.
 * CRITICAL < 0.20 | WATCH 0.20–0.40 | FAIR 0.40–0.60 | HEALTHY > 0.60
 */
export function statusFromNdvi(ndvi) {
  if (ndvi == null || Number.isNaN(Number(ndvi))) return null;
  const v = Number(ndvi);
  if (v < NDVI_THRESHOLDS.WATCH) return 'CRITICAL';
  if (v < NDVI_THRESHOLDS.FAIR) return 'WATCH';
  if (v < NDVI_THRESHOLDS.HEALTHY) return 'FAIR';
  return 'HEALTHY';
}

/**
 * Returns Tailwind + map color tokens for a status string or NDVI number.
 * @param {'CRITICAL'|'WATCH'|'FAIR'|'HEALTHY'|number|string} statusOrNdvi
 */
export function getStatusColors(statusOrNdvi) {
  let status = null;

  if (typeof statusOrNdvi === 'number') {
    status = statusFromNdvi(statusOrNdvi);
  } else if (typeof statusOrNdvi === 'string') {
    const upper = statusOrNdvi.toUpperCase();
    if (STATUS_KEYS.has(upper)) {
      status = upper;
    } else {
      const num = Number(statusOrNdvi);
      status = Number.isNaN(num) ? null : statusFromNdvi(num);
    }
  }

  if (!status || !STATUS_PALETTE[status]) return NO_DATA;
  return STATUS_PALETTE[status];
}

/** Map polygon fill/stroke colors derived from NDVI value. */
export function getNDVIColor(ndvi) {
  const { fill, stroke } = getStatusColors(ndvi);
  return { fill, stroke };
}

/** Human-readable NDVI context for detail views and claim verification. */
export function getNDVIContext(ndviValue) {
  if (ndviValue == null || Number.isNaN(ndviValue)) {
    return {
      icon: 'AlertCircle',
      label: 'No data',
      colorClass: NO_DATA.text,
      bgClass: NO_DATA.bg,
      dotClass: NO_DATA.dot,
      damageEquivalent: 'Satellite data unavailable',
    };
  }
  const v = Number(ndviValue);
  if (v < 0.1) {
    return { icon: 'AlertOctagon', label: 'Bare soil / complete crop loss', colorClass: 'text-red-700', bgClass: 'bg-red-100', dotClass: 'bg-red-600', damageEquivalent: 'Equivalent to ~95% crop loss' };
  }
  if (v < 0.2) {
    return { icon: 'XCircle', label: 'Severely damaged / near-total crop loss', colorClass: 'text-red-700', bgClass: 'bg-red-100', dotClass: 'bg-red-600', damageEquivalent: `Equivalent to ~${Math.round((1 - v / 0.65) * 100)}% crop loss` };
  }
  if (v < 0.35) {
    return { icon: 'AlertCircle', label: 'Significantly stressed / partial crop loss', colorClass: 'text-orange-700', bgClass: 'bg-orange-100', dotClass: 'bg-orange-500', damageEquivalent: `Equivalent to ~${Math.round((1 - v / 0.65) * 100)}% crop loss` };
  }
  if (v < 0.5) {
    return { icon: 'AlertTriangle', label: 'Moderately stressed / watch zone', colorClass: 'text-orange-700', bgClass: 'bg-orange-100', dotClass: 'bg-orange-500', damageEquivalent: 'Partial stress - monitor closely' };
  }
  if (v < 0.65) {
    return { icon: 'Sprout', label: 'Healthy / normal crop growth', colorClass: 'text-green-700', bgClass: 'bg-green-100', dotClass: 'bg-green-500', damageEquivalent: 'Normal pre-season crop health' };
  }
  return { icon: 'Leaf', label: 'Thriving / peak vegetation', colorClass: 'text-green-800', bgClass: 'bg-green-100', dotClass: 'bg-green-700', damageEquivalent: 'Excellent vegetation vigor' };
}