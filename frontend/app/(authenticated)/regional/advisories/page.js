'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Megaphone, AlertTriangle, CloudRain, Sun, Info } from 'lucide-react';
import api from '@/lib/api';
import { getToken } from '@/lib/auth';
import { PageHeaderSkeleton, CardListSkeleton } from '@/components/common/PageSkeleton';
import Badge from '@/components/common/Badge';

const ADVISORY_REFERENCE_DATE = 'Oct 25, 2024';

const ADVISORY_ICONS = {
  critical: AlertTriangle,
  watch: CloudRain,
  info: Info,
  drought: Sun,
};

function AdvisoryCard({ advisory }) {
  const Icon = ADVISORY_ICONS[advisory.level] || Megaphone;
  const levelColors = {
    critical: 'border-red-200 bg-red-50',
    watch: 'border-amber-200 bg-amber-50',
    info: 'border-blue-200 bg-blue-50',
    drought: 'border-orange-200 bg-orange-50',
  };

  return (
    <div className={`rounded-2xl border p-5 ${levelColors[advisory.level] || 'border-gray-100 bg-white'}`}>
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-white border border-gray-100">
          <Icon className={`w-5 h-5 ${
            advisory.level === 'critical' ? 'text-red-600'
              : advisory.level === 'watch' ? 'text-amber-600'
                : advisory.level === 'drought' ? 'text-orange-600'
                  : 'text-blue-600'
          }`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-sm font-semibold text-gray-900">{advisory.title}</h3>
            <Badge
              variant={advisory.level === 'critical' ? 'critical' : advisory.level === 'watch' ? 'watch' : 'healthy'}
              size="sm"
            >
              {advisory.level}
            </Badge>
          </div>
          <p className="text-sm text-gray-600">{advisory.message}</p>
          <div className="flex items-center gap-3 mt-3 text-xs text-gray-400">
            <span>{advisory.municipality}</span>
            <span className="text-gray-300">|</span>
            <span>{advisory.date}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AdvisoriesPage() {
  const router = useRouter();
  const [healthData, setHealthData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    api.get('/farms/regional/health')
      .then((res) => setHealthData(res.data.data))
      .catch((err) => {
        if (err.response?.status === 401) router.push('/login');
      })
      .finally(() => setLoading(false));
  }, [router]);

  const advisories = useMemo(() => {
    const items = [];
    const municipalities = healthData?.municipalities || [];

    municipalities.forEach((mun) => {
      if (mun.critical_pct > 20 && mun.total_farms > 0) {
        items.push({
          id: `critical-${mun.id}`,
          level: 'critical',
          title: 'Critical Crop Stress Alert',
          message: `${mun.name} has ${mun.stats.critical_count} farms (${mun.critical_pct.toFixed(0)}%) in critical condition. Recommend field validation and farmer outreach.`,
          municipality: mun.name,
          date: ADVISORY_REFERENCE_DATE,
        });
      } else if (mun.critical_pct > 10 && mun.total_farms > 0) {
        items.push({
          id: `watch-${mun.id}`,
          level: 'watch',
          title: 'Elevated Stress Levels',
          message: `${mun.name} shows elevated crop stress. Monitor NDVI trends and prepare contingency advisories for affected farmers.`,
          municipality: mun.name,
          date: ADVISORY_REFERENCE_DATE,
        });
      }
    });

    items.push({
      id: 'regional-rain',
      level: 'watch',
      title: 'Rainfall Monitoring - Region V',
      message: 'Seasonal rainfall patterns in Camarines Sur are being monitored. MAOs should verify flood-prone parcels after heavy rainfall events.',
      municipality: 'Region V (Bicol)',
      date: ADVISORY_REFERENCE_DATE,
    });

    items.push({
      id: 'regional-harvest',
      level: 'info',
      title: 'Harvest Season Advisory',
      message: 'Rice harvest window approaching for Naga City farms. Encourage timely harvest to minimize post-disaster loss documentation gaps.',
      municipality: 'Naga City',
      date: ADVISORY_REFERENCE_DATE,
    });

    if (municipalities.every((m) => m.total_farms === 0)) {
      items.push({
        id: 'onboarding',
        level: 'info',
        title: 'Farm Registration Needed',
        message: 'Pili and Iriga City have no registered farms yet. Onboard municipalities to enable satellite monitoring and damage reporting.',
        municipality: 'Region V (Bicol)',
        date: ADVISORY_REFERENCE_DATE,
      });
    }

    return items;
  }, [healthData]);

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeaderSkeleton />
        <div className="flex flex-wrap gap-3 animate-pulse">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-7 bg-gray-100 rounded-full w-24" />
          ))}
        </div>
        <CardListSkeleton count={4} />
      </div>
    );
  }

  const criticalCount = advisories.filter((a) => a.level === 'critical').length;
  const watchCount = advisories.filter((a) => a.level === 'watch').length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Regional Advisories</h1>
        <p className="text-sm text-gray-500 mt-1">Crop health alerts and guidance for Region V municipalities</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <span className="status-pill text-red-600">
          <AlertTriangle className="w-3 h-3 mr-1" />
          {criticalCount} Critical
        </span>
        <span className="status-pill text-amber-600">
          <CloudRain className="w-3 h-3 mr-1" />
          {watchCount} Watch
        </span>
        <span className="status-pill text-gray-600">
          <Megaphone className="w-3 h-3 mr-1" />
          {advisories.length} Total
        </span>
      </div>

      <div className="space-y-4">
        {advisories.map((advisory) => (
          <AdvisoryCard key={advisory.id} advisory={advisory} />
        ))}
      </div>
    </div>
  );
}