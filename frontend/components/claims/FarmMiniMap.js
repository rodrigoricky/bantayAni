'use client';

import dynamic from 'next/dynamic';

const MapView = dynamic(() => import('@/components/map/MapView'), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-gray-100 animate-shimmer" />,
});

export default function FarmMiniMap({ farm }) {
  if (!farm?.polygon) return null;

  return (
    <div className="w-[200px] h-[200px] rounded-lg overflow-hidden border border-gray-300">
      <MapView
        farms={[farm]}
        singleFarm={farm}
        highlightFarm={farm}
        center={[farm.latitude, farm.longitude]}
        zoom={16}
        satellite
        ndviOverlay
      />
    </div>
  );
}