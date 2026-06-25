'use client';

import { X } from 'lucide-react';
import { StatusBadge } from '@/components/common/Badge';

function getBarColor(ndvi, status) {
  if (status === 'CRITICAL') return 'from-red-600 to-red-400';
  if (status === 'WATCH') return 'from-amber-500 to-amber-300';
  return 'from-green-600 to-green-400';
}

export default function FarmDetailCard({ farm, ndviHistory, onClose }) {
  if (!farm) return null;

  const history = ndviHistory?.length
    ? [...ndviHistory].reverse()
    : farm.latest_ndvi != null
      ? [{ date: farm.ndvi_date || 'Now', ndvi: farm.latest_ndvi, status: farm.status }]
      : [];

  return (
    <div className="bg-white border-2 border-gray-400 rounded-md shadow-xl p-6 max-w-sm ml-auto pointer-events-auto">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{farm.farmer_name}</h3>
          <p className="text-sm text-gray-600 font-mono">{farm.rsbsa_number}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded-md transition-colors"
          aria-label="Close"
        >
          <X className="w-4 h-4 text-gray-500" />
        </button>
      </div>

      {history.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-bold text-gray-700 uppercase tracking-widest mb-2">
            NDVI Trend
          </p>
          <div className="h-24 flex items-end gap-1 border border-gray-300 rounded-md p-2 bg-gray-50">
            {history.map((point, i) => {
              const height = Math.max(8, ((point.ndvi + 1) / 2) * 100);
              const status = point.status || farm.status;
              return (
                <div
                  key={i}
                  className={`flex-1 bg-gradient-to-t ${getBarColor(point.ndvi, status)} rounded-t-sm relative group min-w-[12px]`}
                  style={{ height: `${height}%` }}
                >
                  <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 hidden group-hover:block bg-gray-900 text-white text-xs py-0.5 px-1.5 rounded whitespace-nowrap z-10">
                    {point.date}: {Number(point.ndvi).toFixed(3)}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex justify-between text-xs font-light text-gray-500 mt-1">
            <span>Earlier</span>
            <span>Latest</span>
          </div>
        </div>
      )}

      <div className="space-y-2 text-sm border-t border-gray-400 pt-4">
        <div className="flex justify-between">
          <span className="text-gray-600">Crop Type</span>
          <span className="font-medium text-gray-900">{farm.crop_type}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Area</span>
          <span className="font-medium text-gray-900">{farm.area_hectares} ha</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Current NDVI</span>
          <span className="font-mono font-semibold text-gray-900">
            {farm.latest_ndvi != null ? farm.latest_ndvi.toFixed(3) : 'N/A'}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-gray-600">Status</span>
          <StatusBadge status={farm.status} />
        </div>
      </div>
    </div>
  );
}