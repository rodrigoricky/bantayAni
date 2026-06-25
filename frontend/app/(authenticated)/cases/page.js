'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { format, parseISO } from 'date-fns';
import { RefreshCw, FileText } from 'lucide-react';
import api from '@/lib/api';
import { getToken, getUser } from '@/lib/auth';
import { ClaimStatusBadge } from '@/components/common/Badge';
import DataTable from '@/components/common/DataTable';
import { ListPageSkeleton } from '@/components/common/PageSkeleton';
import StatCard from '@/components/stats/StatCard';

function damageColor(pct) {
  if (pct == null) return 'text-gray-500';
  if (pct >= 70) return 'text-red-600';
  if (pct >= 30) return 'text-amber-600';
  return 'text-gray-700';
}

export default function CaseRecordsPage() {
  const router = useRouter();
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchClaims = useCallback(async () => {
    const user = getUser();
    if (!user?.municipality_id) return;
    try {
      const response = await api.get('/claims', {
        params: { municipality_id: user.municipality_id, limit: 200 },
      });
      setClaims(response.data.data.claims);
    } catch (err) {
      if (err.response?.status === 401) router.push('/login');
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    fetchClaims();
  }, [router, fetchClaims]);

  const stats = useMemo(() => ({
    total: claims.length,
    approved: claims.filter((c) => c.status === 'APPROVED').length,
    pending: claims.filter((c) => ['PENDING', 'SUBMITTED'].includes(c.status)).length,
    flagged: claims.filter((c) => c.status === 'FLAGGED').length,
  }), [claims]);

  const statusTabs = useMemo(() => [
    { value: 'ALL', label: 'All', count: claims.length },
    { value: 'PENDING', label: 'Pending', count: claims.filter((c) => c.status === 'PENDING').length },
    { value: 'SUBMITTED', label: 'Submitted', count: claims.filter((c) => c.status === 'SUBMITTED').length },
    { value: 'APPROVED', label: 'Approved', count: stats.approved },
    { value: 'FLAGGED', label: 'Flagged', count: stats.flagged },
    { value: 'REJECTED', label: 'Rejected', count: claims.filter((c) => c.status === 'REJECTED').length },
  ], [claims, stats]);

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    try { return format(parseISO(dateStr), 'MMM d, yyyy'); } catch { return dateStr; }
  };

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
      key: 'farmer_name',
      label: 'Farmer',
      render: (row) => (
        <div>
          <p className="text-sm font-medium text-gray-900">{row.farmer_name}</p>
          <p className="text-xs text-gray-400 font-mono">{row.rsbsa_number}</p>
        </div>
      ),
    },
    {
      key: 'damage_type',
      label: 'Damage Type',
      render: (row) => <span className="capitalize">{row.damage_type || 'N/A'}</span>,
    },
    {
      key: 'damage_percentage',
      label: 'Damage %',
      sortValue: (row) => row.damage_percentage ?? -1,
      render: (row) => (
        <span className={`font-medium ${damageColor(row.damage_percentage)}`}>
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

  if (loading) {
    return <ListPageSkeleton statCount={4} tableRows={8} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="page-title">Case Records</h1>
          <p className="text-sm text-gray-500 mt-1">All insurance claims filed in your municipality</p>
        </div>
        <button type="button" onClick={fetchClaims} className="btn-secondary">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard label="Total Cases" value={stats.total} />
        <StatCard label="Approved" value={stats.approved} statusVariant="approved" statusLabel="Approved" />
        <StatCard label="Pending" value={stats.pending} statusVariant="pending" statusLabel="Pending" />
        <StatCard label="Flagged" value={stats.flagged} statusVariant="flagged" statusLabel="Flagged" />
      </div>

      {claims.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 text-center">
          <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-700 font-medium">No case records yet</p>
          <p className="text-sm text-gray-500 mt-1">
            Claims filed through verification will appear here.
          </p>
        </div>
      ) : (
        <DataTable
          title="Municipality Case Records"
          columns={columns}
          data={claims}
          statusTabs={statusTabs}
          statusKey="status"
          emptyMessage="No cases match the selected filter"
        />
      )}
    </div>
  );
}