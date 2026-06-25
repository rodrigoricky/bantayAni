'use client';

import { Polygon } from '@react-google-maps/api';
import { STATUS_COLORS } from '@/lib/constants';

export default function GooglePolygon({ farm, isSelected, onClick }) {
  const color = STATUS_COLORS[farm.status]?.border || '#6b7280';
  const paths = farm.polygon.map(([lng, lat]) => ({ lat, lng }));

  return (
    <Polygon
      paths={paths}
      onClick={() => onClick?.(farm)}
      options={{
        fillColor: isSelected ? '#3b82f6' : color,
        fillOpacity: isSelected ? 0.5 : 0.35,
        strokeColor: isSelected ? '#1d4ed8' : color,
        strokeWeight: isSelected ? 4 : 2,
        strokeOpacity: 1,
        clickable: true,
        editable: false,
      }}
    />
  );
}