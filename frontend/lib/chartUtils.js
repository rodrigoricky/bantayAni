export function getChartYDomain(data, key = 'ndvi') {
  if (!data || data.length === 0) return [0, 1];

  const values = data.map((d) => d[key]).filter((v) => v != null && !Number.isNaN(v));
  if (values.length === 0) return [0, 1];

  const min = Math.min(...values);
  const max = Math.max(...values);

  if (values.length === 1) {
    const pad = 0.08;
    return [Math.max(0, min - pad), Math.min(1, max + pad)];
  }

  const range = max - min || 0.1;
  const padding = range * 0.15;
  return [Math.max(0, min - padding), Math.min(1, max + padding)];
}