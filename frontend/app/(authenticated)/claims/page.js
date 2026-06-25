'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Satellite, RefreshCw, ChevronRight, CloudRain, Sun, Bug, AlertTriangle, Search,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { getToken, getUser } from '@/lib/auth';
import api from '@/lib/api';
import ClaimForm from '@/components/claims/ClaimForm';
import VerificationResult from '@/components/claims/VerificationResult';
import StatCard from '@/components/stats/StatCard';
import { StatCardsSkeleton } from '@/components/common/PageSkeleton';
import { ClaimStatusBadge } from '@/components/common/Badge';
import VerificationProgressBar from '@/components/claims/VerificationProgressBar';
import { FileText } from 'lucide-react';

const DAMAGE_ICONS = {
  flood: CloudRain,
  typhoon: CloudRain,
  drought: Sun,
  pest: Bug,
  disease: Bug,
};

function DamageIcon({ type }) {
  const Icon = DAMAGE_ICONS[type?.toLowerCase()] || AlertTriangle;
  return <Icon className="w-4 h-4 text-gray-500" />;
}

function damageColor(pct) {
  if (pct == null) return 'text-gray-500';
  if (pct >= 70) return 'text-red-600';
  if (pct >= 30) return 'text-amber-600';
  return 'text-gray-700';
}

export default function ClaimsPage() {
  const router = useRouter();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [claims, setClaims] = useState([]);
  const [claimsLoading, setClaimsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const fetchClaims = useCallback(async () => {
    const user = getUser();
    if (!user?.municipality_id) return;
    try {
      const response = await api.get('/claims', {
        params: { municipality_id: user.municipality_id, limit: 50 },
      });
      setClaims(response.data.data.claims);
    } catch (err) {
      if (err.response?.status === 401) router.push('/login');
    } finally {
      setClaimsLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    fetchClaims();
    const interval = setInterval(fetchClaims, 30000);
    return () => clearInterval(interval);
  }, [router, fetchClaims]);

  const claimStats = useMemo(() => ({
    total: claims.length,
    approved: claims.filter((c) => c.status === 'APPROVED').length,
    flagged: claims.filter((c) => c.status === 'FLAGGED').length,
    rejected: claims.filter((c) => c.status === 'REJECTED').length,
    pending: claims.filter((c) => c.status === 'PENDING' || c.status === 'SUBMITTED').length,
  }), [claims]);

  const filteredClaims = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    return claims.filter((claim) => {
      if (statusFilter !== 'ALL' && claim.status !== statusFilter) return false;
      if (!q) return true;
      return (
        claim.farmer_name?.toLowerCase().includes(q)
        || claim.rsbsa_number?.toLowerCase().includes(q)
        || claim.claim_number?.toLowerCase().includes(q)
      );
    });
  }, [claims, statusFilter, searchQuery]);

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    try { return format(parseISO(dateStr), 'MMM d, yyyy'); } catch { return dateStr; }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="page-title">Claim Verification</h1>
          <p className="text-sm text-gray-500 mt-1">Satellite-based damage assessment</p>
        </div>
      </div>

      {claimsLoading ? (
        <StatCardsSkeleton count={5} cols="grid-cols-1 sm:grid-cols-2 lg:grid-cols-5" />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
          <StatCard label="Total Claims" value={claimStats.total} />
          <StatCard label="Approved" value={claimStats.approved} statusVariant="approved" statusLabel="Approved" />
          <StatCard label="Flagged" value={claimStats.flagged} statusVariant="flagged" statusLabel="Flagged" />
          <StatCard label="Rejected" value={claimStats.rejected} statusVariant="rejected" statusLabel="Rejected" />
          <StatCard label="Pending" value={claimStats.pending} statusVariant="pending" statusLabel="Pending" />
        </div>
      )}

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-4">
          <div className="sticky top-6">
            <ClaimForm onResult={setResult} onLoading={setLoading} onError={setError} />
          </div>
        </div>

        <div className="col-span-12 lg:col-span-8 space-y-6">
          {error && (
            <div className="bg-white border border-gray-200 text-red-600 text-sm p-4 rounded-xl">
              {error}
            </div>
          )}

          <VerificationProgressBar active={loading} complete={!!result && !loading} />

          {!result && !loading && (
            <div className="bg-white border border-dashed border-gray-200 rounded-xl p-12 text-center">
              <Satellite className="w-12 h-12 text-gray-400 mx-auto mb-3" />
              <p className="text-gray-700 font-medium">Run a verification to see results</p>
              <p className="text-gray-500 text-sm mt-1">Enter RSBSA and disaster details in the form</p>
            </div>
          )}

          {result && !loading && <VerificationResult result={result} onStatusChange={fetchClaims} />}

          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
              <h2 className="card-header">Recent Claims</h2>
              <button
                type="button"
                onClick={fetchClaims}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-600 hover:text-gray-900"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Refresh
              </button>
            </div>

            <div className="px-5 py-3 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center gap-3">
              <div className="flex flex-wrap gap-1">
                {['ALL', 'PENDING', 'APPROVED', 'FLAGGED', 'REJECTED'].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setStatusFilter(s)}
                    className={`px-3 py-1 text-xs font-medium rounded-lg border transition-colors ${
                      statusFilter === s
                        ? 'bg-gray-100 text-gray-900 border-gray-300'
                        : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    {s === 'ALL' ? 'All' : s.charAt(0) + s.slice(1).toLowerCase()}
                  </button>
                ))}
              </div>
              <div className="relative flex-1 max-w-xs">
                <Search className="absolute left-3 top-2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search farmer or RSBSA..."
                  className="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            {claimsLoading ? (
              <div className="p-8 space-y-3 animate-pulse">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-14 bg-gray-100 rounded-lg" />
                ))}
              </div>
            ) : claims.length === 0 ? (
              <div className="py-16 text-center px-6">
                <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-700 font-medium">No claims yet</p>
                <p className="text-sm text-gray-500 mt-1">Use Verify Claim to get started.</p>
                <button
                  type="button"
                  onClick={() => document.querySelector('form')?.scrollIntoView({ behavior: 'smooth' })}
                  className="mt-4 btn-primary"
                >
                  Verify a Claim
                </button>
              </div>
            ) : filteredClaims.length === 0 ? (
              <p className="text-sm text-gray-500 p-6 text-center">No claims match your filters</p>
            ) : (
              <div>
                {filteredClaims.map((claim) => (
                  <button
                    key={claim.id}
                    type="button"
                    onClick={() => router.push(`/case/${claim.id}`)}
                    className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-gray-50 cursor-pointer transition-colors border-b border-gray-200 last:border-b-0 min-h-[56px]"
                  >
                    <span className="text-xs font-mono text-blue-600 font-medium w-28 flex-shrink-0 hidden sm:block">
                      {claim.claim_number?.split('-').slice(-1)[0] || claim.claim_number}
                    </span>

                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{claim.farmer_name}</p>
                      <p className="text-xs font-mono text-gray-400">{claim.rsbsa_number}</p>
                    </div>

                    <div className="hidden md:flex items-center gap-1.5 text-sm text-gray-500 w-28 flex-shrink-0">
                      <DamageIcon type={claim.damage_type} />
                      <span className="capitalize">{claim.damage_type}</span>
                    </div>

                    <span className={`text-sm font-medium w-14 text-right flex-shrink-0 ${damageColor(claim.damage_percentage)}`}>
                      {claim.damage_percentage != null ? `${claim.damage_percentage.toFixed(0)}%` : 'N/A'}
                    </span>

                    <ClaimStatusBadge status={claim.status} size="sm" />

                    <span className="text-xs text-gray-400 w-24 text-right hidden lg:block flex-shrink-0">
                      {formatDate(claim.filed_date)}
                    </span>

                    <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}