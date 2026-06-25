'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { format, parseISO } from 'date-fns';
import { AlertTriangle } from 'lucide-react';
import api from '@/lib/api';
import { getToken } from '@/lib/auth';
import { ClaimStatusBadge } from '@/components/common/Badge';
import DataTable from '@/components/common/DataTable';
import { ListPageSkeleton } from '@/components/common/PageSkeleton';
import StatCard from '@/components/stats/StatCard';

export default function DamageReportsPage() {
  const router = useRouter();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    api.get('/claims/regional/summary')
      .then((res) => setData(res.data.data))
      .catch((err) => {
        if (err.response?.status === 401) router.push('/login');
      })
      .finally(() => setLoading(false));
  }, [router]);

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    try { return format(parseISO(dateStr), 'MMM d, yyyy'); } catch { return dateStr; }
  };

  const claims = data?.recent_claims || [];
  const totals = data?.totals || {};

  const statusTabs = [
    { value: 'ALL', label: 'All', count: claims.length },
    { value: 'PENDING', label: 'Pending', count: claims.filter((c) => c.status === 'PENDING').length },
    { value: 'APPROVED', label: 'Approved', count: claims.filter((c) => c.status === 'APPROVED').length },
    { value: 'FLAGGED', label: 'Flagged', count: claims.filter((c) => c.status === 'FLAGGED').length },
    { value: 'REJECTED', label: 'Rejected', count: claims.filter((c) => c.status === 'REJECTED').length },
  ];

  const columns = [
    {
      key: 'claim_number',
      label: 'Claim #',
      render: (row) => (
        <button
          type="button"
          onClick={() => router.push(`/case/${row.id}`)}
          className="text-sm font-medium text-blue-600 hover:text-blue-700 font-mono"
        >
          {row.claim_number}
        </button>
      ),
    },
    {
      key: 'municipality',
      label: 'Municipality',
    },
    {
      key: 'farmer_name',
      label: 'Farmer',
    },
    {
      key: 'damage_type',
      label: 'Type',
      render: (row) => <span className="capitalize">{row.damage_type || 'N/A'}</span>,
    },
    {
      key: 'damage_percentage',
      label: 'Damage %',
      sortValue: (row) => row.damage_percentage ?? -1,
      render: (row) => (
        <span className="font-medium text-gray-900">
          {row.damage_percentage != null ? `${row.damage_percentage.toFixed(1)}%` : 'N/A'}
        </span>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      render: (row) => <ClaimStatusBadge status={row.status} size="sm" />,
    },
    {
      key: 'filed_date',
      label: 'Filed',
      sortValue: (row) => row.filed_date || '',
      render: (row) => <span className="text-gray-500">{formatDate(row.filed_date)}</span>,
    },
  ];

  const munColumns = [
    { key: 'municipality', label: 'Municipality' },
    {
      key: 'claim_count',
      label: 'Claims',
      sortValue: (row) => row.claim_count,
    },
    {
      key: 'avg_damage_pct',
      label: 'Avg Damage %',
      sortValue: (row) => row.avg_damage_pct,
      render: (row) => <span>{row.avg_damage_pct}%</span>,
    },
    {
      key: 'approved',
      label: 'Approved',
      sortValue: (row) => row.approved || 0,
    },
    {
      key: 'pending',
      label: 'Pending',
      sortValue: (row) => row.pending || 0,
    },
    {
      key: 'flagged',
      label: 'Flagged',
      sortValue: (row) => row.flagged || 0,
    },
  ];

  if (loading) {
    return <ListPageSkeleton statCount={4} tableRows={8} />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Damage Reports</h1>
        <p className="text-sm text-gray-500 mt-1">Regional insurance claims and damage assessments</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard label="Total Claims" value={totals.total_claims || 0} />
        <StatCard label="Pending" value={totals.pending || 0} statusVariant="pending" statusLabel="Pending" />
        <StatCard label="Approved" value={totals.approved || 0} statusVariant="approved" statusLabel="Approved" />
        <StatCard label="Avg Damage" value={`${totals.avg_damage_pct || 0}%`} />
      </div>

      {claims.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 text-center">
          <AlertTriangle className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-700 font-medium">No damage reports yet</p>
          <p className="text-sm text-gray-500 mt-1">
            Claims filed by municipalities will appear here.
          </p>
        </div>
      ) : (
        <>
          <DataTable
            title="Recent Damage Reports"
            columns={columns}
            data={claims}
            statusTabs={statusTabs}
            statusKey="status"
          />
          {(data?.municipalities || []).length > 0 && (
            <DataTable
              title="Damage by Municipality"
              columns={munColumns}
              data={data.municipalities}
              emptyMessage="No municipality breakdown available"
            />
          )}
        </>
      )}
    </div>
  );
}