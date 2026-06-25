'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { Eye, XCircle, Loader2 } from 'lucide-react';
import api from '@/lib/api';
import { getUser, getToken } from '@/lib/auth';
import { useSatelliteDate } from '@/lib/SatelliteDateContext';
import { statusFromNdvi } from '@/lib/ndvi';
import Badge from '@/components/common/Badge';
import HealthDistributionCard from '@/components/dashboard/HealthDistributionCard';
import MunicipalitySummaryCard from '@/components/dashboard/MunicipalitySummaryCard';
import SentinelImagePanel from '@/components/map/SentinelImagePanel';
import Toast from '@/components/common/Toast';
import { formatLongDate } from '@/lib/dateUtils';

const GoogleMapView = dynamic(() => import('@/components/map/GoogleMapView'), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-gray-200 animate-pulse" />,
});

const CARD_BASE = 'bg-white border border-gray-200 rounded-xl';

export default function DashboardPage() {
  const router = useRouter();
  const { satelliteDate } = useSatelliteDate();
  const [farms, setFarms] = useState([]);
  const [stats, setStats] = useState({ healthy_count: 0, watch_count: 0, critical_count: 0 });
  const [municipality, setMunicipality] = useState(null);
  const [ndviSource, setNdviSource] = useState('unavailable');
  const [selectedFarm, setSelectedFarm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [ndviRefreshing, setNdviRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [ndviTileUrl, setNdviTileUrl] = useState(null);
  const [scanToast, setScanToast] = useState(null);
  const [dateLoading, setDateLoading] = useState(false);
  const [isDateScanned, setIsDateScanned] = useState(false);
  const initialLoadDone = useRef(false);
  const tileCacheRef = useRef({ date: null, lat: null, lng: null, url: null });
  const municipalityIdRef = useRef(null);

  const lat = municipality?.latitude ?? 13.6192;
  const lng = municipality?.longitude ?? 123.1814;

  const applyFarmData = useCallback((data) => {
    setFarms(data.farms || []);
    setStats(data.stats || { healthy_count: 0, watch_count: 0, critical_count: 0 });
    setMunicipality(data.municipality);
    setNdviSource(data.ndvi_source || 'unavailable');
    setIsDateScanned(Boolean(data.is_date_scanned));
  }, []);

  const fetchFarmsFast = useCallback(async (munId, date) => {
    const params = date ? { satellite_date: date } : {};
    const response = await api.get(`/farms/municipality/${munId}`, { params, skipCache: true });
    applyFarmData(response.data.data);
    return response.data.data;
  }, [applyFarmData]);

  const fetchInitialData = useCallback(async () => {
    const token = getToken();
    const user = getUser();
    if (!token || !user) {
      router.push('/login');
      return;
    }
    if (user.role !== 'MAO' && user.role !== 'ADMIN') {
      setLoading(false);
      router.replace('/farms');
      return;
    }

    municipalityIdRef.current = user.municipality_id;
    setError(null);
    if (!initialLoadDone.current) setLoading(true);

    try {
      await fetchFarmsFast(user.municipality_id, satelliteDate);
      initialLoadDone.current = true;
    } catch (err) {
      if (err.response?.status === 401) router.push('/login');
      else setError('Failed to load farm data');
    } finally {
      setLoading(false);
    }
  }, [router, fetchFarmsFast, satelliteDate]);

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  useEffect(() => {
    if (!initialLoadDone.current || !municipalityIdRef.current || !satelliteDate) return;

    let cancelled = false;
    setDateLoading(true);
    setFarms((prev) => prev.map((farm) => ({
      ...farm,
      status: 'UNKNOWN',
      health_status: 'unknown',
      latest_ndvi: null,
    })));

    (async () => {
      try {
        const data = await fetchFarmsFast(municipalityIdRef.current, satelliteDate);
        if (!cancelled && data) {
          applyFarmData(data);
        }
      } catch {
        if (!cancelled) setError('Failed to load farm data for selected date');
      } finally {
        if (!cancelled) setDateLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [satelliteDate, fetchFarmsFast, applyFarmData]);

  useEffect(() => {
    if (!initialLoadDone.current || !satelliteDate) return;

    const cache = tileCacheRef.current;
    if (cache.date === satelliteDate && cache.lat === lat && cache.lng === lng && cache.url) {
      setNdviTileUrl(cache.url);
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        const tileRes = await api.get('/satellite/ndvi-tiles', {
          params: { latitude: lat, longitude: lng, date: satelliteDate },
          skipCache: true,
        });
        if (cancelled) return;
        const url = tileRes.data.data.tile_url;
        tileCacheRef.current = { date: satelliteDate, lat, lng, url };
        setNdviTileUrl(url);
      } catch {
        if (!cancelled) setNdviTileUrl(null);
      }
    })();

    return () => { cancelled = true; };
  }, [satelliteDate, lat, lng]);

  useEffect(() => {
    if (!initialLoadDone.current || !municipalityIdRef.current) return;

    const munId = municipalityIdRef.current;

    const pollNdviStatus = async () => {
      try {
        const statusRes = await api.get(`/farms/municipality/${munId}/ndvi-status`, { skipCache: true });
        const { status } = statusRes.data.data || {};
        if (status === 'updating') setNdviRefreshing(true);
        if (status === 'updated') {
          setNdviRefreshing(false);
          await fetchFarmsFast(munId, satelliteDate);
        }
        if (status === 'idle') setNdviRefreshing(false);
      } catch {
        /* ignore polling errors */
      }
    };

    pollNdviStatus();
    const interval = setInterval(pollNdviStatus, 15000);
    return () => clearInterval(interval);
  }, [fetchFarmsFast, satelliteDate]);

  const applyNdviResults = useCallback((records, scanDate) => {
    if (!records?.length) return;
    setFarms((prev) => {
      const updated = prev.map((farm) => {
        const rec = records.find((r) => r.parcel_id === farm.id);
        if (!rec) return farm;
        const ndvi = rec.ndvi_value;
        const status = statusFromNdvi(ndvi) || farm.status;
        return {
          ...farm,
          latest_ndvi: ndvi,
          ndvi_date: scanDate,
          status,
        };
      });
      const nextStats = { healthy_count: 0, watch_count: 0, critical_count: 0 };
      updated.forEach((f) => {
        if (f.status === 'HEALTHY') nextStats.healthy_count += 1;
        else if (f.status === 'WATCH' || f.status === 'FAIR') nextStats.watch_count += 1;
        else if (f.status === 'CRITICAL') nextStats.critical_count += 1;
      });
      setStats(nextStats);
      setSelectedFarm((sel) => {
        if (!sel) return sel;
        const match = updated.find((f) => f.id === sel.id);
        return match || sel;
      });
      return updated;
    });
  }, []);

  const handleScanComplete = (result) => {
    if (result?.error) {
      setScanToast({
        type: 'error',
        message: result.message || 'NDVI scan failed. Please check your Earth Engine credentials.',
      });
      return;
    }
    const scanned = typeof result.scanned_farms === 'number'
      ? result.scanned_farms
      : (result.scanned_farms?.length ?? result.ndvi_records?.length ?? 0);
    const failed = typeof result.failed_farms === 'number'
      ? result.failed_farms
      : (result.failed_farm_details?.length ?? 0);
    const total = scanned + failed;
    const dateLabel = formatLongDate(result.scan_date || satelliteDate);

    if (scanned === 0) {
      setScanToast({ type: 'error', message: 'NDVI scan failed. No farms could be processed.' });
      return;
    }

    if (municipalityIdRef.current) {
      fetchFarmsFast(municipalityIdRef.current, satelliteDate);
    } else {
      applyNdviResults(result.ndvi_records || result.results, result.scan_date || satelliteDate);
    }

    const message = failed > 0
      ? `Scan complete. ${scanned} of ${total} farms scanned for ${dateLabel}.`
      : `NDVI scan complete. ${scanned} farms scanned for ${dateLabel}.`;
    setScanToast({ type: 'success', message });
  };

  if (loading) {
    return (
      <div className="relative h-full w-full">
        <div className="absolute inset-0 bg-gray-200 animate-pulse" />
      </div>
    );
  }

  const isLiveNdvi = ndviSource === 'earth-engine' || ndviSource === 'live' || ndviRefreshing;

  return (
    <div className="relative h-full w-full">
      {scanToast && (
        <Toast
          message={scanToast.message}
          type={scanToast.type}
          position="top-right"
          onClose={() => setScanToast(null)}
        />
      )}
      {dateLoading && (
        <div className="absolute inset-0 z-20 pointer-events-none bg-gray-300/10 animate-pulse" />
      )}

      <div className="absolute inset-0">
        <GoogleMapView
          farms={farms}
          center={[lat, lng]}
          zoom={15}
          selectedFarm={selectedFarm}
          onFarmClick={setSelectedFarm}
          ndviTileUrl={ndviTileUrl}
          dateLoading={dateLoading}
          hideDateOverlay
          hideLayerSwitcher
          hideLegend
          hideZoomControls
        />
      </div>

      {ndviRefreshing && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-xs text-gray-600 shadow-sm pointer-events-none">
          <Loader2 className="w-3.5 h-3.5 animate-spin text-green-600" />
          Updating live satellite NDVI...
        </div>
      )}

      {error && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-40 bg-white border border-gray-200 text-red-600 text-sm px-4 py-2 rounded-lg pointer-events-auto">
          {error}
          <button type="button" onClick={fetchInitialData} className="ml-2 underline">Try Again</button>
        </div>
      )}

      <div className="absolute inset-0 z-30 pointer-events-none">
        <div className="absolute top-6 left-6 pointer-events-auto hidden md:block">
          <MunicipalitySummaryCard farms={farms} stats={stats} municipality={municipality} />
        </div>

        <div className="absolute top-6 right-6 pointer-events-auto hidden md:block">
            <SentinelImagePanel
              latitude={lat}
              longitude={lng}
              compact
              isLive={isLiveNdvi}
              isDateScanned={isDateScanned}
              onScanComplete={handleScanComplete}
            />
        </div>

        <div className="absolute bottom-6 left-6 pointer-events-auto hidden md:block">
          <HealthDistributionCard
            stats={stats}
            totalFarms={farms.length}
            farms={farms}
            satelliteDate={satelliteDate}
          />
        </div>

        <div className={`pointer-events-auto transition-all duration-300 absolute top-20 right-6 w-[320px] max-w-[calc(100vw-2rem)] ${selectedFarm ? 'translate-x-0 opacity-100' : 'translate-x-[360px] opacity-0 pointer-events-none'}`}>
          {selectedFarm && (
            <div className={`${CARD_BASE} p-4`}>
              <div className="flex items-start justify-between gap-2 mb-3">
                <div className="min-w-0">
                  <h3 className="text-[15px] font-semibold text-gray-900 truncate">{selectedFarm.farmer_name}</h3>
                  <p className="text-[13px] text-gray-500 font-mono truncate mt-0.5">{selectedFarm.rsbsa_number}</p>
                </div>
                <button type="button" onClick={() => setSelectedFarm(null)} className="p-1 hover:bg-gray-100 rounded-md shrink-0" aria-label="Close">
                  <XCircle className="w-4 h-4 text-gray-400" />
                </button>
              </div>
              <div className="space-y-2 mb-3">
                <div className="flex justify-between items-baseline gap-2">
                  <span className="text-[13px] text-gray-500">NDVI</span>
                  <span className="text-lg font-semibold text-gray-900 font-mono">
                    {selectedFarm.status === 'UNKNOWN'
                      ? 'No data for this date'
                      : (selectedFarm.latest_ndvi?.toFixed(3) || (ndviRefreshing ? '...' : 'N/A'))}
                  </span>
                </div>
                <div className="flex justify-between items-center gap-2">
                  <span className="text-[13px] text-gray-500">Status</span>
                  <Badge variant={selectedFarm.status.toLowerCase()} size="sm">{selectedFarm.status}</Badge>
                </div>
              </div>
              <button type="button" onClick={() => router.push(`/farms/${selectedFarm.id}`)} className="w-full btn-primary h-9 text-sm">
                <Eye className="w-3.5 h-3.5" /> View Details
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}