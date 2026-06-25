'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Settings, ChevronLeft, ChevronRight } from 'lucide-react';
import { getToken, getUser } from '@/lib/auth';
import { useSatelliteDate } from '@/lib/SatelliteDateContext';
import { formatLongDate } from '@/lib/dateUtils';
import Toast from '@/components/common/Toast';
import Badge from '@/components/common/Badge';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function toDateKey(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

function buildCalendarDays(year, month) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < firstDay; i += 1) cells.push(null);
  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push({ day, dateKey: toDateKey(year, month, day) });
  }
  return cells;
}

function roleBadgeVariant(role) {
  if (role === 'MAO') return 'healthy';
  if (role === 'DA_REGIONAL') return 'watch';
  if (role === 'PCIC') return 'critical';
  return 'default';
}

export default function SettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState(null);
  const {
    satelliteDate,
    selectedDate,
    setSatelliteDate,
    availableDates,
    loadingDates,
  } = useSatelliteDate();
  const [localDate, setLocalDate] = useState(selectedDate);
  const [toast, setToast] = useState(null);
  const [viewYear, setViewYear] = useState(2024);
  const [viewMonth, setViewMonth] = useState(9);

  const availableDateSet = useMemo(
    () => new Set(availableDates),
    [availableDates],
  );

  useEffect(() => {
    if (!getToken()) router.push('/login');
    else setUser(getUser());
  }, [router]);

  useEffect(() => {
    setLocalDate(selectedDate);
    const [y, m] = selectedDate.split('-').map(Number);
    if (y && m) {
      setViewYear(y);
      setViewMonth(m - 1);
    }
  }, [selectedDate]);

  const calendarDays = useMemo(() => buildCalendarDays(viewYear, viewMonth), [viewYear, viewMonth]);

  const handleSave = () => {
    if (!localDate) {
      setToast({ type: 'error', message: 'Error — failed to apply date change. Please try again.' });
      return;
    }
    if (availableDateSet.size > 0 && !availableDateSet.has(localDate)) {
      setToast({ type: 'error', message: 'Error — failed to apply date change. Please try again.' });
      return;
    }
    try {
      setSatelliteDate(localDate);
      setToast({ type: 'success', message: `Date simulation updated to ${formatLongDate(localDate)}.` });
    } catch {
      setToast({ type: 'error', message: 'Error — failed to apply date change. Please try again.' });
    }
  };

  const municipalityLabel = user?.municipality_id === 'camarines-naga'
    ? 'Naga City, Camarines Sur'
    : (user?.municipality_id || 'Naga City').replace(/-/g, ' ');

  const showDateSkeleton = false;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {toast && (
        <Toast message={toast.message} type={toast.type} position="top-right" onClose={() => setToast(null)} />
      )}
      <div>
        <h1 className="page-title">Settings</h1>
        <p className="text-sm text-gray-500 mt-0.5">Account preferences and satellite timeline</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="card-base overflow-hidden">
          <div className="border-b border-gray-200 px-5 py-4 text-center">
            <h3 className="text-base font-semibold text-gray-900">Select Satellite Date</h3>
            <p className="text-sm text-gray-500 mt-0.5">
              Choose a date with available Sentinel-2 imagery for Naga City
            </p>
          </div>

          <div className="p-6 space-y-4 flex flex-col items-center">
            <p className="text-sm font-medium text-gray-700 text-center">
              Selected: {localDate ? formatLongDate(localDate) : 'None'}
            </p>
            <div className="w-full max-w-sm mx-auto">
              <div className="flex items-center justify-between mb-4">
                <button type="button" onClick={() => {
                  if (viewMonth === 0) { setViewMonth(11); setViewYear((y) => y - 1); }
                  else setViewMonth((m) => m - 1);
                }} className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100" aria-label="Previous month">
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <p className="text-sm font-semibold text-gray-900">{MONTH_NAMES[viewMonth]} {viewYear}</p>
                <button type="button" onClick={() => {
                  if (viewMonth === 11) { setViewMonth(0); setViewYear((y) => y + 1); }
                  else setViewMonth((m) => m + 1);
                }} className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100" aria-label="Next month">
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>

              <div className="grid grid-cols-7 gap-1 mb-1">
                {WEEKDAY_LABELS.map((label) => (
                  <div key={label} className="text-center text-[11px] font-medium text-gray-400 py-1">{label}</div>
                ))}
              </div>

              {showDateSkeleton ? (
                <div className="grid grid-cols-7 gap-1">
                  {Array.from({ length: 35 }).map((_, i) => (
                    <div key={i} className="h-10 rounded-lg bg-gray-100 animate-pulse" />
                  ))}
                </div>
              ) : (
                <div className="grid grid-cols-7 gap-1">
                  {calendarDays.map((cell, idx) => {
                    if (!cell) return <div key={`empty-${idx}`} className="h-10" />;
                    const isAvailable = availableDateSet.has(cell.dateKey);
                    const isSelected = localDate === cell.dateKey;
                    return (
                      <button
                        key={cell.dateKey}
                        type="button"
                        disabled={!isAvailable}
                        onClick={() => isAvailable && setLocalDate(cell.dateKey)}
                        className={`relative h-10 rounded-lg text-sm font-medium transition-colors ${
                          isAvailable ? 'text-gray-900 hover:bg-green-50 cursor-pointer' : 'text-gray-300 cursor-not-allowed bg-gray-50'
                        } ${isSelected ? 'bg-indigo-100 text-indigo-900 ring-2 ring-indigo-500' : ''}`}
                      >
                        {cell.day}
                        {isAvailable && (
                          <span className="absolute bottom-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-green-500" />
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <div className="border-t border-gray-200 px-5 py-4 flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Current view: <span className="font-semibold text-gray-900">{satelliteDate}</span>
            </p>
            <button
              type="button"
              onClick={handleSave}
              disabled={!localDate || localDate === satelliteDate}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Apply Changes
            </button>
          </div>
        </div>

        <div className="space-y-4">
          <div className="card-base p-4 min-h-[180px]">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Settings className="w-3.5 h-3.5" />
              Profile
            </p>
            <div className="space-y-1">
              <p className="text-base font-semibold text-gray-900">
                {user?.first_name} {user?.last_name}
              </p>
              <p className="text-sm text-gray-500">{user?.email}</p>
              <div className="pt-1">
                <Badge variant={roleBadgeVariant(user?.role)} size="sm">{user?.role}</Badge>
              </div>
              <p className="text-sm text-gray-500 pt-1">{municipalityLabel}</p>
            </div>
          </div>

          <div className="card-padded">
            <h3 className="section-title mb-3">Typhoon Kristine Timeline</h3>
            <div className="relative h-1.5 rounded-full overflow-hidden border border-gray-200 bg-gray-100 mb-3">
              <div className="absolute inset-y-0 left-0 w-1/3 bg-gray-300" />
              <div className="absolute inset-y-0 left-1/3 w-1/3 bg-gray-400" />
              <div className="absolute inset-y-0 right-0 w-1/3 bg-gray-300" />
            </div>
            <div className="flex justify-between text-xs text-gray-600">
              <span>Sep-Oct 15 | Pre-typhoon</span>
              <span className="font-semibold text-gray-900">Oct 22-24 | Typhoon</span>
              <span>Oct 25-Dec | Post-typhoon</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}