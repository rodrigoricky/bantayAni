import { TrendingDown, TrendingUp } from 'lucide-react';
import { getNDVIContext } from '@/lib/constants';
import { NDVIIcon } from '@/lib/ndviIcons';

export default function NDVIComparison({ satelliteAnalysis }) {
  if (!satelliteAnalysis) return null;

  const change = satelliteAnalysis.ndvi_after - satelliteAnalysis.ndvi_before;
  const beforeCtx = getNDVIContext(satelliteAnalysis.ndvi_before);
  const afterCtx = getNDVIContext(satelliteAnalysis.ndvi_after);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-0 border border-gray-200 rounded-xl overflow-hidden">
      <div className="p-5 border-b sm:border-b-0 sm:border-r border-gray-200 bg-white">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-[0.06em] mb-1">
          Before Disaster
        </p>
        <p className="text-xs text-gray-400 mb-3">{satelliteAnalysis.before_date}</p>
        <p className="text-2xl font-semibold font-mono text-gray-900">
          {satelliteAnalysis.ndvi_before.toFixed(3)}
        </p>
        <div className="flex items-center gap-2 mt-2">
          <span className={`w-1.5 h-1.5 rounded-full ${beforeCtx.dotClass}`} />
          <p className={`text-sm font-medium flex items-center gap-1.5 ${beforeCtx.colorClass}`}>
            <NDVIIcon name={beforeCtx.icon} />
            {beforeCtx.label}
          </p>
        </div>
        <p className="text-xs text-gray-500 mt-1">{beforeCtx.damageEquivalent}</p>
      </div>

      <div className="p-5 bg-white">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-[0.06em] mb-1">
          After Disaster
        </p>
        <p className="text-xs text-gray-400 mb-3">{satelliteAnalysis.after_date}</p>
        <p className="text-2xl font-semibold font-mono text-gray-900">
          {satelliteAnalysis.ndvi_after.toFixed(3)}
        </p>
        <div className="flex items-center gap-2 mt-2">
          <span className={`w-1.5 h-1.5 rounded-full ${afterCtx.dotClass}`} />
          <p className={`text-sm font-medium flex items-center gap-1.5 ${afterCtx.colorClass}`}>
            <NDVIIcon name={afterCtx.icon} />
            {afterCtx.label}
          </p>
        </div>
        <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
          {change < 0 ? (
            <TrendingDown className="w-3.5 h-3.5 text-red-600" />
          ) : (
            <TrendingUp className="w-3.5 h-3.5 text-green-600" />
          )}
          <span>
            Change {change >= 0 ? '+' : ''}{change.toFixed(3)} | {afterCtx.damageEquivalent}
          </span>
        </p>
      </div>
    </div>
  );
}