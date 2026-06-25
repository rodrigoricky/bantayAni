'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { MapPin } from 'lucide-react';
import api from '@/lib/api';
import { getToken } from '@/lib/auth';
import { ClaimStatusBadge } from '@/components/common/Badge';
import { PageHeaderSkeleton, MapPageSkeleton } from '@/components/common/PageSkeleton';

const MapView = dynamic(() => import('@/components/map/MapView'), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-gray-200 animate-pulse rounded-2xl" />,
});

export default function PCICMapPage() {
  const router = useRouter();
  const [claims, setClaims] = useState([]);
  const [farms, setFarms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedClaim, setSelectedClaim] = useState(null);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    Promise.all([
      api.get('/claims', { params: { limit: 200 } }),
      api.get('/farms/municipality/camarines-naga'),
    ])
      .then(([claimsRes, farmsRes]) => {
        setClaims(claimsRes.data.data.claims);
        setFarms(farmsRes.data.data.farms);
      })
      .catch((err) => {
        if (err.response?.status === 401) router.push('/login');
      })
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeaderSkeleton />
        <MapPageSkeleton />
      </div>
    );
  }

  const center = farms.length
    ? [farms[0].latitude, farms[0].longitude]
    : [13.6192, 123.1814];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Claims Map View</h1>
        <p className="text-sm text-gray-500 mt-1">PCIC Regional Office | Region V (Bicol)</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="h-[480px]">
            <MapView
              farms={farms}
              center={center}
              zoom={13}
              selectedFarm={selectedClaim}
              onFarmClick={setSelectedClaim}
              hideDateOverlay
            />
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h3 className="section-title">Claims by Location</h3>
            <p className="text-xs text-gray-400 mt-0.5">{claims.length} claims in region</p>
          </div>
          <div className="max-h-[420px] overflow-y-auto">
            {claims.length === 0 ? (
              <div className="p-8 text-center">
                <MapPin className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                <p className="text-sm text-gray-500">No claims to display on map</p>
              </div>
            ) : (
              claims.map((claim) => (
                <button
                  key={claim.id}
                  type="button"
                  onClick={() => router.push(`/case/${claim.id}`)}
                  className="w-full text-left px-5 py-3 border-b border-gray-100 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-mono text-blue-600">{claim.claim_number}</span>
                    <ClaimStatusBadge status={claim.status} size="sm" />
                  </div>
                  <p className="text-sm font-medium text-gray-900 mt-1">{claim.farmer_name}</p>
                  <p className="text-xs text-gray-400">{claim.municipality}</p>
                </button>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}