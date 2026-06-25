'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { getUser, getToken } from '@/lib/auth';
import { getDashboardPath } from '@/lib/satelliteView';

const ROLE_PROTECTED = {
  '/dashboard': ['MAO', 'ADMIN'],
  '/farms': ['MAO', 'ADMIN'],
  '/claims': ['MAO', 'ADMIN'],
  '/cases': ['MAO', 'ADMIN'],
  '/pcic/claims-queue': ['PCIC', 'ADMIN'],
  '/pcic/map': ['PCIC', 'ADMIN'],
  '/pcic/analytics': ['PCIC', 'ADMIN'],
  '/pcic/payouts': ['PCIC', 'ADMIN'],
  '/regional/overview': ['DA_REGIONAL', 'ADMIN'],
  '/regional/health': ['DA_REGIONAL', 'ADMIN'],
  '/regional/damage-reports': ['DA_REGIONAL', 'ADMIN'],
  '/regional/advisories': ['DA_REGIONAL', 'ADMIN'],
};

function getBasePath(pathname) {
  if (pathname.startsWith('/farms')) return '/farms';
  if (pathname.startsWith('/cases')) return '/cases';
  if (pathname.startsWith('/pcic/claims-queue')) return '/pcic/claims-queue';
  if (pathname.startsWith('/pcic/map')) return '/pcic/map';
  if (pathname.startsWith('/pcic/analytics')) return '/pcic/analytics';
  if (pathname.startsWith('/pcic/payouts')) return '/pcic/payouts';
  if (pathname.startsWith('/pcic')) return '/pcic/claims-queue';
  if (pathname.startsWith('/regional/health')) return '/regional/health';
  if (pathname.startsWith('/regional/damage-reports')) return '/regional/damage-reports';
  if (pathname.startsWith('/regional/advisories')) return '/regional/advisories';
  if (pathname.startsWith('/regional')) return '/regional/overview';
  return pathname;
}

export default function RoleBasedLayout({ children }) {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (pathname === '/login' || pathname === '/') return;

    const token = getToken();
    const user = getUser();
    if (!token || !user) return;

    if (pathname === '/dashboard') {
      const target = getDashboardPath(user.role);
      if (target !== '/dashboard') {
        router.replace(target);
        return;
      }
    }

    const base = getBasePath(pathname);
    const allowed = ROLE_PROTECTED[base];
    if (allowed && !allowed.includes(user.role)) {
      router.replace(getDashboardPath(user.role));
    }
  }, [pathname, router]);

  return children;
}