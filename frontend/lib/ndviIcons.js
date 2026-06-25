import {
  Leaf,
  Sprout,
  AlertTriangle,
  AlertCircle,
  XCircle,
  AlertOctagon,
} from 'lucide-react';

export const NDVI_ICONS = {
  Leaf,
  Sprout,
  AlertTriangle,
  AlertCircle,
  XCircle,
  AlertOctagon,
};

export function NDVIIcon({ name, className = 'w-3.5 h-3.5 shrink-0' }) {
  const Icon = NDVI_ICONS[name];
  if (!Icon) return null;
  return <Icon className={className} aria-hidden="true" />;
}