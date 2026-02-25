'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';
import { supabase } from '@/lib/supabase';

const navItems = [
  {
    href: '/dashboard',
    label: 'Overview',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
      </svg>
    ),
  },
  {
    href: '/dashboard/agents',
    label: 'Agents',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 6.75v10.5a2.25 2.25 0 002.25 2.25zm.75-12h9v9h-9v-9z" />
      </svg>
    ),
  },
  {
    href: '/dashboard/logs',
    label: 'Audit Logs',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z" />
      </svg>
    ),
  },
  {
    href: '/dashboard/policies',
    label: 'Policies',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
      </svg>
    ),
  },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [time, setTime] = useState('');
  const [collapsed, setCollapsed] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    const updateTime = () => {
      setTime(new Date().toLocaleTimeString('en-US', { hour12: false, timeZone: 'America/New_York' }));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await supabase.auth.signOut();
      router.push('/login');
    } catch (error) {
      console.error('Logout error:', error);
      setLoggingOut(false);
    }
  };

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-emerald-50 overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`flex flex-col bg-white/40 backdrop-blur-xl border-r border-white/20 flex-shrink-0 shadow-xl
                    transition-all duration-300 ease-in-out ${collapsed ? 'w-[68px]' : 'w-64'}`}
      >
        {/* Logo + Collapse Toggle */}
        <div className="px-3 py-4 border-b border-white/10">
          <div className="flex items-center justify-between">
            <div className={`flex items-center gap-3 ${collapsed ? 'justify-center w-full' : ''}`}>
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-lg flex-shrink-0">
                <span className="text-white font-bold text-sm">#</span>
              </div>
              {!collapsed && (
                <div className="overflow-hidden">
                  <h1 className="text-slate-800 font-bold text-sm tracking-wide">HASHED</h1>
                  <p className="text-emerald-600 text-xs font-medium">Control Plane</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Collapse Toggle Button */}
        <div className="px-3 py-2">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="w-full flex items-center justify-center gap-2 px-2 py-2 rounded-lg text-slate-400 
                       hover:text-slate-600 hover:bg-white/30 transition-all duration-200"
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <svg className={`w-4 h-4 transition-transform duration-300 ${collapsed ? 'rotate-180' : ''}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
            {!collapsed && <span className="text-xs font-medium">Collapse</span>}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-2 py-2 space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                title={collapsed ? item.label : undefined}
                className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium
                  transition-all duration-200 group
                  ${collapsed ? 'justify-center px-2' : ''}
                  ${isActive
                    ? 'bg-white/60 text-emerald-600 shadow-sm backdrop-blur-sm'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-white/30'
                  }
                `}
              >
                <span className={`flex-shrink-0 transition-colors ${isActive ? 'text-emerald-600' : 'group-hover:text-slate-900'}`}>
                  {item.icon}
                </span>
                {!collapsed && (
                  <>
                    <span className="truncate">{item.label}</span>
                    {isActive && (
                      <span className="ml-auto w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50" />
                    )}
                  </>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Bottom Section: Logout + Status */}
        <div className="px-3 py-3 border-t border-white/10 space-y-3">
          {/* Logout Button */}
          <button
            onClick={handleLogout}
            disabled={loggingOut}
            title={collapsed ? 'Sign Out' : undefined}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium
                       text-red-500 hover:bg-red-50/50 hover:text-red-600 transition-all duration-200
                       disabled:opacity-50 disabled:cursor-not-allowed
                       ${collapsed ? 'justify-center px-2' : ''}`}
          >
            <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
            </svg>
            {!collapsed && (
              <span>{loggingOut ? 'Signing out...' : 'Sign Out'}</span>
            )}
          </button>

          {/* System Status */}
          {!collapsed ? (
            <div className="rounded-lg p-3 bg-white/30 border border-slate-900/20 backdrop-blur-sm">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></div>
                <span className="text-slate-500 text-[10px] font-medium tracking-wider uppercase">Online</span>
              </div>
              <div className="text-xs space-y-1">
                <div className="flex justify-between items-center">
                  <span className="text-slate-400 text-[10px]">EST</span>
                  <span className="text-slate-600 font-mono font-medium tabular-nums">{time}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex justify-center" title="System Online">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></div>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Top Bar */}
        <header className="h-14 bg-white border-b border-surface-200 flex items-center justify-between px-6 flex-shrink-0">
          <div className="flex items-center gap-3">
            {/* Breadcrumb */}
            <nav className="flex items-center gap-2 text-sm">
              <span className="text-ink-subtle">Hashed</span>
              <span className="text-ink-subtle">/</span>
              <span className="font-medium text-ink">
                {navItems.find(i => i.href === pathname)?.label ?? 'Dashboard'}
              </span>
            </nav>
          </div>

          <div className="flex items-center gap-4">
            {/* Live badge */}
            <div className="flex items-center gap-2 px-3 py-1.5 bg-matrix-500/10 border border-matrix-500/30 rounded-full">
              <div className="live-dot"></div>
              <span className="text-xs font-mono text-matrix-600 font-medium">LIVE</span>
            </div>

            {/* Docs link */}
            <a
              href="https://github.com/Josoriop9/IAMandagent"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-ink-muted hover:text-ink flex items-center gap-1.5 transition-colors"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
              </svg>
              Docs
            </a>
          </div>
        </header>

        {/* Page Content - Responsive to sidebar */}
        <main className="flex-1 overflow-y-auto">
          <div className="p-6 max-w-7xl mx-auto w-full">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
