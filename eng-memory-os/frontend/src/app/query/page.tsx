'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send, Loader2, Brain, CheckCircle, AlertTriangle, ChevronDown, ChevronUp,
  Clock, Repeat, Zap, FileText,
} from 'lucide-react';
import { createQueryWebSocket, type QueryResponse } from '@/lib/api';
import { clsx } from 'clsx';

// ─── Types ────────────────────────────────────────────────

interface ProgressStep {
  node: string;
  status: string;
  message: string;
  step?: number;
  totalSteps?: number;
}

// ─── Node progress indicator ──────────────────────────────

const NODE_LABELS: Record<string, string> = {
  gateway:   '🔀 Intent Classifier',
  planner:   '📋 Query Planner',
  retriever: '🔍 Hybrid Retriever',
  reasoner:  '🧠 Reasoner',
  critic:    '🎯 Critic / Verifier',
  generator: '✍️ Response Generator',
};

function AgentProgress({ steps, currentNode }: { steps: ProgressStep[]; currentNode: string | null }) {
  const allNodes = ['gateway', 'planner', 'retriever', 'reasoner', 'critic', 'generator'];

  return (
    <div className="card p-4 space-y-2">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
        Agent Pipeline
      </p>
      {allNodes.map((node, i) => {
        const done = steps.some(s => s.node === node);
        const active = currentNode === node;

        return (
          <motion.div
            key={node}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
            className={clsx(
              'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all',
              active   ? 'bg-brand-600/20 border border-brand-500/30' :
              done     ? 'bg-surface-hover' :
                         'opacity-40'
            )}
          >
            {active ? (
              <Loader2 className="w-4 h-4 text-brand-400 animate-spin shrink-0" />
            ) : done ? (
              <CheckCircle className="w-4 h-4 text-accent-green shrink-0" />
            ) : (
              <div className="w-4 h-4 rounded-full border border-slate-600 shrink-0" />
            )}
            <span className={clsx(
              'flex-1',
              active ? 'text-brand-300' : done ? 'text-white' : 'text-slate-500'
            )}>
              {NODE_LABELS[node] ?? node}
            </span>
          </motion.div>
        );
      })}
    </div>
  );
}

// ─── Citation card ────────────────────────────────────────

function CitationCard({ citation, index }: { citation: QueryResponse['citations'][0]; index: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="card p-3 text-sm"
    >
      <div
        className="flex items-center gap-2 cursor-pointer"
        onClick={() => setExpanded(e => !e)}
      >
        <span className="font-mono text-xs text-brand-400 shrink-0">
          [E-{citation.evidence_id.slice(0, 8)}]
        </span>
        <span className="text-slate-300 flex-1 truncate text-xs">{citation.source_uri}</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">
            {(citation.relevance_score * 100).toFixed(0)}%
          </span>
          {expanded
            ? <ChevronUp className="w-3.5 h-3.5 text-slate-500" />
            : <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
          }
        </div>
      </div>
      <AnimatePresence>
        {expanded && (
          <motion.p
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mt-2 pt-2 border-t border-surface-border text-xs text-slate-400 leading-relaxed overflow-hidden"
          >
            {citation.snippet}
          </motion.p>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─── Response display ──────────────────────────────────────

function ResponsePanel({ response }: { response: QueryResponse }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      {/* Metadata bar */}
      <div className="flex items-center gap-3 flex-wrap">
        {response.is_degraded
          ? <span className="badge-pending"><AlertTriangle className="w-3 h-3" /> Low Confidence</span>
          : <span className="badge-active"><CheckCircle className="w-3 h-3" /> High Confidence</span>
        }
        <span className="badge-blue">
          <Zap className="w-3 h-3" /> {(response.confidence * 100).toFixed(0)}%
        </span>
        <span className="badge-purple">
          <Clock className="w-3 h-3" /> {response.total_time_ms.toFixed(0)}ms
        </span>
        {response.retry_count > 0 && (
          <span className="badge-stale">
            <Repeat className="w-3 h-3" /> {response.retry_count} retries
          </span>
        )}
      </div>

      {/* Confidence bar */}
      <div className="confidence-bar">
        <div
          className={clsx(
            'confidence-fill',
            response.confidence >= 0.85
              ? 'bg-gradient-to-r from-accent-green to-accent-cyan'
              : 'bg-gradient-to-r from-accent-orange to-accent-red'
          )}
          style={{ width: `${response.confidence * 100}%` }}
        />
      </div>

      {/* Response text */}
      <div className="card p-5">
        <pre className="text-sm text-slate-200 whitespace-pre-wrap leading-7 font-sans">
          {response.response_text}
        </pre>
      </div>

      {/* Citations */}
      {response.citations.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
            <FileText className="w-3.5 h-3.5" />
            Evidence Sources ({response.citations.length})
          </h4>
          {response.citations.map((c, i) => (
            <CitationCard key={c.evidence_id} citation={c} index={i} />
          ))}
        </div>
      )}
    </motion.div>
  );
}

// ─── Page ─────────────────────────────────────────────────

export default function QueryPage() {
  const [query, setQuery] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [steps, setSteps] = useState<ProgressStep[]>([]);
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<ReturnType<typeof createQueryWebSocket> | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Cleanup WS on unmount
  useEffect(() => () => wsRef.current?.close(), []);

  const handleSubmit = useCallback(() => {
    if (!query.trim() || isStreaming) return;

    setIsStreaming(true);
    setSteps([]);
    setCurrentNode(null);
    setResponse(null);
    setError(null);

    wsRef.current?.close();
    wsRef.current = createQueryWebSocket(
      (msg) => {
        setCurrentNode(msg.node);
        setSteps(prev => {
          // Avoid duplicates
          if (prev.some(s => s.node === msg.node && s.status === 'processing')) return prev;
          return [...prev, msg];
        });
      },
      (data) => {
        setResponse(data);
        setIsStreaming(false);
        setCurrentNode(null);
      },
      (detail) => {
        setError(detail);
        setIsStreaming(false);
        setCurrentNode(null);
      },
    );

    // Wait for WS connection
    setTimeout(() => {
      wsRef.current?.send(query.trim());
    }, 300);
  }, [query, isStreaming]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit();
  };

  const EXAMPLE_QUERIES = [
    'Why did we migrate from Redis to Valkey for session caching?',
    'What caused the payment gateway outage last week?',
    'List all architecture decisions made in Q2 2025.',
    'Which services depend on the Auth service?',
  ];

  return (
    <div className="p-6 h-full flex flex-col gap-6 max-w-6xl mx-auto animate-fade-in">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">
          Query <span className="gradient-text">Knowledge Base</span>
        </h2>
        <p className="text-sm text-slate-400 mt-1">
          Ask anything about your engineering history. All answers are evidence-backed.
        </p>
      </div>

      {/* Input */}
      <div className="card p-4 space-y-3">
        <textarea
          ref={textareaRef}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Why did we choose Kafka over RabbitMQ for our event bus?"
          rows={3}
          className="textarea"
          disabled={isStreaming}
        />
        <div className="flex items-center justify-between">
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUERIES.map(q => (
              <button
                key={q}
                onClick={() => setQuery(q)}
                className="text-xs px-2.5 py-1 rounded-full border border-surface-border text-slate-400
                           hover:text-white hover:border-brand-500/50 transition-all"
              >
                {q.length > 42 ? q.slice(0, 42) + '…' : q}
              </button>
            ))}
          </div>
          <button
            onClick={handleSubmit}
            disabled={!query.trim() || isStreaming}
            className="btn-primary shrink-0"
          >
            {isStreaming
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Thinking…</>
              : <><Send className="w-4 h-4" /> Ask</>
            }
          </button>
        </div>
        <p className="text-xs text-slate-500">⌘ + Enter to submit</p>
      </div>

      {/* Body: pipeline + response */}
      <div className="flex gap-5 flex-1 min-h-0">
        {/* Agent pipeline */}
        <AnimatePresence>
          {(isStreaming || steps.length > 0) && (
            <motion.div
              initial={{ opacity: 0, x: -20, width: 0 }}
              animate={{ opacity: 1, x: 0, width: 240 }}
              exit={{ opacity: 0, x: -20, width: 0 }}
              className="shrink-0"
            >
              <AgentProgress steps={steps} currentNode={currentNode} />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Response */}
        <div className="flex-1 overflow-y-auto">
          {error && (
            <div className="card p-4 border-accent-red/30 text-accent-red text-sm flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              {error}
            </div>
          )}
          {response && <ResponsePanel response={response} />}
          {!response && !error && !isStreaming && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center py-16">
              <Brain className="w-16 h-16 text-slate-700" />
              <p className="text-slate-400 text-sm">
                Ask a question to query your engineering knowledge graph.
              </p>
              <p className="text-slate-600 text-xs">
                Responses are always backed by cited evidence.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
