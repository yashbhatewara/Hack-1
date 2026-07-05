'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Clock, MessageSquare, ChevronDown, Brain, Zap,
  CheckCircle, AlertTriangle, Search, RotateCw,
} from 'lucide-react';
import { memoryApi } from '@/lib/api';
import { format, formatDistanceToNow } from 'date-fns';
import { clsx } from 'clsx';

// ─── Types ────────────────────────────────────────────────

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

// ─── Single entry card ─────────────────────────────────────

function QueryHistoryItem({ entry, index }: { entry: QueryLogEntry; index: number }) {
  const [open, setOpen] = useState(false);
  const isAgentic = entry.classified_intent !== 'rag';
  const confidencePct = Math.round((entry.confidence ?? 0) * 100);
  const clean = (entry.response_text ?? '')
    .replace(/\s*\[\d+\]\s*/g, '')
    .replace(/\[E-[a-f0-9-]+\]/gi, '')
    .trim();

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.035 }}
      className="rounded-xl ring-1 ring-surface-border overflow-hidden"
    >
      {/* Header */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-start gap-3 px-5 py-4 bg-surface-card hover:bg-surface-hover transition-colors text-left"
      >
        {/* Index badge */}
        <span className="w-6 h-6 rounded-full bg-brand-500/20 text-brand-400 text-xs font-mono flex items-center justify-center shrink-0 mt-0.5">
          {index + 1}
        </span>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-white leading-snug line-clamp-2">
            {entry.raw_query}
          </p>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            {/* Mode */}
            <span className={clsx('text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1',
              isAgentic ? 'bg-brand-500/20 text-brand-300 ring-1 ring-brand-500/30'
                        : 'bg-slate-700 text-slate-300 ring-1 ring-slate-600')}>
              {isAgentic ? <Brain className="w-2.5 h-2.5" /> : <Zap className="w-2.5 h-2.5" />}
              {isAgentic ? 'Agentic' : 'Fast RAG'}
            </span>
            {/* Confidence */}
            <span className={clsx('text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1',
              entry.is_degraded
                ? 'bg-accent-orange/20 text-accent-orange ring-1 ring-accent-orange/30'
                : 'bg-accent-green/20 text-accent-green ring-1 ring-accent-green/30')}>
              {entry.is_degraded
                ? <AlertTriangle className="w-2.5 h-2.5" />
                : <CheckCircle className="w-2.5 h-2.5" />}
              {confidencePct}% confidence
            </span>
            {/* Latency */}
            <span className="text-[10px] text-slate-500 flex items-center gap-1">
              <Clock className="w-2.5 h-2.5" />
              {entry.total_time_ms?.toFixed(0) ?? '—'}ms
            </span>
            {/* Retries */}
            {entry.retry_count > 0 && (
              <span className="text-[10px] text-slate-500 flex items-center gap-1">
                <RotateCw className="w-2.5 h-2.5" />
                {entry.retry_count} {entry.retry_count === 1 ? 'retry' : 'retries'}
              </span>
            )}
            {/* Timestamp */}
            <span className="text-[10px] text-slate-600 ml-auto whitespace-nowrap">
              {format(new Date(entry.created_at), 'MMM d, yyyy · HH:mm')}
              {' · '}
              <span className="text-slate-500">
                {formatDistanceToNow(new Date(entry.created_at), { addSuffix: true })}
              </span>
            </span>
          </div>
        </div>

        <motion.div
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          className="shrink-0 mt-1"
        >
          <ChevronDown className="w-4 h-4 text-slate-400" />
        </motion.div>
      </button>

      {/* Expanded answer */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="answer"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.24, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="px-5 py-4 border-t border-surface-border bg-surface-dark/70 space-y-3">
              {/* Confidence bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span>Response confidence</span>
                  <span>{confidencePct}%</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-surface-border">
                  <div
                    className={clsx('h-1.5 rounded-full transition-all', confidencePct >= 60
                      ? 'bg-gradient-to-r from-accent-green to-accent-cyan'
                      : 'bg-gradient-to-r from-accent-orange to-accent-red')}
                    style={{ width: `${confidencePct}%` }}
                  />
                </div>
              </div>

              {/* Answer text */}
              <div className="text-sm text-slate-200 whitespace-pre-wrap leading-7 font-sans">
                {clean || (
                  <span className="text-slate-500 italic">No response text recorded for this query.</span>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─── Page ─────────────────────────────────────────────────

export default function QueryHistoryPage() {
  const [search, setSearch] = useState('');

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['query', 'history', 'full'],
    queryFn: () => memoryApi.history(100),
    refetchInterval: 60_000,
  });

  const entries = (data as QueryLogEntry[] | undefined) ?? [];

  const filtered = search.trim()
    ? entries.filter(e =>
        e.raw_query.toLowerCase().includes(search.toLowerCase()) ||
        e.response_text?.toLowerCase().includes(search.toLowerCase())
      )
    : entries;

  return (
    <div className="p-6 space-y-6 animate-fade-in max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Clock className="w-6 h-6 text-brand-400" />
            Query <span className="gradient-text">History</span>
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Every question you've asked — with the exact answer the system gave.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="btn-secondary flex items-center gap-2 shrink-0"
        >
          <RotateCw className={clsx('w-3.5 h-3.5', isFetching && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
        <input
          type="text"
          placeholder="Search queries or answers…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-surface-card border border-surface-border text-sm text-white
                     placeholder:text-slate-500 focus:outline-none focus:border-brand-500/60 transition-colors"
        />
        {search && (
          <button
            onClick={() => setSearch('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white text-xs"
          >
            ✕
          </button>
        )}
      </div>

      {/* Stats row */}
      {!isLoading && entries.length > 0 && (
        <div className="flex items-center gap-4 text-xs text-slate-400">
          <span><strong className="text-white">{entries.length}</strong> total queries</span>
          <span><strong className="text-white">{entries.filter(e => !e.is_degraded).length}</strong> high-confidence</span>
          <span><strong className="text-white">{entries.filter(e => e.classified_intent !== 'rag').length}</strong> agentic</span>
          {search && (
            <span className="text-brand-400">
              {filtered.length} matching "{search}"
            </span>
          )}
        </div>
      )}

      {/* List */}
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="skeleton h-20 w-full rounded-xl" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
          <MessageSquare className="w-14 h-14 text-slate-700" />
          <p className="text-slate-400 text-sm">
            {search ? `No queries match "${search}"` : 'No query history yet.'}
          </p>
          {!search && (
            <p className="text-slate-600 text-xs">
              Go to the <strong>Query</strong> tab and ask something!
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((entry, i) => (
            <QueryHistoryItem key={entry.id} entry={entry} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
