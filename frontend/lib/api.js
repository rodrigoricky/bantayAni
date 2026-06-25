import axios from 'axios';
import { API_URL } from './constants';
import { getToken, logout } from './auth';

export const API_BASE = API_URL;

const CACHE_TTL_MS = 60 * 1000;
const getCache = new Map();

function buildCacheKey(config) {
  const params = config.params ? JSON.stringify(config.params) : '';
  const base = config.baseURL || '';
  return `GET:${base}${config.url}:${params}`;
}

function getCachedResponse(key) {
  const entry = getCache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.timestamp >= CACHE_TTL_MS) {
    getCache.delete(key);
    return null;
  }
  return entry;
}

function setCachedResponse(key, data, headers) {
  getCache.set(key, { data, headers, timestamp: Date.now() });
}

function invalidateGetCache() {
  getCache.clear();
}

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000,
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  const method = (config.method || 'get').toLowerCase();
  if (method !== 'get' || config.skipCache) {
    return config;
  }

  const cacheKey = buildCacheKey(config);
  const cached = getCachedResponse(cacheKey);
  if (cached) {
    config.adapter = () => Promise.resolve({
      data: cached.data,
      status: 200,
      statusText: 'OK',
      headers: cached.headers || {},
      config,
      request: {},
    });
  }

  return config;
});

api.interceptors.response.use(
  (response) => {
    const method = (response.config.method || 'get').toLowerCase();
    if (method === 'get' && !response.config.skipCache) {
      const cacheKey = buildCacheKey(response.config);
      setCachedResponse(cacheKey, response.data, response.headers);
    } else if (['post', 'put', 'patch', 'delete'].includes(method)) {
      invalidateGetCache();
    }
    return response;
  },
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      logout();
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;