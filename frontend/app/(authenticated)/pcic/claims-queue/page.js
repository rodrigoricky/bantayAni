'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { ExternalLink, Loader2, X } from 'lucide-react';
import api from '@/lib/api';
import { getToken } from '@/lib/auth';
import { ClaimStatusBadge } from '@/components/common/Badge';
import DataTable from '@/components/common/DataTable';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import Toast from '@/components/common/Toast';

const ACTIONABLE = new Set(['PENDING', 'SUBMITTED', 'FLAGGED', 'VERIFIED']);

export default function PCICClaimsQueue() {
  const router = useRouter();
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(null);
  const [toast, setToast] = useState(null);
  const [activeModal, setActiveModal] = useState(null);
  const [selectedClaim, setSelectedClaim] = useState(null);
  const [actionReason, setActionReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [modalError, setModalError] = useState(null);

  const fetchClaims = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get('/claims', { params: { limit: 200 } });
      setClaims(response.data.data.claims);
    } catch (error) {
      console.error('Error fetching claims:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    fetchClaims();
  }, [router, fetchClaims]);

  const closeModal = useCallback(() => {
    setActiveModal(null);
    setSelectedClaim(null);
    setActionReason('');
    setActionLoading(false);
    setModalError(null);
  }, []);

  useEffect(() => {
    if (!activeModal) return undefined;
    const onKeyDown = (e) => {
      if (e.key === 'Escape') closeModal();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [activeModal, closeModal]);

  const openModal = (type, claim) => {
    setActiveModal(type);
    setSelectedClaim(claim);
    setActionReason('');
    setModalError(null);
  };

  const updateClaimStatus = (claimId, updates) => {
    setClaims((prev) =>
      prev.map((c) => (c.id === claimId ? { ...c, ...updates } : c))
    );
  };

  const handleApprove = async () => {
    if (!selectedClaim) return;
    setActionLoading(true);
    setModalError(null);
    try {
      const res = await api.post(`/claims/${selectedClaim.id}/approve`);
      updateClaimStatus(selectedClaim.id, { status: res.data.data.status });
      setToast({ message: `Claim #${selectedClaim.claim_number} has been approved.`, type: 'success' });
      closeModal();
    } catch {
      setModalError('Action failed. Please try again.');
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!selectedClaim || actionReason.length < 20) return;
    setActionLoading(true);
    setModalError(null);
    try {
      const res = await api.post(`/claims/${selectedClaim.id}/reject`, { reason: actionReason });
      updateClaimStatus(selectedClaim.id, { status: res.data.data.status });
      setToast({ message: `Claim #${selectedClaim.claim_number} has been rejected.`, type: 'success' });
      closeModal();
    } catch {
      setModalError('Action failed. Please try again.');
      setActionLoading(false);
    }
  };

  const handleFlag = async () => {
    if (!selectedClaim || actionReason.length < 20) return;
    setActionLoading(true);
    setModalError(null);
    try {
      const res = await api.post(`/claims/${selectedClaim.id}/flag`, { reason: actionReason });
      updateClaimStatus(selectedClaim.id, { status: res.data.data.status });
      setToast({ message: `Claim #${selectedClaim.claim_number} has been flagged.`, type: 'success' });
      closeModal();
    } catch {
      setModalError('Action failed. Please try again.');
      setActionLoading(false);
    }
  };

  const handleReverse = async (claim) => {
    setProcessing(claim.id);
    try {
      const res = await api.post(`/claims/${claim.id}/reverse`);
      updateClaimStatus(claim.id, { status: res.data.data.status });
      setToast({ message: `Claim #${claim.claim_number} decision reversed.`, type: 'success' });
    } catch {
      setToast({ message: 'Failed to reverse decision.', type: 'error' });
    } finally {
      setProcessing(null);
    }
  };

  const statusTabs = useMemo(() => [
    { value: 'ALL', label: 'All', count: claims.length },
    { value: 'PENDING', label: 'Pending', count: claims.filter((c) => c.status === 'PENDING').length },
    { value: 'SUBMITTED', label: 'Submitted', count: claims.filter((c) => c.status === 'SUBMITTED').length },
    { value: 'FLAGGED', label: 'Flagged', count: claims.filter((c) => c.status === 'FLAGGED').length },
    { value: 'APPROVED', label: 'Approved', count: claims.filter((c) => c.status === 'APPROVED').length },
    { value: 'REJECTED', label: 'Rejected', count: claims.filter((c) => c.status === 'REJECTED').length },
  ], [claims]);

  const columns = [
    {
      key: 'claim_number',
      label: 'Claim #',
      render: (row) => (
        <div>
          <button
            type="button"
            onClick={() => router.push(`/case/${row.id}`)}
            className="text-sm font-medium text-blue-600 hover:text-blue-700 font-mono"
          >
            {row.claim_number}
          </button>
          <p className="text-xs text-gray-400 mt-0.5">{row.filed_date}</p>
        </div>
      ),
    },
    {
      key: 'farmer_name',
      label: 'Farmer',
      render: (row) => (
        <div>
          <p className="text-sm font-medium text-gray-900">{row.farmer_name}</p>
          <p className="text-xs text-gray-400 font-mono">{row.rsbsa_number}</p>
          <p className="text-xs text-gray-400">{row.municipality}</p>
        </div>
      ),
    },
    {
      key: 'damage_percentage',
      label: 'Damage',
      sortValue: (row) => row.damage_percentage ?? -1,
      render: (row) => (
        <span className="text-sm font-semibold text-gray-900">
          {row.damage_percentage != null ? `${row.damage_percentage.toFixed(1)}%` : 'N/A'}
        </span>
      ),
    },
    {
      key: 'ndvi_before',
      label: 'NDVI',
      sortable: false,
      render: (row) => (
        <span className="text-xs font-mono text-gray-600">
          {row.ndvi_before?.toFixed(2) ?? 'N/A'} → {row.ndvi_after?.toFixed(2) ?? 'N/A'}
        </span>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      render: (row) => <ClaimStatusBadge status={row.status} size="sm" />,
    },
    {
      key: 'actions',
      label: 'Actions',
      sortable: false,
      align: 'right',
      render: (row) => {
        const canAct = ACTIONABLE.has(row.status);
        const isApproved = row.status === 'APPROVED';
        return (
          <div className="flex items-center justify-end gap-1 flex-wrap">
            <button
              type="button"
              onClick={() => router.push(`/case/${row.id}`)}
              className="btn-secondary h-8 px-2 text-xs"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              View
            </button>
            {canAct && (
              <>
                <button
                  type="button"
                  disabled={processing === row.id}
                  onClick={() => openModal('approve', row)}
                  className="h-8 px-2 text-xs font-medium text-green-600 bg-white border border-gray-200 hover:bg-gray-50 rounded-lg disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  type="button"
                  disabled={processing === row.id}
                  onClick={() => openModal('flag', row)}
                  className="h-8 px-2 text-xs font-medium text-amber-600 bg-white border border-gray-200 hover:bg-gray-50 rounded-lg disabled:opacity-50"
                >
                  Flag
                </button>
                <button
                  type="button"
                  disabled={processing === row.id}
                  onClick={() => openModal('reject', row)}
                  className="h-8 px-2 text-xs font-medium text-red-600 bg-white border border-gray-200 hover:bg-gray-50 rounded-lg disabled:opacity-50"
                >
                  Reject
                </button>
              </>
            )}
            {isApproved && (
              <button
                type="button"
                disabled={processing === row.id}
                onClick={() => handleReverse(row)}
                className="btn-secondary h-8 px-2 text-xs disabled:opacity-50"
              >
                Reverse
              </button>
            )}
          </div>
        );
      },
    },
  ];

  const damageLabel = selectedClaim?.damage_percentage != null
    ? `${selectedClaim.damage_percentage.toFixed(1)}%`
    : 'N/A';

  return (
    <div className="space-y-6">
      {toast && (
        <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />
      )}

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="page-title">Claims Processing Queue</h1>
          <p className="text-sm text-gray-500 mt-0.5">PCIC Regional Office | Region V (Bicol)</p>
        </div>
        <button type="button" onClick={fetchClaims} className="btn-secondary">
          Refresh
        </button>
      </div>

      {loading ? (
        <LoadingSpinner size="lg" text="Loading claims..." className="py-20" />
      ) : claims.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 text-center text-gray-500">
          No claims in queue
        </div>
      ) : (
        <DataTable
          title="Claims Queue"
          columns={columns}
          data={claims}
          statusTabs={statusTabs}
          statusKey="status"
          emptyMessage="No claims match the selected filter"
        />
      )}

      {activeModal && selectedClaim && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={closeModal}
          role="presentation"
        >
          <div
            className="bg-white rounded-xl p-6 w-[480px] max-w-[90vw] shadow-[0_20px_60px_rgba(0,0,0,0.3)]"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="flex items-start justify-between mb-4">
              {activeModal === 'approve' && (
                <h2 className="text-lg font-bold text-gray-900">Approve Claim</h2>
              )}
              {activeModal === 'reject' && (
                <h2 className="text-lg font-bold text-red-600">Reject Claim</h2>
              )}
              {activeModal === 'flag' && (
                <h2 className="text-lg font-bold text-amber-600">Flag for Investigation</h2>
              )}
              <button type="button" onClick={closeModal} className="p-1 text-gray-400 hover:text-gray-600" aria-label="Close">
                <X className="w-5 h-5" />
              </button>
            </div>

            {activeModal === 'approve' && (
              <>
                <p className="text-sm text-gray-700 mb-1">
                  Claim {selectedClaim.claim_number} — {selectedClaim.farmer_name} ({damageLabel} damage)
                </p>
                <p className="text-sm text-gray-500 mb-6">
                  This will mark the claim as approved and notify the farmer.
                </p>
                <div className="flex justify-end gap-2">
                  <button type="button" onClick={closeModal} className="btn-action-secondary" disabled={actionLoading}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleApprove}
                    disabled={actionLoading}
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg disabled:opacity-50"
                  >
                    {actionLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                    Confirm Approval
                  </button>
                </div>
              </>
            )}

            {activeModal === 'reject' && (
              <>
                <p className="text-sm text-gray-700 mb-4">
                  Claim {selectedClaim.claim_number} — {selectedClaim.farmer_name}
                </p>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Reason for rejection
                </label>
                <textarea
                  value={actionReason}
                  onChange={(e) => setActionReason(e.target.value)}
                  rows={4}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  placeholder="Explain why this claim is being rejected..."
                />
                <p className="text-xs text-gray-500 mt-1">
                  {actionReason.length} / 20 minimum
                </p>
                <div className="flex justify-end gap-2 mt-4">
                  <button type="button" onClick={closeModal} className="btn-action-secondary" disabled={actionLoading}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleReject}
                    disabled={actionLoading || actionReason.length < 20}
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50"
                  >
                    {actionLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                    Confirm Rejection
                  </button>
                </div>
              </>
            )}

            {activeModal === 'flag' && (
              <>
                <p className="text-sm text-gray-700 mb-4">
                  Claim {selectedClaim.claim_number} — {selectedClaim.farmer_name}
                </p>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Investigation reason
                </label>
                <textarea
                  value={actionReason}
                  onChange={(e) => setActionReason(e.target.value)}
                  rows={4}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  placeholder="Explain what requires investigation..."
                />
                <p className="text-xs text-gray-500 mt-1">
                  {actionReason.length} / 20 minimum
                </p>
                <div className="flex justify-end gap-2 mt-4">
                  <button type="button" onClick={closeModal} className="btn-action-secondary" disabled={actionLoading}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleFlag}
                    disabled={actionLoading || actionReason.length < 20}
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 rounded-lg disabled:opacity-50"
                  >
                    {actionLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                    Confirm Flag
                  </button>
                </div>
              </>
            )}

            {modalError && (
              <p className="text-sm text-red-600 mt-4">{modalError}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}