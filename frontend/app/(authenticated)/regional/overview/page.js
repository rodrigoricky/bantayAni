'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { AlertTriangle, TrendingDown } from 'lucide-react';
import api from '@/lib/api';
import { getToken, getUser } from '@/lib/auth';
import StatCard from '@/components/stats/StatCard';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import Badge from '@/components/common/Badge';

const MapView = dynamic(() => import('@/components/map/MapView'), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-gray-200 animate-pulse rounded-2xl" />,
});

export default function RegionalOverview() {
  const router = useRouter();
  const [municipalities, setMunicipalities] = useState([]);
  const [farms, setFarms] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    fetchRegionalData();
  }, [router]);

  const fetchRegionalData = async () => {
    const user = getUser();
    const munList = user?.role_data?.municipalities || [];

    try {
      const [healthRes, ...farmResults] = await Promise.all([
        api.get('/farms/regional/health'),
        ...munList.map((mun) =>
          api.get(`/farms/municipality/${mun.id}`).catch(() => null)
        ),
      ]);

      setMunicipalities(healthRes.data.data.municipalities || []);

      const allFarms = farmResults
        .filter(Boolean)
        .flatMap((res) => res.data.data.farms || []);
      setFarms(allFarms);
    } catch (error) {
      console.error('Error fetching regional data:', error);
    } finally {
      setLoading(false);
    }
  };

  const totals = useMemo(() => municipalities.reduce(
    (acc, m) => ({
      farms: acc.farms + m.total_farms,
      healthy: acc.healthy + (m.stats?.healthy_count || 0),
      watch: acc.watch + (m.stats?.watch_count || 0),
      critical: acc.critical + (m.stats?.critical_count || 0),
    }),
    { farms: 0, healthy: 0, watch: 0, critical: 0 }
  ), [municipalities]);

  const ranked = useMemo(() => (
    [...municipalities].sort((a, b) => a.health_score - b.health_score)
  ), [municipalities]);

  const mapCenter = farms.length
    ? [farms.reduce((s, f) => s + f.latitude, 0) / farms.length,
      farms.reduce((s, f) => s + f.longitude, 0) / farms.length]
    : [13.6192, 123.1814];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Regional Overview</h1>
        <p className="text-sm text-gray-500 mt-1">DA Regional Field Office | Region V (Bicol)</p>
      </div>

      {loading ? (
        <LoadingSpinner size="lg" text="Loading regional data..." className="py-20" />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard label="Total Farms" value={totals.farms} />
            <StatCard label="Healthy" value={totals.healthy} statusVariant="healthy" statusLabel="Healthy" />
            <StatCard label="Watch" value={totals.watch} statusVariant="watch" statusLabel="Watch" />
            <StatCard label="Critical" value={totals.critical} statusVariant="critical" statusLabel="Critical" />
          </div>

          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h3 className="section-title">Regional Farm Map</h3>
              <p className="text-xs text-gray-400 mt-0.5">{farms.length} farms across {municipalities.length} municipalities</p>
            </div>
            <div className="h-[400px]">
              <MapView
                farms={farms}
                center={mapCenter}
                zoom={11}
                hideDateOverlay
                hideLayerSwitcher
              />
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 bg-gray-50">
              <h3 className="section-title">Municipality Rankings</h3>
              <p className="text-xs text-gray-400 mt-0.5">Sorted by health score (lowest first — needs attention)</p>
            </div>
            <div className="divide-y divide-gray-100">
              {ranked.map((mun, idx) => {
                const total = mun.total_farms || 1;
                const criticalPct = mun.critical_pct || 0;

                return (
                  <div key={mun.id} className="px-5 py-4 flex items-center gap-4 hover:bg-gray-50 transition-colors">
                    <span className="text-sm font-semibold text-gray-400 w-6">{idx + 1}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-semibold text-gray-900">{mun.name}</h4>
                        {criticalPct > 20 && mun.total_farms > 0 && (
                          <span className="status-pill text-red-600">
                            <AlertTriangle className="w-3 h-3 mr-1" />
                            Alert
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {mun.total_farms} farms · {mun.total_area_hectares || 0} ha
                      </p>
                    </div>
                    <div className="hidden sm:flex items-center gap-4 text-xs">
                      <span className="text-green-600">{mun.stats?.healthy_count || 0} healthy</span>
                      <span className="text-amber-600">{mun.stats?.watch_count || 0} watch</span>
                      <span className="text-red-600">{mun.stats?.critical_count || 0} critical</span>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold text-gray-900">{mun.health_score}%</p>
                      <p className="text-xs text-gray-400">health score</p>
                    </div>
                    {mun.health_score < 70 && (
                      <TrendingDown className="w-4 h-4 text-red-500 flex-shrink-0" />
                    )}
                    {mun.total_farms === 0 && (
                      <Badge variant="watch" size="sm">No farms</Badge>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}