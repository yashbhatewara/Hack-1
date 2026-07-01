'use client';

import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  Brain, Database, Zap, TrendingUp, Network, Clock, AlertTriangle, CheckCircle,
} from 'lucide-react';
import { memoryApi, systemApi, knowledgeApi } from '@/lib/api';
import { formatDistanceToNow } from 'date-fns';

// ─── Animated stat card ───────────────────────────────────

function StatCard({
  label, value, icon: Icon, color, suffix = '',
}: {
  label: string; value: string | number; icon: React.ElementType;
  color: string; suffix?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="card p-5 flex items-center gap-4"
    >
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${color}`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div>
        <p className="text-2xl font-bold text-white">
          {value}<span className="text-sm font-normal text-slate-400 ml-1">{suffix}</span>
        </p>
        <p className="text-xs text-slate-400 mt-0.5">{label}</p>
      </div>
    </motion.div>
  );
}

// ─── Status pill ──────────────────────────────────────────

function StatusBar({ stats }: { stats: Record<string, number> }) {
  const items = [
    { key: 'active',     label: 'Active',     cls: 'badge-active'  },
    { key: 'stale',      label: 'Stale',      cls: 'badge-stale'   },
    { key: 'pending',    label: 'Pending',    cls: 'badge-pending' },
    { key: 'processing', label: 'Processing', cls: 'badge-blue'    },
    { key: 'failed',     label: 'Failed',     cls: 'badge-failed'  },
  ];
  return (
    <div className="flex flex-wrap gap-2">
      {items.map(({ key, label, cls }) => (
        <span key={key} className={cls}>
          {label} <strong>{stats[key] ?? 0}</strong>
        </span>
      ))}
    </div>
  );
}

// ─── Recent memories list ─────────────────────────────────

function RecentMemories() {
  const { data, isLoading } = useQuery({
    queryKey: ['memories', 'recent'],
    queryFn: () => memoryApi.list({ limit: 8 }),
  });

  const statusClass: Record<string, string> = {
    active: 'badge-active', stale: 'badge-stale', pending: 'badge-pending',
    processing: 'badge-blue', failed: 'badge-failed', archived: 'badge-stale',
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="skeleton h-14 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {data?.items.map((m, i) => (
        <motion.div
          key={m.id}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.05 }}
          className="card-hover p-3.5 flex items-center gap-3 cursor-pointer"
        >
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-white truncate">{m.title}</p>
            <p className="text-xs text-slate-400 mt-0.5 truncate">{m.source_uri}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className={statusClass[m.status] ?? 'badge-stale'}>{m.status}</span>
            <span className="text-xs text-slate-500">
              {formatDistanceToNow(new Date(m.updated_at), { addSuffix: true })}
            </span>
          </div>
        </motion.div>
      ))}
      {!data?.items.length && (
        <div className="text-center py-10 text-slate-500 text-sm">
          No memories ingested yet. Try the <strong>Ingest</strong> tab!
        </div>
      )}
    </div>
  );
}

// ─── Provider health row ──────────────────────────────────

function ProviderHealth({ providers }: { providers: Record<string, string> }) {
  const statusIcon = (s: string) =>
    s === 'healthy' || s === 'circuit_closed'
      ? <CheckCircle className="w-4 h-4 text-accent-green" />
      : <AlertTriangle className="w-4 h-4 text-accent-orange" />;

  return (
    <div className="space-y-2">
      {Object.entries(providers).map(([provider, status]) => (
        <div key={provider} className="flex items-center justify-between px-3 py-2 rounded-lg bg-surface-hover">
          <span className="text-sm text-white capitalize">{provider}</span>
          <div className="flex items-center gap-2">
            {statusIcon(status)}
            <span className="text-xs text-slate-400 capitalize">{status}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────

export default function DashboardPage() {
  const { data: memStats } = useQuery({
    queryKey: ['memories', 'stats'],
    queryFn: memoryApi.stats,
    refetchInterval: 30_000,
  });

  const { data: health } = useQuery({
    queryKey: ['system', 'health'],
    queryFn: systemApi.health,
    refetchInterval: 15_000,
  });

  const { data: tokens } = useQuery({
    queryKey: ['system', 'tokens'],
    queryFn: systemApi.tokens,
    refetchInterval: 60_000,
  });

  const { data: graphStats } = useQuery({
    queryKey: ['knowledge', 'stats'],
    queryFn: knowledgeApi.stats,
    refetchInterval: 60_000,
  });

  const stagger = { hidden: {}, visible: { transition: { staggerChildren: 0.07 } } };

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">
          Engineering{' '}
          <span className="gradient-text">Memory OS</span>
        </h2>
        <p className="text-sm text-slate-400 mt-1">
          Real-time overview of your organizational knowledge system.
        </p>
      </div>

      {/* Stat grid */}
      <motion.div
        variants={stagger}
        initial="hidden"
        animate="visible"
        className="grid grid-cols-2 lg:grid-cols-4 gap-4"
      >
        <StatCard
          label="Total Memories"
          value={memStats?.total ?? '—'}
          icon={Brain}
          color="bg-brand-600"
        />
        <StatCard
          label="Active Memories"
          value={memStats?.active ?? '—'}
          icon={CheckCircle}
          color="bg-accent-green/80"
        />
        <StatCard
          label="Knowledge Nodes"
          value={(graphStats as Record<string,number>)?.total_nodes ?? '—'}
          icon={Network}
          color="bg-accent-cyan/80"
        />
        <StatCard
          label="LLM Cost Today"
          value={tokens ? `$${tokens.total_cost_usd.toFixed(4)}` : '—'}
          icon={Zap}
          color="bg-accent-purple/80"
        />
      </motion.div>

      {/* Two-column body */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Recent memories */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Recent Memories</h3>
            {memStats && <StatusBar stats={memStats} />}
          </div>
          <RecentMemories />
        </div>

        {/* Side panel */}
        <div className="space-y-4">

          {/* System health */}
          <div className="card p-4 space-y-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Database className="w-4 h-4 text-accent-cyan" />
              System Health
            </h3>
            {health ? (
              <>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">Uptime</span>
                  <span className="text-white font-mono">
                    {Math.floor(health.uptime_seconds / 3600)}h {Math.floor((health.uptime_seconds % 3600) / 60)}m
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">Database</span>
                  <span className="text-accent-green capitalize">{health.database}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">Qdrant</span>
                  <span className="text-accent-green capitalize">{health.qdrant}</span>
                </div>
                <ProviderHealth providers={health.llm_providers} />
              </>
            ) : (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => <div key={i} className="skeleton h-8" />)}
              </div>
            )}
          </div>

          {/* Token usage */}
          <div className="card p-4 space-y-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Zap className="w-4 h-4 text-accent-orange" />
              Token Usage
            </h3>
            {tokens ? (
              <>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Requests</span>
                  <span className="text-white">{tokens.total_requests.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Total Tokens</span>
                  <span className="text-white">{tokens.total_tokens.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Total Cost</span>
                  <span className="text-accent-orange font-mono">${tokens.total_cost_usd.toFixed(4)}</span>
                </div>
                {/* Prompt vs completion bar */}
                <div className="space-y-1">
                  <div className="confidence-bar">
                    <div
                      className="confidence-fill bg-gradient-to-r from-brand-500 to-accent-cyan"
                      style={{ width: `${tokens.total_tokens > 0 ? (tokens.total_prompt_tokens / tokens.total_tokens) * 100 : 0}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>Prompt: {tokens.total_prompt_tokens.toLocaleString()}</span>
                    <span>Completion: {tokens.total_completion_tokens.toLocaleString()}</span>
                  </div>
                </div>
              </>
            ) : (
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-6" />)}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
