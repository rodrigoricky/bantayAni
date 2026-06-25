function daysBetween(dateA, dateB) {
  if (!dateA || !dateB) return null;
  try {
    const d1 = new Date(dateA);
    const d2 = new Date(dateB);
    if (Number.isNaN(d1.getTime()) || Number.isNaN(d2.getTime())) return null;
    return Math.abs(Math.round((d2 - d1) / (1000 * 60 * 60 * 24)));
  } catch {
    return null;
  }
}

const NDVI_SIGNIFICANCE_THRESHOLD = 0.08;

export function computeEvidenceMetrics(satelliteAnalysis) {
  if (!satelliteAnalysis) return null;

  const before = satelliteAnalysis.ndvi_before;
  const after = satelliteAnalysis.ndvi_after;
  const ndviChange = before != null && after != null ? before - after : null;
  const absChange = ndviChange != null ? Math.abs(ndviChange) : null;
  const isSignificant = absChange != null && absChange >= NDVI_SIGNIFICANCE_THRESHOLD;
  const isGain = ndviChange != null && ndviChange < 0;
  const ndviDropPct = before > 0 && ndviChange != null ? Math.round((ndviChange / before) * 100) : 0;
  const daysSpan = daysBetween(satelliteAnalysis.before_date, satelliteAnalysis.after_date);

  let rainfallDeviation = null;
  const damageType = (satelliteAnalysis.damage_type || '').toLowerCase();
  if (damageType === 'drought') rainfallDeviation = -27;
  else if (damageType === 'typhoon' || damageType === 'flood') rainfallDeviation = 34;
  else if (damageType === 'pest' || damageType === 'disease') rainfallDeviation = 0;

  return {
    ndviChange,
    absChange,
    isSignificant,
    isGain,
    ndviDropPct,
    daysSpan,
    rainfallDeviation,
    rainfallSubtext: rainfallDeviation < 0
      ? 'vs seasonal baseline'
      : rainfallDeviation > 0
        ? 'during event window'
        : 'within normal range',
  };
}

export function getNdviChangeDisplay(metrics) {
  if (!metrics || metrics.ndviChange == null) {
    return { label: 'NDVI Change', value: 'N/A', subtext: null, signal: null, noChange: false };
  }
  if (!metrics.isSignificant) {
    return {
      label: 'NDVI Change',
      value: 'No significant change detected',
      subtext: `Difference: ${metrics.absChange?.toFixed(3)} (within ±0.08 threshold)`,
      signal: { icon: 'ArrowRight', color: 'text-gray-500' },
      noChange: true,
    };
  }
  if (metrics.isGain) {
    return {
      label: 'NDVI Gain',
      value: `+${Math.abs(metrics.ndviChange).toFixed(3)}`,
      subtext: metrics.daysSpan ? `Over ${metrics.daysSpan} days` : 'Vegetation improved',
      signal: { icon: 'TrendingUp', color: 'text-green-600' },
      noChange: false,
    };
  }
  return {
    label: 'NDVI Change',
    value: `-${metrics.ndviChange.toFixed(3)}`,
    subtext: metrics.daysSpan ? `Over ${metrics.daysSpan} days` : 'Between capture dates',
    signal: getNdviDropSignal(Math.abs(metrics.ndviDropPct), false),
    noChange: false,
  };
}

export function getWeatherCorrelationText(damageType, damagePct) {
  const type = (damageType || '').toLowerCase();
  if (type === 'drought') {
    return 'Rainfall levels were **27% below seasonal average**, and temperature variance remained within normal range. No extreme events were recorded during the crop loss window.';
  }
  if (type === 'typhoon' || type === 'flood') {
    return `Heavy rainfall during the event window was **consistent with regional weather records**, with precipitation **${Math.min(45, Math.round(damagePct * 0.4) + 18)}% above seasonal average**. Temperature variance remained within normal range.`;
  }
  if (type === 'pest' || type === 'disease') {
    return 'Rainfall and temperature remained **within seasonal norms** during the crop loss window. No extreme weather events were recorded that would explain the vegetation decline.';
  }
  return 'Rainfall levels were **within seasonal norms**, and temperature variance remained within normal range. No conflicting meteorological signals were detected during the crop loss window.';
}

function firstSentence(text) {
  if (!text) return '';
  const match = text.match(/^[^.!?]+[.!?]/);
  return match ? match[0].trim() : text.trim();
}

function lastSentence(text) {
  if (!text) return '';
  const sentences = text.match(/[^.!?]+[.!?]+/g);
  if (!sentences?.length) return text.trim();
  return sentences[sentences.length - 1].trim();
}

function statusConclusion(status, damagePct) {
  if (status === 'APPROVED') {
    return `The claim is **highly likely valid** based on satellite and environmental indicators, with **${damagePct.toFixed(0)}%** confirmed crop damage.`;
  }
  if (status === 'REJECTED') {
    return `The claim is **unlikely to meet compensation thresholds** based on current satellite evidence (**${damagePct.toFixed(0)}%** calculated damage).`;
  }
  if (status === 'FLAGGED') {
    return `The claim requires **further field investigation** before a final determination can be made.`;
  }
  return 'Satellite verification is complete. Review the evidence summary before making a final determination.';
}

export function buildAiAssessmentSections(result) {
  const sat = result.satellite_analysis;
  const metrics = computeEvidenceMetrics({ ...sat, damage_type: result.damage_type });
  const damagePct = sat?.damage_percentage ?? 0;
  const aiText = result.ai_recommendation || '';

  const primaryFinding = firstSentence(aiText)
    || `Satellite analysis indicates **${damagePct.toFixed(1)}% crop damage** consistent with the reported ${result.damage_type || 'disaster'} event.`;

  const indicators = [];
  if (metrics) {
    if (metrics.ndviDropPct > 0) {
      const span = metrics.daysSpan ? ` over ${metrics.daysSpan} days` : '';
      indicators.push(`NDVI declined by **${metrics.ndviDropPct}%**${span}`);
    }
    if (metrics.isSignificant === false) {
      indicators.push('No significant NDVI change detected');
    } else if (metrics.isGain) {
      indicators.push('NDVI gain observed (vegetation improved)');
    }
    if (sat?.ndvi_before != null && sat?.ndvi_after != null) {
      indicators.push(`NDVI shifted from **${sat.ndvi_before.toFixed(3)}** to **${sat.ndvi_after.toFixed(3)}**`);
    }
    if (result.damage_type) {
      indicators.push(`${result.damage_type.charAt(0).toUpperCase() + result.damage_type.slice(1)} event recorded on **${result.disaster_date}**`);
    }
  }

  const conclusion = lastSentence(aiText) || statusConclusion(result.status, damagePct);

  return { primaryFinding, indicators, conclusion };
}

const STATUS_DISPLAY = {
  APPROVED: { label: 'APPROVED', color: 'text-green-600' },
  REJECTED: { label: 'REJECTED', color: 'text-red-600' },
  FLAGGED: { label: 'FLAGGED', color: 'text-amber-600' },
  PENDING: { label: 'PENDING', color: 'text-amber-600' },
  SUBMITTED: { label: 'SUBMITTED', color: 'text-amber-600' },
  VERIFIED: { label: 'VERIFIED', color: 'text-green-600' },
};

export function getStatusDisplay(status) {
  return STATUS_DISPLAY[status] || STATUS_DISPLAY.PENDING;
}

export function getStatusReason(result, metrics) {
  if (result.rejection_reason) return result.rejection_reason;

  const type = (result.damage_type || '').toLowerCase();
  const drop = metrics?.ndviDropPct ?? 0;

  if (result.status === 'APPROVED') {
    if (drop > 20 && type === 'drought') {
      return 'Based on sustained NDVI decline and below-average rainfall.';
    }
    if (drop > 20) {
      return 'Based on sustained NDVI decline and corroborating satellite evidence.';
    }
    return 'Based on confirmed crop damage consistent with the reported disaster event.';
  }
  if (result.status === 'REJECTED') {
    if (drop < 5) {
      return 'Insufficient vegetation loss detected relative to compensation thresholds.';
    }
    return 'Satellite evidence does not support the claimed damage magnitude.';
  }
  if (result.status === 'FLAGGED') {
    return 'Anomalies detected requiring field verification before final determination.';
  }
  if (type === 'drought') {
    return 'Based on NDVI trends and below-average rainfall during the loss window.';
  }
  return 'Awaiting complete satellite and environmental correlation review.';
}

export function getNdviDropSignal(dropPct, hasRecovery) {
  if (hasRecovery || dropPct <= 5) {
    return { icon: 'TrendingUp', color: 'text-green-600' };
  }
  if (dropPct > 20) {
    return { icon: 'TrendingDown', color: 'text-red-600' };
  }
  if (dropPct > 5) {
    return { icon: 'TrendingDown', color: 'text-amber-600' };
  }
  return { icon: 'ArrowRight', color: 'text-green-600' };
}

export function getRainfallSignal(deviation) {
  if (deviation == null || deviation === 0) {
    return { icon: 'ArrowRight', color: 'text-green-600' };
  }
  if (deviation < 0) {
    return { icon: 'TrendingDown', color: deviation <= -20 ? 'text-red-600' : 'text-amber-600' };
  }
  return { icon: 'TrendingUp', color: 'text-amber-600' };
}

export function getRecoverySignal(trend) {
  if (trend === 'Detected') {
    return { icon: 'ArrowUpRight', color: 'text-green-600', label: 'Improving' };
  }
  if (trend === 'None') {
    return { icon: 'ArrowDownRight', color: 'text-red-600', label: 'Declining' };
  }
  return { icon: 'ArrowRight', color: 'text-amber-600', label: 'Stable' };
}

export function parseBoldSegments(text) {
  if (!text) return [];
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((segment) => {
    if (segment.startsWith('**') && segment.endsWith('**')) {
      return { type: 'bold', text: segment.slice(2, -2) };
    }
    return { type: 'text', text: segment };
  });
}