"""
Knowledge Graph REST API routes.

Endpoints for exploring the knowledge graph, searching entities,
and triggering graph optimization.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from eng_memory_os.application.knowledge.optimize_graph import OptimizeGraphUseCase
from eng_memory_os.domain.knowledge.entities import EntityType
from eng_memory_os.domain.knowledge.value_objects import NodeId
from eng_memory_os.presentation.dependencies import get_event_bus, get_graph_repo
from eng_memory_os.presentation.schemas import (
    KnowledgeEdgeDTO,
    KnowledgeNodeDTO,
    SubgraphResponseDTO,
    ErrorResponseDTO,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge-graph"])


# ──────────────────── GET /knowledge/nodes ────────────────────

@router.get(
    "/nodes",
    response_model=list[KnowledgeNodeDTO],
    summary="Search knowledge graph nodes",
)
async def search_nodes(
    name: str | None = Query(None, description="Search by node name"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
    fuzzy: bool = Query(False, description="Enable fuzzy name matching"),
    limit: int = Query(50, ge=1, le=500),
    graph_repo=Depends(get_graph_repo),
):
    et = None
    if entity_type:
        try:
            et = EntityType(entity_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid entity type: {entity_type}. Valid types: {[e.value for e in EntityType]}",
            )

    if name:
        nodes = await graph_repo.find_nodes_by_name(name, entity_type=et, fuzzy=fuzzy)
    elif et:
        nodes = await graph_repo.find_nodes_by_type(et, limit=limit)
    else:
        # List all nodes (limited)
        nodes = []
        for entity_t in EntityType:
            found = await graph_repo.find_nodes_by_type(entity_t, limit=limit)
            nodes.extend(found)
            if len(nodes) >= limit:
                break
        nodes = nodes[:limit]

    return [
        KnowledgeNodeDTO(
            id=str(n.id),
            entity_type=n.entity_type.value,
            name=n.name,
            description=n.description,
            aliases=n.aliases,
            pagerank_score=n.pagerank_score,
            degree_centrality=n.degree_centrality,
            source_memory_count=len(n.source_memory_ids),
        )
        for n in nodes
    ]


# ──────────────────── GET /knowledge/nodes/{id} ────────────────────

@router.get(
    "/nodes/{node_id}",
    response_model=KnowledgeNodeDTO,
    summary="Get a specific knowledge node",
    responses={404: {"model": ErrorResponseDTO}},
)
async def get_node(
    node_id: str,
    graph_repo=Depends(get_graph_repo),
):
    node = await graph_repo.get_node_by_id(NodeId.from_str(node_id))
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    return KnowledgeNodeDTO(
        id=str(node.id),
        entity_type=node.entity_type.value,
        name=node.name,
        description=node.description,
        aliases=node.aliases,
        pagerank_score=node.pagerank_score,
        degree_centrality=node.degree_centrality,
        source_memory_count=len(node.source_memory_ids),
    )


# ──────────────────── GET /knowledge/nodes/{id}/neighbors ────────────────────

@router.get(
    "/nodes/{node_id}/neighbors",
    response_model=SubgraphResponseDTO,
    summary="Get neighbors of a knowledge node",
    description="Returns the N-degree subgraph around a node for visualization.",
    responses={404: {"model": ErrorResponseDTO}},
)
async def get_node_neighbors(
    node_id: str,
    depth: int = Query(1, ge=1, le=3, description="Traversal depth"),
    graph_repo=Depends(get_graph_repo),
):
    node = await graph_repo.get_node_by_id(NodeId.from_str(node_id))
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    subgraph = await graph_repo.get_neighbors(NodeId.from_str(node_id), depth=depth)

    nodes_dto = [
        KnowledgeNodeDTO(
            id=str(n.id),
            entity_type=n.entity_type.value,
            name=n.name,
            description=n.description,
            aliases=n.aliases,
            pagerank_score=n.pagerank_score,
            degree_centrality=n.degree_centrality,
            source_memory_count=len(n.source_memory_ids),
        )
        for n in subgraph.nodes
    ]

    edges_dto = [
        KnowledgeEdgeDTO(
            id=str(e.id),
            source_node_id=str(e.source_node_id),
            target_node_id=str(e.target_node_id),
            relationship_type=e.relationship_type.value,
            weight=e.weight,
            description=e.description,
        )
        for e in subgraph.edges
    ]

    return SubgraphResponseDTO(
        nodes=nodes_dto,
        edges=edges_dto,
        stats={"node_count": len(nodes_dto), "edge_count": len(edges_dto)},
    )


# ──────────────────── GET /knowledge/stats ────────────────────

@router.get(
    "/stats",
    response_model=dict,
    summary="Get knowledge graph statistics",
)
async def get_graph_stats(graph_repo=Depends(get_graph_repo)):
    return await graph_repo.get_graph_stats()


# ──────────────────── POST /knowledge/optimize ────────────────────

@router.post(
    "/optimize",
    response_model=dict,
    summary="Trigger knowledge graph optimization",
    description="Runs duplicate merging, PageRank recomputation, and centrality updates.",
)
async def optimize_graph(
    graph_repo=Depends(get_graph_repo),
    event_bus=Depends(get_event_bus),
):
    use_case = OptimizeGraphUseCase(graph_repo=graph_repo, event_bus=event_bus)
    result = await use_case.execute()
    return result
