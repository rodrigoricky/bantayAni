'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { Eye, EyeOff, Loader2, Copy } from 'lucide-react';
import api from '@/lib/api';
import { saveToken, saveUser, isAuthenticated, getUser } from '@/lib/auth';
import { getDashboardPath } from '@/lib/satelliteView';

const DEMO_ACCOUNTS = [
  { label: 'MAO Officer', email: 'mao.naga@da.gov.ph' },
  { label: 'DA Regional', email: 'regional.x@da.gov.ph' },
  { label: 'PCIC Officer', email: 'pcic.x@pcic.gov.ph' },
];

export default function LoginPage() {
  const router = useRouter();
  const submitRef = useRef(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [copiedEmail, setCopiedEmail] = useState(null);

  useEffect(() => {
    if (isAuthenticated()) {
      const user = getUser();
      if (user?.role) router.replace(getDashboardPath(user.role));
    }
  }, [router]);

  const fillDemoCredentials = (demoEmail) => {
    setEmail(demoEmail);
    setPassword('demo123');
    setError('');
    submitRef.current?.focus();
  };

  const copyEmail = async (demoEmail) => {
    try {
      await navigator.clipboard.writeText(demoEmail);
      setCopiedEmail(demoEmail);
      setTimeout(() => setCopiedEmail(null), 1500);
    } catch {
      /* ignore */
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await api.post('/login', { email, password });
      const { access_token, user } = response.data.data;
      saveToken(access_token);
      saveUser(user);
      router.push(getDashboardPath(user.role));
    } catch (err) {
      setError(err.response?.data?.error || 'Invalid email or password');
      setPassword('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-[420px] bg-white rounded-2xl shadow-md border border-gray-100 p-8">
        <Image
          src="/logo.png"
          alt="Bantay Ani"
          width={140}
          height={48}
          className="mx-auto object-contain"
          priority
        />
        <p className="text-sm text-gray-400 text-center mt-1">Municipal Agricultural Portal</p>

        <form onSubmit={handleSubmit} className="space-y-4 mt-8">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Email Address</label>
            <input
              type="email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); setError(''); }}
              className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
              placeholder="Enter your email"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => { setPassword(e.target.value); setError(''); }}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                placeholder="Enter your password"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2.5 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            ref={submitRef}
            id="submit-btn"
            type="submit"
            disabled={loading}
            className="w-full bg-green-600 hover:bg-green-700 disabled:opacity-60 text-white font-medium rounded-lg py-2.5 transition-colors flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            Sign In
          </button>
        </form>

        <p className="text-xs text-gray-400 text-center mt-6">
          Bantay Ani — Department of Agriculture Philippines
        </p>
      </div>

      <div className="bg-white/80 border border-gray-100 rounded-xl shadow-sm p-4 max-w-[420px] w-full mx-auto mt-4">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Demo Access</p>
        <p className="text-xs text-gray-400 mb-3">All accounts use password: demo123</p>
        {DEMO_ACCOUNTS.map((account) => (
          <div key={account.email} className="flex items-center justify-between py-1.5">
            <button
              type="button"
              onClick={() => fillDemoCredentials(account.email)}
              className="text-xs font-medium text-gray-600 hover:text-green-700 text-left"
            >
              {account.label}
            </button>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => fillDemoCredentials(account.email)}
                className="text-xs font-mono text-gray-500 hover:text-green-700"
              >
                {account.email}
              </button>
              <button
                type="button"
                onClick={() => copyEmail(account.email)}
                className="text-gray-400 hover:text-gray-600"
                aria-label={`Copy ${account.email}`}
              >
                <Copy className="w-3 h-3" />
              </button>
              {copiedEmail === account.email && (
                <span className="text-[10px] text-green-600">Copied!</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}