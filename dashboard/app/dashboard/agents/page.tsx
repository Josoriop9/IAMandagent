'use client';

import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';

interface Agent {
  id: string;
  name: string;
  agent_type: string;
  public_key: string;
  is_active: boolean;
  created_at: string;
  last_seen_at: string | null;
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    async function fetchAgents() {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;

        let orgId: string | null = null;
        const { data: ownedOrg } = await supabase
          .from('organizations').select('id').eq('owner_id', user.id).single();
        if (ownedOrg) {
          orgId = ownedOrg.id;
        } else {
          const { data: anyOrg } = await supabase
            .from('organizations').select('id').eq('is_active', true).limit(1).single();
          if (anyOrg) {
            await supabase.from('organizations').update({ owner_id: user.id }).eq('id', anyOrg.id);
            orgId = anyOrg.id;
          }
        }
        if (!orgId) return;

        const { data } = await supabase
          .from('agents').select('*').eq('organization_id', orgId)
          .order('created_at', { ascending: false });

        setAgents(data || []);
      } catch (error) {
        console.error('Error fetching agents:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchAgents();
  }, []);

  const filtered = agents.filter(a =>
    a.name.toLowerCase().includes(search.toLowerCase()) ||
    a.agent_type.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-2 border-matrix-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="font-mono text-matrix-600 text-sm">LOADING AGENTS...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">Agents</h1>
          <p className="text-ink-muted text-sm mt-0.5">
            AI agents registered with the control plane
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="badge badge-matrix">{agents.length} registered</span>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card p-4 text-center">
          <p className="metric-number text-2xl text-ink">{agents.length}</p>
          <p className="text-ink-subtle text-xs mt-1">Total Agents</p>
        </div>
        <div className="card p-4 text-center">
          <p className="metric-number text-2xl text-emerald-600">{agents.filter(a => a.is_active).length}</p>
          <p className="text-ink-subtle text-xs mt-1">Active</p>
        </div>
        <div className="card p-4 text-center">
          <p className="metric-number text-2xl text-ink-muted">{agents.filter(a => !a.is_active).length}</p>
          <p className="text-ink-subtle text-xs mt-1">Inactive</p>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-subtle" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          type="text"
          placeholder="Search agents..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2.5 bg-white border border-surface-200 rounded-xl text-sm
                     text-ink placeholder:text-ink-subtle focus:outline-none focus:border-accent-500
                     focus:ring-1 focus:ring-accent-500/20 transition-all"
        />
      </div>

      {/* Agents Grid */}
      {filtered.length === 0 ? (
        <div className="card p-16 text-center">
          <div className="terminal-box rounded-xl p-8 inline-block mx-auto mb-6">
            <span className="font-mono text-matrix-500 text-2xl">{'> _'}</span>
          </div>
          <h3 className="text-lg font-semibold text-ink mb-2">
            {search ? 'No agents found' : 'No Agents Yet'}
          </h3>
          <p className="text-ink-muted text-sm mb-6">
            {search ? 'Try a different search term' : 'Register your first agent using the Hashed SDK'}
          </p>
          {!search && (
            <code className="terminal-box rounded-lg px-4 py-2 text-sm text-matrix-500 inline-block">
              from hashed import HashedCore
            </code>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filtered.map((agent, index) => (
            <div
              key={agent.id}
              className={`card p-5 animate-slide-up stagger-${Math.min(index + 1, 4)} hover:border-matrix-500/20`}
            >
              <div className="flex items-start justify-between">
                {/* Left: Identity */}
                <div className="flex items-center gap-4">
                  {/* Avatar */}
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0
                    ${agent.is_active
                      ? 'bg-matrix-500/10 border border-matrix-500/30'
                      : 'bg-surface-100 border border-surface-200'
                    }`}>
                    <svg className={`w-6 h-6 ${agent.is_active ? 'text-matrix-600' : 'text-ink-subtle'}`}
                      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 6.75v10.5a2.25 2.25 0 002.25 2.25zm.75-12h9v9h-9v-9z" />
                    </svg>
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-ink">{agent.name}</h3>
                      <span className={`badge ${agent.is_active ? 'badge-success' : ''}`}
                        style={!agent.is_active ? { background: '#f1f5f9', color: '#94a3b8', border: '1px solid #e2e8f0' } : {}}>
                        {agent.is_active ? '● Active' : '○ Inactive'}
                      </span>
                      <span className="badge" style={{ background: '#f0f9ff', color: '#0369a1', border: '1px solid #bae6fd' }}>
                        {agent.agent_type}
                      </span>
                    </div>
                    <p className="text-ink-subtle text-xs mt-1">
                      Registered {new Date(agent.created_at).toLocaleDateString('en-US', {
                        year: 'numeric', month: 'short', day: 'numeric'
                      })}
                    </p>
                  </div>
                </div>

                {/* Right: Status dot */}
                {agent.is_active && (
                  <div className="animate-pulse-green w-2 h-2 rounded-full bg-matrix-500 mt-1" />
                )}
              </div>

              {/* Keys section */}
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="bg-surface-50 rounded-lg p-3 border border-surface-200">
                  <p className="text-xs font-medium text-ink-subtle mb-1.5 uppercase tracking-wide">Public Key</p>
                  <code className="font-mono text-xs text-matrix-600 bg-matrix-500/5 px-2 py-1 rounded border border-matrix-500/20">
                    {agent.public_key.substring(0, 20)}...{agent.public_key.slice(-8)}
                  </code>
                </div>
                <div className="bg-surface-50 rounded-lg p-3 border border-surface-200">
                  <p className="text-xs font-medium text-ink-subtle mb-1.5 uppercase tracking-wide">Agent ID</p>
                  <code className="font-mono text-xs text-accent-600 bg-accent-50 px-2 py-1 rounded border border-accent-100">
                    {agent.id.substring(0, 8)}...{agent.id.slice(-4)}
                  </code>
                </div>
              </div>

              {/* Footer */}
              <div className="mt-3 pt-3 border-t border-surface-100 flex items-center justify-between text-xs text-ink-subtle">
                <span className="font-mono">
                  Last seen: {agent.last_seen_at
                    ? new Date(agent.last_seen_at).toLocaleString()
                    : 'Never'
                  }
                </span>
                <div className="flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5 text-matrix-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                  </svg>
                  <span className="text-matrix-600">Cryptographically verified</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info Banner */}
      <div className="terminal-box rounded-xl p-4 scanlines">
        <div className="flex items-start gap-3">
          <span className="text-matrix-500 font-mono text-sm mt-0.5">$</span>
          <div>
            <p className="font-mono text-matrix-500 text-sm">Agent registration</p>
            <p className="font-mono text-terminal-dim text-xs mt-1">
              {`from hashed import HashedCore`}
            </p>
            <p className="font-mono text-terminal-dim text-xs">
              {`core = HashedCore(config=config, agent_name="My Agent")`}
            </p>
            <p className="font-mono text-terminal-dim text-xs">
              {`await core.initialize()  # Auto-registers with control plane`}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
