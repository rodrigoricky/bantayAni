'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import AppLayout from '@/components/layout/AppLayout';
import { SatelliteDateProvider } from '@/lib/SatelliteDateContext';
import { getToken } from '@/lib/auth';

export default function AuthenticatedLayout({ children }) {
  const router = useRouter();
  const pathname = usePathname();
  const [authReady, setAuthReady] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace('/login');
      setAuthed(false);
    } else {
      setAuthed(true);
    }
    setAuthReady(true);
  }, [pathname, router]);

  if (!authReady || !authed) {
    return <div className="h-screen w-screen bg-gray-50" aria-hidden="true" />;
  }

  return (
    <SatelliteDateProvider>
      <AppLayout>{children}</AppLayout>
    </SatelliteDateProvider>
  );
}