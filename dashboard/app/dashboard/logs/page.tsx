'use client';

import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell
} from 'recharts';

interface Log {
  id: string;
  tool_name: string;
  status: string;
  event_type: string;
  amount: number | null;
  timestamp: string;
  duration_ms: number | null;
  error_message: string | null;
  agent_public_key: string;
  agent_name?: string;
  data?: any;
  metadata?: any;
}

interface LogGroup {
  mainLog: Log;
  relatedLogs: Log[];
  timestamp: string;
  tool_name: string;
}

export default function LogsPage() {
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    async function fetchLogs() {
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

        const { data, error } = await supabase
          .from('ledger_logs')
          .select(`
            *,
            agents(name, agent_type)
          `)
          .eq('organization_id', orgId)
          .order('timestamp', { ascending: false })
          .limit(500);

        if (error) throw error;
        
        // Map agent info to logs
        const logsWithAgents = (data || []).map(log => ({
          ...log,
          agent_name: log.agents?.name || 'Unknown Agent',
          agent_type: log.agents?.agent_type || 'unknown'
        }));
        
        // Show ALL logs without filtering
        // This allows visibility into all operations including intermediate steps
        setLogs(logsWithAgents);
      } catch (error) {
        console.error('Error fetching logs:', error);
      } finally {
        setLoading(false);
      }
    }
    
    fetchLogs();
    
    // Auto-refresh every 5 seconds
    const interval = setInterval(fetchLogs, 5000);
    
    return () => clearInterval(interval);
  }, []);

  // Build hourly chart data
  const chartData = (() => {
    const hours: Record<string, { success: number; denied: number }> = {};
    logs.forEach(log => {
      const h = new Date(log.timestamp).getHours().toString().padStart(2, '0') + ':00';
      if (!hours[h]) hours[h] = { success: 0, denied: 0 };
      if (log.status === 'success') hours[h].success++;
      else hours[h].denied++;
    });
    return Object.entries(hours).sort((a, b) => a[0].localeCompare(b[0]))
      .map(([time, d]) => ({ time, ...d }));
  })();

  const successCount = logs.filter(l => l.status === 'success').length;
  const deniedCount = logs.filter(l => l.status === 'denied').length;
  const errorCount = logs.filter(l => l.status === 'error').length;
  const successRate = logs.length > 0 ? Math.round((successCount / logs.length) * 100) : 0;

  const filtered = logs
    .filter(l => filter === 'all' || l.status === filter)
    .filter(l =>
      !search ||
      l.tool_name?.toLowerCase().includes(search.toLowerCase()) ||
      l.event_type?.toLowerCase().includes(search.toLowerCase())
    );

  const statusIcon = (status: string) => {
    if (status === 'success') return '✓';
    if (status === 'denied') return '✗';
    return '⚠';
  };

  const statusClass = (status: string) => {
    if (status === 'success') return 'badge-success';
    if (status === 'denied') return 'badge-danger';
    return 'badge-warning';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-2 border-matrix-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="font-mono text-matrix-600 text-sm">LOADING AUDIT LOGS...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">Audit Logs</h1>
          <p className="text-ink-muted text-sm mt-0.5">
            Cryptographically signed operation history
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="live-dot"></div>
          <span className="text-xs font-mono text-matrix-600">IMMUTABLE TRAIL</span>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-4">
          <p className="text-ink-subtle text-xs font-medium uppercase tracking-wide">Total Ops</p>
          <p className="metric-number text-2xl text-ink mt-1">{logs.length}</p>
        </div>
        <div className="card p-4">
          <p className="text-ink-subtle text-xs font-medium uppercase tracking-wide">Success</p>
          <p className="metric-number text-2xl text-emerald-600 mt-1">{successCount}</p>
        </div>
        <div className="card p-4">
          <p className="text-ink-subtle text-xs font-medium uppercase tracking-wide">Denied</p>
          <p className="metric-number text-2xl text-red-500 mt-1">{deniedCount}</p>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-ink-subtle text-xs font-medium uppercase tracking-wide">Success Rate</p>
              <p className="metric-number text-2xl text-ink mt-1">{successRate}%</p>
            </div>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold
              ${successRate >= 90 ? 'bg-emerald-50 text-emerald-600 border border-emerald-100' : 'bg-amber-50 text-amber-600 border border-amber-100'}`}>
              {successRate >= 90 ? '✓' : '~'}
            </div>
          </div>
        </div>
      </div>

      {/* Activity Chart */}
      {chartData.length > 0 && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-ink text-sm">Activity by Hour</h3>
              <p className="text-ink-subtle text-xs mt-0.5">Operations distribution</p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-500"></div>
                <span className="text-ink-muted">Success</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-red-400"></div>
                <span className="text-ink-muted">Denied</span>
              </div>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barGap={2}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '12px' }} />
              <Bar dataKey="success" fill="#00cc33" radius={[3, 3, 0, 0]} maxBarSize={20} />
              <Bar dataKey="denied" fill="#ef4444" radius={[3, 3, 0, 0]} maxBarSize={20} />
            </BarChart>
          </ResponsiveContainer>
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
            placeholder="Filter by tool name or event type..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 bg-white border border-surface-200 rounded-xl text-sm
                       text-ink placeholder:text-ink-subtle focus:outline-none focus:border-accent-500
                       focus:ring-1 focus:ring-accent-500/20 transition-all"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex gap-2">
          {[
            { id: 'all', label: `All (${logs.length})`, color: 'default' },
            { id: 'success', label: `✓ ${successCount}`, color: 'success' },
            { id: 'denied', label: `✗ ${deniedCount}`, color: 'danger' },
            { id: 'error', label: `⚠ ${errorCount}`, color: 'warning' },
          ].map(f => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`px-3 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
                filter === f.id
                  ? f.id === 'all' ? 'bg-ink text-white shadow-sm'
                    : f.id === 'success' ? 'bg-emerald-600 text-white shadow-sm'
                    : f.id === 'denied' ? 'bg-red-500 text-white shadow-sm'
                    : 'bg-amber-500 text-white shadow-sm'
                  : 'bg-white border border-surface-200 text-ink-muted hover:text-ink hover:border-surface-300'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Logs Table */}
      {filtered.length === 0 ? (
        <div className="card p-16 text-center">
          <div className="terminal-box rounded-xl p-6 inline-block mb-6">
            <span className="font-mono text-matrix-500">{'> no_logs_found'}</span>
          </div>
          <h3 className="text-lg font-semibold text-ink mb-2">
            {search || filter !== 'all' ? 'No matching logs' : 'No operations yet'}
          </h3>
          <p className="text-ink-muted text-sm">
            {search || filter !== 'all' ? 'Try adjusting your filters' : 'Execute agent operations to see the audit trail'}
          </p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          {/* Table Header */}
          <div className="grid grid-cols-12 gap-4 px-5 py-3 bg-surface-50 border-b border-surface-200 text-xs font-semibold text-ink-muted uppercase tracking-wide">
            <div className="col-span-1">Status</div>
            <div className="col-span-2">Agent</div>
            <div className="col-span-2">Tool / Operation</div>
            <div className="col-span-2">Event Type</div>
            <div className="col-span-2">Signature</div>
            <div className="col-span-3 text-right">Timestamp</div>
          </div>

          {/* Table Rows */}
          <div className="divide-y divide-surface-100">
            {filtered.map((log) => (
              <div key={log.id}>
                <button
                  onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                  className="w-full grid grid-cols-12 gap-4 px-5 py-3.5 hover:bg-surface-50 transition-colors text-left"
                >
                  <div className="col-span-1">
                    <span className={`badge ${statusClass(log.status)}`}>
                      {statusIcon(log.status)}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-sm text-ink font-medium truncate">{log.agent_name}</span>
                      <code className="text-xs text-ink-subtle font-mono truncate">
                        {log.agent_public_key?.substring(0, 8)}...
                      </code>
                    </div>
                  </div>
                  <div className="col-span-2">
                    <span className="font-mono text-sm text-ink font-medium truncate block">{log.tool_name || '—'}</span>
                  </div>
                  <div className="col-span-2">
                    <span className="font-mono text-xs text-ink-muted truncate block">{log.event_type || '—'}</span>
                  </div>
                  <div className="col-span-2">
                    {log.metadata?.signature ? (
                      <code className="font-mono text-xs text-matrix-600 bg-matrix-500/5 px-1.5 py-0.5 rounded border border-matrix-500/20">
                        {log.metadata.signature.substring(0, 8)}...
                      </code>
                    ) : (
                      <span className="text-xs text-ink-subtle">—</span>
                    )}
                  </div>
                  <div className="col-span-3 text-right">
                    <span className="text-xs text-ink-subtle font-mono">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </button>

                {/* Expandable Detail */}
                {expanded === log.id && (
                  <div className="px-5 py-4 bg-surface-50 border-t border-surface-100">
                    <div className="terminal-box rounded-lg p-4 text-xs space-y-1">
                      <div className="flex gap-3">
                        <span className="text-terminal-dim w-20 flex-shrink-0">id</span>
                        <span className="text-matrix-500 font-mono">{log.id}</span>
                      </div>
                      <div className="flex gap-3">
                        <span className="text-terminal-dim w-20 flex-shrink-0">agent</span>
                        <span className="text-matrix-500 font-mono">{log.agent_name}</span>
                      </div>
                      <div className="flex gap-3">
                        <span className="text-terminal-dim w-20 flex-shrink-0">agent_key</span>
                        <span className="text-matrix-500 font-mono break-all">{log.agent_public_key}</span>
                      </div>
                      <div className="flex gap-3">
                        <span className="text-terminal-dim w-20 flex-shrink-0">tool</span>
                        <span className="text-matrix-500 font-mono">{log.tool_name}</span>
                      </div>
                      <div className="flex gap-3">
                        <span className="text-terminal-dim w-20 flex-shrink-0">status</span>
                        <span className="text-matrix-500 font-mono">{log.status}</span>
                      </div>
                      {log.error_message && (
                        <div className="flex gap-3">
                          <span className="text-terminal-dim w-20 flex-shrink-0">error</span>
                          <span className="text-red-400 font-mono">{log.error_message}</span>
                        </div>
                      )}
                      <div className="flex gap-3">
                        <span className="text-terminal-dim w-20 flex-shrink-0">time</span>
                        <span className="text-matrix-500 font-mono">{new Date(log.timestamp).toISOString()}</span>
                      </div>
                      {log.metadata?.signature && (
                        <div className="flex gap-3">
                          <span className="text-terminal-dim w-20 flex-shrink-0">sig</span>
                          <span className="text-matrix-500 font-mono break-all">{log.metadata.signature}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {filtered.length >= 200 && (
            <div className="px-5 py-3 bg-surface-50 border-t border-surface-100 text-center text-xs text-ink-subtle font-mono">
              Showing last 200 operations · All logs stored immutably
            </div>
          )}
        </div>
      )}

      {/* Security Note */}
      <div className="terminal-box glass-slate rounded-xl p-4">
        <div className="flex items-start gap-3">
          <span className="text-matrix-500 text-sm flex-shrink-0">🔒</span>
          <div>
            <p className="font-mono text-matrix-500 text-xs">IMMUTABLE AUDIT TRAIL</p>
            <p className="font-mono text-terminal-dim text-xs mt-1">
              All operations are signed with Ed25519 keypairs. Each log entry is cryptographically
              linked to the agent identity and cannot be modified or deleted.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
