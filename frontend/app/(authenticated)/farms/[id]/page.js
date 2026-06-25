'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import {
  ArrowLeft, FileText, Satellite, BarChart3, Wheat, Calendar,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Dot,
} from 'recharts';
import api from '@/lib/api';
import { getToken } from '@/lib/auth';
import { getNDVIContext } from '@/lib/constants';
import { getStatusColors } from '@/lib/ndvi';
import { NDVIIcon } from '@/lib/ndviIcons';
import { getChartYDomain } from '@/lib/chartUtils';
import { ClaimStatusBadge } from '@/components/common/Badge';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import SentinelImagePanel from '@/components/map/SentinelImagePanel';
import InsuranceIndicator from '@/components/common/InsuranceIndicator';

const GoogleMapView = dynamic(() => import('@/components/map/GoogleMapView'), {
  ssr: false,
  loading: () => (
    <div className="h-full flex items-center justify-center bg-gray-50">
      <LoadingSpinner size="md" text="Loading map..." />
    </div>
  ),
});

function statusTextClass(status) {
  return getStatusColors(status).text;
}

export default function FarmDetailPage() {
  const [farmData, setFarmData] = useState(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const params = useParams();

  useEffect(() => {
    const fetchFarmDetail = async () => {
      if (!getToken()) {
        router.push('/login');
        return;
      }
      try {
        const response = await api.get(`/farms/${params.id}`);
        setFarmData(response.data.data);
      } catch {
        setFarmData(null);
      } finally {
        setLoading(false);
      }
    };

    if (params.id) fetchFarmDetail();
  }, [params.id, router]);

  if (loading) {
    return <LoadingSpinner size="lg" text="Loading farm details..." className="py-20" />;
  }

  if (!farmData?.farm) {
    return (
      <div className="text-center py-12">
        <p className="text-sm text-gray-500">Farm not found</p>
        <button
          type="button"
          onClick={() => router.push('/farms')}
          className="mt-4 text-sm text-blue-600 hover:underline"
        >
          Back to Farm Parcels
        </button>
      </div>
    );
  }

  const { farm, ndvi_history = [], recent_claims = [] } = farmData;
  const ndviCtx = getNDVIContext(farm.latest_ndvi);
  const chartData = [...ndvi_history]
    .sort((a, b) => new Date(a.date) - new Date(b.date))
    .map((h) => ({
      date: h.date.slice(5),
      ndvi: h.ndvi,
      fullDate: h.date,
    }));
  const yDomain = getChartYDomain(chartData, 'ndvi');

  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={() => router.push('/farms')}
        className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-gray-900"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Farm Parcels
      </button>

      {/* Farmer meta strip */}
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-6">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-[0.06em]">Farmer</p>
            <h1 className="text-2xl font-semibold text-gray-900 mt-1">
              {farm.farmer_name}
              <InsuranceIndicator isInsured={farm.is_insured ?? farm.insured} />
            </h1>
            <p className="text-sm text-gray-500 font-mono mt-1">{farm.rsbsa_number}</p>
            <p className="text-sm text-gray-500 mt-1">
              {farm.municipality?.name}, {farm.municipality?.province}
            </p>
          </div>
          <div className="md:text-right">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-[0.06em]">NDVI</p>
            <p className="text-2xl font-semibold text-gray-900 font-mono mt-1">
              {farm.latest_ndvi?.toFixed(3) ?? 'N/A'}
            </p>
            <p className={`text-sm font-medium mt-1 flex items-center justify-end gap-1.5 ${ndviCtx.colorClass}`}>
              <NDVIIcon name={ndviCtx.icon} />
              {ndviCtx.label}
            </p>
            <p className={`text-sm font-medium mt-2 ${statusTextClass(farm.status)}`}>
              {farm.status || 'WATCH'}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-6 border-t border-gray-200 text-sm">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-[0.06em]">Parcel ID</p>
            <p className="font-mono font-medium text-blue-600 mt-1">{farm.id}</p>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-[0.06em]">Crop</p>
            <p className="font-medium text-gray-900 mt-1 flex items-center gap-1">
              <Wheat className="w-3.5 h-3.5 text-gray-500" />
              {farm.crop_type}
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-[0.06em]">Area</p>
            <p className="font-medium text-gray-900 mt-1">{farm.area_hectares} hectares</p>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-[0.06em]">Harvest</p>
            <p className="font-medium text-gray-900 mt-1 flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-gray-500" />
              {farm.expected_harvest_date || 'N/A'}
            </p>
          </div>
        </div>
      </div>

      {/* Action row */}
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => router.push(`/claims?rsbsa=${encodeURIComponent(farm.rsbsa_number)}`)}
          className="btn-primary"
        >
          <Satellite className="w-4 h-4" />
          Verify Claim
        </button>
        <button
          type="button"
          onClick={() => router.push('/reports')}
          className="btn-action-secondary"
        >
          <BarChart3 className="w-4 h-4" />
          View Reports
        </button>
        <button
          type="button"
          onClick={() => router.push('/farms')}
          className="btn-action-secondary"
        >
          <FileText className="w-4 h-4" />
          All Parcels
        </button>
      </div>

      {/* Map + NDVI panel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-200">
            <h2 className="section-title">Farm Location</h2>
          </div>
          <div className="min-h-[480px] h-[480px]">
            <GoogleMapView
              farms={[farm]}
              singleFarm={farm}
              highlightFarm={farm}
              center={[farm.latitude, farm.longitude]}
              zoom={16}
              hideLayerSwitcher
            />
          </div>
        </div>
        <SentinelImagePanel latitude={farm.latitude} longitude={farm.longitude} />
      </div>

      {/* NDVI history chart */}
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <h2 className="section-title mb-4">NDVI History</h2>
        {chartData.length === 0 ? (
          <p className="text-sm text-gray-400 py-8 text-center">No NDVI history data available</p>
        ) : chartData.length === 1 ? (
          <div className="h-64 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis domain={yDomain} tick={{ fontSize: 11 }} tickFormatter={(v) => v.toFixed(2)} />
                <Tooltip
                  formatter={(v) => [Number(v).toFixed(3), 'NDVI']}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ''}
                />
                <Line type="monotone" dataKey="ndvi" stroke="#4f46e5" strokeWidth={0} dot={<Dot r={6} fill="#4f46e5" />} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis domain={yDomain} tick={{ fontSize: 11 }} tickFormatter={(v) => v.toFixed(2)} />
                <Tooltip
                  formatter={(v) => [Number(v).toFixed(3), 'NDVI']}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ''}
                />
                <Line
                  type="monotone"
                  dataKey="ndvi"
                  stroke="#4f46e5"
                  strokeWidth={2}
                  dot={{ fill: '#4f46e5', r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Recent claims */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-200">
          <h2 className="section-title">Recent Claims</h2>
        </div>
        {recent_claims.length > 0 ? (
          <div>
            {recent_claims.map((claim) => (
              <div key={claim.claim_number} className="px-5 py-4 flex items-center justify-between border-b border-gray-200 last:border-b-0 hover:bg-gray-50">
                <div>
                  <p className="text-sm font-medium text-blue-600 font-mono">{claim.claim_number}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {claim.damage_type} | {claim.disaster_date} | {claim.damage_percentage?.toFixed(1)}% damage
                  </p>
                </div>
                <ClaimStatusBadge status={claim.status} size="sm" />
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400 px-5 py-8 text-center">No claims filed for this parcel yet</p>
        )}
      </div>
    </div>
  );
}