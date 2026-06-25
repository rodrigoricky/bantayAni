'use client';

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '@/lib/api';
import { getToken } from '@/lib/auth';
import { DEMO_SATELLITE_DATES } from '@/lib/demoSatelliteDates';

export const SATELLITE_DATE_KEY = 'bantay_ani_satellite_date';
export const DEFAULT_SATELLITE_DATE = '2024-10-25';
const DEMO_DATE_MIN = '2024-09-01';
const DEMO_DATE_MAX = '2024-12-31';

function isValidDemoDate(dateStr) {
  if (!dateStr || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return false;
  return dateStr >= DEMO_DATE_MIN && dateStr <= DEMO_DATE_MAX;
}

export function normalizeSatelliteDate(dateStr) {
  return isValidDemoDate(dateStr) ? dateStr : DEFAULT_SATELLITE_DATE;
}

const SatelliteDateContext = createContext(null);

export function SatelliteDateProvider({ children }) {
  const [satelliteDate, setSatelliteDateState] = useState(DEFAULT_SATELLITE_DATE);
  const [availableDates, setAvailableDates] = useState(DEMO_SATELLITE_DATES);
  const [loadingDates, setLoadingDates] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(SATELLITE_DATE_KEY)
      || localStorage.getItem('satellite_view_date');
    const resolved = normalizeSatelliteDate(stored);
    setSatelliteDateState(resolved);
    localStorage.setItem(SATELLITE_DATE_KEY, resolved);
    if (stored && stored !== resolved) {
      localStorage.removeItem('satellite_view_date');
    }
  }, []);

  const refreshAvailableDates = useCallback(async () => {
    if (!getToken()) return;
    try {
      const res = await api.get('/satellite/sentinel-dates', {
        params: {
          lat: 13.6192,
          lng: 123.1814,
          start_date: DEMO_DATE_MIN,
          end_date: DEMO_DATE_MAX,
        },
        skipCache: true,
      });
      const dates = (res.data?.data?.available_dates || []).map((d) => d.date);
      if (dates.length > 0) setAvailableDates(dates);
    } catch {
      setAvailableDates(DEMO_SATELLITE_DATES);
    }
  }, []);

  useEffect(() => {
    refreshAvailableDates();
  }, [refreshAvailableDates]);

  const setSatelliteDate = useCallback((date) => {
    const resolved = normalizeSatelliteDate(date);
    setSatelliteDateState(resolved);
    localStorage.setItem(SATELLITE_DATE_KEY, resolved);
    window.dispatchEvent(new CustomEvent('satellite-date-changed', { detail: date }));
  }, []);

  return (
    <SatelliteDateContext.Provider
      value={{
        satelliteDate,
        selectedDate: satelliteDate,
        setSatelliteDate,
        availableDates,
        loadingDates,
        refreshAvailableDates,
      }}
    >
      {children}
    </SatelliteDateContext.Provider>
  );
}

export function useSatelliteDate() {
  const ctx = useContext(SatelliteDateContext);
  if (!ctx) {
    throw new Error('useSatelliteDate must be used within SatelliteDateProvider');
  }
  return ctx;
}