'use client';

import { useQuery } from '@tanstack/react-query';
import { systemApi } from '@/lib/api';
import { Settings, Database, Zap, Globe, Info } from 'lucide-react';

export default function SettingsPage() {
  const { data: health } = useQuery({ queryKey: ['system', 'health'], queryFn: systemApi.health });
  const { data: tokens } = useQuery({ queryKey: ['system', 'tokens'], queryFn: systemApi.tokens });

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6 animate-fade-in">
      <div className="flex items-center gap-3">
        <Settings className="w-6 h-6 text-slate-400" />
        <h2 className="text-2xl font-bold text-white">Settings</h2>
      </div>

      {/* System info */}
      <div className="card p-5 space-y-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Info className="w-4 h-4 text-accent-cyan" /> System Information
        </h3>
        <div className="grid grid-cols-2 gap-3 text-sm">
          {[
            { label: 'API URL',       value: apiUrl },
            { label: 'Version',       value: health?.version ?? '—' },
            { label: 'Status',        value: health?.status ?? '—' },
            { label: 'Uptime',        value: health ? `${Math.floor(health.uptime_seconds / 60)}m` : '—' },
            { label: 'Database',      value: health?.database ?? '—' },
            { label: 'Vector Store',  value: health?.qdrant ?? '—' },
          ].map(({ label, value }) => (
            <div key={label} className="bg-surface-hover rounded-lg p-3">
              <p className="text-slate-500 text-xs">{label}</p>
              <p className="text-white font-mono mt-1 text-sm truncate">{value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* LLM providers */}
      <div className="card p-5 space-y-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Zap className="w-4 h-4 text-accent-orange" /> LLM Providers
        </h3>
        {health?.llm_providers ? (
          <div className="space-y-2">
            {Object.entries(health.llm_providers).map(([provider, status]) => (
              <div key={provider} className="flex items-center justify-between px-3 py-2.5 bg-surface-hover rounded-lg text-sm">
                <span className="text-white capitalize">{provider}</span>
                <span className={status.includes('healthy') || status.includes('closed')
                  ? 'text-accent-green' : 'text-accent-orange'}>
                  {status}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="skeleton h-20 rounded-lg" />
        )}
      </div>

      {/* Token stats */}
      <div className="card p-5 space-y-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Database className="w-4 h-4 text-brand-400" /> Token & Cost Summary
        </h3>
        {tokens ? (
          <div className="grid grid-cols-2 gap-3 text-sm">
            {[
              { label: 'Total Requests',     value: tokens.total_requests.toLocaleString() },
              { label: 'Prompt Tokens',      value: tokens.total_prompt_tokens.toLocaleString() },
              { label: 'Completion Tokens',  value: tokens.total_completion_tokens.toLocaleString() },
              { label: 'Total Cost (USD)',   value: `$${tokens.total_cost_usd.toFixed(6)}` },
            ].map(({ label, value }) => (
              <div key={label} className="bg-surface-hover rounded-lg p-3">
                <p className="text-slate-500 text-xs">{label}</p>
                <p className="text-white font-mono mt-1">{value}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="skeleton h-24 rounded-lg" />
        )}
      </div>

      {/* API links */}
      <div className="card p-5 space-y-3">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Globe className="w-4 h-4 text-accent-cyan" /> API References
        </h3>
        {[
          { label: 'Interactive Docs (Swagger)', href: `${apiUrl}/docs` },
          { label: 'ReDoc Documentation',        href: `${apiUrl}/redoc` },
          { label: 'OpenAPI JSON Schema',         href: `${apiUrl}/openapi.json` },
          { label: 'Health Check',                href: `${apiUrl}/api/v1/system/health` },
        ].map(({ label, href }) => (
          <a
            key={href}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between px-3 py-2.5 bg-surface-hover rounded-lg text-sm
                       hover:bg-surface-border transition-colors group"
          >
            <span className="text-slate-300 group-hover:text-white transition-colors">{label}</span>
            <span className="text-xs text-slate-500 font-mono truncate max-w-xs">{href}</span>
          </a>
        ))}
      </div>
    </div>
  );
}
