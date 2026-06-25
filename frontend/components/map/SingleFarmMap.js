'use client';

import { useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, Polygon, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { DEFAULT_SATELLITE_DATE, getSatelliteViewDate } from '@/lib/satelliteView';

function parsePolygon(polygon) {
  if (!polygon) return null;
  if (typeof polygon === 'string') {
    try {
      return JSON.parse(polygon);
    } catch {
      return null;
    }
  }
  return polygon;
}

function FarmAnimator({ farm }) {
  const map = useMap();
  const polygonRef = useRef(null);

  useEffect(() => {
    const coords = parsePolygon(farm?.polygon);
    if (!coords) return;

    const bounds = coords.map(([lng, lat]) => [lat, lng]);
    map.fitBounds(bounds, { padding: [50, 50] });

    const timer = setTimeout(() => {
      if (polygonRef.current) {
        polygonRef.current.setStyle({ weight: 6, fillOpacity: 0.5 });
        setTimeout(() => {
          polygonRef.current?.setStyle({ weight: 3, fillOpacity: 0.35 });
        }, 300);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [farm, map]);

  const coords = parsePolygon(farm?.polygon);
  if (!coords) return null;

  const positions = coords.map(([lng, lat]) => [lat, lng]);
  const ndvi = farm.latest_ndvi ?? 0;
  const statusColor = ndvi >= 0.6 ? '#16a34a' : ndvi >= 0.4 ? '#f59e0b' : '#dc2626';

  return (
    <Polygon
      ref={polygonRef}
      positions={positions}
      pathOptions={{
        color: statusColor,
        fillColor: statusColor,
        fillOpacity: 0.35,
        weight: 3,
        opacity: 1,
      }}
    />
  );
}

export default function SingleFarmMap({ farm }) {
  const [viewDate, setViewDate] = useState(DEFAULT_SATELLITE_DATE);

  useEffect(() => {
    setViewDate(getSatelliteViewDate());
    const onDateChange = (e) => setViewDate(e.detail || getSatelliteViewDate());
    window.addEventListener('satellite-date-changed', onDateChange);
    return () => window.removeEventListener('satellite-date-changed', onDateChange);
  }, []);

  if (!farm?.latitude || !farm?.longitude) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-100">
        <p className="text-gray-500">No location data available</p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      <MapContainer
        center={[farm.latitude, farm.longitude]}
        zoom={16}
        className="w-full h-full"
        zoomControl={false}
      >
        <TileLayer
          key={viewDate}
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          attribution="&copy; Esri"
          maxZoom={19}
        />
        <FarmAnimator farm={farm} />
      </MapContainer>
      <div className="absolute top-3 right-3 z-[1000] bg-white/95 border border-gray-200 rounded-md px-3 py-1.5 shadow-sm pointer-events-none">
        <p className="text-xs text-gray-500">Satellite view</p>
        <p className="text-sm font-semibold text-gray-900 font-mono">{viewDate}</p>
      </div>
    </div>
  );
}