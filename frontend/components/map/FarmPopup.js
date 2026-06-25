import { StatusBadge } from '@/components/common/Badge';

export default function FarmPopup({ farm }) {
  return (
    <div className="p-3">
      <div className="flex items-start justify-between mb-2 gap-2">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">{farm.farmer_name}</h3>
          <p className="text-xs text-gray-600 font-mono">{farm.rsbsa_number}</p>
        </div>
        <StatusBadge status={farm.status} />
      </div>
      <div className="space-y-1 text-xs text-gray-600">
        <div className="flex justify-between">
          <span>Crop:</span>
          <span className="font-medium text-gray-900">{farm.crop_type}</span>
        </div>
        <div className="flex justify-between">
          <span>Area:</span>
          <span className="font-medium text-gray-900">{farm.area_hectares} ha</span>
        </div>
        <div className="flex justify-between">
          <span>NDVI:</span>
          <span className="font-mono font-medium text-gray-900">
            {farm.status === 'UNKNOWN' || farm.health_status === 'unknown'
              ? 'No data for this date'
              : (farm.latest_ndvi != null ? farm.latest_ndvi.toFixed(3) : 'N/A')}
          </span>
        </div>
      </div>
    </div>
  );
}