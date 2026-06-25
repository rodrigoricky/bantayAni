'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Activity } from 'lucide-react';
import api from '@/lib/api';
import { getToken } from '@/lib/auth';
import StatCard from '@/components/stats/StatCard';
import DataTable from '@/components/common/DataTable';
import { ListPageSkeleton } from '@/components/common/PageSkeleton';
import Badge from '@/components/common/Badge';

export default function MunicipalityHealthPage() {
  const router = useRouter();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    api.get('/farms/regional/health')
      .then((res) => setData(res.data.data))
      .catch((err) => {
        if (err.response?.status === 401) router.push('/login');
      })
      .finally(() => setLoading(false));
  }, [router]);

  const columns = [
    {
      key: 'name',
      label: 'Municipality',
      render: (row) => (
        <div>
          <p className="text-sm font-medium text-gray-900">{row.name}</p>
          <p className="text-xs text-gray-400">{row.province}</p>
        </div>
      ),
    },
    {
      key: 'total_farms',
      label: 'Farms',
      sortValue: (row) => row.total_farms,
    },
    {
      key: 'healthy_count',
      label: 'Healthy',
      sortValue: (row) => row.stats?.healthy_count ?? 0,
      render: (row) => (
        <span className="text-green-600 font-medium">{row.stats?.healthy_count ?? 0}</span>
      ),
    },
    {
      key: 'watch_count',
      label: 'Watch',
      sortValue: (row) => row.stats?.watch_count ?? 0,
      render: (row) => (
        <span className="text-amber-600 font-medium">{row.stats?.watch_count ?? 0}</span>
      ),
    },
    {
      key: 'critical_count',
      label: 'Critical',
      sortValue: (row) => row.stats?.critical_count ?? 0,
      render: (row) => (
        <span className="text-red-600 font-medium">{row.stats?.critical_count ?? 0}</span>
      ),
    },
    {
      key: 'health_score',
      label: 'Health Score',
      sortValue: (row) => row.health_score,
      render: (row) => (
        <span className="font-medium text-gray-900">{row.health_score}%</span>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      sortable: false,
      render: (row) => {
        if (row.critical_pct > 20) return <Badge variant="critical" size="sm">Alert</Badge>;
        if (row.critical_pct > 10) return <Badge variant="watch" size="sm">Watch</Badge>;
        return <Badge variant="healthy" size="sm">Stable</Badge>;
      },
    },
  ];

  if (loading) {
    return <ListPageSkeleton statCount={4} tableRows={8} />;
  }

  const totals = data?.totals || {};
  const municipalities = data?.municipalities || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Municipality Health</h1>
        <p className="text-sm text-gray-500 mt-1">Region V (Bicol) - crop health by municipality</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard label="Total Farms" value={totals.total_farms || 0} />
        <StatCard label="Healthy" value={totals.healthy_count || 0} statusVariant="healthy" statusLabel="Healthy" />
        <StatCard label="Watch" value={totals.watch_count || 0} statusVariant="watch" statusLabel="Watch" />
        <StatCard label="Critical" value={totals.critical_count || 0} statusVariant="critical" statusLabel="Critical" />
      </div>

      {municipalities.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 text-center">
          <Activity className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-700 font-medium">No municipality data available</p>
        </div>
      ) : (
        <DataTable
          title="Municipality Health Rankings"
          columns={columns}
          data={municipalities}
          emptyMessage="No municipality health data"
        />
      )}
    </div>
  );
}