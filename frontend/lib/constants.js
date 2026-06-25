import {
  NDVI_THRESHOLDS,
  getNDVIContext,
  getNDVIColor,
  getStatusColors,
  statusFromNdvi,
} from './ndvi';

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export const COLORS = {
  healthy: { base: '#22c55e', dark: '#16a34a', bg: '#dcfce7' },
  fair: { base: '#eab308', dark: '#ca8a04', bg: '#fef9c3' },
  watch: { base: '#f97316', dark: '#ea580c', bg: '#ffedd5' },
  critical: { base: '#ef4444', dark: '#dc2626', bg: '#fee2e2' },
  primary: '#1d4ed8',
};

/** @deprecated Prefer getStatusColors() — kept for backward compatibility */
export const STATUS_COLORS = {
  HEALTHY: {
    border: getStatusColors('HEALTHY').stroke,
    fill: getStatusColors('HEALTHY').stroke,
    text: getStatusColors('HEALTHY').text,
    bg: getStatusColors('HEALTHY').bg,
    badge: getStatusColors('HEALTHY').badge,
    dot: getStatusColors('HEALTHY').dot,
  },
  WATCH: {
    border: getStatusColors('WATCH').stroke,
    fill: getStatusColors('WATCH').stroke,
    text: getStatusColors('WATCH').text,
    bg: getStatusColors('WATCH').bg,
    badge: getStatusColors('WATCH').badge,
    dot: getStatusColors('WATCH').dot,
  },
  FAIR: {
    border: getStatusColors('FAIR').stroke,
    fill: getStatusColors('FAIR').stroke,
    text: getStatusColors('FAIR').text,
    bg: getStatusColors('FAIR').bg,
    badge: getStatusColors('FAIR').badge,
    dot: getStatusColors('FAIR').dot,
  },
  CRITICAL: {
    border: getStatusColors('CRITICAL').stroke,
    fill: getStatusColors('CRITICAL').stroke,
    text: getStatusColors('CRITICAL').text,
    bg: getStatusColors('CRITICAL').bg,
    badge: getStatusColors('CRITICAL').badge,
    dot: getStatusColors('CRITICAL').dot,
  },
};

export const CLAIM_STATUS = {
  APPROVED: {
    label: 'Approved',
    icon: 'CheckCircle2',
    gradient: 'bg-gradient-to-br from-green-50 to-emerald-50 border-green-400',
    text: 'text-green-900',
    iconColor: 'text-[#15803d]',
  },
  FLAGGED: {
    label: 'Flagged for Review',
    icon: 'AlertTriangle',
    gradient: 'bg-gradient-to-br from-amber-50 to-yellow-50 border-amber-400',
    text: 'text-amber-900',
    iconColor: 'text-[#b45309]',
  },
  REJECTED: {
    label: 'Rejected',
    icon: 'XCircle',
    gradient: 'bg-gradient-to-br from-red-50 to-rose-50 border-red-400',
    text: 'text-red-900',
    iconColor: 'text-[#b91c1c]',
  },
  PENDING: {
    label: 'Pending',
    icon: 'Info',
    gradient: 'bg-gradient-to-br from-gray-50 to-slate-50 border-gray-400',
    text: 'text-gray-900',
    iconColor: 'text-gray-600',
  },
};

export {
  NDVI_THRESHOLDS,
  getNDVIContext,
  getNDVIColor,
  getStatusColors,
  statusFromNdvi,
};