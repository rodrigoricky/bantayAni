import { format, parseISO } from 'date-fns';

/** Format an ISO or parseable date string for display (e.g. "Jun 25, 2026"). */
export function formatDisplayDate(dateStr) {
  if (!dateStr) return '';
  try {
    const date = typeof dateStr === 'string' ? parseISO(dateStr) : dateStr;
    return format(date, 'MMM d, yyyy');
  } catch {
    return String(dateStr);
  }
}

/** Long format for header/settings (e.g. "October 14, 2024"). */
export function formatLongDate(dateStr) {
  if (!dateStr) return '';
  try {
    const date = typeof dateStr === 'string' ? parseISO(dateStr) : dateStr;
    return format(date, 'MMMM d, yyyy');
  } catch {
    return String(dateStr);
  }
}

const TYPHOON_KRISTINE_DATE = '2024-10-22';

export function getDisasterPhaseLabel(dateStr) {
  if (!dateStr) return 'Pre-Disaster';
  return dateStr < TYPHOON_KRISTINE_DATE ? 'Pre-Disaster' : 'Post-Disaster';
}