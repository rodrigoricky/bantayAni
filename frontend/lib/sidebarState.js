const STORAGE_KEY = 'bantay_ani_sidebar_collapsed';

export function getSidebarCollapsed() {
  if (typeof window === 'undefined') return false;
  try {
    return localStorage.getItem(STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

export function setSidebarCollapsed(collapsed) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, collapsed ? 'true' : 'false');
  } catch {
    /* ignore */
  }
}