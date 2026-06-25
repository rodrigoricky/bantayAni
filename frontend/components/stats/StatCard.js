'use client';

const STATUS_DOTS = {
  healthy: { dot: 'bg-green-600', text: 'text-green-600' },
  watch: { dot: 'bg-amber-600', text: 'text-amber-600' },
  critical: { dot: 'bg-red-600', text: 'text-red-600' },
  approved: { dot: 'bg-green-600', text: 'text-green-600' },
  flagged: { dot: 'bg-amber-600', text: 'text-amber-600' },
  rejected: { dot: 'bg-red-600', text: 'text-red-600' },
  pending: { dot: 'bg-amber-600', text: 'text-amber-600' },
};

export default function StatCard({
  label,
  value,
  statusLabel,
  statusVariant,
}) {
  const status = statusVariant ? STATUS_DOTS[statusVariant] : null;

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-[0.06em]">{label}</p>
      <p className="text-2xl font-semibold text-gray-900 mt-1">{value}</p>
      {status && statusLabel && (
        <div className="flex items-center gap-1.5 mt-2">
          <span className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />
          <span className={`text-xs font-medium ${status.text}`}>{statusLabel}</span>
        </div>
      )}
    </div>
  );
}