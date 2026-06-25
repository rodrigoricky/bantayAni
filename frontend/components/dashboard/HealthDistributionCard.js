'use client';

import { getStatusColors } from '@/lib/ndvi';
import { formatDisplayDate } from '@/lib/dateUtils';

export default function HealthDistributionCard({ stats, totalFarms, farms = [], satelliteDate }) {
  const total = totalFarms || 1;
  const healthyHa = farms.filter((f) => f.status === 'HEALTHY').reduce((s, f) => s + (f.area_hectares || 0), 0);
  const watchHa = farms.filter((f) => f.status === 'WATCH').reduce((s, f) => s + (f.area_hectares || 0), 0);
  const criticalHa = farms.filter((f) => f.status === 'CRITICAL').reduce((s, f) => s + (f.area_hectares || 0), 0);
  const totalHa = healthyHa + watchHa + criticalHa || total;

  const dateLabel = satelliteDate ? formatDisplayDate(satelliteDate) : 'latest pass';

  const blocks = [
    { key: 'healthy', label: 'Healthy', count: stats.healthy_count, ha: healthyHa, ...getStatusColors('HEALTHY') },
    { key: 'watch', label: 'Watch', count: stats.watch_count, ha: watchHa, ...getStatusColors('WATCH') },
    { key: 'critical', label: 'Critical', count: stats.critical_count, ha: criticalHa, ...getStatusColors('CRITICAL') },
  ];

  return (
    <div className="bg-white border border-gray-200 rounded-[14px] p-4 w-[260px] pointer-events-auto">
      <h3 className="text-sm font-semibold text-gray-900">Crop Health Overview</h3>
      <p className="text-xs text-gray-500 mb-3">As of {dateLabel}</p>

      <div className="h-1.5 flex rounded-full overflow-hidden border border-gray-200 mb-3 bg-gray-100">
        {blocks.map((b) => b.ha > 0 && (
          <div key={b.key} className={`${b.dot} h-full opacity-60`} style={{ width: `${(b.ha / totalHa) * 100}%` }} title={`${b.label}: ${b.ha.toFixed(1)} ha`} />
        ))}
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs">
        {blocks.map((b) => (
          <div key={b.key} className="text-center">
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${b.dot} mb-1`} />
            <p className="font-semibold text-gray-900">{b.ha.toFixed(1)} ha</p>
            <p className="text-gray-500">{((b.ha / totalHa) * 100).toFixed(0)}%</p>
            <p className={`${b.text} font-medium`}>{b.count} farms</p>
          </div>
        ))}
      </div>
    </div>
  );
}