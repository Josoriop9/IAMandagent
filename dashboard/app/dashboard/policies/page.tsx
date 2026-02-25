'use client';

import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

interface Policy {
  id: string;
  tool_name: string;
  allowed: boolean;
  max_amount: number | null;
  requires_approval: boolean;
  created_at: string;
  agent_id: string | null;
  agent_name?: string;
  agent_public_key?: string;
}

interface AgentWithPolicies {
  agent_id: string | null;
  agent_name: string;
  agent_public_key?: string;
  policies: Policy[];
}

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());

  useEffect(() => {
    async function fetchPolicies() {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;

        let orgId: string | null = null;
        const { data: ownedOrg, error: orgError } = await supabase
          .from('organizations')
          .select('id')
          .eq('owner_id', user.id)
          .maybeSingle();
        
        if (ownedOrg) {
          orgId = ownedOrg.id;
        } else {
          const { data: anyOrg } = await supabase
            .from('organizations')
            .select('id')
            .eq('is_active', true)
            .limit(1)
            .maybeSingle();
          
          if (anyOrg) {
            await supabase.from('organizations').update({ owner_id: user.id }).eq('id', anyOrg.id);
            orgId = anyOrg.id;
          }
        }
        
        if (!orgId) {
          console.warn('No organization found for user');
          return;
        }

        const { data, error } = await supabase
          .from('policies')
          .select(`
            *,
            agents(name, public_key)
          `)
          .eq('organization_id', orgId)
          .order('created_at', { ascending: false });

        if (error) throw error;
        
        // Map agent info to policies
        const policiesWithAgents = (data || []).map(policy => ({
          ...policy,
          agent_name: policy.agents?.name || null,
          agent_public_key: policy.agents?.public_key || null
        }));
        setPolicies(policiesWithAgents);
        // ← AGREGA AQUÍ:
        console.log('🔍 First 3 policies:', policies.slice(0, 3).map(p => ({
          tool: p.tool_name,
          agent_id: p.agent_id,
          agent_name: p.agent_name,
          agent_public_key: p.agent_public_key?.substring(0, 16)
        })));
        setPolicies(policiesWithAgents);
      } catch (error) {
        console.error('Error fetching policies:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchPolicies();
  }, []);

  const allowedCount = policies.filter(p => p.allowed).length;
  const deniedCount = policies.filter(p => !p.allowed).length;
  const approvalCount = policies.filter(p => p.requires_approval).length;
  const globalCount = policies.filter(p => p.agent_id === null).length;

  const pieData = [
    { name: 'Allowed', value: allowedCount, color: '#00cc33' },
    { name: 'Denied', value: deniedCount, color: '#ef4444' },
  ].filter(d => d.value > 0);

  const filtered = policies
    .filter(p => {
      if (filter === 'allowed') return p.allowed;
      if (filter === 'denied') return !p.allowed;
      if (filter === 'approval') return p.requires_approval;
      if (filter === 'global') return p.agent_id === null;
      return true;
    })
    .filter(p => !search || p.tool_name.toLowerCase().includes(search.toLowerCase()));

  // Group policies by agent
  const groupedPolicies: AgentWithPolicies[] = [];
  
  // First, add global policies
  const globalPolicies = filtered.filter(p => p.agent_id === null);
  if (globalPolicies.length > 0) {
    groupedPolicies.push({
      agent_id: null,
      agent_name: 'Global Policies',
      agent_public_key: undefined,
      policies: globalPolicies
    });
  }
  
  // Then, group by agent
  const agentMap = new Map<string, AgentWithPolicies>();
  filtered.filter(p => p.agent_id !== null).forEach(policy => {
    const agentId = policy.agent_id!;
    if (!agentMap.has(agentId)) {
      agentMap.set(agentId, {
        agent_id: agentId,
        agent_name: policy.agent_name || 'Unknown Agent',
        agent_public_key: policy.agent_public_key,
        policies: []
      });
    }
    agentMap.get(agentId)!.policies.push(policy);
  });
  
  // Add agent groups to array
  groupedPolicies.push(...Array.from(agentMap.values()));

  const toggleAgent = (agentId: string) => {
    setExpandedAgents(prev => {
      const newSet = new Set(prev);
      if (newSet.has(agentId)) {
        newSet.delete(agentId);
      } else {
        newSet.add(agentId);
      }
      return newSet;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-2 border-matrix-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="font-mono text-matrix-600 text-sm">LOADING POLICIES...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">Policies</h1>
          <p className="text-ink-muted text-sm mt-0.5">
            Governance rules for AI agent operations
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="live-dot"></div>
          <span className="text-xs font-mono text-matrix-600">ENFORCED</span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-4">
          <p className="text-ink-subtle text-xs font-medium uppercase tracking-wide">Total</p>
          <p className="metric-number text-2xl text-ink mt-1">{policies.length}</p>
        </div>
        <div className="card p-4">
          <p className="text-ink-subtle text-xs font-medium uppercase tracking-wide">Allowed</p>
          <p className="metric-number text-2xl text-emerald-600 mt-1">{allowedCount}</p>
        </div>
        <div className="card p-4">
          <p className="text-ink-subtle text-xs font-medium uppercase tracking-wide">Denied</p>
          <p className="metric-number text-2xl text-red-500 mt-1">{deniedCount}</p>
        </div>
        <div className="card p-4">
          <p className="text-ink-subtle text-xs font-medium uppercase tracking-wide">Need Approval</p>
          <p className="metric-number text-2xl text-amber-600 mt-1">{approvalCount}</p>
        </div>
      </div>

      {/* Chart + Info Row */}
      {pieData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Pie Chart */}
          <div className="card p-5">
            <div className="mb-4">
              <h3 className="font-semibold text-ink text-sm">Policy Distribution</h3>
              <p className="text-ink-subtle text-xs mt-0.5">Allow vs Deny</p>
            </div>
            <ResponsiveContainer width="100%" height={140}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={65}
                  dataKey="value"
                  paddingAngle={3}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '12px' }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2 mt-2">
              {pieData.map((entry) => (
                <div key={entry.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ background: entry.color }}></div>
                    <span className="text-xs text-ink-muted">{entry.name}</span>
                  </div>
                  <span className="text-xs font-mono font-medium text-ink">{entry.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Stats */}
          <div className="lg:col-span-2 card p-5">
            <h3 className="font-semibold text-ink text-sm mb-4">Policy Breakdown</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-surface-50 rounded-lg p-3 border border-surface-200">
                <p className="text-xs text-ink-subtle font-medium mb-1 uppercase tracking-wide">Global Policies</p>
                <p className="metric-number text-xl text-ink">{globalCount}</p>
                <p className="text-xs text-ink-subtle mt-1">Apply to all agents</p>
              </div>
              <div className="bg-surface-50 rounded-lg p-3 border border-surface-200">
                <p className="text-xs text-ink-subtle font-medium mb-1 uppercase tracking-wide">Agent-Specific</p>
                <p className="metric-number text-xl text-ink">{policies.length - globalCount}</p>
                <p className="text-xs text-ink-subtle mt-1">Scoped to one agent</p>
              </div>
              <div className="bg-surface-50 rounded-lg p-3 border border-surface-200">
                <p className="text-xs text-ink-subtle font-medium mb-1 uppercase tracking-wide">With Amount Limits</p>
                <p className="metric-number text-xl text-ink">{policies.filter(p => p.max_amount !== null).length}</p>
                <p className="text-xs text-ink-subtle mt-1">Financial restrictions</p>
              </div>
              <div className="bg-surface-50 rounded-lg p-3 border border-surface-200">
                <p className="text-xs text-ink-subtle font-medium mb-1 uppercase tracking-wide">Require Approval</p>
                <p className="metric-number text-xl text-ink">{approvalCount}</p>
                <p className="text-xs text-ink-subtle mt-1">Human-in-the-loop</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filters + Search */}
      <div className="flex flex-col sm:flex-row gap-3">
        {/* Search */}
        <div className="relative flex-1">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-subtle" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search by tool name..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 bg-white border border-surface-200 rounded-xl text-sm
                       text-ink placeholder:text-ink-subtle focus:outline-none focus:border-accent-500
                       focus:ring-1 focus:ring-accent-500/20 transition-all"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex gap-2 flex-wrap">
          {[
            { id: 'all', label: `All (${policies.length})` },
            { id: 'allowed', label: `✓ ${allowedCount}` },
            { id: 'denied', label: `✗ ${deniedCount}` },
            { id: 'approval', label: `⚠ ${approvalCount}` },
            { id: 'global', label: `🌐 ${globalCount}` },
          ].map(f => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`px-3 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
                filter === f.id
                  ? 'bg-ink text-white shadow-sm'
                  : 'bg-white border border-surface-200 text-ink-muted hover:text-ink hover:border-surface-300'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Policies List - Grouped by Agent */}
      {groupedPolicies.length === 0 ? (
        <div className="card p-16 text-center">
          <div className="terminal-box rounded-xl p-8 inline-block mb-6">
            <span className="font-mono text-matrix-500 text-2xl">{'🛡️'}</span>
          </div>
          <h3 className="text-lg font-semibold text-ink mb-2">
            {search || filter !== 'all' ? 'No matching policies' : 'No Policies Yet'}
          </h3>
          <p className="text-ink-muted text-sm mb-6">
            {search || filter !== 'all'
              ? 'Try adjusting your filters'
              : 'Policies are synced when you initialize agents with the SDK'}
          </p>
          {!search && filter === 'all' && (
            <div className="terminal-box rounded-lg p-4 inline-block text-left">
              <p className="font-mono text-xs text-matrix-500">from hashed import HashedCore</p>
              <p className="font-mono text-xs text-terminal-dim mt-1">
                core = HashedCore(config, policies=[...])
              </p>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {groupedPolicies.map((agentGroup) => {
            const agentKey = agentGroup.agent_id || 'global';
            const isExpanded = expandedAgents.has(agentKey);
            const allowedInGroup = agentGroup.policies.filter(p => p.allowed).length;
            const deniedInGroup = agentGroup.policies.filter(p => !p.allowed).length;
            const approvalInGroup = agentGroup.policies.filter(p => p.requires_approval).length;
            
            return (
              <div key={agentKey} className="card overflow-hidden">
                {/* Collapsible Agent Header */}
                <button
                  onClick={() => toggleAgent(agentKey)}
                  className="w-full p-5 flex items-center gap-4 hover:bg-surface-50 transition-colors"
                >
                  {/* Agent Icon */}
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 ${
                    agentGroup.agent_id === null
                      ? 'bg-blue-50 text-blue-600 border border-blue-100'
                      : 'bg-purple-50 text-purple-600 border border-purple-100'
                  }`}>
                    {agentGroup.agent_id === null ? '🌐' : '🤖'}
                  </div>

                  {/* Agent Info */}
                  <div className="flex-1 text-left">
                    <h3 className="font-semibold text-ink text-lg">{agentGroup.agent_name}</h3>
                    <div className="flex items-center gap-3 mt-1">
                      {agentGroup.agent_public_key && (
                        <code className="text-xs text-ink-subtle font-mono">
                          {agentGroup.agent_public_key.substring(0, 20)}...
                        </code>
                      )}
                      {agentGroup.agent_id === null && (
                        <span className="text-xs text-ink-subtle">Apply to all agents</span>
                      )}
                    </div>
                  </div>

                  {/* Summary Stats */}
                  <div className="flex items-center gap-3">
                    <div className="text-center">
                      <p className="text-xs text-ink-subtle uppercase tracking-wide">Policies</p>
                      <p className="text-lg font-semibold text-ink">{agentGroup.policies.length}</p>
                    </div>
                    <div className="w-px h-10 bg-surface-200"></div>
                    <div className="flex gap-2">
                      <div className="bg-emerald-50 px-2 py-1 rounded border border-emerald-100">
                        <span className="text-xs font-medium text-emerald-600">✓ {allowedInGroup}</span>
                      </div>
                      <div className="bg-red-50 px-2 py-1 rounded border border-red-100">
                        <span className="text-xs font-medium text-red-500">✗ {deniedInGroup}</span>
                      </div>
                      {approvalInGroup > 0 && (
                        <div className="bg-amber-50 px-2 py-1 rounded border border-amber-100">
                          <span className="text-xs font-medium text-amber-600">⚠ {approvalInGroup}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Expand/Collapse Icon */}
                  <div className="flex-shrink-0">
                    <svg
                      className={`w-5 h-5 text-ink-muted transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </button>

                {/* Expanded Policy Details */}
                {isExpanded && (
                  <div className="border-t border-surface-200 bg-surface-50">
                    <div className="p-5 space-y-3">
                {agentGroup.policies.map((policy, index) => (
                  <div
                    key={policy.id}
                    className={`card p-5 animate-slide-up stagger-${Math.min(index + 1, 4)}`}
                  >
              <div className="flex items-start justify-between">
                {/* Left: Tool Name + Badges */}
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-ink text-lg font-mono">{policy.tool_name}</h3>
                    <span className={`badge ${policy.allowed ? 'badge-success' : 'badge-danger'}`}>
                      {policy.allowed ? '✓ Allowed' : '✗ Denied'}
                    </span>
                    {policy.requires_approval && (
                      <span className="badge badge-warning">⚠ Requires Approval</span>
                    )}
                    {policy.agent_id === null && (
                      <span className="badge" style={{ background: '#eff6ff', color: '#1e40af', border: '1px solid #bfdbfe' }}>
                        🌐 Global
                      </span>
                    )}
                  </div>

                  {/* Policy Details Grid */}
                  <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
                    {policy.max_amount !== null && (
                      <div className="bg-surface-50 rounded-lg p-3 border border-surface-200">
                        <p className="text-xs text-ink-subtle font-medium uppercase tracking-wide">Max Amount</p>
                        <p className="metric-number text-lg text-ink mt-0.5">
                          ${policy.max_amount.toLocaleString()}
                        </p>
                      </div>
                    )}
                    <div className="bg-surface-50 rounded-lg p-3 border border-surface-200">
                      <p className="text-xs text-ink-subtle font-medium uppercase tracking-wide">Scope</p>
                      <p className="text-sm text-ink mt-0.5">
                        {policy.agent_id ? 'Agent-specific' : 'All agents'}
                      </p>
                    </div>
                    <div className="bg-surface-50 rounded-lg p-3 border border-surface-200">
                      <p className="text-xs text-ink-subtle font-medium uppercase tracking-wide">Created</p>
                      <p className="text-sm text-ink mt-0.5">
                        {new Date(policy.created_at).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                        })}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Right: Status Icon */}
                <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                  policy.allowed
                    ? 'bg-emerald-50 text-emerald-600 border border-emerald-100'
                    : 'bg-red-50 text-red-500 border border-red-100'
                }`}>
                  {policy.allowed ? '✓' : '✗'}
                </div>
              </div>
            </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Info Banner */}
      <div className="terminal-box glass-violet rounded-xl p-4">
        <div className="flex items-start gap-3">
          <span className="text-matrix-500 text-sm flex-shrink-0">💡</span>
          <div>
            <p className="font-mono text-matrix-500 text-xs">POLICY SYNC</p>
            <p className="font-mono text-terminal-dim text-xs mt-1">
              Policies are defined in your agent code and automatically synced to the control plane.
              Changes require restarting your agent to take effect.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
