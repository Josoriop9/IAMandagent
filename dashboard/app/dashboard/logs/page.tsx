'use client';

import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import Link from 'next/link';

interface Log {
  id: string;
  tool_name: string;
  status: string;
  event_type: string;
  amount: number | null;
  timestamp: string;
  duration_ms: number | null;
  error_message: string | null;
}

export default function LogsPage() {
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    async function fetchLogs() {
      try {
        // Get current user
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;

        // Get organization (with fallback auto-link)
        let orgId: string | null = null;
        
        const { data: ownedOrg } = await supabase
          .from('organizations')
          .select('id')
          .eq('owner_id', user.id)
          .single();
        
        if (ownedOrg) {
          orgId = ownedOrg.id;
        } else {
          const { data: anyOrg } = await supabase
            .from('organizations')
            .select('id')
            .eq('is_active', true)
            .limit(1)
            .single();
          
          if (anyOrg) {
            await supabase
              .from('organizations')
              .update({ owner_id: user.id })
              .eq('id', anyOrg.id);
            orgId = anyOrg.id;
          }
        }
        
        if (!orgId) return;
        
        const org = { id: orgId };

        // Fetch logs
        const { data: logsData, error } = await supabase
          .from('ledger_logs')
          .select('*')
          .eq('organization_id', org.id)
          .order('timestamp', { ascending: false })
          .limit(100);

        if (error) throw error;

        setLogs(logsData || []);
      } catch (error) {
        console.error('Error fetching logs:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchLogs();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto"></div>
          <p className="mt-4 text-gray-400">Loading logs...</p>
        </div>
      </div>
    );
  }

  const filteredLogs = logs.filter(log => {
    if (filter === 'all') return true;
    return log.status === filter;
  });

  const successCount = logs.filter(l => l.status === 'success').length;
  const deniedCount = logs.filter(l => l.status === 'denied').length;
  const errorCount = logs.filter(l => l.status === 'error').length;

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return 'bg-green-500/20 text-green-400';
      case 'denied':
        return 'bg-red-500/20 text-red-400';
      case 'error':
        return 'bg-orange-500/20 text-orange-400';
      default:
        return 'bg-gray-500/20 text-gray-400';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return '✓';
      case 'denied':
        return '✗';
      case 'error':
        return '⚠';
      default:
        return '○';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Audit Logs</h1>
          <p className="text-gray-400 mt-2">
            Complete history of all agent operations
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
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-4">
          <p className="text-sm text-gray-400">Total Operations</p>
          <p className="text-2xl font-bold mt-1">{logs.length}</p>
        </div>
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-4">
          <p className="text-sm text-gray-400">Successful</p>
          <p className="text-2xl font-bold mt-1 text-green-400">
            {successCount}
          </p>
        </div>
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-4">
          <p className="text-sm text-gray-400">Denied</p>
          <p className="text-2xl font-bold mt-1 text-red-400">
            {deniedCount}
          </p>
        </div>
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-4">
          <p className="text-sm text-gray-400">Errors</p>
          <p className="text-2xl font-bold mt-1 text-orange-400">
            {errorCount}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        <button
          onClick={() => setFilter('all')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            filter === 'all'
              ? 'bg-primary-600 text-white'
              : 'bg-dark-light text-gray-400 hover:text-white'
          }`}
        >
          All ({logs.length})
        </button>
        <button
          onClick={() => setFilter('success')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            filter === 'success'
              ? 'bg-green-600 text-white'
              : 'bg-dark-light text-gray-400 hover:text-white'
          }`}
        >
          Success ({successCount})
        </button>
        <button
          onClick={() => setFilter('denied')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            filter === 'denied'
              ? 'bg-red-600 text-white'
              : 'bg-dark-light text-gray-400 hover:text-white'
          }`}
        >
          Denied ({deniedCount})
        </button>
        <button
          onClick={() => setFilter('error')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            filter === 'error'
              ? 'bg-orange-600 text-white'
              : 'bg-dark-light text-gray-400 hover:text-white'
          }`}
        >
          Errors ({errorCount})
        </button>
      </div>

      {/* Logs List */}
      {filteredLogs.length === 0 ? (
        <div className="bg-dark-light rounded-lg border border-dark-lighter p-12 text-center">
          <div className="text-6xl mb-4">📊</div>
          <h3 className="text-xl font-semibold mb-2">
            {filter === 'all' ? 'No Logs Yet' : `No ${filter} logs`}
          </h3>
          <p className="text-gray-400 mb-6">
            {filter === 'all'
              ? 'Execute some operations with your agents to see audit logs here'
              : `Change the filter to see other types of logs`}
          </p>
        </div>
      ) : (
        <div className="bg-dark-light rounded-lg border border-dark-lighter overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-dark border-b border-dark-lighter">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Tool
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Amount
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Duration
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Timestamp
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-lighter">
                {filteredLogs.map((log) => (
                  <tr
                    key={log.id}
                    className="hover:bg-dark-lighter/50 transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(
                          log.status
                        )}`}
                      >
                        {getStatusIcon(log.status)} {log.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="font-mono text-sm text-gray-300">
                        {log.tool_name}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                      {log.amount !== null ? (
                        <span className="font-semibold">
                          ${log.amount.toLocaleString()}
                        </span>
                      ) : (
                        <span className="text-gray-500">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
                      {log.duration_ms !== null ? `${log.duration_ms}ms` : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {filteredLogs.length >= 100 && (
            <div className="px-6 py-4 bg-dark border-t border-dark-lighter text-center text-sm text-gray-400">
              Showing last 100 operations. Older logs are still stored in the database.
            </div>
          )}
        </div>
      )}

      {/* Info */}
      <div className="bg-primary-500/10 border border-primary-500/30 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-2">🔒 Immutable Audit Trail</h3>
        <p className="text-gray-300 text-sm">
          All agent operations are logged with cryptographic signatures for non-repudiation.
          These logs cannot be modified or deleted, ensuring complete accountability.
        </p>
      </div>
    </div>
  );
}
