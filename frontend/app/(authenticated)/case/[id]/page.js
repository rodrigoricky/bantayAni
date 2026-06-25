'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft, Download, CheckCircle, Flag, XCircle, RotateCcw,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Dot,
} from 'recharts';
import api from '@/lib/api';
import { getToken, getUser } from '@/lib/auth';
import { getChartYDomain } from '@/lib/chartUtils';

import LoadingSpinner from '@/components/common/LoadingSpinner';
import VerificationResult from '@/components/claims/VerificationResult';
import Toast from '@/components/common/Toast';

export default function CaseDetailPage() {
  const router = useRouter();
  const params = useParams();
  const [user, setUser] = useState(null);
  const [claim, setClaim] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [actionMode, setActionMode] = useState(null);
  const [actionReason, setActionReason] = useState('');
  const [toast, setToast] = useState(null);

  const fetchClaim = useCallback(async () => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    try {
      const res = await api.get(`/claims/${params.id}`);
      setClaim(res.data.data);
    } catch {
      setClaim(null);
    } finally {
      setLoading(false);
    }
  }, [params.id, router]);

  useEffect(() => {
    setUser(getUser());
  }, []);

  useEffect(() => {
    if (params.id) fetchClaim();
  }, [params.id, fetchClaim]);

  const handleDownload = async () => {
    try {
      const response = await api.post(
        '/reports/generate',
        { claim_id: claim.claim_id },
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Claim_${claim.claim_number}_Report.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      setToast({ message: 'Failed to generate PDF', type: 'error' });
    }
  };

  const runAction = async (action) => {
    setProcessing(true);
    try {
      let res;
      if (action === 'approve') {
        res = await api.post(`/claims/${claim.claim_id}/approve`);
      } else if (action === 'reject') {
        res = await api.post(`/claims/${claim.claim_id}/reject`, { reason: actionReason });
      } else if (action === 'flag') {
        res = await api.post(`/claims/${claim.claim_id}/flag`, { reason: actionReason });
      } else if (action === 'reverse') {
        res = await api.post(`/claims/${claim.claim_id}/reverse`);
      }
      setClaim((prev) => ({ ...prev, status: res.data.data.status }));
      setActionMode(null);
      setActionReason('');
      setToast({ message: `Claim ${action}d successfully`, type: 'success' });
    } catch {
      setToast({ message: `Failed to ${action} claim`, type: 'error' });
    } finally {
      setProcessing(false);
    }
  };

  if (loading) {
    return <LoadingSpinner size="lg" text="Loading case details..." className="py-20" />;
  }

  if (!claim) {
    return (
      <div className="text-center py-12">
        <p className="text-sm text-gray-500">Claim not found</p>
        <button type="button" onClick={() => router.push('/claims')} className="mt-4 text-sm text-blue-600 hover:underline">
          Back to Claims
        </button>
      </div>
    );
  }

  const timeline = claim.ndvi_timeline || [];
  const chartData = timeline.map((t) => ({
    date: t.date.slice(5),
    ndvi: t.ndvi,
    fullDate: t.date,
  }));
  const yDomain = getChartYDomain(chartData, 'ndvi');

  const isPCIC = user?.role === 'PCIC';
  const isMAO = user?.role === 'MAO' || user?.role === 'ADMIN';
  const canAct = isPCIC && ['PENDING', 'SUBMITTED', 'FLAGGED', 'VERIFIED'].includes(claim.status);

  return (
    <div className="space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <button
        type="button"
        onClick={() => router.back()}
        className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900"
      >
        <ArrowLeft className="w-4 h-4" />
        Back
      </button>

      <VerificationResult result={claim} hideActions />

      {chartData.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <p className="card-header border-b border-gray-200 pb-3 mb-4">NDVI Timeline</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis domain={yDomain} tick={{ fontSize: 11 }} tickFormatter={(v) => v.toFixed(2)} />
                <Tooltip
                  formatter={(v) => [Number(v).toFixed(3), 'NDVI']}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ''}
                />
                {chartData.length === 1 ? (
                  <Line type="monotone" dataKey="ndvi" stroke="#4f46e5" strokeWidth={0} dot={<Dot r={6} fill="#4f46e5" />} />
                ) : (
                  <Line type="monotone" dataKey="ndvi" stroke="#4f46e5" strokeWidth={2} dot={{ r: 3, fill: '#4f46e5' }} />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-3 pt-4 border-t border-gray-200">
        {isMAO && (
          <button
            type="button"
            onClick={handleDownload}
            className="btn-action-secondary"
          >
            <Download className="w-4 h-4" />
            Download PDF
          </button>
        )}

        {canAct && (
          <>
            <button
              type="button"
              disabled={processing}
              onClick={() => setActionMode('approve')}
              className="btn-primary disabled:opacity-50"
            >
              <CheckCircle className="w-4 h-4" />
              Approve
            </button>
            <button
              type="button"
              disabled={processing}
              onClick={() => setActionMode('flag')}
              className="btn-action-secondary disabled:opacity-50"
            >
              <Flag className="w-4 h-4" />
              Flag
            </button>
            <button
              type="button"
              disabled={processing}
              onClick={() => setActionMode('reject')}
              className="btn-action-secondary text-red-600 disabled:opacity-50"
            >
              <XCircle className="w-4 h-4" />
              Reject
            </button>
          </>
        )}

        {isPCIC && claim.status === 'APPROVED' && (
          <button
            type="button"
            disabled={processing}
            onClick={() => runAction('reverse')}
            className="btn-secondary disabled:opacity-50"
          >
            <RotateCcw className="w-4 h-4" />
            Reverse Decision
          </button>
        )}
      </div>

      {actionMode === 'approve' && (
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-sm text-gray-700 mb-3">Confirm approval for {claim.claim_number}?</p>
          <div className="flex gap-3">
            <button type="button" disabled={processing} onClick={() => runAction('approve')} className="btn-primary disabled:opacity-50">
              Confirm Approve
            </button>
            <button type="button" onClick={() => setActionMode(null)} className="btn-secondary">
              Cancel
            </button>
          </div>
        </div>
      )}

      {(actionMode === 'reject' || actionMode === 'flag') && (
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {actionMode === 'reject' ? 'Rejection reason (min 20 chars)' : 'Flag reason'}
          </label>
          <textarea
            value={actionReason}
            onChange={(e) => setActionReason(e.target.value)}
            rows={3}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <div className="flex gap-3 mt-3">
            <button
              type="button"
              disabled={processing || (actionMode === 'reject' && actionReason.length < 20) || (actionMode === 'flag' && !actionReason.trim())}
              onClick={() => runAction(actionMode)}
              className="btn-primary disabled:opacity-50"
            >
              Confirm
            </button>
            <button type="button" onClick={() => { setActionMode(null); setActionReason(''); }} className="btn-secondary">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}