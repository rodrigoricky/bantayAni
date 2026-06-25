'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import { ShieldCheck, ShieldX } from 'lucide-react';
import { API_URL, CLAIM_STATUS } from '@/lib/constants';
import LoadingSpinner from '@/components/common/LoadingSpinner';

function DetailRow({ label, value }) {
  return (
    <div className="flex justify-between gap-4 py-2 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-500 shrink-0">{label}</span>
      <span className="text-sm font-medium text-gray-900 text-right">{value ?? 'N/A'}</span>
    </div>
  );
}

export default function VerifyPage({ params }) {
  const { id } = params;
  const [state, setState] = useState('loading');
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchVerification() {
      try {
        const response = await fetch(`${API_URL}/verify/${encodeURIComponent(id)}`, {
          cache: 'no-store',
        });
        const json = await response.json();
        if (cancelled) return;

        const payload = json?.data;
        if (payload?.verified) {
          setData(payload);
          setState('verified');
        } else {
          setState('not_found');
        }
      } catch {
        if (!cancelled) setState('not_found');
      }
    }

    fetchVerification();
    return () => { cancelled = true; };
  }, [id]);

  if (state === 'loading') {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-6">
        <LoadingSpinner size="md" />
        <p className="mt-4 text-sm text-gray-500">Verifying report...</p>
      </div>
    );
  }

  if (state === 'not_found') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
          <div className="flex justify-center mb-6">
            <Image src="/logo.png" alt="Bantay Ani" width={180} height={44} className="h-11 w-auto object-contain" priority />
          </div>
          <div className="mx-auto w-16 h-16 rounded-full bg-red-50 flex items-center justify-center mb-4">
            <ShieldX className="w-8 h-8 text-red-600" />
          </div>
          <h1 className="text-xl font-semibold text-gray-900 mb-2">Report Not Found</h1>
          <p className="text-sm text-gray-500 mb-4">
            This report ID could not be verified. It may be invalid, expired, or not yet registered in the BantayANI system.
          </p>
          <p className="text-xs font-mono text-gray-400 bg-gray-50 rounded-lg px-3 py-2 break-all">{id}</p>
        </div>
      </div>
    );
  }

  const statusMeta = CLAIM_STATUS[data.status] || CLAIM_STATUS.PENDING;

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        <div className="flex justify-center mb-6">
          <Image src="/logo.png" alt="Bantay Ani" width={200} height={48} className="h-12 w-auto object-contain" priority />
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="bg-green-50 border-b border-green-100 px-6 py-5 text-center">
            <div className="mx-auto w-14 h-14 rounded-full bg-green-100 flex items-center justify-center mb-3">
              <ShieldCheck className="w-7 h-7 text-green-600" />
            </div>
            <h1 className="text-lg font-semibold text-green-900">Report Verified</h1>
            <p className="text-sm text-green-700 mt-1">
              This satellite damage verification report is authentic and registered with BantayANI.
            </p>
          </div>

          <div className="px-6 py-5">
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-3">Claim Details</h2>
            <div className="rounded-lg border border-gray-100 bg-gray-50/50 px-4 py-1">
              <DetailRow label="Claim Number" value={data.claim_number} />
              <DetailRow label="Farmer" value={data.farmer_name} />
              <DetailRow label="Municipality" value={data.municipality} />
              <DetailRow label="Barangay" value={data.barangay} />
              <DetailRow label="Crop Type" value={data.crop_type} />
              <DetailRow label="Area (hectares)" value={data.area_hectares?.toFixed?.(2) ?? data.area_hectares} />
              <DetailRow label="Damage" value={`${data.damage_percentage}%`} />
              <DetailRow label="Status" value={statusMeta.label} />
              <DetailRow label="Disaster Date" value={data.disaster_date} />
              <DetailRow label="Verification Date" value={data.verification_date} />
              <DetailRow label="Verified By" value={data.verified_by} />
            </div>

            <div className="mt-5 pt-4 border-t border-gray-100 space-y-2">
              <p className="text-xs text-gray-400">
                Generated: {data.generated_at}
              </p>
              <p className="text-xs text-gray-400 font-mono break-all">
                Integrity: {data.report_integrity}
              </p>
            </div>
          </div>
        </div>

        <p className="text-center text-xs text-gray-400 mt-4">
          BantayANI — Satellite Crop Intelligence for Naga City, Camarines Sur
        </p>
      </div>
    </div>
  );
}