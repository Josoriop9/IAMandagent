'use client';

import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import Link from 'next/link';

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

  useEffect(() => {
    async function fetchAgents() {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;

        const { data: org } = await supabase
          .from('organizations')
          .select('id')
          .eq('owner_id', user.id)
          .single();

        if (!org) return;

        const { data: agentsData, error } = await supabase
          .from('agents')
          .select('*')
          .eq('organization_id', org.id)
          .order('created_at', { ascending: false });

        if (error) throw error;

        setAgents(agentsData || []);
      } catch (error) {
        console.error('Error fetching agents:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchAgents();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto"></div>
          <p className="mt-4 text-gray-400">Loading agents...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Agents</h1>
          <p className="text-gray-400 mt-2">
            Manage your AI agents and their identities
          </p>
        </div>
        <Link
          href="/dashboard"
          className="px-4 py-2 bg-dark-light hover:bg-dark-lighter border border-dark-lighter rounded-lg transition-colors"
        >
          ← Back
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-4">
          <p className="text-sm text-gray-400">Total Agents</p>
          <p className="text-2xl font-bold mt-1">{agents.length}</p>
        </div>
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-4">
          <p className="text-sm text-gray-400">Active</p>
          <p className="text-2xl font-bold mt-1 text-green-400">
            {agents.filter(a => a.is_active).length}
          </p>
        </div>
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-4">
          <p className="text-sm text-gray-400">Inactive</p>
          <p className="text-2xl font-bold mt-1 text-gray-500">
            {agents.filter(a => !a.is_active).length}
          </p>
        </div>
      </div>

      {agents.length === 0 ? (
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-12 text-center">
          <div className="text-6xl mb-4">🤖</div>
          <h3 className="text-xl font-semibold mb-2">No Agents Yet</h3>
          <p className="text-gray-400 mb-6">
            Start using the Hashed SDK to register your first agent
          </p>
          <code className="bg-dark px-4 py-2 rounded text-sm">
            python3 examples/my_first_agent.py
          </code>
        </div>
      ) : (
        <div className="space-y-4">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className="bg-dark-light rounded-lg border border-dark-lighter p-6 hover:border-primary-500/50 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="text-xl font-semibold">{agent.name}</h3>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        agent.is_active
                          ? 'bg-green-500/20 text-green-400'
                          : 'bg-gray-500/20 text-gray-400'
                      }`}
                    >
                      {agent.is_active ? 'Active' : 'Inactive'}
                    </span>
                    <span className="px-2 py-1 rounded text-xs font-medium bg-primary-500/20 text-primary-400">
                      {agent.agent_type}
                    </span>
                  </div>

                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-gray-400">Public Key</p>
                      <code className="text-primary-400 font-mono text-xs">
                        {agent.public_key.substring(0, 16)}...
                      </code>
                    </div>
                    <div>
                      <p className="text-gray-400">Agent ID</p>
                      <code className="text-gray-300 font-mono text-xs">
                        {agent.id.substring(0, 8)}...
                      </code>
                    </div>
                    <div>
                      <p className="text-gray-400">Created</p>
                      <p className="text-gray-300">
                        {new Date(agent.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-400">Last Seen</p>
                      <p className="text-gray-300">
                        {agent.last_seen_at
                          ? new Date(agent.last_seen_at).toLocaleString()
                          : 'Never'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
