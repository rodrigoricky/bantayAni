import { CLAIM_STATUS } from '@/lib/constants';
import { getStatusColors } from '@/lib/ndvi';

const HEALTH_VARIANTS = {
  healthy: { label: 'Healthy', text: getStatusColors('HEALTHY').text },
  watch: { label: 'Watch', text: getStatusColors('WATCH').text },
  fair: { label: 'Fair', text: getStatusColors('FAIR').text },
  critical: { label: 'Critical', text: getStatusColors('CRITICAL').text },
};

const CLAIM_VARIANTS = {
  approved: { label: 'Approved', text: 'text-green-600' },
  flagged: { label: 'Flagged', text: 'text-amber-600' },
  rejected: { label: 'Rejected', text: 'text-red-600' },
  pending: { label: 'Pending', text: 'text-amber-600' },
  submitted: { label: 'Submitted', text: 'text-gray-600' },
  verified: { label: 'Verified', text: 'text-gray-600' },
};

const SIZES = {
  sm: 'px-2.5 py-1 text-xs',
  default: 'px-2.5 py-1 text-xs',
  md: 'px-2.5 py-1 text-xs',
  lg: 'px-2.5 py-1 text-xs',
};

function OutlinePill({ config, children, size = 'default', className = '' }) {
  return (
    <span
      className={`
        inline-flex items-center font-medium rounded-full
        border border-gray-300 bg-white
        ${config.text}
        ${SIZES[size] || SIZES.default}
        ${className}
      `}
    >
      {children || config.label}
    </span>
  );
}

export default function Badge({ variant, children, size = 'default', className = '' }) {
  const resolved = variant?.toLowerCase() || 'pending';
  const config = HEALTH_VARIANTS[resolved] || CLAIM_VARIANTS[resolved] || CLAIM_VARIANTS.pending;
  return <OutlinePill config={config} size={size} className={className}>{children}</OutlinePill>;
}

export function StatusBadge({ status, className = '', size = 'sm' }) {
  const key = status?.toLowerCase() || 'watch';
  const config = HEALTH_VARIANTS[key] || HEALTH_VARIANTS.watch;
  return <OutlinePill config={config} size={size} className={className}>{status || config.label}</OutlinePill>;
}

export function ClaimStatusBadge({ status, className = '', size = 'default' }) {
  const key = status?.toLowerCase() || 'pending';
  const config = CLAIM_VARIANTS[key] || CLAIM_VARIANTS.pending;
  const claimMeta = CLAIM_STATUS[status] || {};
  return (
    <OutlinePill config={config} size={size} className={className}>
      {config.label || claimMeta.label || status}
    </OutlinePill>
  );
}