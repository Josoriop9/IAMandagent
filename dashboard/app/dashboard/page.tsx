'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { supabase } from '@/lib/supabase';
import AgentIcon from '@/components/AgentIcon';
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
  agent_name?: string;
  agent_icon?: string;
  agent_color?: string;
  agents?: {
    name: string;
    icon?: string;
    color?: string;
  };
}

// ============================================
// HELPERS
// ============================================

function buildChartData(logs: Log[]) {
  const bySlot: Record<string, { success: number; error: number; permission_denied: number; sortKey: string }> = {};

  logs.forEach(log => {
    const d = new Date(log.timestamp);
    // Format as "MM/DD HH:mm" in EST
    const label = d.toLocaleString('en-US', {
      timeZone: 'America/New_York',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
    const sortKey = d.toISOString();
    if (!bySlot[label]) bySlot[label] = { success: 0, error: 0, permission_denied: 0, sortKey };
    if (log.status === 'success') bySlot[label].success++;
    else if (log.status === 'denied') bySlot[label].permission_denied++;
    else bySlot[label].error++;
  });

  return Object.entries(bySlot)
    .sort((a, b) => a[1].sortKey.localeCompare(b[1].sortKey))
    .map(([time, { sortKey, ...data }]) => ({ time, ...data }));
}

function filterLogsByPeriod(logs: Log[], period: string, customDate?: string): Log[] {
  const now = new Date();
  return logs.filter(log => {
    const logDate = new Date(log.timestamp);
    switch (period) {
      case 'today': {
        const todayEST = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
        const logEST = new Date(logDate.toLocaleString('en-US', { timeZone: 'America/New_York' }));
        return logEST.toDateString() === todayEST.toDateString();
      }
      case '7d':
        return (now.getTime() - logDate.getTime()) < 7 * 24 * 60 * 60 * 1000;
      case '30d':
        return (now.getTime() - logDate.getTime()) < 30 * 24 * 60 * 60 * 1000;
      case 'custom':
        if (!customDate) return true;
        const target = new Date(customDate + 'T00:00:00');
        const nextDay = new Date(customDate + 'T23:59:59');
        return logDate >= target && logDate <= nextDay;
      default:
        return true;
    }
  });
}

function buildToolData(logs: Log[]) {
  const byTool: Record<string, { count: number; agents: Set<string>; agentData: Map<string, { icon: string; color: string }> }> = {};
  
  logs.forEach(log => {
    if (!byTool[log.tool_name]) {
      byTool[log.tool_name] = { 
        count: 0, 
        agents: new Set(), 
        agentData: new Map() 
      };
    }
    byTool[log.tool_name].count++;
    if (log.agent_name) {
      byTool[log.tool_name].agents.add(log.agent_name);
      byTool[log.tool_name].agentData.set(log.agent_name, {
        icon: log.agent_icon || 'robot',
        color: log.agent_color || 'purple'
      });
    }
  });
  
  return Object.entries(byTool)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 6)
    .map(([name, data]) => ({ 
      name, 
      count: data.count,
      agents: Array.from(data.agentData.entries()).map(([agentName, { icon, color }]) => ({
        name: agentName,
        icon,
        color
      }))
    }));
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
  const [apiKeyVisible, setApiKeyVisible] = useState(false);
  const [chartPeriod, setChartPeriod] = useState<string>('all');
  const [customDate, setCustomDate] = useState<string>('');

  // Fetch data function (reusable for polling)
  async function fetchData() {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      let org: any = organization;
      if (!org) {
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
      }

      const [agents, policies, logs] = await Promise.all([
        supabase.from('agents').select('*', { count: 'exact', head: true }).eq('organization_id', org.id),
        supabase.from('policies').select('*', { count: 'exact', head: true }).eq('organization_id', org.id),
        supabase.from('ledger_logs').select(`
          *,
          agents(name, icon, color)
        `).eq('organization_id', org.id).order('timestamp', { ascending: false}).limit(500),
      ]);

      const logData = (logs.data || []).map(log => ({
        ...log,
        agent_name: log.agents?.name || 'Unknown Agent',
        agent_icon: (log.agents && 'icon' in log.agents) ? log.agents.icon : 'robot',
        agent_color: (log.agents && 'color' in log.agents) ? log.agents.color : 'purple'
      }));
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

  // Initial fetch + auto-refresh every 10 seconds
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const filteredLogs = filterLogsByPeriod(allLogs, chartPeriod, customDate);
  const chartData = buildChartData(filteredLogs);
  const toolData = buildToolData(allLogs);

  // Pie chart uses same logic as chart: success / denied / everything else = error
  const successTotal = allLogs.filter(l => l.status === 'success').length;
  const deniedTotal = allLogs.filter(l => l.status === 'denied').length;
  const errorTotal = allLogs.length - successTotal - deniedTotal;

  const pieData = [
    { name: 'Success', value: successTotal, color: '#00cc33' },
    { name: 'Permission Denied', value: deniedTotal, color: '#ef4444' },
    { name: 'Error', value: errorTotal, color: '#f59e0b' },
  ].filter(d => d.value > 0);

  const pieColors = pieData.map(d => d.color);

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
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="font-semibold text-ink text-sm">Operations Timeline</h3>
              <p className="text-ink-subtle text-xs mt-0.5">
                {filteredLogs.length} ops · {chartData.length} intervals · 
                <span className="font-mono"> EST</span>
              </p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-500"></div>
                <span className="text-ink-muted">Success</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-amber-400"></div>
                <span className="text-ink-muted">Error</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-red-400"></div>
                <span className="text-ink-muted">Permission Denied</span>
              </div>
            </div>
          </div>

          {/* Period Filters */}
          <div className="flex items-center gap-2 mb-4 flex-wrap">
            {[
              { id: 'all', label: 'All Time' },
              { id: 'today', label: 'Today' },
              { id: '7d', label: 'Last 7 Days' },
              { id: '30d', label: 'Last 30 Days' },
              { id: 'custom', label: 'Pick Date' },
            ].map(p => (
              <button
                key={p.id}
                onClick={() => { setChartPeriod(p.id); if (p.id !== 'custom') setCustomDate(''); }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 ${
                  chartPeriod === p.id
                    ? 'bg-ink text-white shadow-sm'
                    : 'bg-surface-50 border border-surface-200 text-ink-muted hover:text-ink hover:border-surface-300'
                }`}
              >
                {p.label}
              </button>
            ))}
            {chartPeriod === 'custom' && (
              <input
                type="date"
                value={customDate}
                onChange={e => setCustomDate(e.target.value)}
                className="px-3 py-1.5 rounded-lg text-xs font-mono bg-white border border-surface-200 
                           text-ink focus:outline-none focus:border-accent-500 focus:ring-1 focus:ring-accent-500/20"
              />
            )}
            {chartPeriod !== 'all' && (
              <span className="text-xs text-ink-subtle font-mono ml-auto">
                {filteredLogs.filter(l => l.status === 'success').length} ✓ · 
                {filteredLogs.filter(l => l.status !== 'success' && l.status !== 'denied').length} ⚠ · 
                {filteredLogs.filter(l => l.status === 'denied').length} ✗
              </span>
            )}
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
                  <linearGradient id="errorGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '12px' }}
                  cursor={{ stroke: '#e2e8f0' }}
                />
                <Area type="monotone" dataKey="success" name="Success" stroke="#00cc33" fill="url(#successGrad)" strokeWidth={2} dot={false} />
                <Area type="monotone" dataKey="error" name="Error" stroke="#f59e0b" fill="url(#errorGrad)" strokeWidth={2} dot={false} />
                <Area type="monotone" dataKey="permission_denied" name="Permission Denied" stroke="#ef4444" fill="url(#deniedGrad)" strokeWidth={2} dot={false} />
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
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={toolData} margin={{ top: 40, right: 5, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} angle={-15} dy={8} />
                <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '12px' }} />
                <Bar 
                  dataKey="count" 
                  radius={[4, 4, 0, 0]}
                  label={(props: any) => {
                    const { x, y, width, value, index } = props;
                    const tool = toolData[index];
                    if (!tool || !tool.agents || tool.agents.length === 0) return <g />;
                    
                    const iconSize = 32; // sm size
                    const gap = 2;
                    const totalWidth = (tool.agents.slice(0, 3).length * iconSize) + ((tool.agents.slice(0, 3).length - 1) * gap);
                    const startX = x + (width / 2) - (totalWidth / 2);
                    
                    return (
                      <g>
                        {tool.agents.slice(0, 3).map((agent, i) => {
                          const iconX = startX + (i * (iconSize + gap));
                          const iconY = y - 10; // 10px above bar
                          
                          return (
                            <foreignObject
                              key={agent.name}
                              x={iconX}
                              y={iconY}
                              width={iconSize}
                              height={iconSize}
                            >
                              <div style={{ width: iconSize, height: iconSize }}>
                                <AgentIcon
                                  icon={agent.icon}
                                  color={agent.color}
                                  size="sm"
                                />
                              </div>
                            </foreignObject>
                          );
                        })}
                      </g>
                    );
                  }}
                >
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
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <span className={`badge ${
                      log.status === 'success' ? 'badge-success' :
                      log.status === 'denied' ? 'badge-danger' : 'badge-warning'
                    }`}>
                      {log.status === 'success' ? '✓' : log.status === 'denied' ? '✗' : '⚠'}
                    </span>
                    <AgentIcon 
                      icon={log.agent_icon || 'robot'} 
                      color={log.agent_color || 'purple'} 
                      size="sm" 
                    />
                    <div className="flex flex-col gap-0.5 min-w-0">
                      <span className="font-mono text-xs text-ink font-medium truncate">{log.tool_name}</span>
                      <span className="text-xs text-ink-subtle truncate">{log.agent_name}</span>
                    </div>
                  </div>
                  <span className="text-xs text-ink-subtle font-mono whitespace-nowrap ml-2">
                    {new Date(log.timestamp).toLocaleString('en-US', {
                      timeZone: 'America/New_York',
                      month: '2-digit', day: '2-digit',
                      hour: '2-digit', minute: '2-digit',
                      hour12: true,
                    })} EST
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
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse"></div>
            <span className="text-xs text-slate-500 font-medium tracking-wide uppercase">API Key</span>
          </div>
          <div className="flex items-center gap-3">
            <code className="flex-1 font-mono text-sm text-slate-600 bg-slate-50 px-4 py-2.5 rounded-lg border border-slate-200 truncate">
              {apiKeyVisible ? organization.api_key : '••••••••••••••••••••••••••••••••'}
            </code>
            <button
              onClick={() => setApiKeyVisible(!apiKeyVisible)}
              className="p-2.5 bg-slate-100 hover:bg-slate-200 border border-slate-200 
                         text-slate-600 rounded-lg transition-all duration-150"
              title={apiKeyVisible ? 'Hide API key' : 'Show API key'}
            >
              {apiKeyVisible ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              )}
            </button>
            <button
              onClick={handleCopyKey}
              className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 border border-slate-200 
                         text-slate-700 font-medium text-xs rounded-lg transition-all duration-150 whitespace-nowrap"
            >
              {apiKeyCopied ? '✓ Copied' : 'Copy'}
            </button>
          </div>
          <p className="text-xs text-slate-400 mt-3 font-mono">
            pip install git+https://github.com/Josoriop9/IAMandagent.git
          </p>
        </div>
      )}
    </div>
  );
}
