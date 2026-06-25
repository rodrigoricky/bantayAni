'use client';

import dynamic from 'next/dynamic';

const MapView = dynamic(() => import('./MapView'), { ssr: false });

const hasGoogleMapsKey = Boolean(process.env.NEXT_PUBLIC_GOOGLE_MAPS_KEY?.trim());

export default function GoogleMapView(props) {
  if (!hasGoogleMapsKey) {
    return <MapView {...props} deferNdviOverlay />;
  }
  return <MapView {...props} deferNdviOverlay />;
}