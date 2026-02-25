'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { supabase } from '@/lib/supabase';
import AgentIcon from '@/components/AgentIcon';

interface Agent {
  id: string;
  name: string;
  agent_type: string;
  public_key: string;
  is_active: boolean;
  created_at: string;
  last_seen_at: string | null;
  icon?: string;
  color?: string;
}

interface AgentStats {
  success: number;
  denied: number;
  error: number;
  total: number;
}

interface NodePosition {
  x: number;
  y: number;
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [viewMode, setViewMode] = useState<'list' | 'ecosystem'>('list');
  const [agentStats, setAgentStats] = useState<Record<string, AgentStats>>({});
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [positions, setPositions] = useState<Record<string, NodePosition>>({});
  const [dragging, setDragging] = useState<{ id: string; offsetX: number; offsetY: number } | null>(null);

  // Refs for animation loop (avoid stale closures)
  const posRef = useRef<Record<string, NodePosition>>({});
  const velRef = useRef<Record<string, { vx: number; vy: number }>>({});
  const rafRef = useRef<number | null>(null);
  const draggingRef = useRef<string | null>(null);

  // Sync draggingRef when dragging changes
  useEffect(() => { draggingRef.current = dragging?.id ?? null; }, [dragging]);

  // Sync posRef when positions change (from drag)
  useEffect(() => { posRef.current = positions; }, [positions]);

  // Start / stop animation when viewMode or agents change
  useEffect(() => {
    if (viewMode !== 'ecosystem' || agents.length === 0) {
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
      return;
    }

    // Init velocities for agents that don't have one yet
    agents.forEach(agent => {
      if (!velRef.current[agent.id]) {
        const speed = 0.4 + Math.random() * 0.4; // slow float
        const angle = Math.random() * Math.PI * 2;
        velRef.current[agent.id] = { vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed };
      }
    });

    const W = 800; // approximate canvas width
    const H = 480; // canvas height - margin
    const MARGIN = 50;

    const tick = () => {
      const newPositions: Record<string, NodePosition> = { ...posRef.current };
      let changed = false;

      agents.forEach(agent => {
        if (draggingRef.current === agent.id) return; // skip dragged node
        const pos = posRef.current[agent.id];
        const vel = velRef.current[agent.id];
        if (!pos || !vel) return;

        let nx = pos.x + vel.vx;
        let ny = pos.y + vel.vy;

        // Bounce off walls
        if (nx < MARGIN) { nx = MARGIN; vel.vx = Math.abs(vel.vx); }
        if (nx > W - MARGIN) { nx = W - MARGIN; vel.vx = -Math.abs(vel.vx); }
        if (ny < MARGIN) { ny = MARGIN; vel.vy = Math.abs(vel.vy); }
        if (ny > H - MARGIN) { ny = H - MARGIN; vel.vy = -Math.abs(vel.vy); }

        // Add tiny random wobble
        vel.vx += (Math.random() - 0.5) * 0.02;
        vel.vy += (Math.random() - 0.5) * 0.02;

        // Clamp speed
        const speed = Math.sqrt(vel.vx * vel.vx + vel.vy * vel.vy);
        if (speed > 0.8) { vel.vx *= 0.8 / speed; vel.vy *= 0.8 / speed; }
        if (speed < 0.2) { vel.vx *= 1.05; vel.vy *= 1.05; }

        newPositions[agent.id] = { x: nx, y: ny };
        changed = true;
      });

      if (changed) {
        posRef.current = newPositions;
        setPositions({ ...newPositions });
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [viewMode, agents]);

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

        const agentList = data || [];
        setAgents(agentList);

        // Fetch logs to compute per-agent stats
        const { data: logs } = await supabase
          .from('ledger_logs')
          .select('agent_id, status')
          .eq('organization_id', orgId);

        const statsMap: Record<string, AgentStats> = {};
        (logs || []).forEach((log: any) => {
          const aid = log.agent_id;
          if (!aid) return;
          if (!statsMap[aid]) statsMap[aid] = { success: 0, denied: 0, error: 0, total: 0 };
          statsMap[aid].total++;
          if (log.status === 'success') statsMap[aid].success++;
          else if (log.status === 'denied') statsMap[aid].denied++;
          else statsMap[aid].error++;
        });
        setAgentStats(statsMap);

        // Initialize random positions for ecosystem view
        const posMap: Record<string, NodePosition> = {};
        agentList.forEach((agent: Agent, i: number) => {
          const cols = Math.ceil(Math.sqrt(agentList.length + 1));
          const col = i % cols;
          const row = Math.floor(i / cols);
          posMap[agent.id] = {
            x: 120 + col * 220 + (Math.random() * 40 - 20),
            y: 100 + row * 200 + (Math.random() * 40 - 20),
          };
        });
        setPositions(posMap);
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
        <div className="flex items-center gap-3">
          <span className="badge badge-matrix text-xs font-mono">{agents.length} registered</span>
          {/* View Toggle */}
          <div className="flex items-center bg-surface-100 rounded-lg p-1 gap-1">
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${viewMode === 'list' ? 'bg-white text-ink shadow-sm' : 'text-ink-muted hover:text-ink'}`}
            >
              ☰ List
            </button>
            <button
              onClick={() => setViewMode('ecosystem')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${viewMode === 'ecosystem' ? 'bg-white text-ink shadow-sm' : 'text-ink-muted hover:text-ink'}`}
            >
              🌐 Ecosystem
            </button>
          </div>
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

      {/* ===== ECOSYSTEM VIEW ===== */}
      {viewMode === 'ecosystem' && (
        <div
          className="relative rounded-2xl overflow-hidden shadow-2xl"
          style={{ height: '520px', background: 'linear-gradient(135deg, #1a0533 0%, #0d0a2e 30%, #051a2e 60%, #0a1a1a 100%)' }}
          onMouseMove={e => {
            if (!dragging) return;
            const rect = e.currentTarget.getBoundingClientRect();
            setPositions(prev => ({
              ...prev,
              [dragging.id]: {
                x: e.clientX - rect.left - dragging.offsetX,
                y: e.clientY - rect.top - dragging.offsetY,
              }
            }));
          }}
          onMouseUp={() => setDragging(null)}
          onMouseLeave={() => setDragging(null)}
        >
          {/* Colorful blobs for glassmorphism background */}
          <div className="absolute" style={{ width: 320, height: 320, top: -80, left: -60,
            background: 'radial-gradient(circle, rgba(139,92,246,0.55) 0%, transparent 70%)', filter: 'blur(40px)', borderRadius: '50%' }} />
          <div className="absolute" style={{ width: 280, height: 280, top: 60, right: -40,
            background: 'radial-gradient(circle, rgba(6,182,212,0.5) 0%, transparent 70%)', filter: 'blur(40px)', borderRadius: '50%' }} />
          <div className="absolute" style={{ width: 300, height: 300, bottom: -60, left: '40%',
            background: 'radial-gradient(circle, rgba(168,85,247,0.45) 0%, transparent 70%)', filter: 'blur(40px)', borderRadius: '50%' }} />
          <div className="absolute" style={{ width: 220, height: 220, bottom: 20, left: 80,
            background: 'radial-gradient(circle, rgba(20,184,166,0.4) 0%, transparent 70%)', filter: 'blur(35px)', borderRadius: '50%' }} />
          <div className="absolute" style={{ width: 200, height: 200, top: 100, left: '55%',
            background: 'radial-gradient(circle, rgba(236,72,153,0.35) 0%, transparent 70%)', filter: 'blur(35px)', borderRadius: '50%' }} />

          {/* Grid lines */}
          <svg className="absolute inset-0 w-full h-full opacity-[0.06]" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#ffffff" strokeWidth="0.5"/>
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
          </svg>

          {/* Title */}
          <div className="absolute top-4 left-4 flex items-center gap-2 z-10">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
            <span className="font-mono text-xs text-emerald-500 tracking-widest">AGENT ECOSYSTEM · {agents.length} NODES</span>
          </div>
          <p className="absolute top-4 right-4 font-mono text-xs text-emerald-900 z-10">drag nodes to arrange</p>

          {/* Nodes */}
          {agents.map((agent, idx) => {
            const pos = positions[agent.id] || { x: 100 + idx * 180, y: 150 };
            const stats = agentStats[agent.id] || { success: 0, denied: 0, error: 0, total: 0 };
            const isSelected = selectedAgent?.id === agent.id;
            const initials = agent.name.split(' ').map((w: string) => w[0]).join('').substring(0, 2).toUpperCase();

            return (
              <div
                key={agent.id}
                style={{ position: 'absolute', left: pos.x, top: pos.y, transform: 'translate(-50%, -50%)', cursor: 'grab', zIndex: isSelected ? 20 : 10, userSelect: 'none' }}
                onMouseDown={e => {
                  e.preventDefault();
                  setDragging({ id: agent.id, offsetX: 0, offsetY: 0 });
                }}
                onClick={() => setSelectedAgent(isSelected ? null : agent)}
              >
                {/* Glow ring for active */}
                {agent.is_active && (
                  <div className="absolute inset-0 rounded-full animate-ping"
                    style={{ background: 'radial-gradient(circle, rgba(0,204,51,0.15) 0%, transparent 70%)', width: '100px', height: '100px', margin: '-10px' }} />
                )}

                {/* Node circle - glassmorphism */}
                <div className={`relative w-20 h-20 rounded-full flex flex-col items-center justify-center transition-all duration-200
                  ${isSelected ? 'scale-110' : 'hover:scale-105'}`}
                  style={{
                    backdropFilter: 'blur(16px)',
                    WebkitBackdropFilter: 'blur(16px)',
                    background: 'rgba(255,255,255,0.08)',
                    border: isSelected
                      ? '1.5px solid rgba(167,139,250,0.8)'
                      : agent.is_active
                        ? '1.5px solid rgba(167,139,250,0.4)'
                        : '1.5px solid rgba(255,255,255,0.15)',
                    boxShadow: isSelected
                      ? '0 0 24px rgba(139,92,246,0.5), inset 0 1px 0 rgba(255,255,255,0.15)'
                      : agent.is_active
                        ? '0 0 16px rgba(139,92,246,0.3), inset 0 1px 0 rgba(255,255,255,0.1)'
                        : 'inset 0 1px 0 rgba(255,255,255,0.05)',
                  }}
                >
                  <span className="text-white font-bold text-sm">{initials}</span>
                  <span className="text-emerald-400/70 text-xs mt-0.5">{agent.agent_type.substring(0, 4)}</span>

                  {/* Status dot */}
                  {agent.is_active && (
                    <div className="absolute top-1 right-1 w-2.5 h-2.5 rounded-full bg-emerald-400 border border-emerald-900 animate-pulse" />
                  )}
                </div>

                {/* Name label */}
                <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 whitespace-nowrap">
                  <span className="text-white/80 text-xs font-medium">{agent.name.length > 12 ? agent.name.substring(0, 12) + '…' : agent.name}</span>
                </div>

                {/* Stats badges */}
                {stats.total > 0 && (
                  <div className="absolute -top-8 left-1/2 -translate-x-1/2 flex gap-1 whitespace-nowrap">
                    {stats.success > 0 && (
                      <span className="text-xs px-1.5 py-0.5 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 font-mono">
                        ✓{stats.success}
                      </span>
                    )}
                    {stats.denied > 0 && (
                      <span className="text-xs px-1.5 py-0.5 rounded-full bg-red-500/20 border border-red-500/40 text-red-400 font-mono">
                        ✗{stats.denied}
                      </span>
                    )}
                    {stats.error > 0 && (
                      <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-400 font-mono">
                        ⚠{stats.error}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {/* Empty state */}
          {agents.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center">
              <p className="font-mono text-emerald-900 text-sm">{'> no_agents_registered'}</p>
            </div>
          )}

          {/* ===== SELECTED AGENT PANEL - Overlay inside canvas ===== */}
          {selectedAgent && (() => {
            const stats = agentStats[selectedAgent.id] || { success: 0, denied: 0, error: 0, total: 0 };
            return (
              <div
                className="absolute top-4 right-4 w-72 z-30 overflow-y-auto"
                style={{
                  maxHeight: 'calc(100% - 32px)',
                  backdropFilter: 'blur(24px)',
                  WebkitBackdropFilter: 'blur(24px)',
                  background: 'linear-gradient(160deg, rgba(15,12,40,0.85) 0%, rgba(20,10,50,0.90) 100%)',
                  border: '1px solid rgba(167,139,250,0.35)',
                  borderRadius: '16px',
                  boxShadow: '0 8px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.08)',
                  animation: 'slideInRight 0.25s ease-out',
                }}
              >
                <style>{`@keyframes slideInRight { from { opacity:0; transform: translateX(20px); } to { opacity:1; transform: translateX(0); } }`}</style>
                <div className="p-4">
                  {/* Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <div className="w-9 h-9 rounded-full flex items-center justify-center"
                        style={{ background: 'rgba(139,92,246,0.2)', border: '1px solid rgba(167,139,250,0.4)' }}>
                        <span className="text-purple-300 font-bold text-sm">
                          {selectedAgent.name.split(' ').map((w: string) => w[0]).join('').substring(0, 2).toUpperCase()}
                        </span>
                      </div>
                      <div>
                        <h3 className="font-semibold text-white text-sm">{selectedAgent.name}</h3>
                        <p className="text-xs text-purple-300/70">{selectedAgent.agent_type} · {selectedAgent.is_active ? '● Active' : '○ Inactive'}</p>
                      </div>
                    </div>
                    <button onClick={() => setSelectedAgent(null)}
                      className="text-white/40 hover:text-white/80 text-xl leading-none transition-colors w-6 h-6 flex items-center justify-center rounded-full hover:bg-white/10">
                      ×
                    </button>
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-3 gap-2 mb-4">
                    <div className="rounded-lg p-2 text-center" style={{ background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.2)' }}>
                      <p className="text-emerald-400 font-bold text-lg font-mono">{stats.success}</p>
                      <p className="text-xs text-emerald-500/70 mt-0.5">✓ OK</p>
                    </div>
                    <div className="rounded-lg p-2 text-center" style={{ background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.2)' }}>
                      <p className="text-red-400 font-bold text-lg font-mono">{stats.denied}</p>
                      <p className="text-xs text-red-400/70 mt-0.5">✗ Denied</p>
                    </div>
                    <div className="rounded-lg p-2 text-center" style={{ background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.2)' }}>
                      <p className="text-amber-400 font-bold text-lg font-mono">{stats.error}</p>
                      <p className="text-xs text-amber-400/70 mt-0.5">⚠ Err</p>
                    </div>
                  </div>

                  {/* Progress bar */}
                  {stats.total > 0 && (
                    <div className="mb-4">
                      <div className="flex justify-between text-xs text-white/40 mb-1">
                        <span>Success Rate</span>
                        <span className="text-emerald-400">{Math.round((stats.success / stats.total) * 100)}%</span>
                      </div>
                      <div className="h-1.5 rounded-full overflow-hidden flex" style={{ background: 'rgba(255,255,255,0.08)' }}>
                        <div className="bg-emerald-500 h-full" style={{ width: `${(stats.success / stats.total) * 100}%` }} />
                        <div className="bg-red-500 h-full" style={{ width: `${(stats.denied / stats.total) * 100}%` }} />
                        <div className="bg-amber-500 h-full" style={{ width: `${(stats.error / stats.total) * 100}%` }} />
                      </div>
                      <p className="text-xs text-white/30 mt-1">{stats.total} total ops</p>
                    </div>
                  )}

                  {/* Details */}
                  <div className="space-y-1.5 text-xs">
                    {[
                      { label: 'Agent ID', value: `${selectedAgent.id.substring(0, 8)}...${selectedAgent.id.slice(-4)}`, mono: true, color: '#a78bfa' },
                      { label: 'Public Key', value: `${selectedAgent.public_key.substring(0, 14)}...`, mono: true, color: '#34d399' },
                      { label: 'Last Seen', value: selectedAgent.last_seen_at ? new Date(selectedAgent.last_seen_at).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour12: true }) + ' EST' : 'Never', mono: false, color: 'rgba(255,255,255,0.7)' },
                      { label: 'Registered', value: new Date(selectedAgent.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }), mono: false, color: 'rgba(255,255,255,0.7)' },
                    ].map(item => (
                      <div key={item.label} className="flex items-center gap-2 px-2 py-1.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.04)' }}>
                        <span style={{ color: 'rgba(167,139,250,0.6)', width: '64px', flexShrink: 0 }}>{item.label}</span>
                        <span style={{ color: item.color, fontFamily: item.mono ? 'monospace' : 'inherit', fontSize: '11px', wordBreak: 'break-all' }}>{item.value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* ===== LIST VIEW ===== */}
      {viewMode === 'list' && (filtered.length === 0 ? (
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
                  {/* Avatar with AgentIcon */}
                  <AgentIcon 
                    icon={agent.icon || 'robot'} 
                    color={agent.color || 'purple'} 
                    size="lg" 
                  />

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
      ))}

      {/* Info Banner */}
      <div className="terminal-box glass-indigo rounded-xl p-4">
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
