'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Profile {
  id: string;
  profile_name: string;
  whatsapp_number: string | null;
  gateway_status: string;
  personality: string;
  email_accounts: any[];
  enabled_skills: string[];
}

interface User {
  id: string;
  email: string;
  name: string;
  status: string;
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) { router.push('/'); return; }
    
    Promise.all([
      fetch(`${API}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } }),
      fetch(`${API}/api/profiles/me`, { headers: { Authorization: `Bearer ${token}` } }),
    ])
      .then(async ([userRes, profileRes]) => {
        if (!userRes.ok) throw new Error('Auth failed');
        setUser(await userRes.json());
        if (profileRes.ok) setProfile(await profileRes.json());
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function logout() {
    localStorage.removeItem('token');
    router.push('/');
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950">
        <p className="text-zinc-400">Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Top bar */}
      <header className="border-b border-zinc-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">AI Assistant</h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-zinc-400">{user?.name}</span>
          <button onClick={logout} className="text-sm text-zinc-500 hover:text-white">
            Sign Out
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        {error && (
          <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Status Card */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className={`w-3 h-3 rounded-full ${profile?.gateway_status === 'online' ? 'bg-green-400' : 'bg-zinc-600'}`} />
            <h2 className="text-lg font-semibold text-white">
              {profile?.gateway_status === 'online' ? 'Assistant Online' : 'Assistant Offline'}
            </h2>
          </div>
          <p className="text-sm text-zinc-400">
            {profile?.whatsapp_number 
              ? `Connected to WhatsApp: ${profile.whatsapp_number}` 
              : 'WhatsApp not yet connected. Contact support.'}
          </p>
        </div>

        {/* Personality */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
          <h2 className="text-lg font-semibold text-white mb-2">Assistant Personality</h2>
          <p className="text-sm text-zinc-400 bg-zinc-800 rounded-lg p-4 font-mono whitespace-pre-wrap">
            {profile?.personality || 'Default personality'}
          </p>
        </div>

        {/* Connected Accounts */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
          <h2 className="text-lg font-semibold text-white mb-3">Connected Accounts</h2>
          {profile?.email_accounts?.length ? (
            <ul className="space-y-2">
              {profile.email_accounts.map((acct: any, i: number) => (
                <li key={i} className="flex items-center gap-2 text-sm text-zinc-300">
                  <span className="text-green-400">&#10003;</span>
                  {acct.email} ({acct.type})
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-zinc-500">No email accounts connected. Contact support to add one.</p>
          )}
        </div>

        {/* Enabled Skills */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
          <h2 className="text-lg font-semibold text-white mb-3">Enabled Skills</h2>
          <div className="flex flex-wrap gap-2">
            {profile?.enabled_skills?.map(skill => (
              <span key={skill} className="rounded-full bg-zinc-800 px-3 py-1 text-xs text-zinc-300 border border-zinc-700">
                {skill}
              </span>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
