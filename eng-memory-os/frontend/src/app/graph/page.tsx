'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ReactFlow, {
  Background, Controls, MiniMap,
  type Node, type Edge,
  BackgroundVariant,
  useNodesState, useEdgesState,
  MarkerType,
  Panel,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Network, Search, RefreshCw, Loader2,
  X, GitBranch, Cpu, Users, Lightbulb,
  AlertCircle, BarChart2, FileCode2, Globe2,
  Link2, Maximize2, Info,
} from 'lucide-react';
import { knowledgeApi, type KnowledgeNode, type KnowledgeEdge } from '@/lib/api';

// ─── Entity type configuration ───────────────────────────────

const ENTITY_CONFIG: Record<string, {
  bg: string; border: string; text: string;
  glow: string; icon: React.ReactNode; label: string;
}> = {
  actor:        { bg: '#0f1e3d', border: '#3b82f6', text: '#93c5fd', glow: '#3b82f620', icon: <Users className="w-3 h-3" />,      label: 'Actor' },
  component:    { bg: '#0a2020', border: '#06b6d4', text: '#67e8f9', glow: '#06b6d420', icon: <Cpu className="w-3 h-3" />,        label: 'Component' },
  decision:     { bg: '#1a0f3d', border: '#a855f7', text: '#d8b4fe', glow: '#a855f720', icon: <Lightbulb className="w-3 h-3" />,  label: 'Decision' },
  incident:     { bg: '#2d0a0a', border: '#ef4444', text: '#fca5a5', glow: '#ef444420', icon: <AlertCircle className="w-3 h-3" />,label: 'Incident' },
  technology:   { bg: '#0a1f0a', border: '#10b981', text: '#6ee7b7', glow: '#10b98120', icon: <GitBranch className="w-3 h-3" />,  label: 'Technology' },
  concept:      { bg: '#1f1a0a', border: '#f59e0b', text: '#fcd34d', glow: '#f59e0b20', icon: <Lightbulb className="w-3 h-3" />,  label: 'Concept' },
  metric:       { bg: '#0a1a2d', border: '#06b6d4', text: '#67e8f9', glow: '#06b6d420', icon: <BarChart2 className="w-3 h-3" />,  label: 'Metric' },
  document:     { bg: '#0f0f2d', border: '#6366f1', text: '#a5b4fc', glow: '#6366f120', icon: <FileCode2 className="w-3 h-3" />,  label: 'Document' },
  environment:  { bg: '#1a0a2d', border: '#ec4899', text: '#f9a8d4', glow: '#ec489920', icon: <Globe2 className="w-3 h-3" />,     label: 'Environment' },
  api_endpoint: { bg: '#1f1a0a', border: '#f59e0b', text: '#fcd34d', glow: '#f59e0b20', icon: <Link2 className="w-3 h-3" />,     label: 'API Endpoint' },
};

function getConfig(type: string) {
  return ENTITY_CONFIG[type] ?? ENTITY_CONFIG['concept'];
}

// ─── Force-directed layout helper ────────────────────────────
// Simple force simulation to spread nodes naturally

function forceLayout(nodes: KnowledgeNode[], edges: KnowledgeEdge[], width = 1200, height = 800) {
  const positions: Record<string, { x: number; y: number }> = {};

  // Start with random positions
  nodes.forEach(n => {
    positions[n.id] = {
      x: 100 + Math.random() * (width - 200),
      y: 100 + Math.random() * (height - 200),
    };
  });

  const edgeSet = new Set(edges.map(e => `${e.source_node_id}-${e.target_node_id}`));
  const k = Math.sqrt((width * height) / Math.max(nodes.length, 1));

  // 50 iterations of Fruchterman–Reingold
  for (let iter = 0; iter < 50; iter++) {
    const disp: Record<string, { x: number; y: number }> = {};
    nodes.forEach(n => { disp[n.id] = { x: 0, y: 0 }; });

    // Repulsion
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        const dx = positions[a.id].x - positions[b.id].x;
        const dy = positions[a.id].y - positions[b.id].y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 0.1);
        const force = (k * k) / dist;
        disp[a.id].x += (dx / dist) * force;
        disp[a.id].y += (dy / dist) * force;
        disp[b.id].x -= (dx / dist) * force;
        disp[b.id].y -= (dy / dist) * force;
      }
    }

    // Attraction along edges
    edges.forEach(e => {
      const a = positions[e.source_node_id];
      const b = positions[e.target_node_id];
      if (!a || !b) return;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 0.1);
      const force = (dist * dist) / k;
      disp[e.source_node_id].x += (dx / dist) * force;
      disp[e.source_node_id].y += (dy / dist) * force;
      disp[e.target_node_id].x -= (dx / dist) * force;
      disp[e.target_node_id].y -= (dy / dist) * force;
    });

    // Apply with cooling
    const temp = k * (1 - iter / 50);
    nodes.forEach(n => {
      const d = disp[n.id];
      const len = Math.max(Math.sqrt(d.x * d.x + d.y * d.y), 0.1);
      positions[n.id].x += (d.x / len) * Math.min(len, temp);
      positions[n.id].y += (d.y / len) * Math.min(len, temp);
      // Clamp to canvas
      positions[n.id].x = Math.max(60, Math.min(width - 60, positions[n.id].x));
      positions[n.id].y = Math.max(60, Math.min(height - 60, positions[n.id].y));
    });
  }

  return positions;
}

// ─── Build ReactFlow nodes/edges ──────────────────────────────

function apiToFlow(nodes: KnowledgeNode[], edges: KnowledgeEdge[], positions?: Record<string, { x: number; y: number }>) {
  const maxPagerank = Math.max(...nodes.map(n => n.pagerank_score), 0.001);

  const flowNodes: Node[] = nodes.map((n) => {
    const cfg = getConfig(n.entity_type);
    const importance = n.pagerank_score / maxPagerank;
    const size = 28 + importance * 40; // 28–68px based on importance

    return {
      id: n.id,
      position: positions?.[n.id] ?? { x: Math.random() * 800, y: Math.random() * 600 },
      data: { label: n.name, node: n },
      style: {
        background: cfg.bg,
        border: `${1 + importance * 2}px solid ${cfg.border}`,
        borderRadius: '12px',
        color: cfg.text,
        padding: `${6 + importance * 4}px ${10 + importance * 6}px`,
        fontSize: `${10 + importance * 3}px`,
        fontWeight: importance > 0.5 ? '600' : '500',
        cursor: 'pointer',
        minWidth: `${size + 40}px`,
        textAlign: 'center' as const,
        boxShadow: `0 0 ${8 + importance * 20}px ${cfg.border}${Math.round(20 + importance * 50).toString(16)}`,
        transition: 'all 0.2s ease',
      },
    };
  });

  const flowEdges: Edge[] = edges.map(e => ({
    id: e.id,
    source: e.source_node_id,
    target: e.target_node_id,
    label: e.relationship_type,
    labelStyle: { fill: '#64748b', fontSize: 9, fontWeight: '500' },
    labelBgStyle: { fill: '#0d111a', opacity: 0.9, rx: 4, ry: 4 },
    labelBgPadding: [4, 6] as [number, number],
    style: { stroke: '#2a3a5a', strokeWidth: 1.5 },
    animated: false,
    type: 'smoothstep',
    markerEnd: { type: MarkerType.ArrowClosed, color: '#2a3a5a', width: 12, height: 12 },
  }));

  return { flowNodes, flowEdges };
}

// ─── Node detail side panel ───────────────────────────────────

function NodeDetail({ node, neighbors, onClose, onExpand }: {
  node: KnowledgeNode;
  neighbors: KnowledgeNode[];
  onClose: () => void;
  onExpand: (id: string) => void;
}) {
  const cfg = getConfig(node.entity_type);

  return (
    <motion.div
      initial={{ opacity: 0, x: 30 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 30 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="absolute top-4 right-4 w-80 z-20 flex flex-col gap-3"
    >
      {/* Header card */}
      <div className="card p-4 shadow-xl" style={{ borderColor: cfg.border + '60' }}>
        <div className="flex items-start justify-between mb-3">
          <span
            className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full"
            style={{ background: cfg.bg, color: cfg.text, border: `1px solid ${cfg.border}` }}
          >
            {cfg.icon}
            {node.entity_type}
          </span>
          <button onClick={onClose} className="btn-ghost p-1 rounded-lg hover:bg-surface-hover">
            <X className="w-4 h-4" />
          </button>
        </div>

        <h3 className="text-base font-bold text-white mb-1">{node.name}</h3>
        {node.description && (
          <p className="text-xs text-slate-400 leading-relaxed">{node.description}</p>
        )}

        {/* Stats grid */}
        <div className="grid grid-cols-3 gap-2 mt-3">
          <div className="bg-surface-hover rounded-lg p-2 text-center">
            <p className="text-slate-500 text-xs">PageRank</p>
            <p className="text-white font-mono text-xs font-semibold">{node.pagerank_score.toFixed(3)}</p>
          </div>
          <div className="bg-surface-hover rounded-lg p-2 text-center">
            <p className="text-slate-500 text-xs">Centrality</p>
            <p className="text-white font-mono text-xs font-semibold">{node.degree_centrality.toFixed(3)}</p>
          </div>
          <div className="bg-surface-hover rounded-lg p-2 text-center">
            <p className="text-slate-500 text-xs">Sources</p>
            <p className="text-white font-mono text-xs font-semibold">{node.source_memory_count}</p>
          </div>
        </div>

        {/* Aliases */}
        {node.aliases.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-3">
            {node.aliases.map(a => (
              <span key={a} className="badge-stale text-xs">{a}</span>
            ))}
          </div>
        )}
      </div>

      {/* Connected nodes */}
      {neighbors.length > 0 && (
        <div className="card p-3 shadow-xl">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <GitBranch className="w-3 h-3" />
            Connected ({neighbors.length})
          </p>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {neighbors.slice(0, 8).map(nb => {
              const nbCfg = getConfig(nb.entity_type);
              return (
                <button
                  key={nb.id}
                  onClick={() => onExpand(nb.id)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-surface-hover transition-colors text-left"
                >
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ background: nbCfg.border }}
                  />
                  <span className="text-xs text-slate-300 truncate">{nb.name}</span>
                  <span className="text-xs text-slate-600 shrink-0">{nb.entity_type}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </motion.div>
  );
}

// ─── Legend ──────────────────────────────────────────────────

function Legend() {
  const [open, setOpen] = useState(false);
  const visibleTypes = Object.entries(ENTITY_CONFIG).slice(0, 6);

  return (
    <div className="absolute bottom-4 left-4 z-20">
      <button
        onClick={() => setOpen(o => !o)}
        className="btn-secondary text-xs h-8 px-3 flex items-center gap-1.5"
      >
        <Info className="w-3.5 h-3.5" />
        Legend
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className="card p-3 mt-2 space-y-1.5 w-44"
          >
            {visibleTypes.map(([type, cfg]) => (
              <div key={type} className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: cfg.border }} />
                <span className="text-xs text-slate-300">{cfg.label}</span>
              </div>
            ))}
            <div className="border-t border-surface-border pt-1.5 text-xs text-slate-500">
              Node size = importance
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────

export default function GraphPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null);
  const [neighborNodes, setNeighborNodes] = useState<KnowledgeNode[]>([]);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [allApiNodes, setAllApiNodes] = useState<KnowledgeNode[]>([]);

  // Load all nodes
  const { data: rawNodes, isLoading } = useQuery({
    queryKey: ['knowledge', 'nodes', search],
    queryFn: () => knowledgeApi.searchNodes({ name: search || undefined, fuzzy: !!search, limit: 200 }),
    placeholderData: [],
  });

  const { data: stats } = useQuery({
    queryKey: ['knowledge', 'stats'],
    queryFn: knowledgeApi.stats,
  });

  const optimizeMutation = useMutation({
    mutationFn: knowledgeApi.optimize,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge'] }),
  });

  // Build force-directed graph when nodes load
  useEffect(() => {
    if (!rawNodes?.length) return;
    setAllApiNodes(rawNodes);
    const positions = forceLayout(rawNodes, [], 1400, 900);
    const { flowNodes } = apiToFlow(rawNodes, [], positions);
    setNodes(flowNodes);
    setEdges([]);
    setSelectedNode(null);
  }, [rawNodes]);

  // Click a node → load its subgraph + expand edges
  const handleNodeClick = useCallback(async (_: React.MouseEvent, rfNode: Node) => {
    const apiNode = allApiNodes.find(n => n.id === rfNode.id);
    if (!apiNode) return;
    setSelectedNode(apiNode);

    try {
      const subgraph = await knowledgeApi.getNeighbors(rfNode.id, 1);
      setNeighborNodes(subgraph.nodes.filter(n => n.id !== rfNode.id));

      // Merge positions from the existing layout for known nodes
      setNodes(existing => {
        const existingMap: Record<string, { x: number; y: number }> = {};
        existing.forEach(n => { existingMap[n.id] = n.position; });

        // Position new neighbor nodes around the clicked node
        const newNodes = subgraph.nodes.filter(n => !existingMap[n.id]);
        newNodes.forEach((n, i) => {
          const angle = (i / Math.max(newNodes.length, 1)) * 2 * Math.PI;
          existingMap[n.id] = {
            x: (existingMap[rfNode.id]?.x ?? 400) + 220 * Math.cos(angle),
            y: (existingMap[rfNode.id]?.y ?? 300) + 220 * Math.sin(angle),
          };
        });

        const { flowNodes } = apiToFlow(subgraph.nodes, subgraph.edges, existingMap);
        const existingIds = new Set(existing.map(n => n.id));
        const merged = [...existing];
        flowNodes.forEach(fn => {
          if (!existingIds.has(fn.id)) merged.push(fn);
        });
        return merged;
      });

      // Animate the edges for this subgraph
      const { flowEdges } = apiToFlow(subgraph.nodes, subgraph.edges);
      setEdges(flowEdges.map(e => ({
        ...e,
        animated: e.source === rfNode.id || e.target === rfNode.id,
        style: {
          ...e.style,
          stroke: e.source === rfNode.id || e.target === rfNode.id ? '#6366f1' : '#2a3a5a',
          strokeWidth: e.source === rfNode.id || e.target === rfNode.id ? 2.5 : 1.5,
        },
      })));
    } catch {
      // keep state
    }
  }, [allApiNodes]);

  // Expand a neighbor from the detail panel
  const handleExpandNeighbor = useCallback(async (nodeId: string) => {
    const node = allApiNodes.find(n => n.id === nodeId);
    if (!node) return;
    setSelectedNode(node);

    try {
      const subgraph = await knowledgeApi.getNeighbors(nodeId, 1);
      setNeighborNodes(subgraph.nodes.filter(n => n.id !== nodeId));

      setNodes(existing => {
        const existingMap: Record<string, { x: number; y: number }> = {};
        existing.forEach(n => { existingMap[n.id] = n.position; });

        const newNodes = subgraph.nodes.filter(n => !existingMap[n.id]);
        newNodes.forEach((n, i) => {
          const angle = (i / Math.max(newNodes.length, 1)) * 2 * Math.PI;
          existingMap[n.id] = {
            x: (existingMap[nodeId]?.x ?? 400) + 220 * Math.cos(angle),
            y: (existingMap[nodeId]?.y ?? 300) + 220 * Math.sin(angle),
          };
        });

        const { flowNodes } = apiToFlow(subgraph.nodes, subgraph.edges, existingMap);
        const existingIds = new Set(existing.map(n => n.id));
        const merged = [...existing];
        flowNodes.forEach(fn => { if (!existingIds.has(fn.id)) merged.push(fn); });
        return merged;
      });

      const { flowEdges } = apiToFlow(subgraph.nodes, subgraph.edges);
      setEdges(prev => {
        const existingIds = new Set(prev.map(e => e.id));
        const newEdges = flowEdges.filter(e => !existingIds.has(e.id));
        return [...prev, ...newEdges.map(e => ({
          ...e,
          animated: e.source === nodeId || e.target === nodeId,
          style: { ...e.style, stroke: '#6366f1', strokeWidth: 2 },
        }))];
      });
    } catch { /* keep */ }
  }, [allApiNodes]);

  return (
    <div className="flex flex-col h-full animate-fade-in">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-5 py-3.5 border-b border-surface-border bg-surface-card shrink-0">
        <Network className="w-5 h-5 text-accent-cyan shrink-0" />
        <h2 className="text-sm font-semibold text-white">Knowledge Graph</h2>

        <div className="flex-1 max-w-xs">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search entities…"
              className="input pl-9 py-1.5 text-xs h-8"
            />
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="hidden lg:flex items-center gap-4 text-xs text-slate-400 ml-2">
            <span><strong className="text-white">{(stats as Record<string,number>).total_nodes ?? 0}</strong> nodes</span>
            <span><strong className="text-white">{(stats as Record<string,number>).total_edges ?? 0}</strong> edges</span>
          </div>
        )}

        <button
          onClick={() => optimizeMutation.mutate()}
          disabled={optimizeMutation.isPending}
          className="btn-secondary text-xs h-8 px-3"
        >
          {optimizeMutation.isPending
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <RefreshCw className="w-3.5 h-3.5" />
          }
          Optimize
        </button>

        {selectedNode && (
          <button
            onClick={() => { setSelectedNode(null); setEdges([]); }}
            className="btn-ghost text-xs h-8 px-3"
          >
            <X className="w-3.5 h-3.5" />
            Clear Selection
          </button>
        )}
      </div>

      {/* Graph canvas */}
      <div className="flex-1 relative">
        {isLoading ? (
          <div className="flex items-center justify-center h-full gap-3 text-slate-500">
            <Loader2 className="w-6 h-6 animate-spin text-accent-cyan" />
            <span className="text-sm">Building knowledge graph…</span>
          </div>
        ) : nodes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-slate-500">
            <Network className="w-20 h-20 text-slate-700" />
            <p className="text-sm font-medium">No knowledge nodes yet</p>
            <p className="text-xs text-slate-600">Ingest a repository to populate the graph.</p>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={handleNodeClick}
            fitView
            fitViewOptions={{ padding: 0.15 }}
            attributionPosition="bottom-left"
            minZoom={0.05}
            maxZoom={3}
          >
            <Background variant={BackgroundVariant.Dots} gap={28} size={1} color="#1a2035" />
            <Controls
              showInteractive={false}
              style={{ background: '#171923', border: '1px solid #1e2536', borderRadius: '10px' }}
            />
            <MiniMap
              nodeColor={rfNode => {
                const apiNode = allApiNodes.find(n => n.id === rfNode.id);
                return apiNode ? getConfig(apiNode.entity_type).border : '#2a3147';
              }}
              maskColor="rgba(10, 13, 20, 0.85)"
              style={{ background: '#0d111a', border: '1px solid #1e2536', borderRadius: '10px' }}
            />
            <Panel position="top-left">
              <div className="text-xs text-slate-500 bg-surface-card border border-surface-border rounded-lg px-3 py-2">
                {nodes.length} nodes visible · Click a node to explore connections
              </div>
            </Panel>
          </ReactFlow>
        )}

        {/* Node detail panel */}
        <AnimatePresence>
          {selectedNode && (
            <NodeDetail
              node={selectedNode}
              neighbors={neighborNodes}
              onClose={() => { setSelectedNode(null); setEdges([]); setNeighborNodes([]); }}
              onExpand={handleExpandNeighbor}
            />
          )}
        </AnimatePresence>

        {/* Legend */}
        {nodes.length > 0 && <Legend />}
      </div>
    </div>
  );
}
