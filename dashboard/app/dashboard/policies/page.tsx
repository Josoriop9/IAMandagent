'use client';

import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import Link from 'next/link';

interface Policy {
  id: string;
  tool_name: string;
  allowed: boolean;
  max_amount: number | null;
  requires_approval: boolean;
  created_at: string;
  agent_id: string | null;
}

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchPolicies() {
      try {
        // Get current user
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;

        // Get user's organization
        const { data: org } = await supabase
          .from('organizations')
          .select('id')
          .eq('owner_id', user.id)
          .single();

        if (!org) return;

        // Fetch policies
        const { data: policiesData, error } = await supabase
          .from('policies')
          .select('*')
          .eq('organization_id', org.id)
          .order('created_at', { ascending: false });

        if (error) throw error;

        setPolicies(policiesData || []);
      } catch (error) {
        console.error('Error fetching policies:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchPolicies();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto"></div>
          <p className="mt-4 text-gray-400">Loading policies...</p>
        </div>
      </div>
    );
  }

  const allowedPolicies = policies.filter(p => p.allowed);
  const deniedPolicies = policies.filter(p => !p.allowed);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Policies</h1>
          <p className="text-gray-400 mt-2">
            Manage permission rules for your AI agents
          </p>
        </div>
        <Link
          href="/dashboard"
          className="px-4 py-2 bg-dark-light hover:bg-dark-lighter border border-dark-lighter rounded-lg transition-colors"
        >
          ← Back
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-4">
          <p className="text-sm text-gray-400">Total Policies</p>
          <p className="text-2xl font-bold mt-1">{policies.length}</p>
        </div>
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-4">
          <p className="text-sm text-gray-400">Allowed</p>
          <p className="text-2xl font-bold mt-1 text-green-400">
            {allowedPolicies.length}
          </p>
        </div>
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-4">
          <p className="text-sm text-gray-400">Denied</p>
          <p className="text-2xl font-bold mt-1 text-red-400">
            {deniedPolicies.length}
          </p>
        </div>
      </div>

      {/* Policies List */}
      {policies.length === 0 ? (
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-12 text-center">
          <div className="text-6xl mb-4">🛡️</div>
          <h3 className="text-xl font-semibold mb-2">No Policies Yet</h3>
          <p className="text-gray-400 mb-6">
            Policies will be synced when you register an agent with the SDK
          </p>
          <div className="text-sm text-gray-500">
            <p>Policies define what operations your agents can perform:</p>
            <ul className="mt-2 space-y-1">
              <li>• Which tools/functions are allowed or denied</li>
              <li>• Maximum amounts for financial operations</li>
              <li>• Operations requiring human approval</li>
            </ul>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {policies.map((policy) => (
            <div
              key={policy.id}
              className="bg-dark-light rounded-lg border border-dark-lighter p-6"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="text-lg font-semibold">{policy.tool_name}</h3>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        policy.allowed
                          ? 'bg-green-500/20 text-green-400'
                          : 'bg-red-500/20 text-red-400'
                      }`}
                    >
                      {policy.allowed ? '✓ Allowed' : '✗ Denied'}
                    </span>
                    {policy.requires_approval && (
                      <span className="px-2 py-1 rounded text-xs font-medium bg-yellow-500/20 text-yellow-400">
                        Requires Approval
                      </span>
                    )}
                    {policy.agent_id === null && (
                      <span className="px-2 py-1 rounded text-xs font-medium bg-primary-500/20 text-primary-400">
                        Global
                      </span>
                    )}
                  </div>

                  <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                    {policy.max_amount !== null && (
                      <div>
                        <p className="text-gray-400">Max Amount</p>
                        <p className="text-gray-300 font-semibold">
                          ${policy.max_amount.toLocaleString()}
                        </p>
                      </div>
                    )}
                    <div>
                      <p className="text-gray-400">Scope</p>
                      <p className="text-gray-300">
                        {policy.agent_id ? 'Agent-specific' : 'All agents'}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-400">Created</p>
                      <p className="text-gray-300">
                        {new Date(policy.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info Box */}
      <div className="bg-primary-500/10 border border-primary-500/30 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-2">💡 About Policies</h3>
        <p className="text-gray-300 text-sm mb-3">
          Policies are synced from your agent code when using the SDK. To add or modify policies:
        </p>
        <ol className="text-sm text-gray-400 space-y-2 ml-4">
          <li>1. Define policies in your agent code when initializing HashedCore</li>
          <li>2. Run your agent - policies will sync automatically</li>
          <li>3. View and monitor them here in the dashboard</li>
        </ol>
      </div>
    </div>
  );
}
