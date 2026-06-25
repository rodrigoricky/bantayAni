'use client';

import { useState, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Header from './Header';
import Sidebar, { useSidebarCollapse } from './Sidebar';
import ChatWidget from '@/components/chat/ChatWidget';
import { getToken, getUser } from '@/lib/auth';

const PREFETCH_ROUTES_BY_ROLE = {
  MAO: ['/farms', '/claims', '/settings', '/cases'],
  ADMIN: ['/farms', '/claims', '/settings', '/cases'],
  DA_REGIONAL: ['/regional/health', '/regional/damage-reports', '/regional/advisories'],
  PCIC: ['/pcic/map', '/pcic/analytics', '/pcic/payouts'],
};

const CHAT_STORAGE_KEY = 'bantay_ani_chat_history';
const LEGACY_CHAT_KEY = 'bantayani_chat_history';
const MAX_CHAT_MESSAGES = 10;
const CHAT_LIMIT_RESET_MS = 30 * 60 * 1000;

const CHAT_GREETING =
  'Hello, I am BantayANI AI — your satellite crop intelligence assistant. I can help you with NDVI analysis, crop damage assessments, insurance claim guidance, and farm health monitoring for Naga City. How can I assist you today?';

const CHAT_LIMIT_MESSAGE =
  'Chat limit reached. You have used your 10 messages for this session. Please log out and log back in to start a new session, or try again in 30 minutes.';

function loadChatHistory() {
  if (typeof window === 'undefined') return [];
  try {
    const saved = localStorage.getItem(CHAT_STORAGE_KEY) || localStorage.getItem(LEGACY_CHAT_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed)) {
        localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(parsed));
        return parsed;
      }
    }
  } catch {
    /* ignore */
  }
  return [];
}

export default function AppLayout({ children }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [fadeIn, setFadeIn] = useState(true);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [chatMessageCount, setChatMessageCount] = useState(0);
  const [limitReachedAt, setLimitReachedAt] = useState(null);
  const [hasShownGreeting, setHasShownGreeting] = useState(false);
  const { collapsed, toggle: toggleSidebar } = useSidebarCollapse();
  const pathname = usePathname();
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    setIsAuthenticated(!!getToken() && pathname !== '/login');
  }, [pathname]);
  const fullBleed = pathname === '/dashboard';
  const chatLimited = chatMessageCount >= MAX_CHAT_MESSAGES;

  useEffect(() => {
    setChatHistory(loadChatHistory());
  }, []);

  useEffect(() => {
    const user = getUser();
    const role = user?.role || 'MAO';
    const routes = PREFETCH_ROUTES_BY_ROLE[role] || PREFETCH_ROUTES_BY_ROLE.MAO;
    routes.forEach((route) => router.prefetch(route));
  }, [router]);

  useEffect(() => {
    if (!chatLimited || !limitReachedAt) return;

    const interval = setInterval(() => {
      if (Date.now() - limitReachedAt >= CHAT_LIMIT_RESET_MS) {
        setChatMessageCount(0);
        setLimitReachedAt(null);
      }
    }, 60000);

    return () => clearInterval(interval);
  }, [chatLimited, limitReachedAt]);

  useEffect(() => {
    if (!chatOpen || hasShownGreeting) return;

    setHasShownGreeting(true);
    setChatHistory((prev) => {
      if (prev.some((m) => m.isGreeting)) return prev;
      return [
        ...prev,
        {
          role: 'assistant',
          content: CHAT_GREETING,
          timestamp: new Date().toISOString(),
          isGreeting: true,
        },
      ];
    });
  }, [chatOpen, hasShownGreeting]);

  const handleChatMessageSent = () => {
    setChatMessageCount((prev) => {
      const next = prev + 1;
      if (next >= MAX_CHAT_MESSAGES) {
        setLimitReachedAt(Date.now());
      }
      return next;
    });
  };

  useEffect(() => {
    const user = getUser();
    if (!user?.email) return;
    try {
      const storedFor = localStorage.getItem('bantay_ani_chat_user');
      if (storedFor && storedFor !== user.email) {
        setChatHistory([]);
        setChatMessageCount(0);
        setLimitReachedAt(null);
        setHasShownGreeting(false);
        localStorage.removeItem(CHAT_STORAGE_KEY);
        localStorage.removeItem(LEGACY_CHAT_KEY);
      }
      localStorage.setItem('bantay_ani_chat_user', user.email);
    } catch {
      /* ignore */
    }
  }, [pathname]);

  useEffect(() => {
    if (chatHistory.length > 0) {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chatHistory));
    }
  }, [chatHistory]);

  useEffect(() => {
    setFadeIn(false);
    const t = setTimeout(() => setFadeIn(true), 150);
    return () => clearTimeout(t);
  }, [pathname]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-white">
      <Sidebar
        mobileOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
        collapsed={collapsed}
        onToggleCollapse={toggleSidebar}
      />

      <div className="flex flex-1 flex-col min-w-0 min-h-0">
        <Header
          onMenuClick={() => setMobileOpen(true)}
          onAskAI={() => setChatOpen(true)}
        />

        <main className={`flex-1 min-h-0 bg-gray-50 ${fullBleed ? 'overflow-hidden' : 'overflow-y-auto'}`}>
          <div
            className={`transition-opacity duration-150 h-full ${
              fadeIn ? 'opacity-100' : 'opacity-0'
            }`}
          >
            {fullBleed ? children : (
              <div className="px-6 py-6">{children}</div>
            )}
          </div>
        </main>
      </div>

      {isAuthenticated && (
        <ChatWidget
          isOpen={chatOpen}
          onOpenChange={setChatOpen}
          messages={chatHistory}
          onMessagesChange={setChatHistory}
          onMessageSent={handleChatMessageSent}
          messageCount={chatMessageCount}
          maxMessages={MAX_CHAT_MESSAGES}
          limitMessage={CHAT_LIMIT_MESSAGE}
        />
      )}
    </div>
  );
}