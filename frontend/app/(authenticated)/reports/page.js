'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Download, X, FileText, MoreHorizontal } from 'lucide-react';
import api from '@/lib/api';
import { getToken, getUser } from '@/lib/auth';
import { ClaimStatusBadge } from '@/components/common/Badge';
import LoadingSpinner from '@/components/common/LoadingSpinner';

function FarmerAvatar({ name }) {
  const initials = name?.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase() || 'F';
  return (
    <div className="w-8 h-8 rounded-full bg-gray-100 text-gray-700 flex items-center justify-center text-xs font-semibold flex-shrink-0">
      {initials}
    </div>
  );
}

export default function ReportsPage() {
  const router = useRouter();
  const [claims, setClaims] = useState([]);
  const [selectedClaim, setSelectedClaim] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchClaims = async () => {
      if (!getToken()) {
        router.push('/login');
        return;
      }
      try {
        const user = getUser();
        const params = user?.municipality_id ? `?municipality_id=${user.municipality_id}` : '';
        const response = await api.get(`/claims${params}`);
        setClaims(response.data.data.claims);
      } catch (err) {
        if (err.response?.status === 401) router.push('/login');
      } finally {
        setLoading(false);
      }
    };
    fetchClaims();
  }, [router]);

  const handleDownloadPDF = async (claimId, claimNumber) => {
    try {
      const response = await api.post(
        '/reports/generate',
        { claim_id: claimId },
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Claim_${claimNumber}_Report.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      alert('Failed to download report');
    }
  };

  const formatVerifiedDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <>
      <div className="space-y-6">
        <div>
          <h1 className="page-title">Verified Claims</h1>
          <p className="text-sm text-gray-500 mt-1">{claims.length} total claims with reports</p>
        </div>

        {loading ? (
          <LoadingSpinner size="lg" text="Loading reports..." className="py-20" />
        ) : claims.length === 0 ? (
          <div className="card-padded text-center">
            <FileText className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-600">No verified claims yet</p>
            <p className="text-xs text-gray-400 mt-1">Run a claim verification to generate reports</p>
          </div>
        ) : (
          <div className="card-base overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200">
              <h3 className="section-title">Claim Reports</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="table-th">Claim #</th>
                    <th className="table-th">Farmer</th>
                    <th className="table-th">Disaster Date</th>
                    <th className="table-th">Damage</th>
                    <th className="table-th">Status</th>
                    <th className="table-th text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {claims.map((claim) => (
                    <tr key={claim.id} className="border-b border-gray-200 hover:bg-gray-50 transition-colors duration-150">
                      <td className="table-td">
                        <button
                          type="button"
                          onClick={() => router.push(`/case/${claim.id}`)}
                          className="text-sm font-medium text-blue-600 hover:text-blue-700 font-mono"
                        >
                          {claim.claim_number}
                        </button>
                      </td>
                      <td className="table-td">
                        <div className="flex items-center gap-2.5">
                          <FarmerAvatar name={claim.farmer_name} />
                          <div>
                            <p className="text-sm font-medium text-gray-900">{claim.farmer_name}</p>
                            <p className="text-xs text-gray-400">{claim.municipality}</p>
                          </div>
                        </div>
                      </td>
                      <td className="table-td">
                        <p className="text-sm font-medium text-gray-900">{claim.disaster_date}</p>
                        <p className="text-xs text-gray-400">Filed {claim.filed_date}</p>
                      </td>
                      <td className="table-td">
                        <span className="text-sm font-medium text-gray-900">
                          {claim.damage_percentage != null ? `${claim.damage_percentage.toFixed(1)}%` : 'N/A'}
                        </span>
                      </td>
                      <td className="table-td">
                        <ClaimStatusBadge status={claim.status} size="sm" />
                      </td>
                      <td className="table-td text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => handleDownloadPDF(claim.id, claim.claim_number)}
                            className="btn-secondary h-8 px-2.5 text-xs"
                          >
                            <Download className="w-3.5 h-3.5" />
                            PDF
                          </button>
                          <button
                            type="button"
                            onClick={() => setSelectedClaim(claim)}
                            className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors duration-150"
                          >
                            <MoreHorizontal className="w-5 h-5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {selectedClaim && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="card-base max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-lg">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-5 py-4 flex items-center justify-between">
              <div>
                <h2 className="section-title">Claim Details</h2>
                <p className="text-xs text-blue-600 font-mono font-medium mt-0.5">{selectedClaim.claim_number}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedClaim(null)}
                className="p-2 hover:bg-gray-50 rounded-lg transition-colors duration-150"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            <div className="p-5 space-y-5">
              <div className="flex items-center gap-4">
                <ClaimStatusBadge status={selectedClaim.status} size="md" />
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    Damage: {selectedClaim.damage_percentage != null ? `${selectedClaim.damage_percentage.toFixed(1)}%` : 'N/A'}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Verified {formatVerifiedDate(selectedClaim.verified_at)}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="card-header mb-1">Farmer</p>
                  <p className="font-medium text-gray-900">{selectedClaim.farmer_name}</p>
                </div>
                <div>
                  <p className="card-header mb-1">RSBSA</p>
                  <p className="font-mono text-gray-900">{selectedClaim.rsbsa_number}</p>
                </div>
              </div>

              <div className="flex gap-3 pt-4 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => handleDownloadPDF(selectedClaim.id, selectedClaim.claim_number)}
                  className="btn-primary flex-1"
                >
                  <Download className="w-4 h-4" />
                  Download PDF
                </button>
                <button type="button" onClick={() => setSelectedClaim(null)} className="btn-secondary">
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}