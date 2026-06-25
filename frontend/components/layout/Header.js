'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Menu, Search, Sparkles, Bell, Download, Satellite } from 'lucide-react';
import { getUser, getToken } from '@/lib/auth';
import { useSatelliteDate } from '@/lib/SatelliteDateContext';
import { formatLongDate, getDisasterPhaseLabel } from '@/lib/dateUtils';
import api from '@/lib/api';

function locationLabel(user) {
  if (!user) return 'Bantay Ani';
  if (user.role === 'MAO') {
    if (user.municipality_id?.includes('naga')) return 'Naga City, Camarines Sur';
    const name = user.municipality_id?.replace(/^[^-]+-/, '').replace(/-/g, ' ');
    return name ? `${name.replace(/\b\w/g, (c) => c.toUpperCase())}, Camarines Sur` : 'Naga City, Camarines Sur';
  }
  if (user.role === 'DA_REGIONAL') return 'DA Region V - Bicol';
  if (user.role === 'PCIC') return 'PCIC - Region V';
  return 'Bantay Ani';
}

function formatNotificationTime(isoString) {
  if (!isoString) return '';
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString('en-PH', { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

export default function Header({ onMenuClick, onAskAI }) {
  const router = useRouter();
  const { satelliteDate } = useSatelliteDate();
  const [user, setUser] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);
  const prevUnreadRef = useRef(0);
  const audioUnlockedRef = useRef(false);
  const notificationAudioRef = useRef(null);

  const playNotificationSound = useCallback(() => {
    if (!audioUnlockedRef.current) return;
    try {
      if (!notificationAudioRef.current) {
        notificationAudioRef.current = new Audio('/notification-bell.mp3');
        notificationAudioRef.current.volume = 0.5;
      }
      notificationAudioRef.current.currentTime = 0;
      notificationAudioRef.current.play().catch(() => {});
    } catch {
      /* autoplay blocked */
    }
  }, []);

  const fetchNotifications = useCallback(async () => {
    if (!getToken()) return;
    try {
      const res = await api.get('/notifications');
      const data = res.data?.data || {};
      const newUnread = data.unread_count || 0;
      if (newUnread > prevUnreadRef.current) {
        playNotificationSound();
      }
      prevUnreadRef.current = newUnread;
      setNotifications(data.notifications || []);
      setUnreadCount(newUnread);
    } catch {
      // Silently ignore polling errors
    }
  }, [playNotificationSound]);

  useEffect(() => {
    setUser(getUser());
  }, []);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === '/') {
        e.preventDefault();
        document.getElementById('global-search')?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    const unlockAudio = () => {
      audioUnlockedRef.current = true;
      document.removeEventListener('click', unlockAudio);
      document.removeEventListener('keydown', unlockAudio);
    };
    document.addEventListener('click', unlockAudio);
    document.addEventListener('keydown', unlockAudio);
    return () => {
      document.removeEventListener('click', unlockAudio);
      document.removeEventListener('keydown', unlockAudio);
    };
  }, []);

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    if (dropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [dropdownOpen]);

  const handleSearch = (e) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (q.length < 2) return;
    router.push(`/search?q=${encodeURIComponent(q)}`);
  };

  const handleNotificationClick = async (notification) => {
    if (!notification.is_read) {
      try {
        await api.post(`/notifications/${notification.id}/read`);
        setNotifications((prev) =>
          prev.map((n) => (n.id === notification.id ? { ...n, is_read: true } : n))
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
      } catch {
        // Continue navigation even if mark-read fails
      }
    }
    setDropdownOpen(false);
    if (notification.claim_id) {
      router.push(`/case/${notification.claim_id}`);
    }
  };

  return (
    <header className="h-14 bg-white border-b border-gray-200 shrink-0 z-10">
      <div className="flex items-center justify-between h-full px-6 gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onMenuClick}
            className="md:hidden p-2 text-gray-500 hover:text-gray-700 rounded-lg transition-colors duration-150 shrink-0"
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          <form onSubmit={handleSearch} className="hidden sm:flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                id="global-search"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search data"
                className="h-9 w-64 pl-9 pr-14 text-sm text-gray-900 bg-gray-50 border border-gray-200 rounded-lg placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-colors duration-150"
              />
              <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[11px] font-medium text-gray-500 bg-gray-200 px-1.5 py-0.5 rounded">
                Cmd+/
              </span>
            </div>

            <button
              type="button"
              onClick={onAskAI}
              className="hidden md:inline-flex items-center gap-2 h-9 px-3.5 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors duration-150"
            >
              <Sparkles className="w-4 h-4 text-gray-500" />
              Ask AI
            </button>
          </form>

          <p className="sm:hidden text-sm font-semibold text-gray-900 truncate">
            {locationLabel(user)}
          </p>
        </div>

        <div className="hidden md:flex flex-1 justify-center items-center px-4">
          <div className="bg-gray-50 rounded-lg px-4 py-1.5 border border-gray-100 flex items-center gap-2 text-sm font-medium text-gray-600">
            <Satellite className="w-3.5 h-3.5 text-gray-500 shrink-0" />
            <span>
              {formatLongDate(satelliteDate)} — {getDisasterPhaseLabel(satelliteDate)}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <p className="hidden lg:block text-sm font-medium text-gray-700 mr-2">
            {locationLabel(user)}
          </p>

          <div className="relative" ref={dropdownRef}>
            <button
              type="button"
              onClick={() => setDropdownOpen((open) => !open)}
              className="relative p-2 text-gray-500 hover:text-gray-700 rounded-lg transition-colors duration-150"
              aria-label="Notifications"
              aria-expanded={dropdownOpen}
            >
              <Bell className="w-5 h-5" />
              {unreadCount > 0 && (
                <span className="absolute top-1 right-1 min-w-[18px] h-[18px] flex items-center justify-center text-[10px] font-bold text-white bg-red-500 rounded-full px-1">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>

            {dropdownOpen && (
              <div className="absolute right-0 mt-2 w-80 bg-white border border-gray-200 rounded-xl shadow-lg z-50 overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-100">
                  <p className="text-sm font-semibold text-gray-900">Notifications</p>
                  {unreadCount > 0 && (
                    <p className="text-xs text-gray-500 mt-0.5">{unreadCount} unread</p>
                  )}
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <p className="px-4 py-6 text-sm text-gray-500 text-center">No notifications yet</p>
                  ) : (
                    notifications.map((notification) => (
                      <button
                        key={notification.id}
                        type="button"
                        onClick={() => handleNotificationClick(notification)}
                        className={`w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors duration-150 ${
                          !notification.is_read ? 'bg-indigo-50/50' : ''
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          {!notification.is_read && (
                            <span className="mt-1.5 w-2 h-2 rounded-full bg-indigo-500 shrink-0" />
                          )}
                          <div className={notification.is_read ? 'pl-4' : ''}>
                            <p className="text-sm font-medium text-gray-900 line-clamp-1">
                              {notification.title}
                            </p>
                            <p className="text-xs text-gray-600 mt-0.5 line-clamp-2">
                              {notification.message}
                            </p>
                            <p className="text-[11px] text-gray-400 mt-1">
                              {formatNotificationTime(notification.created_at)}
                            </p>
                          </div>
                        </div>
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={() => router.push('/farms')}
            className="hidden sm:inline-flex items-center gap-2 h-9 px-3.5 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors duration-150"
          >
            <Download className="w-4 h-4 text-gray-500" />
            Export
          </button>
        </div>
      </div>
    </header>
  );
}