'use client';

import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, Database, Zap, Network, AlertTriangle, CheckCircle,
  ChevronDown, GitBranch, FolderGit2, Search, Clock, MessageSquare, RotateCw,
} from 'lucide-react';
import { memoryApi, systemApi, knowledgeApi, MemoryStats, Memory } from '@/lib/api';
import { formatDistanceToNow, format } from 'date-fns';
import { useState, useMemo } from 'react';

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

function StatusBar({ stats }: { stats: MemoryStats }) {
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
          {label} <strong>{stats[key as keyof MemoryStats] ?? 0}</strong>
        </span>
      ))}
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────

/** Extract a human-readable repo label from a GitHub source URI. */
function repoFromUri(uri: string): string {
  try {
    const u = new URL(uri);
    // e.g. github.com/owner/repo/blob/…  → "owner/repo"
    const parts = u.pathname.split('/').filter(Boolean);
    if (parts.length >= 2) return `${parts[0]}/${parts[1]}`;
    return u.hostname;
  } catch {
    // not a URL — return the raw string trimmed
    return uri.split('/').slice(0, 2).join('/') || uri;
  }
}

// Palette of accent colours cycled per repo
const REPO_COLORS = [
  { ring: 'ring-brand-500',      bg: 'bg-brand-500/15',      icon: 'text-brand-400'      },
  { ring: 'ring-accent-cyan',    bg: 'bg-accent-cyan/15',    icon: 'text-accent-cyan'    },
  { ring: 'ring-accent-purple',  bg: 'bg-accent-purple/15',  icon: 'text-accent-purple'  },
  { ring: 'ring-accent-orange',  bg: 'bg-accent-orange/15',  icon: 'text-accent-orange'  },
  { ring: 'ring-accent-green',   bg: 'bg-accent-green/15',   icon: 'text-accent-green'   },
];

// ─── Single repo accordion ────────────────────────────────

function RepoGroup({
  repo, memories, colorIdx, defaultOpen,
}: {
  repo: string;
  memories: Memory[];
  colorIdx: number;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const col = REPO_COLORS[colorIdx % REPO_COLORS.length];

  const statusClass: Record<string, string> = {
    active: 'badge-active', stale: 'badge-stale', pending: 'badge-pending',
    processing: 'badge-blue', failed: 'badge-failed', archived: 'badge-stale',
  };

  return (
    <div className={`rounded-xl ring-1 ${col.ring} overflow-hidden`}>
      {/* Header */}
      <button
        onClick={() => setOpen(o => !o)}
        className={`w-full flex items-center gap-3 px-4 py-3 ${col.bg} hover:brightness-110 transition-all`}
      >
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${col.bg} ring-1 ${col.ring}`}>
          <FolderGit2 className={`w-4 h-4 ${col.icon}`} />
        </div>
        <div className="flex-1 min-w-0 text-left">
          <p className={`text-sm font-semibold truncate ${col.icon}`}>{repo}</p>
        </div>
        <span className={`text-xs font-mono px-2 py-0.5 rounded-full ring-1 ${col.ring} ${col.icon} bg-surface`}>
          {memories.length} log{memories.length !== 1 ? 's' : ''}
        </span>
        <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown className="w-4 h-4 text-slate-400" />
        </motion.div>
      </button>

      {/* Log rows */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="rows"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="divide-y divide-surface-hover">
              {memories.map((m, i) => (
                <motion.div
                  key={m.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-surface-hover transition-colors cursor-pointer"
                >
                  <GitBranch className="w-3.5 h-3.5 text-slate-600 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">{m.title}</p>
                    <p className="text-xs text-slate-500 truncate mt-0.5">{m.source_uri}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={statusClass[m.status] ?? 'badge-stale'}>{m.status}</span>
                    <span className="text-xs text-slate-500 whitespace-nowrap">
                      {formatDistanceToNow(new Date(m.updated_at), { addSuffix: true })}
                    </span>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Recent memories list ──────────────────────────────────

function RecentMemories({ memStats }: { memStats?: MemoryStats }) {
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['memories', 'recent'],
    queryFn: () => memoryApi.list({ limit: 500 }),   // fetch ALL repos
    refetchInterval: 30_000,                          // auto-refresh every 30s
    staleTime: 10_000,
  });

  // Group memories by repo, preserving insertion order
  const groups = useMemo(() => {
    if (!data?.items) return [];
    const map = new Map<string, Memory[]>();
    for (const m of data.items) {
      const key = repoFromUri(m.source_uri);
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(m);
    }
    return Array.from(map.entries());
  }, [data]);

  return (
    <div className="space-y-4">
      {/* Section header with refresh button */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-white">Ingested Repositories</h3>
          {!isLoading && (
            <span className="text-xs text-slate-500">{groups.length} repo{groups.length !== 1 ? 's' : ''} · {data?.total ?? 0} memories</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {memStats && <StatusBar stats={memStats} />}
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            title="Refresh now"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-surface-hover transition-colors disabled:opacity-40"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Body */}
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="skeleton h-14 w-full rounded-xl" />
          ))}
        </div>
      ) : !groups.length ? (
        <div className="text-center py-10 text-slate-500 text-sm">
          No memories ingested yet. Try the <strong>Ingest</strong> or <strong>Integrations</strong> tab!
        </div>
      ) : (
        <div className="space-y-3">
          {groups.map(([repo, mems], idx) => (
            <RepoGroup
              key={repo}
              repo={repo}
              memories={mems}
              colorIdx={idx}
              defaultOpen={idx === 0}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Query log panel ─────────────────────────────────────

interface QueryLogEntry {
  id: string;
  raw_query: string;
  classified_intent: string;
  response_text: string;
  confidence: number;
  is_degraded: boolean;
  total_time_ms: number;
  retry_count: number;
  created_at: string;
}

function QueryLogItem({ entry, index }: { entry: QueryLogEntry; index: number }) {
  const [open, setOpen] = useState(false);
  const isAgentic = entry.classified_intent !== 'rag';
  const confidencePct = Math.round((entry.confidence ?? 0) * 100);
  const clean = entry.response_text
    ?.replace(/\s*\[\d+\]\s*/g, '')
    .replace(/\[E-[a-f0-9-]+\]/gi, '')
    .trim() ?? '';

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      className="rounded-xl ring-1 ring-surface-border overflow-hidden"
    >
      {/* Header row */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-start gap-3 px-4 py-3 bg-surface-dark hover:bg-surface-hover transition-colors text-left"
      >
        <div className="w-6 h-6 rounded-lg bg-brand-500/20 flex items-center justify-center shrink-0 mt-0.5">
          <MessageSquare className="w-3.5 h-3.5 text-brand-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white line-clamp-1">{entry.raw_query}</p>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className={isAgentic ? 'badge-blue' : 'badge-stale'}>
              {isAgentic ? 'Agentic' : 'Fast RAG'}
            </span>
            <span className={entry.is_degraded ? 'badge-pending' : 'badge-active'}>
              {confidencePct}% conf
            </span>
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {entry.total_time_ms.toFixed(0)}ms
            </span>
            <span className="text-xs text-slate-500">
              {format(new Date(entry.created_at), 'MMM d, HH:mm')}
            </span>
          </div>
        </div>
        <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }} className="shrink-0 mt-1">
          <ChevronDown className="w-4 h-4 text-slate-400" />
        </motion.div>
      </button>

      {/* Answer body */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="answer"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="px-4 py-3 border-t border-surface-border bg-surface-dark/60">
              {/* Confidence bar */}
              <div className="h-1 w-full rounded-full bg-surface-border mb-3">
                <div
                  className={`h-1 rounded-full ${
                    confidencePct >= 60
                      ? 'bg-gradient-to-r from-accent-green to-accent-cyan'
                      : 'bg-gradient-to-r from-accent-orange to-accent-red'
                  }`}
                  style={{ width: `${confidencePct}%` }}
                />
              </div>
              <p className="text-sm text-slate-200 whitespace-pre-wrap leading-7 font-sans">
                {clean || <span className="text-slate-500 italic">No response recorded.</span>}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function QueryLogPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ['query', 'history'],
    queryFn: () => memoryApi.history(50),
    refetchInterval: 30_000,
  });

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(3)].map((_, i) => <div key={i} className="skeleton h-14 w-full rounded-xl" />)}
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="text-center py-8 text-slate-500 text-sm">
        No queries yet. Go to the <strong>Query</strong> tab and ask something!
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {(data as QueryLogEntry[]).map((entry, i) => (
        <QueryLogItem key={entry.id} entry={entry} index={i} />
      ))}
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
        className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4"
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
          label="Queries Run"
          value={memStats?.total_queries ?? '—'}
          icon={Search}
          color="bg-brand-500/50"
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
        <div className="lg:col-span-2">
          <RecentMemories memStats={memStats} />
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

      {/* Query Log */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-brand-400" />
          <h3 className="text-sm font-semibold text-white">Query Log</h3>
          <span className="text-xs text-slate-500">— every query you've run, with full answers</span>
        </div>
        <QueryLogPanel />
      </div>
    </div>
  );
}
