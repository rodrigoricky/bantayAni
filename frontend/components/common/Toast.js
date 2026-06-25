'use client';

import { useEffect, useState } from 'react';
import { CheckCircle, AlertCircle } from 'lucide-react';

export default function Toast({
  message,
  type = 'success',
  onClose,
  position = 'bottom-right',
  duration = 4000,
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const showTimer = requestAnimationFrame(() => setVisible(true));
    const hideTimer = setTimeout(() => {
      setVisible(false);
      setTimeout(onClose, 300);
    }, duration);
    return () => {
      cancelAnimationFrame(showTimer);
      clearTimeout(hideTimer);
    };
  }, [onClose, duration]);

  const isTopRight = position === 'top-right';
  const positionClass = isTopRight
    ? 'top-4 right-4'
    : 'bottom-24 right-8';

  const bgClass = type === 'success'
    ? 'bg-green-600 text-white'
    : 'bg-red-600 text-white';

  const Icon = type === 'success' ? CheckCircle : AlertCircle;

  return (
    <div
      className={`fixed ${positionClass} z-[9999] flex items-center gap-2 px-4 py-3 rounded-xl shadow-lg transition-transform duration-300 ${bgClass} ${
        visible ? 'translate-x-0' : 'translate-x-full'
      }`}
      role="status"
    >
      <Icon className="w-4 h-4 shrink-0" />
      <span className="text-sm font-medium">{message}</span>
    </div>
  );
}