'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { BarChart3 } from 'lucide-react';
import api from '@/lib/api';
import { getToken } from '@/lib/auth';
import StatCard from '@/components/stats/StatCard';
import DataTable from '@/components/common/DataTable';
import { ListPageSkeleton } from '@/components/common/PageSkeleton';

function formatCurrency(amount) {
  return new Intl.NumberFormat('en-PH', {
    style: 'currency',
    currency: 'PHP',
    maximumFractionDigits: 0,
  }).format(amount || 0);
}

export default function PCICAnalyticsPage() {
  const router = useRouter();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    api.get('/claims/pcic/analytics')
      .then((res) => setData(res.data.data))
      .catch((err) => {
        if (err.response?.status === 401) router.push('/login');
      })
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) {
    return <ListPageSkeleton statCount={4} tableRows={6} />;
  }

  const statusColumns = [
    { key: 'status', label: 'Status' },
    { key: 'count', label: 'Count', sortValue: (row) => row.count },
  ];

  const munColumns = [
    { key: 'municipality', label: 'Municipality' },
    { key: 'count', label: 'Claims', sortValue: (row) => row.count },
  ];

  const damageColumns = [
    {
      key: 'damage_type',
      label: 'Damage Type',
      render: (row) => <span className="capitalize">{row.damage_type}</span>,
    },
    { key: 'count', label: 'Count', sortValue: (row) => row.count },
  ];

  const statusRows = Object.entries(data?.by_status || {}).map(([status, count]) => ({
    id: status,
    status,
    count,
  }));

  const hasData = (data?.total_claims || 0) > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Claims Analytics</h1>
        <p className="text-sm text-gray-500 mt-1">PCIC Regional Office | Region V (Bicol)</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard label="Total Claims" value={data?.total_claims || 0} />
        <StatCard label="Approval Rate" value={`${data?.approval_rate || 0}%`} statusVariant="approved" statusLabel="Rate" />
        <StatCard label="Avg Damage" value={`${data?.avg_damage_pct || 0}%`} />
        <StatCard label="Est. Payouts" value={formatCurrency(data?.total_estimated_payout)} />
      </div>

      {!hasData ? (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 text-center">
          <BarChart3 className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-700 font-medium">No analytics data yet</p>
          <p className="text-sm text-gray-500 mt-1">
            Claims data will populate analytics once municipalities file claims.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <DataTable
            title="Claims by Status"
            columns={statusColumns}
            data={statusRows}
            emptyMessage="No status data"
          />
          <DataTable
            title="Claims by Municipality"
            columns={munColumns}
            data={data?.by_municipality || []}
            emptyMessage="No municipality data"
          />
          <DataTable
            title="Claims by Damage Type"
            columns={damageColumns}
            data={data?.by_damage_type || []}
            emptyMessage="No damage type data"
          />
        </div>
      )}
    </div>
  );
}