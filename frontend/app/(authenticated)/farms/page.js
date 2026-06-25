'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Search, Filter, Download, TrendingDown, TrendingUp, Wheat, Plus, MoreHorizontal, Pencil,
} from 'lucide-react';
import api from '@/lib/api';
import { getUser, getToken } from '@/lib/auth';
import Badge from '@/components/common/Badge';
import StatCard from '@/components/stats/StatCard';
import { ListPageSkeleton } from '@/components/common/PageSkeleton';
import AddFarmerModal from '@/components/farms/AddFarmerModal';
import Toast from '@/components/common/Toast';
import InsuranceIndicator from '@/components/common/InsuranceIndicator';

function FarmerAvatar({ name }) {
  const initials = name?.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase() || 'F';
  return (
    <div className="w-8 h-8 rounded-full bg-gray-100 text-gray-700 flex items-center justify-center text-xs font-semibold flex-shrink-0">
      {initials}
    </div>
  );
}

export default function FarmsPage() {
  const router = useRouter();
  const [farms, setFarms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showAddModal, setShowAddModal] = useState(false);
  const [editFarm, setEditFarm] = useState(null);
  const [user, setUser] = useState(null);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    const fetchFarms = async () => {
      const token = getToken();
      const currentUser = getUser();
      if (!token || !currentUser) {
        router.push('/login');
        return;
      }
      setUser(currentUser);
      try {
        const response = await api.get(`/farms/municipality/${currentUser.municipality_id}`);
        setFarms(response.data.data.farms);
      } catch (err) {
        if (err.response?.status === 401) router.push('/login');
      } finally {
        setLoading(false);
      }
    };
    fetchFarms();
  }, [router]);

  const filteredFarms = useMemo(() => {
    return farms.filter((farm) => {
      const query = searchQuery.toLowerCase();
      const matchesSearch =
        farm.farmer_name.toLowerCase().includes(query) ||
        farm.rsbsa_number.toLowerCase().includes(query) ||
        farm.id.toLowerCase().includes(query);
      const matchesStatus =
        statusFilter === 'all' || farm.status.toLowerCase() === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [farms, searchQuery, statusFilter]);

  const stats = useMemo(() => ({
    total: farms.length,
    healthy: farms.filter((f) => f.status === 'HEALTHY').length,
    watch: farms.filter((f) => f.status === 'WATCH').length,
    critical: farms.filter((f) => f.status === 'CRITICAL').length,
  }), [farms]);

  const handleExport = () => {
    try {
      const headers = ['Farmer Name', 'RSBSA Number', 'Crop Type', 'Area (ha)', 'NDVI', 'Status'];
      const rows = filteredFarms.map((farm) => [
        `"${farm.farmer_name}"`,
        farm.rsbsa_number,
        farm.crop_type,
        farm.area_hectares,
        farm.latest_ndvi?.toFixed(3) ?? 'N/A',
        farm.status,
      ]);
      const csv = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `farms_export_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      setToast({ message: 'CSV export successful', type: 'success' });
    } catch {
      setToast({ message: 'Export failed', type: 'error' });
    }
  };

  if (loading) {
    return <ListPageSkeleton statCount={4} tableRows={8} />;
  }

  return (
    <>
      {toast && (
        <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />
      )}
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="page-title">Farm Parcels</h1>
            <p className="text-sm text-gray-500 mt-1">{farms.length} registered farms monitored</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setShowAddModal(true)}
              className="btn-primary"
            >
              <Plus className="w-4 h-4" />
              Add Farmer
            </button>
            <button type="button" onClick={handleExport} className="btn-secondary">
              <Download className="w-4 h-4" />
              Export
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard label="Total Farms" value={stats.total} />
          <StatCard label="Healthy" value={stats.healthy} statusVariant="healthy" statusLabel="Healthy" />
          <StatCard label="Watch Zone" value={stats.watch} statusVariant="watch" statusLabel="Watch" />
          <StatCard label="Critical" value={stats.critical} statusVariant="critical" statusLabel="Critical" />
        </div>

        <div className="card-base overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <h3 className="section-title">All Farm Parcels</h3>
            <div className="flex items-center gap-2">
              <div className="relative flex-1 sm:w-56">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search farmers..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="input-base pl-9"
                />
              </div>
              <div className="relative">
                <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="h-9 pl-9 pr-8 text-sm text-gray-700 bg-white border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 appearance-none cursor-pointer"
                >
                  <option value="all">All Status</option>
                  <option value="healthy">Healthy</option>
                  <option value="watch">Watch</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="table-th">Farmer</th>
                  <th className="table-th">Parcel ID</th>
                  <th className="table-th">Crop</th>
                  <th className="table-th">Area</th>
                  <th className="table-th">NDVI</th>
                  <th className="table-th">Status</th>
                  <th className="table-th text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredFarms.map((farm) => (
                  <tr key={farm.id} className="border-b border-gray-200 hover:bg-gray-50 transition-colors duration-150">
                    <td className="table-td">
                      <div className="flex items-center gap-2.5">
                        <FarmerAvatar name={farm.farmer_name} />
                        <div>
                          <p className="text-sm font-medium text-gray-900">
                            {farm.farmer_name}
                            <InsuranceIndicator isInsured={farm.is_insured} />
                          </p>
                          <p className="text-xs text-gray-400 font-mono">{farm.rsbsa_number}</p>
                        </div>
                      </div>
                    </td>
                    <td className="table-td">
                      <button
                        type="button"
                        onClick={() => router.push(`/farms/${farm.id}`)}
                        className="text-sm font-medium text-blue-600 hover:text-blue-700 font-mono"
                      >
                        {farm.id}
                      </button>
                    </td>
                    <td className="table-td">
                      <span className="text-sm text-gray-700">{farm.crop_type}</span>
                    </td>
                    <td className="table-td">
                      <span className="text-sm font-medium text-gray-900">{farm.area_hectares} ha</span>
                    </td>
                    <td className="table-td">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-mono font-medium text-gray-900">
                          {farm.latest_ndvi?.toFixed(3) || 'N/A'}
                        </span>
                        {farm.ndvi_trend != null && (
                          farm.ndvi_trend > 0
                            ? <TrendingUp className="w-3.5 h-3.5 text-green-600" />
                            : <TrendingDown className="w-3.5 h-3.5 text-red-600" />
                        )}
                      </div>
                    </td>
                    <td className="table-td">
                      <Badge variant={farm.status.toLowerCase()} size="sm" />
                    </td>
                    <td className="table-td text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => { setEditFarm(farm); setShowAddModal(true); }}
                          className="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-gray-100 rounded-lg transition-colors duration-150"
                          aria-label="Edit farm"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => router.push(`/farms/${farm.id}`)}
                          className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors duration-150"
                          aria-label="View farm"
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

          {filteredFarms.length === 0 && (
            <div className="py-12 text-center">
              <Wheat className="w-10 h-10 text-gray-300 mx-auto mb-3" />
              <p className="text-sm text-gray-500">No farms found matching your filters</p>
            </div>
          )}

          <div className="border-t border-gray-200 px-5 py-3">
            <p className="text-xs text-gray-400">
              Showing {filteredFarms.length} of {farms.length} farms
            </p>
          </div>
        </div>
      </div>

      <AddFarmerModal
        isOpen={showAddModal}
        onClose={() => { setShowAddModal(false); setEditFarm(null); }}
        municipalityId={user?.municipality_id}
        editFarm={editFarm}
        onSuccess={() => window.location.reload()}
      />
    </>
  );
}