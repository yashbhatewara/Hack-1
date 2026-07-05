'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload, CheckCircle, AlertTriangle, X, Plus, Tag,
  FileText, Loader2, Terminal as TerminalIcon
} from 'lucide-react';
import { memoryApi, type SourceType } from '@/lib/api';
import { clsx } from 'clsx';

const SOURCE_TYPES: { value: SourceType; label: string; emoji: string }[] = [
  { value: 'github_pr',       label: 'GitHub PR',        emoji: '🔀' },
  { value: 'github_issue',    label: 'GitHub Issue',     emoji: '🐛' },
  { value: 'github_commit',   label: 'GitHub Commit',    emoji: '💾' },
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

interface LogLine {
  id: string;
  type: 'info' | 'success' | 'error' | 'warn';
  message: string;
  timestamp: string;
}

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
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [showLogs, setShowLogs] = useState(false);

  const addLog = (message: string, type: LogLine['type'] = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    const id = Math.random().toString(36).substring(7);
    setLogs((prev) => [...prev, { id, type, message, timestamp }]);
  };

  const mutation = useMutation({
    mutationFn: memoryApi.ingest,
    onMutate: () => {
      setLogs([]);
      setSuccess(null);
      addLog('Initializing manual memory ingestion...', 'info');
      addLog(`Validating payload: "${form.title}"`, 'info');
      addLog(`Source URI: ${form.source_uri}`, 'info');
    },
    onSuccess: (data) => {
      addLog('Connection to backend API established successfully.', 'success');
      addLog(`Saved memory object to PostgreSQL.`, 'info');
      addLog(`Spawned ingestion task with ID: ${data.memory_id}`, 'success');
      addLog(`Pipeline trigger complete.`, 'success');
      setSuccess(data.memory_id);
      setForm({ title: '', source_uri: '', source_type: 'manual_input', author: '', raw_content: '', tags: [] });
      qc.invalidateQueries({ queryKey: ['memories'] });
    },
    onError: (error: any) => {
      const errMsg = error.response?.data?.detail || error.message || 'Ingestion failed';
      addLog(`Ingestion failed: ${errMsg}`, 'error');
    }
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
    mutation.mutate(form);
  };

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
              placeholder="e.g. ADR-024: Switch to Valkey for caching"
              className="input text-sm"
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Source URI / Link *</label>
            <input
              value={form.source_uri}
              onChange={e => setForm(f => ({ ...f, source_uri: e.target.value }))}
              placeholder="e.g. https://github.com/my-org/docs/adr-024.md"
              className="input text-sm"
              required
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Author *</label>
            <input
              value={form.author}
              onChange={e => setForm(f => ({ ...f, author: e.target.value }))}
              placeholder="e.g. engineering-lead@company.com"
              className="input text-sm"
              required
            />
          </div>
          {/* Tags input */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Tags</label>
            <div className="flex gap-2">
              <input
                value={tagInput}
                onChange={e => setTagInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addTag())}
                placeholder="caching, architecture..."
                className="input text-sm"
              />
              <button type="button" onClick={addTag} className="btn-secondary px-4 text-xs font-semibold">
                Add Tag
              </button>
            </div>
            {/* Tag list */}
            {form.tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {form.tags.map(t => (
                  <span key={t} className="badge-blue text-xs flex items-center gap-1">
                    {t}
                    <button type="button" onClick={() => removeTag(t)} className="text-brand-300 hover:text-white">
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <FileText className="w-4 h-4 text-brand-400" /> Content *
          </label>
          <textarea
            value={form.raw_content}
            onChange={e => setForm(f => ({ ...f, raw_content: e.target.value }))}
            placeholder="Paste raw markdown, slack thread transcripts, or any detailed document text here (min 10 characters)..."
            className="input font-mono text-sm h-64 resize-none leading-relaxed"
            required
          />
        </div>

        <button
          type="submit"
          disabled={mutation.isPending || !form.title || !form.source_uri || !form.author || form.raw_content.length < 10}
          className="btn-primary w-full py-3 flex items-center justify-center gap-2 font-medium"
        >
          {mutation.isPending ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" /> Ingesting...
            </>
          ) : (
            <>
              <Upload className="w-4 h-4" /> Ingest Memory
            </>
          )}
        </button>
      </form>

      {/* Log extend button and logs terminal console */}
      <div className="space-y-3 pt-4 border-t border-surface-border/50">
        <button
          type="button"
          onClick={() => setShowLogs(prev => !prev)}
          className="flex items-center gap-2 text-xs font-semibold text-brand-400 hover:text-brand-300 transition-colors bg-surface-hover/30 px-3 py-1.5 rounded-lg border border-surface-border/40"
        >
          <TerminalIcon className="w-3.5 h-3.5" />
          {showLogs ? 'Hide Ingestion Console' : 'Extend Logs / View Console'}
        </button>

        <AnimatePresence>
          {showLogs && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
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
                  {logs.length === 0 ? (
                    <div className="text-slate-600 italic">No logs generated yet. Trigger an ingestion above.</div>
                  ) : (
                    logs.map((log) => (
                      <div key={log.id} className="flex gap-2">
                        <span className="text-slate-500">[{log.timestamp}]</span>
                        <span className={clsx(
                          log.type === 'error' && 'text-accent-red',
                          log.type === 'success' && 'text-accent-green',
                          log.type === 'warn' && 'text-accent-orange',
                          log.type === 'info' && 'text-slate-300'
                        )}>
                          {log.type === 'error' && '[ERROR] '}
                          {log.type === 'success' && '[SUCCESS] '}
                          {log.type === 'warn' && '[WARN] '}
                          {log.message}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
