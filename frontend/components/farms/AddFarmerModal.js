'use client';

import { useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { X, MapPin, RotateCcw, Check } from 'lucide-react';
import api from '@/lib/api';

const MapView = dynamic(() => import('@/components/map/MapView'), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-gray-200 animate-pulse rounded-lg" />,
});

const INITIAL_FORM = {
  farmer_name: '',
  rsbsa_number: '',
  crop_type: 'Rice',
  area_hectares: '',
  insured: false,
};

const NAGA_CENTER = [13.6192, 123.1814];

function polygonAreaHectares(vertices) {
  if (vertices.length < 3) return 0;
  const latMid = vertices.reduce((s, c) => s + c.lat, 0) / vertices.length;
  const mPerDegLat = 111320;
  const mPerDegLng = 111320 * Math.cos((latMid * Math.PI) / 180);
  const xy = vertices.map((c) => ({
    x: c.lng * mPerDegLng,
    y: c.lat * mPerDegLat,
  }));
  let sum = 0;
  for (let i = 0; i < xy.length; i++) {
    const j = (i + 1) % xy.length;
    sum += xy[i].x * xy[j].y - xy[j].x * xy[i].y;
  }
  return Math.abs(sum) / 2 / 10000;
}

function coordsToVertices(polygon) {
  if (!polygon?.length) return [];
  const ring = polygon[0]?.[0] === polygon[polygon.length - 1]?.[0]
    ? polygon.slice(0, -1)
    : polygon;
  return ring.map(([lng, lat]) => ({ lat, lng }));
}

export default function AddFarmerModal({
  isOpen,
  onClose,
  municipalityId,
  onSuccess,
  editFarm = null,
}) {
  const isEdit = Boolean(editFarm);
  const [formData, setFormData] = useState(INITIAL_FORM);
  const [loading, setLoading] = useState(false);
  const [drawingMode, setDrawingMode] = useState(!isEdit);
  const [vertices, setVertices] = useState([]);
  const [finishedPolygon, setFinishedPolygon] = useState(null);
  const [polygonCoords, setPolygonCoords] = useState(null);

  useEffect(() => {
    if (!isOpen) return;
    if (editFarm) {
      const verts = coordsToVertices(editFarm.polygon);
      setFormData({
        farmer_name: editFarm.farmer_name || '',
        rsbsa_number: editFarm.rsbsa_number || '',
        crop_type: editFarm.crop_type || 'Rice',
        area_hectares: String(editFarm.area_hectares || ''),
        insured: editFarm.insured || false,
      });
      setVertices(verts);
      setFinishedPolygon(verts);
      const coords = verts.map((v) => [v.lng, v.lat]);
      if (coords.length) coords.push(coords[0]);
      setPolygonCoords(coords);
      setDrawingMode(false);
    } else {
      setFormData(INITIAL_FORM);
      setVertices([]);
      setFinishedPolygon(null);
      setPolygonCoords(null);
      setDrawingMode(true);

      if (municipalityId) {
        api.get('/farms/next-rsbsa', { params: { municipality_id: municipalityId } })
          .then((res) => {
            const nextRsbsa = res.data?.data?.rsbsa_number;
            if (nextRsbsa) {
              setFormData((prev) => ({ ...prev, rsbsa_number: nextRsbsa }));
            }
          })
          .catch(() => {});
      }
    }
  }, [isOpen, editFarm, municipalityId]);

  const resetDrawing = () => {
    setVertices([]);
    setFinishedPolygon(null);
    setPolygonCoords(null);
    setDrawingMode(true);
    setFormData((prev) => ({ ...prev, area_hectares: '' }));
  };

  const handleMapClick = useCallback(({ lat, lng }) => {
    if (!drawingMode) return;
    setVertices((prev) => [...prev, { lat, lng }]);
  }, [drawingMode]);

  const handleVertexMove = useCallback((index, { lat, lng }) => {
    setVertices((prev) => {
      const next = [...prev];
      next[index] = { lat, lng };
      const coords = next.map((v) => [v.lng, v.lat]);
      coords.push(coords[0]);
      setPolygonCoords(coords);
      setFinishedPolygon(next);
      setFormData((f) => ({ ...f, area_hectares: polygonAreaHectares(next).toFixed(2) }));
      return next;
    });
  }, []);

  const handleFinishDrawing = () => {
    if (vertices.length < 3) {
      alert('Place at least 3 points to define the farm boundary.');
      return;
    }
    const area = polygonAreaHectares(vertices);
    const coords = vertices.map((v) => [v.lng, v.lat]);
    coords.push(coords[0]);
    setFinishedPolygon(vertices);
    setPolygonCoords(coords);
    setDrawingMode(false);
    setFormData((prev) => ({ ...prev, area_hectares: area.toFixed(2) }));
  };

  const mapCenter = vertices.length
    ? [vertices.reduce((s, v) => s + v.lat, 0) / vertices.length, vertices.reduce((s, v) => s + v.lng, 0) / vertices.length]
    : editFarm
      ? [editFarm.latitude, editFarm.longitude]
      : NAGA_CENTER;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!polygonCoords || polygonCoords.length < 4) {
      alert('Please draw the farm boundary on the map before submitting.');
      return;
    }

    setLoading(true);
    try {
      const activeVertices = finishedPolygon || vertices;
      const payload = {
        farmer_name: formData.farmer_name,
        rsbsa_number: formData.rsbsa_number,
        crop_type: formData.crop_type,
        area_hectares: parseFloat(formData.area_hectares),
        municipality_id: municipalityId,
        insured: formData.insured,
        polygon: polygonCoords,
        latitude: activeVertices.reduce((s, v) => s + v.lat, 0) / activeVertices.length,
        longitude: activeVertices.reduce((s, v) => s + v.lng, 0) / activeVertices.length,
      };

      if (isEdit) {
        await api.put(`/farms/${editFarm.id}`, payload);
      } else {
        await api.post('/farms/add', payload);
      }

      setFormData(INITIAL_FORM);
      resetDrawing();
      onSuccess?.();
      onClose();
    } catch (error) {
      const message = error.response?.data?.detail || `Failed to ${isEdit ? 'update' : 'add'} farmer. Please check all fields.`;
      alert(message);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-5xl w-full max-h-[95vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between z-10">
          <h2 className="text-xl font-bold text-gray-900">{isEdit ? 'Edit Farm Parcel' : 'Add New Farmer'}</h2>
          <button type="button" onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6">
          <div className="flex flex-col lg:flex-row gap-6">
            <div className="w-full lg:w-[40%] flex flex-col gap-3">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Farmer Information</p>

              <div>
                <label className="block mb-1.5 text-sm font-medium text-gray-700">
                  Farmer Name <span className="text-red-600">*</span>
                </label>
                <input
                  type="text"
                  value={formData.farmer_name}
                  onChange={(e) => setFormData({ ...formData, farmer_name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Juan Dela Cruz"
                  required
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-sm font-medium text-gray-700">
                    RSBSA Number <span className="text-red-600">*</span>
                  </label>
                  {formData.rsbsa_number && !isEdit && (
                    <span className="text-[11px] text-gray-400">Auto-generated</span>
                  )}
                </div>
                <input
                  type="text"
                  value={formData.rsbsa_number}
                  onChange={(e) => setFormData({ ...formData, rsbsa_number: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="RSBSA-NAG-2024-00005"
                  required
                />
              </div>

              <div>
                <label className="block mb-1.5 text-sm font-medium text-gray-700">
                  Crop Type <span className="text-red-600">*</span>
                </label>
                <select
                  value={formData.crop_type}
                  onChange={(e) => setFormData({ ...formData, crop_type: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="Rice">Rice</option>
                  <option value="Corn">Corn</option>
                  <option value="Banana">Banana</option>
                  <option value="Coconut">Coconut</option>
                  <option value="Cacao">Cacao</option>
                  <option value="Coffee">Coffee</option>
                </select>
              </div>

              <div>
                <label className="block mb-1.5 text-sm font-medium text-gray-700">
                  Farm Area (hectares) <span className="text-red-600">*</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.area_hectares}
                  onChange={(e) => setFormData({ ...formData, area_hectares: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
                  placeholder="Auto-calculated from polygon"
                  required
                  readOnly={!!finishedPolygon}
                />
              </div>

              <div className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <input
                  type="checkbox"
                  id="insured"
                  checked={formData.insured}
                  onChange={(e) => setFormData({ ...formData, insured: e.target.checked })}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-2 focus:ring-blue-500"
                />
                <label htmlFor="insured" className="text-sm font-medium text-gray-900">
                  This farmer is insured with PCIC
                </label>
              </div>
            </div>

            <div className="w-full lg:w-[60%] flex flex-col">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-blue-600" />
                  <p className="text-sm font-medium text-gray-900">
                    {drawingMode ? 'Draw Farm Boundary' : 'Farm Boundary'}
                  </p>
                </div>
                <div className="flex gap-2">
                  {drawingMode && vertices.length >= 3 && (
                    <button
                      type="button"
                      onClick={handleFinishDrawing}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg"
                    >
                      <Check className="w-3.5 h-3.5" />
                      Finish Drawing
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={resetDrawing}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 rounded-lg"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    {isEdit && !drawingMode ? 'Clear and Redraw' : 'Reset'}
                  </button>
                </div>
              </div>

              <div className="relative flex-1 min-h-[400px] border border-gray-200 rounded-xl overflow-hidden">
                {drawingMode && (
                  <div className="absolute top-3 left-1/2 -translate-x-1/2 z-50 bg-white/90 rounded-lg px-4 py-2 text-sm text-gray-700 shadow-md pointer-events-none">
                    Click on the map to place vertices ({vertices.length} placed, need 3+). Then click Finish Drawing.
                  </div>
                )}
                {!drawingMode && finishedPolygon && (
                  <div className="absolute top-3 left-1/2 -translate-x-1/2 z-50 bg-white/90 rounded-lg px-4 py-2 text-sm text-gray-700 shadow-md pointer-events-none">
                    {isEdit ? 'Drag vertices to adjust boundary' : 'Boundary captured'} - {vertices.length} vertices, {formData.area_hectares || 'N/A'} ha
                  </div>
                )}
                <MapView
                  center={mapCenter}
                  zoom={15}
                  farms={[]}
                  drawingMode={drawingMode}
                  drawingVertices={vertices}
                  finishedPolygon={finishedPolygon}
                  editableVertices={!drawingMode && finishedPolygon ? vertices : null}
                  onVertexMove={handleVertexMove}
                  onMapClick={handleMapClick}
                  hideLayerSwitcher
                  hideLegend
                  hideDateOverlay
                />
              </div>
            </div>
          </div>

          <div className="flex gap-3 pt-6 mt-6 border-t border-gray-200">
            <button
              type="submit"
              disabled={loading || !finishedPolygon}
              className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 rounded-lg transition-colors"
            >
              {loading ? (isEdit ? 'Saving...' : 'Adding Farmer...') : (isEdit ? 'Save Changes' : 'Add Farmer')}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-6 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 rounded-lg"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}