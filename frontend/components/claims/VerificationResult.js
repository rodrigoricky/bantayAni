'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Download, Upload, MapPin, Ruler, ShieldAlert, ImageOff, ArrowRight, Cloud,
  TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, Circle,
} from 'lucide-react';
import { format } from 'date-fns';
import NDVIComparison from './NDVIComparison';
import AIAssessmentCard from './AIAssessmentCard';
import { getNDVIContext } from '@/lib/constants';
import { NDVIIcon } from '@/lib/ndviIcons';
import {
  computeEvidenceMetrics,
  getWeatherCorrelationText,
  getStatusDisplay,
  getStatusReason,
  getNdviDropSignal,
  getRainfallSignal,
  getNdviChangeDisplay,
  parseBoldSegments,
} from '@/lib/formatAiAssessment';
import api from '@/lib/api';
import InsuranceIndicator from '@/components/common/InsuranceIndicator';

function BoldText({ text, className = '' }) {
  const segments = parseBoldSegments(text);
  return (
    <span className={className}>
      {segments.map((seg, i) => (
        seg.type === 'bold'
          ? <strong key={i} className="font-semibold text-gray-900">{seg.text}</strong>
          : <span key={i}>{seg.text}</span>
      ))}
    </span>
  );
}

function SatelliteImage({ src, alt, fallbackLabel }) {
  const [loading, setLoading] = useState(Boolean(src));
  const [failed, setFailed] = useState(!src);

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg overflow-hidden aspect-square relative">
      {loading && !failed && <div className="absolute inset-0 animate-pulse bg-gray-100" />}
      {failed || !src ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-400 p-4 text-center">
          <ImageOff className="w-8 h-8 mb-2" />
          <p className="text-xs">{fallbackLabel || 'Satellite image not available'}</p>
        </div>
      ) : (
        <img
          src={src}
          alt={alt}
          className="w-full h-full object-cover"
          onLoad={() => setLoading(false)}
          onError={() => { setLoading(false); setFailed(true); }}
        />
      )}
    </div>
  );
}

const SIGNAL_ICONS = {
  TrendingUp,
  TrendingDown,
  ArrowRight,
  ArrowUpRight,
  ArrowDownRight,
};

function EvidenceBlock({ label, value, subtext, signal }) {
  const SignalIcon = signal?.icon ? SIGNAL_ICONS[signal.icon] : null;
  return (
    <div className="card-base p-5">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-[0.06em]">{label}</p>
      <p className={`text-[22px] font-semibold mt-2 flex items-center gap-1.5 ${signal?.color || 'text-gray-900'}`}>
        {SignalIcon && <SignalIcon className="w-5 h-5 shrink-0" aria-hidden="true" />}
        <span>{value}</span>
      </p>
      {subtext && <p className="text-xs text-gray-500 mt-1.5">{subtext}</p>}
    </div>
  );
}

function PremiumCard({ title, children, icon: Icon }) {
  return (
    <div className="card-base overflow-hidden">
      <div className="px-6 pt-6">
        <div className="flex items-center gap-2 card-section-header mb-0">
          {Icon && <Icon className="w-4 h-4 text-gray-500" />}
          <h3 className="text-base font-semibold text-gray-900">{title}</h3>
        </div>
      </div>
      <div className="mx-6 border-t border-gray-100" />
      <div className="px-6 py-6">{children}</div>
    </div>
  );
}

export default function VerificationResult({ result, onDownloadError, onStatusChange, hideActions = false }) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(null);

  if (!result) return null;

  const { satellite_analysis: sat, farm, fraud_indicators = [] } = result;
  const damagePct = sat?.damage_percentage || 0;
  const metrics = computeEvidenceMetrics({ ...sat, damage_type: result.damage_type });
  const statusDisplay = getStatusDisplay(result.status);
  const statusReason = getStatusReason(result, metrics);

  const verifiedSource = result.verified_at || result.created_at || '';
  const verifiedDate = verifiedSource
    ? format(new Date(verifiedSource), 'MMM d, yyyy')
    : '—';

  const handleDownloadReport = async () => {
    try {
      const response = await api.post(
        '/reports/generate',
        { claim_id: result.claim_id },
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Claim_${result.claim_number}_Report.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      if (onDownloadError) onDownloadError('Failed to generate PDF report');
      else alert('Failed to generate PDF report');
    }
  };

  const handleSubmitToPCIC = async () => {
    if (!confirm('Submit this claim to PCIC for final processing?')) return;
    setSubmitting(true);
    try {
      const response = await api.post(`/claims/${result.claim_id}/submit`);
      setSubmitSuccess(response.data.data.claim_number);
      if (onStatusChange) onStatusChange();
    } catch {
      alert('Failed to submit claim to PCIC');
    } finally {
      setSubmitting(false);
    }
  };

  const beforeCtx = sat?.ndvi_before != null ? getNDVIContext(sat.ndvi_before) : null;
  const afterCtx = sat?.ndvi_after != null ? getNDVIContext(sat.ndvi_after) : null;
  const areaMatch = farm && result.claimed_area_hectares <= farm.area_hectares;
  const fraudRisk = fraud_indicators.length === 0
    ? 'LOW'
    : fraud_indicators.some((f) => f.severity === 'CRITICAL')
      ? 'CRITICAL'
      : 'MEDIUM';

  const weatherText = getWeatherCorrelationText(result.damage_type, damagePct);
  const ndviChangeDisplay = metrics ? getNdviChangeDisplay(metrics) : null;
  const rainfallSignal = metrics ? getRainfallSignal(metrics.rainfallDeviation) : null;

  return (
    <div className="space-y-8">
      {/* Status Dominance Card */}
      <div className="card-base min-h-[140px] p-8">
        <p className={`text-[34px] font-bold tracking-tight uppercase ${statusDisplay.color}`}>
          {statusDisplay.label}
        </p>
        <p className="text-base font-medium text-gray-700 mt-3">
          {statusReason}
        </p>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 mt-5 text-[13px] text-gray-500">
          <span><span className="text-gray-400">Claim</span> {result.claim_number}</span>
          <span>
            <span className="text-gray-400">Farmer</span>
            {' '}
            {result.farmer_name}
            <InsuranceIndicator isInsured={result.farm?.is_insured ?? result.is_insured} />
          </span>
          <span><span className="text-gray-400">Parcel</span> {result.parcel_id}</span>
          <span><span className="text-gray-400">Date</span> {verifiedDate}</span>
        </div>
      </div>

      {submitSuccess && (
        <div className="card-base p-6 text-green-600 text-sm">
          Claim {submitSuccess} submitted to PCIC successfully.
        </div>
      )}

      <AIAssessmentCard result={result} />

      {metrics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <EvidenceBlock
            label={ndviChangeDisplay?.label || 'NDVI Change'}
            value={ndviChangeDisplay?.value || 'N/A'}
            subtext={ndviChangeDisplay?.subtext}
            signal={ndviChangeDisplay?.noChange ? { icon: 'ArrowRight', color: 'text-gray-500' } : ndviChangeDisplay?.signal}
          />
          <EvidenceBlock
            label="Rainfall Deviation"
            value={metrics.rainfallDeviation != null && metrics.rainfallDeviation !== 0
              ? `${Math.abs(metrics.rainfallDeviation)}%`
              : 'Normal'}
            subtext={metrics.rainfallSubtext}
            signal={rainfallSignal}
          />
        </div>
      )}

      <PremiumCard title="Weather Correlation" icon={Cloud}>
        <p className="text-sm text-gray-600 leading-relaxed max-w-3xl">
          <BoldText text={weatherText} />
        </p>
      </PremiumCard>

      <div className="space-y-6">
        <h3 className="text-base font-semibold text-gray-900">Supporting Data</h3>

        <PremiumCard title="NDVI Satellite Analysis">
          <NDVIComparison satelliteAnalysis={sat} />
        </PremiumCard>

        <PremiumCard title="Satellite Evidence">
          {(sat?.ndwi_after != null || sat?.lst_celsius_after != null) && (
            <div className="mb-6 space-y-2 text-sm text-gray-600 border-b border-gray-100 pb-4">
              {sat?.ndwi_after != null && (
                <p>
                  <span className="font-medium text-gray-800">NDWI:</span>{' '}
                  <span className="font-mono">{Number(sat.ndwi_after).toFixed(3)}</span>
                  {' — '}
                  {sat.flood_detected_after
                    ? 'Standing water detected (possible flood damage)'
                    : 'No significant standing water detected'}
                </p>
              )}
              {sat?.lst_celsius_after != null && (
                <p>
                  <span className="font-medium text-gray-800">Surface Temperature:</span>{' '}
                  <span className="font-mono">{Number(sat.lst_celsius_after).toFixed(1)}°C</span>
                  {' — '}
                  {sat.heat_stress_after
                    ? 'Heat stress detected on crop surface'
                    : 'Temperature within normal range'}
                </p>
              )}
            </div>
          )}
          <div className="flex flex-col md:flex-row items-center gap-4">
            <div className="flex-1 w-full">
              <p className="text-xs font-medium text-gray-500 mb-2">Before ({sat?.before_date})</p>
              <SatelliteImage src={sat?.before_image_url} alt="Before disaster" fallbackLabel="Before imagery unavailable" />
              <p className="text-xs text-center mt-2 text-gray-500 flex items-center justify-center gap-1.5">
                {beforeCtx && <NDVIIcon name={beforeCtx.icon} className="w-3 h-3" />}
                <span className="font-mono">NDVI {sat?.ndvi_before?.toFixed(3)}</span>
              </p>
            </div>

            <div className="flex flex-col items-center justify-center px-2">
              <ArrowRight className="w-5 h-5 text-gray-400 hidden md:block" />
              <div className="md:hidden w-full h-px bg-gray-200 my-2" />
              <div className="border border-gray-200 rounded-lg px-3 py-2 text-center">
                <p className="text-[11px] text-gray-400 font-medium uppercase tracking-wide">Damage</p>
                <p className="text-lg font-semibold text-gray-900">{damagePct.toFixed(1)}%</p>
              </div>
            </div>

            <div className="flex-1 w-full">
              <p className="text-xs font-medium text-gray-500 mb-2">After ({sat?.after_date})</p>
              <SatelliteImage src={sat?.after_image_url} alt="After disaster" fallbackLabel="After imagery unavailable" />
              <p className="text-xs text-center mt-2 text-gray-500 flex items-center justify-center gap-1.5">
                {afterCtx && <NDVIIcon name={afterCtx.icon} className="w-3 h-3" />}
                <span className="font-mono">NDVI {sat?.ndvi_after?.toFixed(3)}</span>
              </p>
            </div>
          </div>
        </PremiumCard>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <PremiumCard title="Area Verification" icon={Ruler}>
            <p className="text-sm text-gray-500">
              Claimed {result.claimed_area_hectares} ha vs registered {farm?.area_hectares ?? 'N/A'} ha
            </p>
            <p className={`text-sm font-medium mt-3 ${areaMatch ? 'text-green-600' : 'text-red-600'}`}>
              {areaMatch ? 'Area within registered parcel' : 'Area exceeds registered parcel'}
            </p>
          </PremiumCard>

          <PremiumCard title="Fraud Risk" icon={ShieldAlert}>
            <p className={`text-base font-semibold ${
              fraudRisk === 'LOW' ? 'text-green-600' : fraudRisk === 'CRITICAL' ? 'text-red-600' : 'text-amber-600'
            }`}>
              {fraudRisk} risk
            </p>
            {fraud_indicators.length > 0 ? (
              <ul className="text-sm text-gray-500 mt-3 space-y-1.5">
                {fraud_indicators.map((f, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <Circle className="w-1.5 h-1.5 mt-1.5 shrink-0 fill-current" aria-hidden="true" />
                    {f.description}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-500 mt-3">No fraud indicators detected</p>
            )}
          </PremiumCard>
        </div>
      </div>

      {farm && (
        <button
          type="button"
          onClick={() => router.push(`/farms/${farm.id}`)}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-50"
        >
          <MapPin className="w-4 h-4" />
          View {farm.farmer_name}&apos;s Farm Details
        </button>
      )}

      {!hideActions && (
        <div className="flex flex-col sm:flex-row gap-3 pt-4 border-t border-gray-200">
          <button type="button" onClick={handleDownloadReport} className="btn-action-secondary flex-1">
            <Download className="w-4 h-4" />
            Download PDF
          </button>
          <button
            type="button"
            onClick={handleSubmitToPCIC}
            disabled={submitting || !!submitSuccess}
            className="btn-primary flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Upload className="w-4 h-4" />
            {submitting ? 'Submitting...' : submitSuccess ? 'Submitted' : 'Submit to PCIC'}
          </button>
        </div>
      )}
    </div>
  );
}