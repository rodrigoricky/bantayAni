'use client';

import { useState, useEffect, useMemo, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ChevronRight } from 'lucide-react';
import api from '@/lib/api';
import { getToken, getUser } from '@/lib/auth';
import LoadingSpinner from '@/components/common/LoadingSpinner';

function matchesQuery(value, query) {
  if (!value || !query) return false;
  return String(value).toLowerCase().includes(query.toLowerCase());
}

function ResultRow({ title, subtitle, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full flex items-center justify-between px-4 py-4 text-left border-b border-gray-100 last:border-b-0 hover:bg-gray-50 transition-colors"
    >
      <div className="min-w-0">
        <p className="text-[15px] font-semibold text-gray-900 truncate">{title}</p>
        {subtitle && <p className="text-xs text-gray-500 mt-0.5 truncate">{subtitle}</p>}
      </div>
      <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0 ml-3" />
    </button>
  );
}

function GroupSection({ label, children, count }) {
  if (count === 0) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <p className="px-4 py-3 text-sm font-semibold text-gray-400 uppercase tracking-[0.06em] border-b border-gray-200">
        {label}
      </p>
      {children}
    </div>
  );
}

function SearchResultsInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const query = (searchParams.get('q') || '').trim();
  const [farms, setFarms] = useState([]);
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }

    const fetchData = async () => {
      setLoading(true);
      const user = getUser();
      try {
        if (user?.municipality_id) {
          const [farmsRes, claimsRes] = await Promise.all([
            api.get(`/farms/municipality/${user.municipality_id}`),
            api.get('/claims', { params: { municipality_id: user.municipality_id, limit: 100 } }),
          ]);
          setFarms(farmsRes.data.data.farms || []);
          setClaims(claimsRes.data.data.claims || []);
        } else {
          const claimsRes = await api.get('/claims', { params: { limit: 100 } });
          setFarms([]);
          setClaims(claimsRes.data.data.claims || []);
        }
      } catch (err) {
        if (err.response?.status === 401) router.push('/login');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [router]);

  const results = useMemo(() => {
    if (query.length < 2) {
      return { claims: [], farms: [], farmers: [] };
    }

    const matchedClaims = claims.filter((c) =>
      matchesQuery(c.claim_number, query)
      || matchesQuery(c.farmer_name, query)
      || matchesQuery(c.rsbsa_number, query)
    );

    const matchedFarms = farms.filter((f) =>
      matchesQuery(f.id, query)
      || matchesQuery(f.farmer_name, query)
      || matchesQuery(f.rsbsa_number, query)
    );

    const farmerMap = new Map();
    farms.forEach((f) => {
      if (matchesQuery(f.farmer_name, query)) {
        const key = f.rsbsa_number || f.farmer_name;
        if (!farmerMap.has(key)) farmerMap.set(key, f);
      }
    });

    return {
      claims: matchedClaims,
      farms: matchedFarms,
      farmers: Array.from(farmerMap.values()),
    };
  }, [query, claims, farms]);

  if (loading) {
    return <LoadingSpinner size="lg" text="Searching..." className="py-20" />;
  }

  if (query.length < 2) {
    return (
      <div className="text-center py-16">
        <p className="text-sm text-gray-500">Enter at least 2 characters to search</p>
      </div>
    );
  }

  const totalResults = results.claims.length + results.farms.length + results.farmers.length;

  if (totalResults === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-xs text-gray-400">No results found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <GroupSection label="Claims" count={results.claims.length}>
        {results.claims.map((claim) => (
          <ResultRow
            key={claim.id}
            title={claim.claim_number}
            subtitle={`${claim.farmer_name} | ${claim.status}${claim.damage_percentage != null ? ` | ${claim.damage_percentage.toFixed(0)}%` : ''}`}
            onClick={() => router.push(`/case/${claim.id}`)}
          />
        ))}
      </GroupSection>

      <GroupSection label="Farm Parcels" count={results.farms.length}>
        {results.farms.map((farm) => (
          <ResultRow
            key={farm.id}
            title={farm.id}
            subtitle={`${farm.farmer_name} | ${farm.crop_type} | ${farm.area_hectares} ha`}
            onClick={() => router.push(`/farms/${farm.id}`)}
          />
        ))}
      </GroupSection>

      <GroupSection label="Farmers" count={results.farmers.length}>
        {results.farmers.map((farm) => (
          <ResultRow
            key={farm.rsbsa_number || farm.id}
            title={farm.farmer_name}
            subtitle={`${farm.rsbsa_number} | Parcel ${farm.id}`}
            onClick={() => router.push(`/farms/${farm.id}`)}
          />
        ))}
      </GroupSection>
    </div>
  );
}

function SearchHeader() {
  const searchParams = useSearchParams();
  const query = (searchParams.get('q') || '').trim();

  return (
    <div>
      <h1 className="page-title">
        {query.length >= 2 ? `Search Results for "${query}"` : 'Search'}
      </h1>
      {query.length >= 2 && (
        <p className="text-sm text-gray-500 mt-1">Claims, farm parcels, and farmers</p>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <div className="space-y-6">
      <Suspense fallback={<div className="h-10" />}>
        <SearchHeader />
      </Suspense>
      <Suspense fallback={<LoadingSpinner size="lg" text="Searching..." className="py-20" />}>
        <SearchResultsInner />
      </Suspense>
    </div>
  );
}