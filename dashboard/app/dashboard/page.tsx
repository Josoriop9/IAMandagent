'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { supabase } from '@/lib/supabase';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line
} from 'recharts';

// ============================================
// TYPES
// ============================================

interface Stats {
  agents: number;
  policies: number;
  logs: number;
  successRate: number;
  deniedOps: number;
}

interface Log {
  id: string;
  tool_name: string;
  status: string;
  event_type: string;
  timestamp: string;
}

// ============================================
// HELPERS
// ============================================

function buildChartData(logs: Log[]) {
  const byHour: Record<string, { success: number; denied: number; error: number }> = {};

  logs.forEach(log => {
    const hour = new Date(log.timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
    if (!byHour[hour]) byHour[hour] = { success: 0, denied: 0, error: 0 };
    if (log.status === 'success') byHour[hour].success++;
    else if (log.status === 'denied') byHour[hour].denied++;
    else byHour[hour].error++;
  });

  return Object.entries(byHour)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .slice(-12)
    .map(([time, data]) => ({ time, ...data }));
}

function buildToolData(logs: Log[]) {
  const byTool: Record<string, number> = {};
  logs.forEach(log => {
    byTool[log.tool_name] = (byTool[log.tool_name] || 0) + 1;
  });
  return Object.entries(byTool)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([name, count]) => ({ name, count }));
}

// ============================================
// SUB-COMPONENTS
// ============================================

function StatCard({
  label,
  value,
  delta,
  icon,
  accent = 'green',
}: {
  label: string;
  value: string | number;
  delta?: string;
  icon: React.ReactNode;
  accent?: 'green' | 'blue' | 'red' | 'yellow';
}) {
  const accentColors = {
    green: 'text-emerald-600 bg-emerald-50 border-emerald-100',
    blue: 'text-blue-600 bg-blue-50 border-blue-100',
    red: 'text-red-500 bg-red-50 border-red-100',
    yellow: 'text-amber-600 bg-amber-50 border-amber-100',
  };

  return (
    <div className="card-stat animate-slide-up">
      <div className="flex items-center justify-between mb-4">
        <span className={`p-2 rounded-lg border ${accentColors[accent]}`}>
          {icon}
        </span>
        {delta && (
          <span className="badge badge-success text-xs">{delta}</span>
        )}
      </div>
      <p className="text-ink-muted text-sm font-medium">{label}</p>
      <p className="metric-number text-3xl text-ink mt-1">{value}</p>
    </div>
  );
}

const COLORS = ['#00cc33', '#6366f1', '#f59e0b', '#ef4444', '#06b6d4', '#8b5cf6'];

// ============================================
// MAIN PAGE
// ============================================

export default function DashboardOverview() {
  const [stats, setStats] = useState<Stats>({
    agents: 0,
    policies: 0,
    logs: 0,
    successRate: 0,
    deniedOps: 0,
  });
  const [organization, setOrganization] = useState<any>(null);
  const [recentLogs, setRecentLogs] = useState<Log[]>([]);
  const [allLogs, setAllLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiKeyCopied, setApiKeyCopied] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;

        let org: any = null;
        const { data: ownedOrg } = await supabase
          .from('organizations').select('*').eq('owner_id', user.id).single();

        if (ownedOrg) {
          org = ownedOrg;
        } else {
          const { data: anyOrg } = await supabase
            .from('organizations').select('*').eq('is_active', true).limit(1).single();
          if (anyOrg) {
            await supabase.from('organizations').update({ owner_id: user.id }).eq('id', anyOrg.id);
            org = anyOrg;
          }
        }

        if (!org) return;
        setOrganization(org);

        const [agents, policies, logs] = await Promise.all([
          supabase.from('agents').select('*', { count: 'exact', head: true }).eq('organization_id', org.id),
          supabase.from('policies').select('*', { count: 'exact', head: true }).eq('organization_id', org.id),
          supabase.from('ledger_logs').select('*').eq('organization_id', org.id).order('timestamp', { ascending: false }).limit(100),
        ]);

        const logData = logs.data || [];
        const successCount = logData.filter(l => l.status === 'success').length;
        const deniedCount = logData.filter(l => l.status === 'denied').length;
        const successRate = logData.length > 0 ? Math.round((successCount / logData.length) * 100) : 0;

        setStats({
          agents: agents.count || 0,
          policies: policies.count || 0,
          logs: logData.length,
          successRate,
          deniedOps: deniedCount,
        });

        setAllLogs(logData);
        setRecentLogs(logData.slice(0, 6));
      } catch (error) {
        console.error('Error:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  const chartData = buildChartData(allLogs);
  const toolData = buildToolData(allLogs);

  const pieData = [
    { name: 'Success', value: allLogs.filter(l => l.status === 'success').length },
    { name: 'Denied', value: allLogs.filter(l => l.status === 'denied').length },
    { name: 'Error', value: allLogs.filter(l => l.status === 'error').length },
  ].filter(d => d.value > 0);

  const pieColors = ['#00cc33', '#ef4444', '#f59e0b'];

  const handleCopyKey = () => {
    if (organization?.api_key) {
      navigator.clipboard.writeText(organization.api_key);
      setApiKeyCopied(true);
      setTimeout(() => setApiKeyCopied(false), 2000);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-2 border-matrix-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="font-mono text-matrix-600 text-sm">LOADING SYSTEM DATA...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ---- HEADER ---- */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">Overview</h1>
          <p className="text-ink-muted text-sm mt-0.5">
            AI Agent Governance · Real-time monitoring
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-ink-subtle">
          <span className="live-dot"></span>
          <span>Updated live</span>
        </div>
      </div>

      {/* ---- STAT CARDS ---- */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Active Agents"
          value={stats.agents}
          icon={<svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9 3.75H6.912a2.25 2.25 0 00-2.15 1.588L2.35 13.177a2.25 2.25 0 00-.1.661V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18v-4.162c0-.224-.034-.447-.1-.661L19.24 5.338a2.25 2.25 0 00-2.15-1.588H15M2.25 13.5h3.86a2.25 2.25 0 012.012 1.244l.256.512a2.25 2.25 0 002.013 1.244h3.218a2.25 2.25 0 002.013-1.244l.256-.512a2.25 2.25 0 012.013-1.244h3.859M12 3v8.25m0 0l-3-3m3 3l3-3" /></svg>}
          accent="green"
        />
        <StatCard
          label="Total Operations"
          value={stats.logs.toLocaleString()}
          icon={<svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M7.5 14.25v2.25m3-4.5v4.5m3-6.75v6.75m3-9v9M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z" /></svg>}
          accent="blue"
        />
        <StatCard
          label="Success Rate"
          value={`${stats.successRate}%`}
          delta={stats.successRate >= 90 ? '↑ High' : undefined}
          icon={<svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
          accent="green"
        />
        <StatCard
          label="Denied Ops"
          value={stats.deniedOps}
          icon={<svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" /></svg>}
          accent="red"
        />
      </div>

      {/* ---- CHARTS ROW ---- */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Area Chart - Operations Timeline */}
        <div className="lg:col-span-2 card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-ink text-sm">Operations Timeline</h3>
              <p className="text-ink-subtle text-xs mt-0.5">Last {chartData.length} intervals</p>
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
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="successGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00cc33" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#00cc33" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="deniedGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '12px' }}
                  cursor={{ stroke: '#e2e8f0' }}
                />
                <Area type="monotone" dataKey="success" stroke="#00cc33" fill="url(#successGrad)" strokeWidth={2} dot={false} />
                <Area type="monotone" dataKey="denied" stroke="#ef4444" fill="url(#deniedGrad)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center">
              <div className="text-center">
                <div className="font-mono text-matrix-500 text-xs opacity-50 mb-2">_</div>
                <p className="text-ink-subtle text-sm">No operations yet</p>
                <p className="text-ink-subtle text-xs mt-1">Run your agent to see data here</p>
              </div>
            </div>
          )}
        </div>

        {/* Pie Chart - Status Distribution */}
        <div className="card p-5">
          <div className="mb-4">
            <h3 className="font-semibold text-ink text-sm">Status Distribution</h3>
            <p className="text-ink-subtle text-xs mt-0.5">All operations</p>
          </div>
          {pieData.length > 0 ? (
            <div>
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
                      <Cell key={entry.name} fill={pieColors[index % pieColors.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '12px' }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2 mt-2">
                {pieData.map((entry, index) => (
                  <div key={entry.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full" style={{ background: pieColors[index] }}></div>
                      <span className="text-xs text-ink-muted">{entry.name}</span>
                    </div>
                    <span className="text-xs font-mono font-medium text-ink">{entry.value}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-[140px] flex items-center justify-center">
              <p className="text-ink-subtle text-sm">No data yet</p>
            </div>
          )}
        </div>
      </div>

      {/* ---- TOOL USAGE + RECENT LOGS ---- */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Bar Chart - Tool Usage */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-ink text-sm">Top Tools</h3>
              <p className="text-ink-subtle text-xs mt-0.5">Operations by tool name</p>
            </div>
          </div>
          {toolData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={toolData} margin={{ top: 5, right: 5, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} angle={-15} dy={8} />
                <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '12px' }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {toolData.map((entry, index) => (
                    <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center">
              <p className="text-ink-subtle text-sm">No tool data yet</p>
            </div>
          )}
        </div>

        {/* Recent Logs Table */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-ink text-sm">Recent Operations</h3>
              <p className="text-ink-subtle text-xs mt-0.5">Last {recentLogs.length} events</p>
            </div>
            <Link href="/dashboard/logs" className="text-xs text-accent-500 hover:text-accent-600 font-medium transition-colors">
              View all →
            </Link>
          </div>
          {recentLogs.length > 0 ? (
            <div className="space-y-2">
              {recentLogs.map(log => (
                <div key={log.id} className="flex items-center justify-between py-2 border-b border-surface-100 last:border-0">
                  <div className="flex items-center gap-3">
                    <span className={`badge ${
                      log.status === 'success' ? 'badge-success' :
                      log.status === 'denied' ? 'badge-danger' : 'badge-warning'
                    }`}>
                      {log.status === 'success' ? '✓' : log.status === 'denied' ? '✗' : '⚠'} {log.status}
                    </span>
                    <span className="font-mono text-xs text-ink-muted">{log.tool_name}</span>
                  </div>
                  <span className="text-xs text-ink-subtle">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="h-[180px] flex items-center justify-center">
              <div className="text-center">
                <div className="text-3xl mb-2">📊</div>
                <p className="text-ink-subtle text-sm">No operations yet</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ---- API KEY SECTION ---- */}
      {organization && (
        <div className="terminal-box rounded-xl p-5 scanlines">
          <div className="flex items-center gap-2 mb-3">
            <div className="live-dot"></div>
            <span className="font-mono text-xs text-matrix-500 tracking-wider">API_KEY / CONTROL_PLANE_CONNECTION</span>
          </div>
          <div className="flex items-center gap-3">
            <code className="flex-1 font-mono text-sm text-matrix-500 bg-black/30 px-4 py-2.5 rounded-lg border border-terminal-border truncate">
              {organization.api_key}
            </code>
            <button
              onClick={handleCopyKey}
              className="px-4 py-2.5 bg-matrix-500/20 hover:bg-matrix-500/30 border border-matrix-500/40 
                         text-matrix-500 font-mono text-xs rounded-lg transition-all duration-150 whitespace-nowrap"
            >
              {apiKeyCopied ? '✓ COPIED' : 'COPY KEY'}
            </button>
          </div>
          <p className="font-mono text-xs text-terminal-dim mt-3">
            $ pip install git+https://github.com/Josoriop9/IAMandagent.git<span className="animate-blink">_</span>
          </p>
        </div>
      )}
    </div>
  );
}
