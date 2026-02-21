'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { supabase } from '@/lib/supabase';

export default function DashboardOverview() {
  const [stats, setStats] = useState({
    agents: 0,
    policies: 0,
    logs: 0,
    recentActivity: [] as any[],
  });
  const [organization, setOrganization] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchRealData() {
      try {
        // 1. Get current user
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;

        // 2. Get user's organization
        const { data: org, error: orgError } = await supabase
          .from('organizations')
          .select('*')
          .eq('owner_id', user.id)
          .single();

        if (orgError) {
          console.error('Error fetching organization:', orgError);
          return;
        }

        setOrganization(org);

        // 3. Count agents
        const { count: agentCount } = await supabase
          .from('agents')
          .select('*', { count: 'exact', head: true })
          .eq('organization_id', org.id);

        // 4. Count policies
        const { count: policyCount } = await supabase
          .from('policies')
          .select('*', { count: 'exact', head: true })
          .eq('organization_id', org.id);

        // 5. Count logs
        const { count: logCount } = await supabase
          .from('ledger_logs')
          .select('*', { count: 'exact', head: true })
          .eq('organization_id', org.id);

        setStats({
          agents: agentCount || 0,
          policies: policyCount || 0,
          logs: logCount || 0,
          recentActivity: [],
        });
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchRealData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto"></div>
          <p className="mt-4 text-gray-400">Loading your data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Dashboard Overview</h1>
        <p className="text-gray-400 mt-2">
          Welcome to your AI Agent Control Plane
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Agents */}
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">Active Agents</p>
              <p className="text-3xl font-bold mt-2">{stats.agents}</p>
            </div>
            <div className="text-4xl">🤖</div>
          </div>
          <Link
            href="/dashboard/agents"
            className="text-primary-500 hover:text-primary-400 text-sm mt-4 inline-block"
          >
            View all →
          </Link>
        </div>

        {/* Policies */}
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">Policies</p>
              <p className="text-3xl font-bold mt-2">{stats.policies}</p>
            </div>
            <div className="text-4xl">🛡️</div>
          </div>
          <Link
            href="/dashboard/policies"
            className="text-primary-500 hover:text-primary-400 text-sm mt-4 inline-block"
          >
            Manage policies →
          </Link>
        </div>

        {/* Logs */}
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">Total Operations</p>
              <p className="text-3xl font-bold mt-2">{stats.logs.toLocaleString()}</p>
            </div>
            <div className="text-4xl">📊</div>
          </div>
          <Link
            href="/dashboard/logs"
            className="text-primary-500 hover:text-primary-400 text-sm mt-4 inline-block"
          >
            View logs →
          </Link>
        </div>
      </div>

      {/* API Key Section */}
      {organization && (
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-6">
          <h2 className="text-xl font-semibold mb-4">Your API Key</h2>
          <p className="text-sm text-gray-400 mb-4">
            Use this key to connect your AI agents to the control plane
          </p>
          <div className="flex items-center space-x-2">
            <code className="flex-1 bg-dark px-4 py-3 rounded-lg text-sm font-mono text-primary-400 border border-dark-lighter">
              {organization.api_key}
            </code>
            <button
              onClick={() => {
                navigator.clipboard.writeText(organization.api_key);
                alert('API key copied to clipboard!');
              }}
              className="px-4 py-3 bg-primary-600 hover:bg-primary-700 rounded-lg text-sm font-semibold transition-colors whitespace-nowrap"
            >
              Copy
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            ⚠️ Keep this key secret! Anyone with this key can control your agents.
          </p>
        </div>
      )}

      {/* Quick Actions */}
      <div className="bg-dark-light rounded-lg border border-dark-lighter p-6">
        <h2 className="text-xl font-semibold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Link
            href="/dashboard/agents"
            className="p-4 bg-dark border border-dark-lighter rounded-lg hover:border-primary-500 transition-colors"
          >
            <h3 className="font-semibold mb-2">Register New Agent</h3>
            <p className="text-sm text-gray-400">
              Add a new AI agent to your organization
            </p>
          </Link>
          <Link
            href="/dashboard/policies"
            className="p-4 bg-dark border border-dark-lighter rounded-lg hover:border-primary-500 transition-colors"
          >
            <h3 className="font-semibold mb-2">Create Policy</h3>
            <p className="text-sm text-gray-400">
              Define rules and limits for agent operations
            </p>
          </Link>
        </div>
      </div>

      {/* Getting Started */}
      <div className="bg-primary-500/10 border border-primary-500/30 rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-2">🚀 Getting Started</h2>
        <p className="text-gray-300 mb-4">
          Connect your first AI agent to start monitoring and controlling its operations.
        </p>
        <div className="space-y-2 text-sm">
          <p className="text-gray-400">
            1. Install the SDK: <code className="bg-dark px-2 py-1 rounded">pip install hashed-sdk</code>
          </p>
          <p className="text-gray-400">
            2. Initialize with your API key
          </p>
          <p className="text-gray-400">
            3. Wrap your agent tools with @guard decorator
          </p>
        </div>
        <Link
          href="https://github.com/yourorg/hashed-sdk"
          target="_blank"
          className="text-primary-400 hover:text-primary-300 text-sm mt-4 inline-block"
        >
          View documentation →
        </Link>
      </div>
    </div>
  );
}
