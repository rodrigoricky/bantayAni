'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Calendar, Satellite, CheckCircle, AlertCircle, ChevronDown, ArrowRight } from 'lucide-react';
import api from '@/lib/api';
import { getUser, getToken } from '@/lib/auth';
import { consumeClaimPrefill } from '@/lib/claimPrefill';
import InsuranceIndicator from '@/components/common/InsuranceIndicator';

export default function ClaimForm({ onResult, onLoading, onError }) {
  const router = useRouter();
  const wrapperRef = useRef(null);
  const [farms, setFarms] = useState([]);
  const [search, setSearch] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [selectedFarm, setSelectedFarm] = useState(null);
  const [rsbsaNumber, setRsbsaNumber] = useState('');
  const [disasterDate, setDisasterDate] = useState('2024-10-23');
  const [damageType, setDamageType] = useState('typhoon');
  const [claimedArea, setClaimedArea] = useState('');
  const [loading, setLoading] = useState(false);
  const [farmsLoading, setFarmsLoading] = useState(true);
  const [pendingAutostart, setPendingAutostart] = useState(false);
  const autostartTriggered = useRef(false);

  const inputClass =
    'w-full h-9 px-3 text-sm text-gray-900 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-colors duration-150';

  useEffect(() => {
    const fetchFarms = async () => {
      const user = getUser();
      if (!user?.municipality_id || !getToken()) return;
      try {
        const res = await api.get(`/farms/municipality/${user.municipality_id}`);
        const list = res.data.data.farms || [];
        setFarms(list);
      } catch {
        /* ignore */
      } finally {
        setFarmsLoading(false);
      }
    };
    fetchFarms();
  }, []);

  useEffect(() => {
    const prefill = consumeClaimPrefill();
    if (!prefill) return;
    setRsbsaNumber(prefill.rsbsa_number || '');
    setSearch(prefill.rsbsa_number || prefill.farmer_name || '');
    setDisasterDate(prefill.disaster_date || '2024-10-23');
    setDamageType(prefill.damage_type || 'typhoon');
    setClaimedArea(
      prefill.claimed_area_hectares != null
        ? String(prefill.claimed_area_hectares)
        : '',
    );
    if (prefill.autostart) setPendingAutostart(true);
  }, []);

  useEffect(() => {
    if (!pendingAutostart || farmsLoading || autostartTriggered.current) return;
    const farm = farms.find((f) => f.rsbsa_number === rsbsaNumber);
    if (farm) {
      setSelectedFarm(farm);
    }
    const area = claimedArea || (farm ? String(farm.area_hectares) : '');
    if (!rsbsaNumber || !area) return;
    if (!claimedArea && farm) setClaimedArea(String(farm.area_hectares));
    autostartTriggered.current = true;
    setPendingAutostart(false);
    window.requestAnimationFrame(() => {
      const form = document.getElementById('claim-verification-form');
      if (form) form.requestSubmit();
    });
  }, [pendingAutostart, farmsLoading, farms, rsbsaNumber, claimedArea]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectFarm = (farm) => {
    setSelectedFarm(farm);
    setRsbsaNumber(farm.rsbsa_number);
    setSearch(farm.rsbsa_number);
    setDamageType(farm.crop_type === 'Corn' ? 'typhoon' : damageType);
    setClaimedArea(String(farm.area_hectares));
    setDropdownOpen(false);
  };

  const maxClaimableArea = selectedFarm
    ? Math.round(selectedFarm.area_hectares * 100) / 100
    : null;

  const areaError = useMemo(() => {
    if (!selectedFarm || claimedArea === '') return null;
    const parsed = parseFloat(claimedArea);
    if (Number.isNaN(parsed)) return null;
    if (parsed > maxClaimableArea + 0.001) {
      return `Exceeds registered area of ${maxClaimableArea.toFixed(2)} ha.`;
    }
    return null;
  }, [selectedFarm, claimedArea, maxClaimableArea]);

  const filteredFarms = farms.filter((f) => {
    const q = search.toLowerCase();
    if (!q) return true;
    return (
      f.rsbsa_number.toLowerCase().includes(q)
      || f.farmer_name.toLowerCase().includes(q)
      || (f.barangay || f.municipality_id || '').toLowerCase().includes(q)
    );
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!rsbsaNumber) return;
    setLoading(true);
    onLoading?.(true);
    onError?.(null);

    try {
      const response = await api.post('/claims/verify', {
        rsbsa_number: rsbsaNumber,
        disaster_date: disasterDate,
        damage_type: damageType,
        claimed_area_hectares: parseFloat(claimedArea),
      });
      onResult?.(response.data.data);
    } catch (error) {
      const message =
        error.response?.data?.error
        || error.response?.data?.detail
        || (error.response?.status === 404
          ? 'Farm not found or satellite imagery unavailable'
          : 'Verification failed. Please try again.');
      onError?.(message);
      onResult?.(null);
    } finally {
      setLoading(false);
      onLoading?.(false);
    }
  };

  return (
    <div className="card-padded">
      <p className="card-header border-b border-gray-200 pb-3 mb-5">Claim Verification</p>

      <form id="claim-verification-form" onSubmit={handleSubmit} className="space-y-5">
        <div ref={wrapperRef} className="relative">
          <label className="block mb-1.5 text-sm font-medium text-gray-700">RSBSA Number</label>
          <div className="relative">
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setRsbsaNumber(e.target.value);
                setSelectedFarm(null);
                setDropdownOpen(true);
              }}
              onFocus={() => setDropdownOpen(true)}
              className={`${inputClass} pr-10`}
              placeholder="Search or select a farmer..."
              required
              autoComplete="off"
            />
            <ChevronDown className="absolute right-3 top-2.5 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>

          {dropdownOpen && !farmsLoading && filteredFarms.length > 0 && (
            <div className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-md max-h-[300px] overflow-y-auto">
              {filteredFarms.map((farm) => (
                <button
                  key={farm.id}
                  type="button"
                  onClick={() => selectFarm(farm)}
                  className="w-full text-left px-4 py-3 hover:bg-gray-50 border-b border-gray-100 last:border-0"
                >
                  <p className="text-sm">
                    <span className="font-semibold text-gray-900">
                      {farm.farmer_name}
                      <InsuranceIndicator isInsured={farm.is_insured} />
                    </span>
                    {' '}
                    <span className="font-mono text-gray-600">{farm.rsbsa_number}</span>
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {farm.crop_type} | {farm.area_hectares} ha
                  </p>
                </button>
              ))}
            </div>
          )}

          {farmsLoading && (
            <p className="mt-1.5 text-xs text-gray-500">Loading farmers...</p>
          )}

          {selectedFarm && (
            <div className="mt-3 p-4 bg-white border border-gray-200 rounded-lg">
              <div className="flex items-center gap-2 text-green-600 text-sm font-medium mb-2">
                <CheckCircle className="w-4 h-4" />
                Farmer Selected
              </div>
              <p className="font-semibold text-gray-900">
                {selectedFarm.farmer_name}
                <InsuranceIndicator isInsured={selectedFarm.is_insured} />
              </p>
              <p className="text-sm font-mono text-gray-600">{selectedFarm.rsbsa_number}</p>
              <p className="text-sm text-gray-700 mt-1">
                Parcel: {selectedFarm.id} | {selectedFarm.area_hectares} ha {selectedFarm.crop_type}
              </p>
              <button
                type="button"
                onClick={() => router.push(`/farms/${selectedFarm.id}`)}
                className="mt-2 text-sm text-blue-700 hover:underline font-medium"
              >
                <span className="inline-flex items-center gap-1">
                  View Farm Details
                  <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
                </span>
              </button>
            </div>
          )}

          {!selectedFarm && search && !farmsLoading && filteredFarms.length === 0 && (
            <div className="mt-3 p-3 bg-white border border-gray-200 rounded-lg flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-red-600 mt-0.5" />
              <p className="text-sm text-red-600">No matching farmers found.</p>
            </div>
          )}
        </div>

        <div>
          <label className="block mb-1.5 text-sm font-medium text-gray-700">Disaster Date</label>
          <div className="relative">
            <input
              type="date"
              value={disasterDate}
              onChange={(e) => setDisasterDate(e.target.value)}
              className={`${inputClass} pr-10`}
              required
            />
            <Calendar className="absolute right-3 top-2.5 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
        </div>

        <div>
          <label className="block mb-1.5 text-sm font-medium text-gray-700">Damage Type</label>
          <select
            value={damageType}
            onChange={(e) => setDamageType(e.target.value)}
            className={inputClass}
          >
            <option value="flood">Flood</option>
            <option value="drought">Drought</option>
            <option value="typhoon">Typhoon</option>
            <option value="pest">Pest Infestation</option>
            <option value="disease">Crop Disease</option>
            <option value="other">Other</option>
          </select>
        </div>

        <div>
          <label className="block mb-1.5 text-sm font-medium text-gray-700">Claimed Area (hectares)</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            max={maxClaimableArea ?? undefined}
            value={claimedArea}
            onChange={(e) => setClaimedArea(e.target.value)}
            className={`${inputClass}${areaError ? ' border-red-300 focus:ring-red-500' : ''}`}
            placeholder={maxClaimableArea != null ? `Max: ${maxClaimableArea.toFixed(2)} ha` : '2.5'}
            required
          />
          {selectedFarm && (
            <p className="text-xs text-gray-500 mt-1.5">
              Max registered area: {maxClaimableArea.toFixed(2)} ha.
            </p>
          )}
          {areaError && (
            <p className="text-xs text-red-600 mt-1.5">{areaError}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={loading || !rsbsaNumber || Boolean(areaError)}
          className="btn-primary w-full h-10 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
              Analyzing Satellite Data...
            </>
          ) : (
            <>
              <Satellite className="w-4 h-4" />
              Run Satellite Verification
            </>
          )}
        </button>
      </form>
    </div>
  );
}