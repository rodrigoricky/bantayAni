'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  Home, Wheat, FileText, Settings, LogOut, X, Map, ClipboardList,
  PanelLeftClose, PanelLeftOpen, FolderOpen, Activity, AlertTriangle,
  Megaphone, BarChart3, Banknote,
} from 'lucide-react';
import { logout, getUser } from '@/lib/auth';
import { getSidebarCollapsed, setSidebarCollapsed } from '@/lib/sidebarState';
import LogoutDialog from './LogoutDialog';

const SYSTEM_NAV = {
  label: 'System',
  items: [
    { name: 'Settings', href: '/settings', icon: Settings },
  ],
};

const NAVIGATION_BY_ROLE = {
  MAO: [{ label: 'Main', items: [
    { name: 'Dashboard', href: '/dashboard', icon: Home },
    { name: 'Farms', href: '/farms', icon: Wheat },
    { name: 'Claims', href: '/claims', icon: FileText },
    { name: 'Case Records', href: '/cases', icon: FolderOpen },
    { name: 'Settings', href: '/settings', icon: Settings },
  ]}],
  DA_REGIONAL: [{ label: 'Regional', items: [
    { name: 'Overview', href: '/regional/overview', icon: Map },
    { name: 'Municipality Health', href: '/regional/health', icon: Activity },
    { name: 'Damage Reports', href: '/regional/damage-reports', icon: AlertTriangle },
    { name: 'Advisories', href: '/regional/advisories', icon: Megaphone },
  ]}, SYSTEM_NAV],
  PCIC: [{ label: 'Claims Processing', items: [
    { name: 'Claims Queue', href: '/pcic/claims-queue', icon: ClipboardList },
    { name: 'Map View', href: '/pcic/map', icon: Map },
    { name: 'Analytics', href: '/pcic/analytics', icon: BarChart3 },
    { name: 'Payout Tracking', href: '/pcic/payouts', icon: Banknote },
  ]}, SYSTEM_NAV],
  ADMIN: [{ label: 'Main', items: [
    { name: 'Dashboard', href: '/dashboard', icon: Home },
    { name: 'Farms', href: '/farms', icon: Wheat },
    { name: 'Claims', href: '/claims', icon: FileText },
    { name: 'Case Records', href: '/cases', icon: FolderOpen },
    { name: 'Settings', href: '/settings', icon: Settings },
  ]}],
};

const ROLE_LABELS = {
  MAO: 'Municipal Officer',
  DA_REGIONAL: 'Regional Officer',
  PCIC: 'PCIC Processor',
  ADMIN: 'Administrator',
};

function roleSubtitle(user) {
  const role = user?.role;
  if (role === 'DA_REGIONAL') return 'DA Region V';
  if (role === 'PCIC') return 'PCIC — Bicol Region';
  if (role === 'MAO' || role === 'ADMIN') {
    if (user?.municipality_id?.includes('naga')) return 'Naga City, Camarines Sur';
    const name = user?.municipality_id?.replace(/^[^-]+-/, '').replace(/-/g, ' ');
    return name ? `${name.replace(/\b\w/g, (c) => c.toUpperCase())}, Camarines Sur` : 'Naga City, Camarines Sur';
  }
  return 'Bantay Ani';
}

function NavButton({ item, isActive, onClick, collapsed }) {
  const Icon = item.icon;
  const baseClass = `relative flex items-center h-9 rounded-md text-sm font-medium transition-colors duration-150 w-full ${
    collapsed ? 'justify-center px-0' : 'gap-2.5 px-3'
  }`;
  const activeClass = collapsed
    ? 'bg-gray-100 text-gray-900'
    : 'bg-gray-100 text-gray-900 border-l-2 border-indigo-600 pl-[10px]';
  const inactiveClass = 'text-gray-600 hover:bg-gray-100';

  const content = (
    <>
      <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-gray-900' : 'text-gray-500'}`} />
      {!collapsed && <span className="flex-1 text-left">{item.name}</span>}
    </>
  );

  const className = `${baseClass} ${isActive ? activeClass : inactiveClass}`;

  if (item.href) {
    return (
      <Link
        href={item.href}
        prefetch
        onClick={onClick}
        className={className}
        title={collapsed ? item.name : undefined}
      >
        {content}
      </Link>
    );
  }

  return (
    <button type="button" onClick={onClick} className={className} title={collapsed ? item.name : undefined}>
      {content}
    </button>
  );
}

function UserAvatar({ user }) {
  const initials = user?.first_name && user?.last_name
    ? `${user.first_name[0]}${user.last_name[0]}`
    : (user?.email?.[0]?.toUpperCase() || 'U');

  return (
    <div className="w-8 h-8 rounded-full bg-gray-100 text-gray-700 flex items-center justify-center text-xs font-semibold flex-shrink-0">
      {initials}
    </div>
  );
}

function SidebarContent({
  pathname, onClose, onLogout, navigation, user, collapsed, onToggleCollapse,
}) {
  const isActive = (href) => pathname === href;

  const displayName = user?.first_name && user?.last_name
    ? `${user.first_name} ${user.last_name}`
    : user?.email?.split('@')[0] || 'User';

  const userRole = user?.role || 'MAO';

  const subtitle = roleSubtitle(user);

  return (
    <div className="flex flex-col h-full">
      <div className={`relative flex flex-shrink-0 min-h-[80px] border-b border-gray-100 ${
        collapsed ? 'px-2' : 'px-4 py-3'
      }`}>
        <div className="flex flex-col items-center justify-center w-full">
          <Image
            src="/logo.png"
            alt="Bantay Ani"
            width={140}
            height={48}
            style={{ objectFit: 'contain' }}
            className={collapsed ? 'h-10 w-10' : 'h-auto w-[140px]'}
            priority
          />
          {!collapsed && (
            <p className="text-[11px] text-gray-400 text-center mt-1 leading-tight">{subtitle}</p>
          )}
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="absolute top-2 right-2 p-1.5 text-gray-400 hover:text-gray-600 rounded-md"
            aria-label="Close menu"
          >
            <X className="w-4 h-4" />
          </button>
        ) : (
          <button
            type="button"
            onClick={onToggleCollapse}
            className="absolute top-2 right-2 p-1.5 text-gray-400 hover:text-gray-600 rounded-md transition-colors duration-150 hidden lg:block"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
          </button>
        )}
      </div>

      <nav className={`flex-1 min-h-0 overflow-y-auto ${collapsed ? 'px-2' : 'px-3'} py-3`}>
        {navigation.map((section, idx) => (
          <div key={section.label} className={idx > 0 ? 'mt-6' : ''}>
            {!collapsed && (
              <p className="px-3 text-[11px] font-semibold text-gray-400 uppercase tracking-[0.08em] mb-2">
                {section.label}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => (
                <NavButton
                  key={item.href + item.name}
                  item={item}
                  isActive={isActive(item.href)}
                  onClick={onClose}
                  collapsed={collapsed}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className={`flex-shrink-0 border-t border-gray-200 space-y-1 ${collapsed ? 'p-2' : 'p-4'}`}>
        <button
          type="button"
          onClick={onLogout}
          title={collapsed ? 'Logout' : undefined}
          className={`w-full flex items-center rounded-md text-sm font-medium text-gray-600 hover:bg-gray-100 transition-colors duration-150 h-9 ${
            collapsed ? 'justify-center px-0' : 'gap-2.5 px-3'
          }`}
        >
          <LogOut className="w-4 h-4 text-gray-500" />
          {!collapsed && <span>Logout</span>}
        </button>

        {!collapsed && (
          <div className="flex items-center gap-2.5 px-3 py-2">
            <UserAvatar user={user} />
            <div className="flex-1 min-w-0 text-left">
              <p className="text-sm font-medium text-gray-900 truncate">{displayName}</p>
              <p className="text-xs text-gray-400 truncate">{ROLE_LABELS[userRole] || userRole}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function Sidebar({ mobileOpen, onClose, collapsed, onToggleCollapse }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [showLogout, setShowLogout] = useState(false);

  useEffect(() => {
    setUser(getUser());
  }, [pathname]);

  const userRole = user?.role || 'MAO';
  const navigation = NAVIGATION_BY_ROLE[userRole] || NAVIGATION_BY_ROLE.MAO;

  const handleLogout = () => {
    logout();
    onClose?.();
    setShowLogout(false);
    router.push('/login');
  };

  const widthClass = collapsed ? 'w-[72px]' : 'w-60';

  return (
    <>
      <LogoutDialog isOpen={showLogout} onConfirm={handleLogout} onCancel={() => setShowLogout(false)} />

      <aside className={`hidden md:flex ${widthClass} bg-white border-r border-gray-200 flex-col shrink-0 h-full transition-[width] duration-200 ease-in-out relative`}>
        <SidebarContent
          pathname={pathname}
          onLogout={() => setShowLogout(true)}
          navigation={navigation}
          user={user}
          collapsed={collapsed}
          onToggleCollapse={onToggleCollapse}
        />
      </aside>

      {mobileOpen && <div className="md:hidden fixed inset-0 bg-black/30 z-40" onClick={onClose} />}
      <aside className={`md:hidden fixed left-0 top-0 bottom-0 w-60 bg-white border-r border-gray-200 flex flex-col z-50 h-full transition-transform duration-200 ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <SidebarContent
          pathname={pathname}
          onClose={onClose}
          onLogout={() => setShowLogout(true)}
          navigation={navigation}
          user={user}
          collapsed={false}
          onToggleCollapse={onToggleCollapse}
        />
      </aside>
    </>
  );
}

export function useSidebarCollapse() {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setCollapsed(getSidebarCollapsed());
  }, []);

  const toggle = () => {
    setCollapsed((prev) => {
      const next = !prev;
      setSidebarCollapsed(next);
      return next;
    });
  };

  return { collapsed, toggle };
}