'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Client {
  id: string;
  email: string;
  name: string;
  status: string;
  plan: string;
  subscription_status: string;
  profile_name: string | null;
  gateway_status: string | null;
  created_at: string | null;
}

export default function AdminPage() {
  const router = useRouter();
  const [clients, setClients] = useState<Client[]>([]);
  const [stats, setStats] = useState({ total_clients: 0, active_clients: 0 });
  const [loading, setLoading] = useState(true);

  // New client form
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ email: '', name: '', whatsapp_number: '', plan: 'starter' });
  const [creating, setCreating] = useState(false);

  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : '';

  useEffect(() => {
    if (!token) { router.push('/'); return; }
    Promise.all([
      fetch(`${API}/api/admin/clients`, { headers: { Authorization: `Bearer ${token}` } }),
      fetch(`${API}/api/admin/stats`, { headers: { Authorization: `Bearer ${token}` } }),
    ])
      .then(async ([clientsRes, statsRes]) => {
        if (clientsRes.ok) setClients(await clientsRes.json());
        if (statsRes.ok) setStats(await statsRes.json());
      })
      .finally(() => setLoading(false));
  }, []);

  async function createClient(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const res = await fetch(`${API}/api/admin/clients/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed');
      alert(`Client created! Profile: ${data.profile_name}\nTemp password: ${data.temp_password}`);
      setShowForm(false);
      setForm({ email: '', name: '', whatsapp_number: '', plan: 'starter' });
      // Refresh list
      window.location.reload();
    } catch (e: any) {
      alert(e.message);
    } finally {
      setCreating(false);
    }
  }

  if (loading) return <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-zinc-400">Loading...</div>;

  return (
    <div className="min-h-screen bg-zinc-950">
      <header className="border-b border-zinc-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-white">Admin Panel</h1>
          <p className="text-xs text-zinc-500">{stats.active_clients} active / {stats.total_clients} total clients</p>
        </div>
        <div className="flex gap-3">
          <button onClick={() => setShowForm(!showForm)} className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-black hover:bg-zinc-200">
            + New Client
          </button>
          <button onClick={() => { localStorage.removeItem('token'); router.push('/'); }} className="text-sm text-zinc-500 hover:text-white">
            Sign Out
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        {/* New Client Form */}
        {showForm && (
          <div className="mb-8 rounded-xl border border-zinc-700 bg-zinc-900 p-6">
            <h2 className="text-lg font-semibold text-white mb-4">Provision New Client</h2>
            <form onSubmit={createClient} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <input type="text" placeholder="Full name" required value={form.name}
                  onChange={e => setForm({...form, name: e.target.value})}
                  className="rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 text-white text-sm placeholder-zinc-500 outline-none focus:border-zinc-500" />
                <input type="email" placeholder="Email" required value={form.email}
                  onChange={e => setForm({...form, email: e.target.value})}
                  className="rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 text-white text-sm placeholder-zinc-500 outline-none focus:border-zinc-500" />
                <input type="text" placeholder="WhatsApp number (+1...)" required value={form.whatsapp_number}
                  onChange={e => setForm({...form, whatsapp_number: e.target.value})}
                  className="rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 text-white text-sm placeholder-zinc-500 outline-none focus:border-zinc-500" />
                <select value={form.plan}
                  onChange={e => setForm({...form, plan: e.target.value})}
                  className="rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 text-white text-sm outline-none focus:border-zinc-500">
                  <option value="starter">Starter - $49/mo</option>
                  <option value="pro">Pro - $149/mo</option>
                  <option value="enterprise">Enterprise - $499/mo</option>
                </select>
              </div>
              <div className="flex gap-3">
                <button type="submit" disabled={creating}
                  className="rounded-lg bg-white px-6 py-3 text-sm font-semibold text-black hover:bg-zinc-200 disabled:opacity-50">
                  {creating ? 'Creating...' : 'Create Client + Profile'}
                </button>
                <button type="button" onClick={() => setShowForm(false)}
                  className="rounded-lg border border-zinc-700 px-6 py-3 text-sm text-zinc-400 hover:text-white">
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Client Table */}
        <div className="rounded-xl border border-zinc-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-zinc-900 border-b border-zinc-800">
              <tr className="text-left text-zinc-400">
                <th className="px-4 py-3 font-medium">Client</th>
                <th className="px-4 py-3 font-medium">Plan</th>
                <th className="px-4 py-3 font-medium">WhatsApp</th>
                <th className="px-4 py-3 font-medium">Gateway</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {clients.map(client => (
                <tr key={client.id} className="border-b border-zinc-800/50 hover:bg-zinc-900/50">
                  <td className="px-4 py-3">
                    <p className="text-white font-medium">{client.name}</p>
                    <p className="text-xs text-zinc-500">{client.email}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-zinc-800 px-2 py-1 text-xs text-zinc-300 capitalize">
                      {client.plan}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-zinc-400 font-mono text-xs">
                    {client.profile_name ? 'Connected' : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1.5 text-xs ${client.gateway_status === 'online' ? 'text-green-400' : 'text-zinc-500'}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${client.gateway_status === 'online' ? 'bg-green-400' : 'bg-zinc-600'}`} />
                      {client.gateway_status || 'pending'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-1 text-xs ${
                      client.status === 'active' ? 'bg-green-500/10 text-green-400' :
                      client.status === 'suspended' ? 'bg-yellow-500/10 text-yellow-400' :
                      'bg-zinc-800 text-zinc-500'
                    }`}>
                      {client.status}
                    </span>
                  </td>
                </tr>
              ))}
              {clients.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-zinc-500">
                    No clients yet. Create your first one above.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
