'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload, CheckCircle, AlertTriangle, X, Plus, Tag,
  FileText, Loader2,
} from 'lucide-react';
import { memoryApi, type SourceType } from '@/lib/api';
import { clsx } from 'clsx';

const SOURCE_TYPES: { value: SourceType; label: string; emoji: string }[] = [
  { value: 'github_pr',       label: 'GitHub PR',        emoji: '🔀' },
  { value: 'github_issue',    label: 'GitHub Issue',     emoji: '🐛' },
  { value: 'adr',             label: 'ADR',              emoji: '📐' },
  { value: 'incident_report', label: 'Incident Report',  emoji: '🚨' },
  { value: 'jira_ticket',     label: 'Jira Ticket',      emoji: '🎫' },
  { value: 'slack_thread',    label: 'Slack Thread',     emoji: '💬' },
  { value: 'confluence_page', label: 'Confluence',       emoji: '📄' },
  { value: 'notion_doc',      label: 'Notion',           emoji: '📝' },
  { value: 'runbook',         label: 'Runbook',          emoji: '📋' },
  { value: 'meeting_notes',   label: 'Meeting Notes',    emoji: '📅' },
  { value: 'code_review',     label: 'Code Review',      emoji: '👀' },
  { value: 'manual_input',    label: 'Manual Entry',     emoji: '✏️' },
];

export default function IngestPage() {
  const qc = useQueryClient();

  const [form, setForm] = useState({
    title: '',
    source_uri: '',
    source_type: 'manual_input' as SourceType,
    author: '',
    raw_content: '',
    tags: [] as string[],
  });
  const [tagInput, setTagInput] = useState('');
  const [success, setSuccess] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: memoryApi.ingest,
    onSuccess: (data) => {
      setSuccess(data.memory_id);
      setForm({ title: '', source_uri: '', source_type: 'manual_input', author: '', raw_content: '', tags: [] });
      qc.invalidateQueries({ queryKey: ['memories'] });
    },
  });

  const addTag = () => {
    const t = tagInput.trim().toLowerCase();
    if (t && !form.tags.includes(t)) {
      setForm(f => ({ ...f, tags: [...f.tags, t] }));
    }
    setTagInput('');
  };

  const removeTag = (t: string) =>
    setForm(f => ({ ...f, tags: f.tags.filter(x => x !== t) }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSuccess(null);
    mutation.mutate(form);
  };

  const isValid = form.title && form.source_uri && form.author && form.raw_content.length >= 10;

  return (
    <div className="p-6 max-w-4xl mx-auto animate-fade-in space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">
          Ingest <span className="gradient-text">Memory</span>
        </h2>
        <p className="text-sm text-slate-400 mt-1">
          Add engineering artifacts to the knowledge base. Ingestion triggers
          entity extraction and vectorization automatically.
        </p>
      </div>

      {/* Success toast */}
      <AnimatePresence>
        {success && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="card p-4 border border-accent-green/30 flex items-center gap-3"
          >
            <CheckCircle className="w-5 h-5 text-accent-green shrink-0" />
            <div>
              <p className="text-sm font-medium text-white">Memory ingested successfully!</p>
              <p className="text-xs text-slate-400 font-mono">{success}</p>
            </div>
            <button onClick={() => setSuccess(null)} className="ml-auto btn-ghost p-1">
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error toast */}
      <AnimatePresence>
        {mutation.isError && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="card p-4 border border-accent-red/30 flex items-center gap-3"
          >
            <AlertTriangle className="w-5 h-5 text-accent-red shrink-0" />
            <p className="text-sm text-accent-red">
              {(mutation.error as Error)?.message ?? 'Ingestion failed.'}
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      <form onSubmit={handleSubmit} className="space-y-5">

        {/* Source type selector */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Source Type
          </label>
          <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-2">
            {SOURCE_TYPES.map(({ value, label, emoji }) => (
              <button
                key={value}
                type="button"
                onClick={() => setForm(f => ({ ...f, source_type: value }))}
                className={clsx(
                  'flex flex-col items-center gap-1 p-3 rounded-xl border text-xs font-medium transition-all duration-150',
                  form.source_type === value
                    ? 'border-brand-500/60 bg-brand-600/15 text-brand-300'
                    : 'border-surface-border bg-surface-hover text-slate-400 hover:border-surface-border hover:text-white'
                )}
              >
                <span className="text-xl">{emoji}</span>
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Two columns */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Title *</label>
            <input
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              placeholder="ADR-042: Switch to gRPC"
              className="input"
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Author *</label>
            <input
              value={form.author}
              onChange={e => setForm(f => ({ ...f, author: e.target.value }))}
              placeholder="alice@company.com"
              className="input"
              required
            />
          </div>
        </div>

        {/* Source URI */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Source URI *</label>
          <input
            value={form.source_uri}
            onChange={e => setForm(f => ({ ...f, source_uri: e.target.value }))}
            placeholder="https://github.com/org/repo/pull/123"
            className="input"
            required
          />
        </div>

        {/* Content */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
            <FileText className="w-3.5 h-3.5" />
            Content *
            <span className="text-slate-600 font-normal normal-case">
              ({form.raw_content.length} chars)
            </span>
          </label>
          <textarea
            value={form.raw_content}
            onChange={e => setForm(f => ({ ...f, raw_content: e.target.value }))}
            placeholder="Paste the full content of your engineering artifact here…"
            rows={10}
            className="textarea font-mono text-xs"
            required
            minLength={10}
          />
        </div>

        {/* Tags */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
            <Tag className="w-3.5 h-3.5" /> Tags
          </label>
          <div className="flex gap-2">
            <input
              value={tagInput}
              onChange={e => setTagInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
              placeholder="architecture, grpc, migration…"
              className="input flex-1"
            />
            <button type="button" onClick={addTag} className="btn-secondary">
              <Plus className="w-4 h-4" />
            </button>
          </div>
          {form.tags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {form.tags.map(t => (
                <span key={t} className="badge-blue flex items-center gap-1">
                  {t}
                  <button onClick={() => removeTag(t)} className="hover:text-white transition-colors">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={!isValid || mutation.isPending}
          className="btn-primary w-full justify-center py-3"
        >
          {mutation.isPending
            ? <><Loader2 className="w-4 h-4 animate-spin" /> Ingesting…</>
            : <><Upload className="w-4 h-4" /> Ingest Memory</>
          }
        </button>
      </form>
    </div>
  );
}
