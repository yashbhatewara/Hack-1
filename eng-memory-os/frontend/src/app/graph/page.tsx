'use client';

import { useState, useCallback, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ReactFlow, {
  Background, Controls, MiniMap,
  type Node, type Edge,
  BackgroundVariant,
  useNodesState, useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Network, Search, RefreshCw, ZoomIn, Loader2,
  Info, ChevronRight, X,
} from 'lucide-react';
import { knowledgeApi, type KnowledgeNode, type KnowledgeEdge } from '@/lib/api';

// ─── Entity type color map ────────────────────────────────

const ENTITY_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  actor:        { bg: '#1e2a45', border: '#3b82f6', text: '#93c5fd' },
  component:    { bg: '#1e2d2d', border: '#06b6d4', text: '#67e8f9' },
  decision:     { bg: '#2d1e45', border: '#a855f7', text: '#d8b4fe' },
  incident:     { bg: '#2d1e1e', border: '#ef4444', text: '#fca5a5' },
  technology:   { bg: '#1e2d1e', border: '#10b981', text: '#6ee7b7' },
  concept:      { bg: '#2d2a1e', border: '#f59e0b', text: '#fcd34d' },
  metric:       { bg: '#1e2d2d', border: '#06b6d4', text: '#67e8f9' },
  document:     { bg: '#1e1e2d', border: '#6366f1', text: '#a5b4fc' },
  environment:  { bg: '#251e2d', border: '#ec4899', text: '#f9a8d4' },
  api_endpoint: { bg: '#2d2a1e', border: '#f59e0b', text: '#fcd34d' },
};

function getEntityStyle(type: string) {
  return ENTITY_COLORS[type] ?? ENTITY_COLORS['concept'];
}

// ─── Convert API data to ReactFlow nodes/edges ────────────

function apiToFlow(nodes: KnowledgeNode[], edges: KnowledgeEdge[]) {
  const flowNodes: Node[] = nodes.map((n, i) => {
    const style = getEntityStyle(n.entity_type);
    const angle = (i / Math.max(nodes.length - 1, 1)) * 2 * Math.PI;
    const radius = 280;
    return {
      id: n.id,
      position: {
        x: 400 + radius * Math.cos(angle),
        y: 300 + radius * Math.sin(angle),
      },
      data: { label: n.name, node: n },
      style: {
        background: style.bg,
        border: `1.5px solid ${style.border}`,
        borderRadius: '10px',
        color: style.text,
        padding: '8px 14px',
        fontSize: '12px',
        fontWeight: '500',
        cursor: 'pointer',
        minWidth: '100px',
        textAlign: 'center',
        boxShadow: `0 0 12px ${style.border}30`,
      },
    };
  });

  const flowEdges: Edge[] = edges.map(e => ({
    id: e.id,
    source: e.source_node_id,
    target: e.target_node_id,
    label: e.relationship_type,
    labelStyle: { fill: '#64748b', fontSize: 10 },
    labelBgStyle: { fill: '#171923', opacity: 0.8 },
    style: { stroke: '#2a3147', strokeWidth: 1.5 },
    animated: false,
    type: 'smoothstep',
  }));

  return { flowNodes, flowEdges };
}

// ─── Node detail panel ────────────────────────────────────

function NodeDetail({ node, onClose }: { node: KnowledgeNode; onClose: () => void }) {
  const style = getEntityStyle(node.entity_type);

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      className="absolute top-4 right-4 w-72 card p-4 space-y-3 z-10 shadow-card"
    >
      <div className="flex items-start justify-between">
        <div>
          <span
            className="text-xs font-medium px-2 py-0.5 rounded-full"
            style={{ background: style.bg, color: style.text, border: `1px solid ${style.border}` }}
          >
            {node.entity_type}
          </span>
          <h3 className="text-sm font-semibold text-white mt-2">{node.name}</h3>
        </div>
        <button onClick={onClose} className="btn-ghost p-1">
          <X className="w-4 h-4" />
        </button>
      </div>

      {node.description && (
        <p className="text-xs text-slate-400 leading-relaxed">{node.description}</p>
      )}

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="bg-surface-hover rounded-lg p-2">
          <p className="text-slate-500">PageRank</p>
          <p className="text-white font-mono">{node.pagerank_score.toFixed(4)}</p>
        </div>
        <div className="bg-surface-hover rounded-lg p-2">
          <p className="text-slate-500">Centrality</p>
          <p className="text-white font-mono">{node.degree_centrality.toFixed(4)}</p>
        </div>
        <div className="bg-surface-hover rounded-lg p-2">
          <p className="text-slate-500">Sources</p>
          <p className="text-white font-mono">{node.source_memory_count}</p>
        </div>
        <div className="bg-surface-hover rounded-lg p-2">
          <p className="text-slate-500">Aliases</p>
          <p className="text-white font-mono">{node.aliases.length}</p>
        </div>
      </div>

      {node.aliases.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {node.aliases.map(a => (
            <span key={a} className="badge-stale text-xs">{a}</span>
          ))}
        </div>
      )}
    </motion.div>
  );
}

// ─── Page ─────────────────────────────────────────────────

export default function GraphPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Load all nodes
  const { data: allNodes, isLoading } = useQuery({
    queryKey: ['knowledge', 'nodes', search],
    queryFn: () => knowledgeApi.searchNodes({ name: search || undefined, fuzzy: !!search, limit: 100 }),
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

  // Build initial graph from nodes (no edges until a node is clicked)
  useEffect(() => {
    if (!allNodes?.length) return;
    const { flowNodes } = apiToFlow(allNodes, []);
    setNodes(flowNodes);
    setEdges([]);
  }, [allNodes]);

  // Load neighbors on node click
  const handleNodeClick = useCallback(async (_: React.MouseEvent, rfNode: Node) => {
    const apiNode = allNodes?.find(n => n.id === rfNode.id);
    if (!apiNode) return;
    setSelectedNode(apiNode);

    try {
      const subgraph = await knowledgeApi.getNeighbors(rfNode.id, 1);
      const { flowNodes, flowEdges } = apiToFlow(subgraph.nodes, subgraph.edges);
      // Merge new nodes with existing without duplication
      setNodes(existing => {
        const existingIds = new Set(existing.map(n => n.id));
        const newNodes = flowNodes.filter(n => !existingIds.has(n.id));
        return [...existing, ...newNodes];
      });
      setEdges(flowEdges);
    } catch {
      // Edge fetch failed, keep current state
    }
  }, [allNodes]);

  return (
    <div className="flex flex-col h-full animate-fade-in">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-5 py-3.5 border-b border-surface-border bg-surface-card">
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
      </div>

      {/* Graph canvas */}
      <div className="flex-1 relative">
        {isLoading ? (
          <div className="flex items-center justify-center h-full gap-3 text-slate-500">
            <Loader2 className="w-6 h-6 animate-spin" />
            <span className="text-sm">Loading knowledge graph…</span>
          </div>
        ) : nodes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-500">
            <Network className="w-16 h-16 text-slate-700" />
            <p className="text-sm">No knowledge nodes yet.</p>
            <p className="text-xs">Ingest some memories to populate the graph.</p>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={handleNodeClick}
            fitView
            fitViewOptions={{ padding: 0.3 }}
            attributionPosition="bottom-left"
          >
            <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="#1e2231" />
            <Controls showInteractive={false} />
            <MiniMap
              nodeColor={rfNode => {
                const apiNode = allNodes?.find(n => n.id === rfNode.id);
                return apiNode ? getEntityStyle(apiNode.entity_type).border : '#2a3147';
              }}
              maskColor="rgba(15, 17, 23, 0.8)"
            />
          </ReactFlow>
        )}

        {/* Node detail panel */}
        <AnimatePresence>
          {selectedNode && (
            <NodeDetail
              node={selectedNode}
              onClose={() => setSelectedNode(null)}
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
