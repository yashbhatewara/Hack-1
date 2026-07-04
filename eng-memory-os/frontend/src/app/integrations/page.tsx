'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  GitFork, CheckCircle, AlertTriangle, Loader2, ArrowRight,
  Database, MessageSquare, BookOpen, Key, Terminal as TerminalIcon
} from 'lucide-react';
import { integrationApi } from '@/lib/api';
import Link from 'next/link';

interface LogLine {
  id: string;
  type: 'info' | 'success' | 'error' | 'warn';
  message: string;
  timestamp: string;
}

const PROVIDERS = [
  { id: 'github', name: 'GitHub', desc: 'Sync issues, PRs, and review comments.', emoji: '🐙', active: true },
  { id: 'jira', name: 'Jira Software', desc: 'Sync project boards, tasks, and stories.', emoji: '🎫', active: false },
  { id: 'slack', name: 'Slack', desc: 'Sync discussion channels and threads.', emoji: '💬', active: false },
  { id: 'notion', name: 'Notion Workspace', desc: 'Sync documentation, wikis, and notes.', emoji: '📝', active: false },
];

export default function IntegrationsPage() {
  const queryClient = useQueryClient();
  const [repoUrl, setRepoUrl] = useState('');
  const [token, setToken] = useState('');
  const [limit, setLimit] = useState(30);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [syncedRepo, setSyncedRepo] = useState<{ owner: string; name: string; count: number } | null>(null);

  const addLog = (message: string, type: LogLine['type'] = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    const id = Math.random().toString(36).substring(7);
    setLogs((prev) => [...prev, { id, type, message, timestamp }]);
  };

  const mutation = useMutation({
    mutationFn: integrationApi.syncGithub,
    onMutate: () => {
      setLogs([]);
      setSyncedRepo(null);
      addLog(`Initializing GitHub integration sync...`, 'info');
      addLog(`Parsing repository URL: ${repoUrl}`, 'info');
      if (token) {
        addLog(`Authorization token supplied. Using authenticated sessions.`, 'info');
      } else {
        addLog(`No token supplied. Using public unauthenticated endpoints (subject to rate limit).`, 'warn');
      }
    },
    onSuccess: (data) => {
      addLog(`Connection established with GitHub API successfully.`, 'success');
      addLog(`Discovered issues and PRs in ${data.repo_owner}/${data.repo_name}.`, 'info');
      addLog(`Queueing ${data.synced_count} items through the semantic ingestion pipeline...`, 'info');
      addLog(`Completed repository ingestion. All items are processing in background!`, 'success');
      
      setSyncedRepo({
        owner: data.repo_owner,
        name: data.repo_name,
        count: data.synced_count,
      });
      queryClient.invalidateQueries({ queryKey: ['memories'] });
    },
    onError: (error: any) => {
      const errMsg = error.response?.data?.detail || error.message || 'An error occurred during synchronization';
      addLog(`Synchronization failed: ${errMsg}`, 'error');
    },
  });

  const handleSync = (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl) return;
    mutation.mutate({ repo_url: repoUrl, github_token: token || undefined, limit });
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-8 animate-fade-in">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">
          External <span className="gradient-text">Integrations</span>
        </h2>
        <p className="text-sm text-slate-400 mt-1">
          Automate the ingestion process. Replicate external systems directly into the Engineering Knowledge Graph.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Sync Controls / Main integration form */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card p-6 space-y-5 border border-surface-border">
            <div className="flex items-center gap-3">
              <span className="text-2xl">🐙</span>
              <div>
                <h3 className="text-md font-semibold text-white">GitHub Ingest Adapter</h3>
                <p className="text-xs text-slate-400 mt-0.5">Ingest code reviews, issues, and PR comments to map past architectural decisions.</p>
              </div>
            </div>

            <form onSubmit={handleSync} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Repository URL *</label>
                <div className="relative">
                  <GitFork className="absolute left-3 top-3 w-4 h-4 text-slate-500" />
                  <input
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    placeholder="https://github.com/huggingface/transformers"
                    className="input pl-10"
                    disabled={mutation.isPending}
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Key className="w-3.5 h-3.5" /> Personal Access Token (Optional)
                  </label>
                  <input
                    type="password"
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                    className="input font-mono text-xs"
                    disabled={mutation.isPending}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Ingest Limit</label>
                  <select
                    value={limit}
                    onChange={(e) => setLimit(Number(e.target.value))}
                    className="input text-xs"
                    disabled={mutation.isPending}
                  >
                    <option value={10}>Recent 10 Issues & PRs</option>
                    <option value={30}>Recent 30 Issues & PRs</option>
                    <option value={50}>Recent 50 Issues & PRs</option>
                    <option value={100}>Recent 100 Issues & PRs</option>
                  </select>
                </div>
              </div>

              <button
                type="submit"
                disabled={mutation.isPending || !repoUrl}
                className="btn-primary w-full py-2.5 flex items-center justify-center gap-2 mt-2 font-medium"
              >
                {mutation.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Synchronizing Repository...
                  </>
                ) : (
                  <>
                    <Database className="w-4 h-4" />
                    Ingest & Sync Repository
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Sync logs terminal */}
          {(logs.length > 0 || mutation.isPending) && (
            <div className="card p-5 border border-surface-border bg-slate-950/80 font-mono text-xs text-slate-300">
              <div className="flex items-center gap-2 border-b border-surface-border/40 pb-2 mb-3">
                <TerminalIcon className="w-4 h-4 text-brand-400" />
                <span className="text-white font-semibold">Synchronization Log Console</span>
                {mutation.isPending && (
                  <span className="ml-auto flex items-center gap-1.5 text-slate-500 animate-pulse">
                    <Loader2 className="w-3 h-3 animate-spin text-brand-400" /> Live
                  </span>
                )}
              </div>
              <div className="h-48 overflow-y-auto space-y-1.5 scrollbar-thin">
                {logs.map((log) => (
                  <div key={log.id} className="flex gap-2">
                    <span className="text-slate-500">[{log.timestamp}]</span>
                    <span className={
                      log.type === 'error' ? 'text-accent-red' :
                      log.type === 'success' ? 'text-accent-green' :
                      log.type === 'warn' ? 'text-accent-orange' : 'text-slate-300'
                    }>
                      {log.type === 'error' && '[ERROR] '}
                      {log.type === 'success' && '[SUCCESS] '}
                      {log.type === 'warn' && '[WARN] '}
                      {log.message}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Success summary redirect card */}
          <AnimatePresence>
            {syncedRepo && (
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="card p-5 border border-accent-green/30 bg-accent-green/5 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="flex items-start gap-3">
                  <CheckCircle className="w-5 h-5 text-accent-green shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-semibold text-white">Repository Ingest Complete!</h4>
                    <p className="text-xs text-slate-400 mt-1">
                      Successfully parsed and queued <strong>{syncedRepo.count}</strong> items from{' '}
                      <span className="text-slate-200 font-semibold">{syncedRepo.owner}/{syncedRepo.name}</span>.
                      The items are being chunked, extracted and indexed.
                    </p>
                  </div>
                </div>
                <Link href="/query">
                  <button className="btn-primary py-2 px-4 text-xs font-semibold flex items-center gap-1.5 shrink-0">
                    Ask a Query <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </Link>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Integration adapters grid - list view */}
        <div className="space-y-4">
          <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest px-1">Available Adapters</h3>
          
          <div className="space-y-3">
            {PROVIDERS.map((prov) => (
              <div
                key={prov.id}
                className={`card p-4 flex gap-3 border ${
                  prov.active ? 'border-brand-500/20 bg-surface-card' : 'border-surface-border/40 bg-surface/30 opacity-60'
                }`}
              >
                <span className="text-2xl mt-0.5">{prov.emoji}</span>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-white">{prov.name}</span>
                    {prov.active ? (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-green/10 text-accent-green border border-accent-green/20">
                        Active
                      </span>
                    ) : (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-500">
                        Soon
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400 mt-1">{prov.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
