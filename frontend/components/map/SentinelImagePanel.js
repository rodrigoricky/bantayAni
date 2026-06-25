'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { RefreshCw, Satellite, ImageOff, ScanLine, Loader2 } from 'lucide-react';
import api from '@/lib/api';
import { format, parseISO } from 'date-fns';
import { useSatelliteDate } from '@/lib/SatelliteDateContext';
import { getUser } from '@/lib/auth';

function ThumbnailImage({ src, alt }) {
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <div className="w-20 h-20 rounded-lg bg-gray-100 flex flex-col items-center justify-center text-gray-400">
        <Satellite className="w-5 h-5 mb-1" />
        <span className="text-[10px] text-center px-1">Satellite imagery unavailable for this date</span>
      </div>
    );
  }

  return (
    <div className="relative w-20 h-20 rounded-lg overflow-hidden bg-gray-100 flex-shrink-0">
      {loading && <div className="absolute inset-0 animate-pulse bg-gray-200" />}
      <img
        src={src}
        alt={alt}
        width={80}
        height={80}
        className="w-20 h-20 object-cover bg-gray-100"
        onLoad={() => setLoading(false)}
        onError={() => { setLoading(false); setFailed(true); }}
      />
    </div>
  );
}

export default function SentinelImagePanel({
  latitude,
  longitude,
  className = '',
  compact = false,
  isLive = false,
  isDateScanned = false,
  onScanComplete,
}) {
  const { satelliteDate } = useSatelliteDate();
  const [viewType, setViewType] = useState('true-color');
  const [scanning, setScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState(null);
  const [imageUrl, setImageUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actualDate, setActualDate] = useState(null);
  const [requestedDate, setRequestedDate] = useState(satelliteDate);
  const [imageSource, setImageSource] = useState(null);
  const pollRef = useRef(null);
  const pollStartRef = useRef(null);

  useEffect(() => {
    if (!latitude || !longitude || !satelliteDate) return;
    let revoked = null;
    const fetchImage = async () => {
      setLoading(true);
      setError(null);
      setRequestedDate(satelliteDate);
      try {
        const res = await api.get('/satellite/sentinel-image', {
          params: {
            lat: latitude,
            lng: longitude,
            date: satelliteDate,
            type: viewType,
            buffer_km: 0.5,
          },
          responseType: 'blob',
        });
        const url = URL.createObjectURL(res.data);
        revoked = url;
        setImageUrl(url);
        setActualDate(res.headers['x-actual-date'] || satelliteDate);
        setRequestedDate(res.headers['x-requested-date'] || satelliteDate);
        setImageSource(res.headers['x-image-source'] || null);
      } catch {
        setImageUrl(null);
        setError('Imagery unavailable');
      } finally {
        setLoading(false);
      }
    };
    fetchImage();
    return () => { if (revoked) URL.revokeObjectURL(revoked); };
  }, [satelliteDate, viewType, latitude, longitude]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const pollScanStatus = useCallback((jobId) => {
    pollStartRef.current = Date.now();
    const SCAN_TIMEOUT_MS = 60000;

    const poll = async () => {
      if (Date.now() - pollStartRef.current > SCAN_TIMEOUT_MS) {
        setScanning(false);
        setScanProgress({ percent: 0, phase: 'failed', error: 'Scan timed out after 60 seconds.' });
        onScanComplete?.({ error: true, message: 'NDVI scan timed out. Please try again.' });
        pollRef.current = setTimeout(() => setScanProgress(null), 3000);
        return;
      }

      try {
        const res = await api.get(`/satellite/scan-status/${jobId}`);
        const status = res.data?.data || {};
        const total = status.total_farms || 1;
        const completed = status.completed_farms || 0;
        const percent = typeof status.progress === 'number'
          ? status.progress
          : Math.round((completed / total) * 100);

        if (status.status === 'running' || status.status === 'started') {
          setScanProgress({
            percent,
            completed,
            total,
            currentFarm: status.current_farm,
            message: status.message,
            phase: 'scanning',
          });
          pollRef.current = setTimeout(poll, 800);
          return;
        }

        if (status.status === 'completed') {
          setScanProgress({
            percent: 100,
            completed: status.scanned_farms?.length || completed,
            total,
            phase: 'complete',
          });
          setScanning(false);
          onScanComplete?.({
            ...status,
            scanned_farms: status.scanned_farms?.length ?? completed,
            failed_farms: status.failed_farms ?? 0,
          });
          pollRef.current = setTimeout(() => setScanProgress(null), 2000);
          return;
        }

        if (status.status === 'failed') {
          setScanProgress({
            percent,
            completed,
            total,
            phase: 'failed',
            error: status.error || 'Scan failed',
          });
          setScanning(false);
          onScanComplete?.({
            error: true,
            message: status.error || 'NDVI scan failed. Please try again.',
          });
          pollRef.current = setTimeout(() => setScanProgress(null), 3000);
        }
      } catch {
        setScanning(false);
        setScanProgress(null);
        onScanComplete?.({ error: true, message: 'Could not check scan status. Please try again.' });
      }
    };
    poll();
  }, [onScanComplete]);

  const handleScanNdvi = async () => {
    const user = getUser();
    if (!user?.municipality_id || scanning) return;
    stopPolling();
    setScanning(true);
    setScanProgress({ percent: 0, completed: 0, total: 0, phase: 'starting', currentFarm: null });

    try {
      const res = await api.post('/satellite/scan-ndvi', {
        municipality_id: user.municipality_id,
        satellite_date: satelliteDate,
      });
      const data = res.data?.data || {};
      const total = data.total_farms || 4;
      setScanProgress({ percent: 0, completed: 0, total, phase: 'scanning', currentFarm: null });
      if (data.job_id) {
        pollScanStatus(data.job_id);
      } else {
        setScanning(false);
        setScanProgress(null);
        onScanComplete?.({ error: true, message: 'NDVI scan could not be started.' });
      }
    } catch {
      setScanning(false);
      setScanProgress(null);
      onScanComplete?.({ error: true, message: 'NDVI scan request failed. Please try again.' });
    }
  };

  const showDateNote = actualDate && requestedDate && actualDate !== requestedDate;
  const displayDate = actualDate || satelliteDate;
  const formattedDate = displayDate
    ? (() => { try { return format(parseISO(displayDate), 'MMM d, yyyy'); } catch { return displayDate; } })()
    : 'N/A';

  const isDemoData = imageSource === 'prefetched-demo' || !isLive;

  if (compact) {
    return (
      <div className={`bg-white border border-gray-200 rounded-xl px-4 py-3 w-[220px] ${className}`}>
        <div className="flex items-center gap-2 mb-2">
          <Satellite className="w-4 h-4 text-gray-500" />
          <span className="text-xs font-semibold text-gray-900">Sentinel-2</span>
          <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium border border-gray-300 ${
            isDemoData ? 'text-gray-600' : 'text-green-600'
          }`}>
            {isDemoData ? 'Demo Data' : 'Live Data'}
          </span>
        </div>

        <div className="flex gap-3 items-start">
          {loading ? (
            <div className="w-20 h-20 rounded-lg bg-gray-200 animate-pulse flex-shrink-0" />
          ) : (
            <ThumbnailImage src={imageUrl} alt="Sentinel thumbnail" />
          )}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-700">{formattedDate}</p>
            <div className="flex gap-1 mt-2">
              {['true-color', 'ndvi'].map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setViewType(t)}
                  className={`px-2 py-0.5 text-[10px] rounded font-medium border ${
                    viewType === t ? 'bg-gray-100 text-gray-900 border-gray-300' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  {t === 'ndvi' ? 'NDVI' : 'RGB'}
                </button>
              ))}
            </div>
          </div>
        </div>

        {error && !loading && (
          <p className="text-[10px] text-gray-500 mt-2">{error}</p>
        )}

        <button
          type="button"
          onClick={handleScanNdvi}
          disabled={scanning}
          className="w-full mt-3 border border-gray-300 text-gray-700 text-xs font-semibold rounded-lg py-2 hover:bg-gray-50 transition-colors flex items-center justify-center gap-1.5 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {scanning ? (
            <>
              <Loader2 className="w-3 h-3 animate-spin" />
              Scanning...
            </>
          ) : (
            <>
              <ScanLine className="w-3 h-3" />
              {isDateScanned ? 'Rescan' : 'Scan NDVI'}
            </>
          )}
        </button>

        {scanProgress && (
          <div className="mt-2">
            <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  scanProgress.phase === 'failed' ? 'bg-red-500' : 'bg-green-600'
                }`}
                style={{ width: `${scanProgress.percent}%` }}
              />
            </div>
            <p className="text-[10px] text-gray-500 mt-1.5 leading-snug">
              {scanProgress.phase === 'complete' && 'Scan complete'}
              {scanProgress.phase === 'failed' && (scanProgress.error || 'Scan failed')}
              {scanProgress.phase === 'scanning' && scanProgress.message && (
                <>{scanProgress.message}... {scanProgress.percent}%</>
              )}
              {scanProgress.phase === 'scanning' && !scanProgress.message && scanProgress.currentFarm && (
                <>Scanning {scanProgress.currentFarm}... {scanProgress.percent}%</>
              )}
              {scanProgress.phase === 'scanning' && !scanProgress.message && !scanProgress.currentFarm && (
                <>Starting scan... {scanProgress.percent}%</>
              )}
            </p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={`bg-white border border-gray-200 rounded-xl p-5 ${className}`}>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-[0.06em]">Sentinel View</p>
          <p className="text-sm text-gray-500 mt-1">
            ~1 km area | {satelliteDate}
          </p>
        </div>
        <div className="flex gap-1">
          {['true-color', 'ndvi'].map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setViewType(t)}
              className={`px-3 py-1 text-xs rounded-md font-medium border ${viewType === t ? 'bg-gray-100 text-gray-900 border-gray-300' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'}`}
            >
              {t === 'ndvi' ? 'NDVI' : 'RGB'}
            </button>
          ))}
        </div>
      </div>

      {showDateNote && (
        <p className="text-xs text-amber-600 bg-white border border-gray-200 rounded-lg px-3 py-2 mb-3">
          No clear imagery for {format(parseISO(requestedDate), 'MMM d, yyyy')} — showing {format(parseISO(actualDate), 'MMM d, yyyy')}
        </p>
      )}

      <div className="relative w-full max-w-2xl mx-auto aspect-square bg-gray-100 rounded-lg overflow-hidden">
        {loading && <div className="absolute inset-0 animate-pulse bg-gray-200" />}
        {imageUrl && !error && (
          <img
            src={imageUrl}
            alt="Sentinel imagery"
            className="w-full h-full object-cover"
            onError={() => {
              setImageUrl(null);
              setError('Satellite imagery unavailable for this date');
            }}
          />
        )}
        {error && !loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-sm text-gray-500 p-4 text-center">
            <ImageOff className="w-8 h-8 mb-2 text-gray-400" />
            <p>{error}</p>
            <button
              type="button"
              onClick={() => setViewType((t) => t)}
              className="mt-3 flex items-center gap-1.5 text-blue-600 text-xs"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Retry
            </button>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mt-3 text-xs text-gray-600">
        <span>
          Capture: <span className="font-mono font-medium text-gray-900">{formattedDate}</span>
        </span>
        {imageSource && (
          <span className="text-gray-500">
            Source: {imageSource === 'prefetched-demo' ? 'Sentinel Hub (cached)' : imageSource}
          </span>
        )}
      </div>
    </div>
  );
}