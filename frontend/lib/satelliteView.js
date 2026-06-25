import { SATELLITE_DATE_KEY, DEFAULT_SATELLITE_DATE, normalizeSatelliteDate } from './SatelliteDateContext';

export { SATELLITE_DATE_KEY, DEFAULT_SATELLITE_DATE };

export function getSatelliteViewDate() {
  if (typeof window === 'undefined') return DEFAULT_SATELLITE_DATE;
  const stored = localStorage.getItem(SATELLITE_DATE_KEY)
    || localStorage.getItem('satellite_view_date');
  return normalizeSatelliteDate(stored);
}

export function setSatelliteViewDate(date) {
  if (typeof window !== 'undefined') {
    localStorage.setItem(SATELLITE_DATE_KEY, date);
    window.dispatchEvent(new CustomEvent('satellite-date-changed', { detail: date }));
  }
}

export function getDashboardPath(role) {
  switch (role) {
    case 'PCIC':
      return '/pcic/claims-queue';
    case 'DA_REGIONAL':
      return '/regional/overview';
    default:
      return '/dashboard';
  }
}