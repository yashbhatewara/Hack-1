'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, Search, Filter, Trash2, ExternalLink,
  ChevronDown, Loader2, AlertTriangle,
} from 'lucide-react';
import { memoryApi, type Memory, type MemoryStatus } from '@/lib/api';
import { formatDistanceToNow } from 'date-fns';
import { clsx } from 'clsx';

const STATUS_OPTIONS: { value: MemoryStatus | ''; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'stale', label: 'Stale' },
  { value: 'pending', label: 'Pending' },
  { value: 'processing', label: 'Processing' },
  { value: 'failed', label: 'Failed' },
  { value: 'archived', label: 'Archived' },
];

const STATUS_CLASS: Record<string, string> = {
  active: 'badge-active', stale: 'badge-stale', pending: 'badge-pending',
  processing: 'badge-blue', failed: 'badge-failed', archived: 'badge-stale',
};

function MemoryRow({ memory, onDelete }: { memory: Memory; onDelete: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="card overflow-hidden"
    >
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-surface-hover transition-colors"
        onClick={() => setExpanded(e => !e)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-white truncate">{memory.title}</p>
            <span className={STATUS_CLASS[memory.status]}>{memory.status}</span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5 truncate">{memory.source_uri}</p>
        </div>

        <div className="hidden sm:flex items-center gap-4 text-xs text-slate-500 shrink-0">
          <span>{memory.author}</span>
          <span>{formatDistanceToNow(new Date(memory.updated_at), { addSuffix: true })}</span>
          <span className="font-mono">
            {(memory.importance_score).toFixed(1)}★
          </span>
          <span className="font-mono text-xs text-slate-600">
            {(memory.decay_factor * 100).toFixed(0)}% fresh
          </span>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <a
            href={memory.source_uri}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-ghost p-1.5"
            onClick={e => e.stopPropagation()}
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
          <button
            className="btn-ghost p-1.5 text-accent-red hover:bg-accent-red/10"
            onClick={e => { e.stopPropagation(); onDelete(memory.id); }}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
          <ChevronDown
            className={clsx('w-4 h-4 text-slate-500 transition-transform duration-200', expanded && 'rotate-180')}
          />
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 pt-2 border-t border-surface-border space-y-3">
              {/* Score bars */}
              <div className="grid grid-cols-3 gap-3 text-xs">
                {[
                  { label: 'Importance', value: memory.importance_score / 10 },
                  { label: 'Confidence', value: memory.confidence_score },
                  { label: 'Freshness', value: memory.decay_factor },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <div className="flex justify-between text-slate-400 mb-1">
                      <span>{label}</span>
                      <span>{(value * 100).toFixed(0)}%</span>
                    </div>
                    <div className="confidence-bar">
                      <div
                        className="confidence-fill bg-gradient-to-r from-brand-500 to-accent-cyan"
                        style={{ width: `${value * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              {/* Tags */}
              {memory.tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {memory.tags.map(t => (
                    <span key={t} className="badge-blue text-xs">{t}</span>
                  ))}
                </div>
              )}

              {/* Content preview */}
              <div className="code-block text-slate-300 leading-relaxed max-h-40 overflow-y-auto">
                {memory.raw_content}
              </div>

              <p className="text-xs text-slate-500">
                Accessed {memory.access_count} times · Created {formatDistanceToNow(new Date(memory.created_at), { addSuffix: true })}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function MemoriesPage() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<MemoryStatus | ''>('');
  const [search, setSearch] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['memories', 'list', statusFilter],
    queryFn: () => memoryApi.list({
      status: statusFilter || undefined,
      limit: 100,
    }),
  });

  const deleteMutation = useMutation({
    mutationFn: memoryApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['memories'] }),
  });

  const filtered = data?.items.filter(m =>
    !search || m.title.toLowerCase().includes(search.toLowerCase())
      || m.source_uri.toLowerCase().includes(search.toLowerCase())
  ) ?? [];

  return (
    <div className="p-6 space-y-5 animate-fade-in max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Brain className="w-6 h-6 text-brand-400" />
        <h2 className="text-2xl font-bold text-white">Memories</h2>
        {data && (
          <span className="badge-blue ml-auto">{data.total} total</span>
        )}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search memories…"
            className="input pl-9 h-9 text-sm w-64"
          />
        </div>
        <div className="flex items-center gap-1.5">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          {STATUS_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setStatusFilter(value)}
              className={clsx(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                statusFilter === value
                  ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30'
                  : 'text-slate-400 hover:text-white hover:bg-surface-hover'
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="skeleton h-14 rounded-xl" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-slate-500">
          <Brain className="w-12 h-12 text-slate-700" />
          <p className="text-sm">No memories found.</p>
        </div>
      ) : (
        <div className="space-y-2">
          <AnimatePresence mode="popLayout">
            {filtered.map(m => (
              <MemoryRow
                key={m.id}
                memory={m}
                onDelete={id => deleteMutation.mutate(id)}
              />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
