'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Brain,
  Search,
  Network,
  Upload,
  Activity,
  Settings,
  ChevronRight,
  Zap,
  GitFork,
  Clock,
} from 'lucide-react';
import { clsx } from 'clsx';
import { motion } from 'framer-motion';

const NAV_ITEMS = [
  { href: '/',           icon: Activity,  label: 'Dashboard' },
  { href: '/query',      icon: Search,    label: 'Query' },
  { href: '/history',    icon: Clock,     label: 'Query History' },
  { href: '/ingest',     icon: Upload,    label: 'Ingest' },
  { href: '/integrations', icon: GitFork,  label: 'Integrations' },
  { href: '/graph',      icon: Network,   label: 'Knowledge Graph' },
  { href: '/memories',   icon: Brain,     label: 'Memories' },
  { href: '/settings',   icon: Settings,  label: 'Settings' },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 flex flex-col h-screen bg-surface-card border-r border-surface-border shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-surface-border">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-accent-cyan
                        flex items-center justify-center shadow-glow-sm shrink-0">
          <Brain className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-sm font-semibold text-white leading-none">Engineering</h1>
          <p className="text-xs text-slate-400 mt-0.5">Memory OS</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const active = pathname === href;
          return (
            <Link key={href} href={href}>
              <motion.div
                whileHover={{ x: 2 }}
                whileTap={{ scale: 0.97 }}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 cursor-pointer group',
                  active
                    ? 'bg-brand-600/20 text-brand-300 border border-brand-500/20'
                    : 'text-slate-400 hover:text-white hover:bg-surface-hover'
                )}
              >
                <Icon className={clsx('w-4 h-4 shrink-0', active ? 'text-brand-400' : 'text-slate-500 group-hover:text-slate-300')} />
                <span className="flex-1">{label}</span>
                {active && <ChevronRight className="w-3 h-3 text-brand-400" />}
              </motion.div>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-surface-border">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-hover">
          <Zap className="w-3.5 h-3.5 text-accent-cyan" />
          <span className="text-xs text-slate-400">v0.1.0</span>
          <span className="ml-auto w-2 h-2 rounded-full bg-accent-green animate-pulse" />
        </div>
      </div>
    </aside>
  );
}
