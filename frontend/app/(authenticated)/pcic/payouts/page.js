'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { format, parseISO } from 'date-fns';
import { Banknote, AlertTriangle } from 'lucide-react';
import api from '@/lib/api';
import { getToken } from '@/lib/auth';
import { ClaimStatusBadge } from '@/components/common/Badge';
import DataTable from '@/components/common/DataTable';
import { PageHeaderSkeleton, StatCardsSkeleton, TableSkeleton } from '@/components/common/PageSkeleton';
import StatCard from '@/components/stats/StatCard';

function formatCurrency(amount) {
  return new Intl.NumberFormat('en-PH', {
    style: 'currency',
    currency: 'PHP',
    maximumFractionDigits: 0,
  }).format(amount || 0);
}

export default function PCICPayoutsPage() {
  const router = useRouter();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    api.get('/claims/pcic/payouts')
      .then((res) => setData(res.data.data))
      .catch((err) => {
        if (err.response?.status === 401) router.push('/login');
      })
      .finally(() => setLoading(false));
  }, [router]);

  const payouts = data?.payouts || [];
  const summary = data?.summary || {};

  const statusTabs = [
    { value: 'ALL', label: 'All', count: payouts.length },
    { value: 'PAID', label: 'Paid', count: payouts.filter((p) => p.payout_status === 'PAID').length },
    { value: 'PENDING', label: 'Pending', count: payouts.filter((p) => p.payout_status === 'PENDING').length },
  ];

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
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
    },
    {
      key: 'municipality',
      label: 'Municipality',
    },
    {
      key: 'damage_percentage',
      label: 'Damage %',
      sortValue: (row) => row.damage_percentage ?? -1,
      render: (row) => (
        <span>{row.damage_percentage != null ? `${row.damage_percentage.toFixed(1)}%` : '—'}</span>
      ),
    },
    {
      key: 'estimated_payout',
      label: 'Est. Payout',
      sortValue: (row) => row.estimated_payout ?? 0,
      render: (row) => (
        <span className="font-medium text-gray-900">{formatCurrency(row.estimated_payout)}</span>
      ),
    },
    {
      key: 'payout_status',
      label: 'Payout Status',
      render: (row) => (
        <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${
          row.payout_status === 'PAID'
            ? 'text-green-600 border-green-200 bg-green-50'
            : 'text-amber-600 border-amber-200 bg-amber-50'
        }`}
        >
          {row.payout_status}
        </span>
      ),
    },
    {
      key: 'status',
      label: 'Claim Status',
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
    return (
      <div className="space-y-6">
        <PageHeaderSkeleton />
        <StatCardsSkeleton count={3} cols="grid-cols-1 sm:grid-cols-3" />
        <TableSkeleton rows={8} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-3 flex items-center gap-3">
        <AlertTriangle className="w-[18px] h-[18px] text-amber-500 flex-shrink-0" />
        <p className="text-sm text-amber-900">
          <span className="font-semibold">For demonstration purposes only</span>
          {' '}
          — figures are estimates and not official determinations.
        </p>
      </div>

      <div>
        <h1 className="page-title">Payout Tracking</h1>
        <p className="text-sm text-gray-500 mt-1">Monitor insurance payout disbursements across Region V</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <StatCard label="Total Records" value={summary.total_records || 0} />
        <StatCard label="Total Paid" value={formatCurrency(summary.total_paid)} statusVariant="approved" statusLabel="Paid" />
        <StatCard label="Pending Payouts" value={formatCurrency(summary.total_pending)} statusVariant="pending" statusLabel="Pending" />
      </div>

      {payouts.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 text-center">
          <Banknote className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-700 font-medium">No payout records yet</p>
          <p className="text-sm text-gray-500 mt-1">
            Approved claims will appear here for payout tracking.
          </p>
        </div>
      ) : (
        <DataTable
          title="Payout Records"
          columns={columns}
          data={payouts}
          statusTabs={statusTabs}
          statusKey="payout_status"
          emptyMessage="No payouts match the selected filter"
        />
      )}
    </div>
  );
}