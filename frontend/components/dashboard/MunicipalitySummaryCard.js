'use client';

import { Wheat, Map, Bell } from 'lucide-react';

export default function MunicipalitySummaryCard({ farms, stats, municipality }) {
  const totalArea = farms.reduce((sum, f) => sum + (f.area_hectares || 0), 0);
  const activeAlerts = (stats?.watch_count || 0) + (stats?.critical_count || 0);

  const rows = [
    { icon: Wheat, value: farms.length, label: 'Farms Monitored' },
    { icon: Map, value: totalArea.toFixed(1), label: 'Hectares' },
    { icon: Bell, value: activeAlerts, label: 'Active Alerts' },
  ];

  return (
    <div className="bg-white border border-gray-200 rounded-[14px] px-4 py-3 w-[200px] pointer-events-auto">
      {municipality?.name && (
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-[0.06em] mb-2">
          {municipality.name}
        </p>
      )}
      <div className="space-y-2.5">
        {rows.map(({ icon: Icon, value, label }) => (
          <div key={label} className="flex items-center gap-3">
            <Icon className="w-4 h-4 text-gray-500 flex-shrink-0" />
            <span className="text-base font-semibold text-gray-900">{value}</span>
            <span className="text-xs text-gray-500">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}