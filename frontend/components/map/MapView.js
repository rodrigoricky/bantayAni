'use client';

import { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, Polygon, Popup, Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { getNDVIColor, getStatusColors } from '@/lib/ndvi';
import { useSatelliteDate } from '@/lib/SatelliteDateContext';
import FarmPopup from './FarmPopup';

const BASE_LAYERS = {
  satellite: {
    name: 'Satellite (Esri)',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri, Maxar, Earthstar Geographics',
  },
  street: {
    name: 'OpenStreetMap',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap contributors',
  },
  light: {
    name: 'Carto Light',
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; OpenStreetMap &copy; CARTO',
  },
};

function MapBoundsController({ farms }) {
  const map = useMap();
  useEffect(() => {
    if (!farms?.length) return;
    const coords = farms.flatMap((f) => f.polygon?.map(([lng, lat]) => [lat, lng]) || []);
    if (coords.length) {
      map.fitBounds(coords, { padding: [20, 20], maxZoom: 16 });
    }
  }, [farms, map]);
  return null;
}

function MonitoringArea({ farms }) {
  const hull = useMemo(() => {
    if (!farms?.length) return null;
    const lats = farms.map((f) => f.latitude);
    const lngs = farms.map((f) => f.longitude);
    const pad = 0.004;
    return [
      [Math.min(...lats) - pad, Math.min(...lngs) - pad],
      [Math.min(...lats) - pad, Math.max(...lngs) + pad],
      [Math.max(...lats) + pad, Math.max(...lngs) + pad],
      [Math.max(...lats) + pad, Math.min(...lngs) - pad],
    ];
  }, [farms]);

  if (!hull) return null;
  return (
    <Polygon
      positions={hull}
      pathOptions={{ color: '#1d4ed8', weight: 1, dashArray: '6 4', fillOpacity: 0, opacity: 0.6 }}
    />
  );
}

export default function MapView({
  farms = [],
  center = [13.6192, 123.1814],
  ndviTileUrl = null,
  zoom = 15,
  onFarmSelect,
  onFarmClick,
  selectedFarm,
  satellite = true,
  singleFarm,
  highlightFarm,
  hideDateOverlay = false,
  hideLayerSwitcher = false,
  hideLegend = false,
  hideZoomControls = false,
  dateLoading = false,
  drawingMode = false,
  drawingVertices = [],
  onMapClick,
  finishedPolygon,
  editableVertices = null,
  onVertexMove,
}) {
  const handleFarmClick = onFarmClick || onFarmSelect;
  const { satelliteDate } = useSatelliteDate();
  const [baseLayer, setBaseLayer] = useState('satellite');

  const displayFarms = singleFarm ? [singleFarm] : farms;
  const layer = BASE_LAYERS[baseLayer] || BASE_LAYERS.satellite;

  return (
    <div className={`relative w-full h-full min-h-[300px] ${drawingMode ? 'cursor-crosshair' : ''}`}>
      <MapContainer
        center={center}
        zoom={zoom}
        minZoom={11}
        maxZoom={18}
        zoomControl={!hideZoomControls}
        className="w-full h-full z-0"
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom={!drawingMode}
        dragging={!drawingMode}
        doubleClickZoom={!drawingMode}
        touchZoom={!drawingMode}
        boxZoom={!drawingMode}
      >
        <TileLayer attribution={layer.attribution} url={layer.url} maxZoom={19} zIndex={0} />
        {ndviTileUrl && (
          <TileLayer
            url={ndviTileUrl}
            opacity={0.7}
            zIndex={10}
            maxZoom={18}
          />
        )}
        {drawingMode && onMapClick && (
          <MapClickHandler onClick={onMapClick} />
        )}
        <MapBoundsController farms={displayFarms} />
        {!singleFarm && !drawingMode && <MonitoringArea farms={displayFarms} />}
        {drawingVertices.length >= 2 && (
          <Polygon
            positions={drawingVertices.map((v) => [v.lat, v.lng])}
            pathOptions={{ color: '#16a34a', fillColor: '#16a34a', fillOpacity: 0.25, weight: 2, dashArray: '4 4' }}
          />
        )}
        {finishedPolygon?.length >= 3 && (
          <Polygon
            positions={finishedPolygon.map((v) => [v.lat, v.lng])}
            pathOptions={{ color: '#15803d', fillColor: '#16a34a', fillOpacity: 0.4, weight: 2 }}
          />
        )}
        {editableVertices?.map((v, idx) => (
          <Marker
            key={`vertex-${idx}`}
            position={[v.lat, v.lng]}
            draggable
            icon={L.divIcon({
              className: 'vertex-handle',
              iconSize: [14, 14],
              iconAnchor: [7, 7],
              html: '<div style="width:14px;height:14px;border-radius:50%;background:#fff;border:2px solid #15803d;box-shadow:0 1px 3px rgba(0,0,0,0.2);"></div>',
            })}
            eventHandlers={{
              dragend: (e) => {
                const { lat, lng } = e.target.getLatLng();
                onVertexMove?.(idx, { lat, lng });
              },
            }}
          />
        ))}
        {!drawingMode && displayFarms.map((farm) => {
          if (!farm.polygon?.length) return null;
          const positions = farm.polygon.map(([lng, lat]) => [lat, lng]);
          const isUnknown = dateLoading || farm.status === 'UNKNOWN' || farm.health_status === 'unknown';
          const ndviColors = isUnknown
            ? { fill: 'rgba(156, 163, 175, 0.45)', stroke: '#9CA3AF' }
            : getNDVIColor(farm.latest_ndvi);
          const isSelected = selectedFarm?.id === farm.id || highlightFarm?.id === farm.id;
          return (
            <Polygon
              key={farm.id}
              positions={positions}
              pathOptions={{
                color: isSelected ? '#1d4ed8' : ndviColors.stroke,
                fillColor: isSelected ? '#3b82f6' : ndviColors.fill,
                fillOpacity: dateLoading ? 0.3 : (isSelected ? 0.5 : 0.4),
                weight: isSelected ? 3 : 2,
              }}
              eventHandlers={{ click: () => handleFarmClick?.(farm) }}
            >
              <Popup>
                <FarmPopup farm={farm} />
              </Popup>
            </Polygon>
          );
        })}
      </MapContainer>

      {!hideLayerSwitcher && (
        <div className="absolute top-3 left-3 z-[1000] flex gap-1 bg-white/90 backdrop-blur-sm rounded-lg shadow p-1 pointer-events-auto">
          {Object.entries(BASE_LAYERS).map(([key, cfg]) => (
            <button
              key={key}
              type="button"
              onClick={() => setBaseLayer(key)}
              className={`px-2 py-1 text-xs rounded-md transition-colors ${
                baseLayer === key ? 'bg-blue-600 text-white' : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              {cfg.name.split(' ')[0]}
            </button>
          ))}
        </div>
      )}

      {!hideLegend && (
        <div className="absolute bottom-3 left-3 z-[1000] bg-white/90 backdrop-blur-sm rounded-lg shadow px-3 py-2 pointer-events-none text-xs">
          <p className="font-semibold text-gray-800 mb-1">Farm NDVI</p>
          <div className="flex flex-col gap-1">
            <span className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#3b82f6]" /> Selected Farm (blue)</span>
            <span className="flex items-center gap-2"><span className={`w-3 h-3 rounded-full ${getStatusColors('HEALTHY').dot}`} /> Healthy (&gt;0.6)</span>
            <span className="flex items-center gap-2"><span className={`w-3 h-3 rounded-full ${getStatusColors('FAIR').dot}`} /> Fair (0.4-0.6)</span>
            <span className="flex items-center gap-2"><span className={`w-3 h-3 rounded-full ${getStatusColors('WATCH').dot}`} /> Watch (0.2-0.4)</span>
            <span className="flex items-center gap-2"><span className={`w-3 h-3 rounded-full ${getStatusColors('CRITICAL').dot}`} /> Critical (&lt;0.2)</span>
          </div>
        </div>
      )}

      {satellite && !hideDateOverlay && (
        <div className="absolute top-44 left-6 z-[1] bg-white/95 border border-gray-200 rounded-md px-3 py-1.5 shadow-sm pointer-events-none">
          <p className="text-xs text-gray-500">Satellite view</p>
          <p className="text-sm font-semibold text-gray-900 font-mono">{satelliteDate}</p>
        </div>
      )}
    </div>
  );
}

function MapClickHandler({ onClick }) {
  const map = useMap();
  useEffect(() => {
    const handler = (e) => onClick({ lat: e.latlng.lat, lng: e.latlng.lng });
    map.on('click', handler);
    return () => map.off('click', handler);
  }, [map, onClick]);
  return null;
}