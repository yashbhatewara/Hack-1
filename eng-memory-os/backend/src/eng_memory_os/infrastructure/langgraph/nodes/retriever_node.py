"""
Retriever Node — Hybrid search (Vector + Graph + BM25).

Executes three retrieval strategies in parallel and merges results
using the composite evidence ranking algorithm.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from eng_memory_os.infrastructure.langgraph.evidence_ranker import EvidenceRanker

if TYPE_CHECKING:
    from eng_memory_os.domain.knowledge.repositories import (
        KnowledgeGraphRepository,
        VectorStoreRepository,
    )
    from eng_memory_os.infrastructure.db.vector.embedding_service import EmbeddingService
    from eng_memory_os.infrastructure.langgraph.state import AgentState

logger = structlog.get_logger(__name__)


class RetrieverNode:
    """Executes hybrid retrieval: vector similarity + graph traversal + lexical."""

    def __init__(
        self,
        vector_store: VectorStoreRepository,
        graph_repo: KnowledgeGraphRepository,
        embedding_service: EmbeddingService,
    ) -> None:
        self._vector_store = vector_store
        self._graph_repo = graph_repo
        self._embedding_service = embedding_service
        self._ranker = EvidenceRanker()

    async def __call__(self, state: AgentState) -> dict:
        sub_queries = state.get("sub_queries", [state.get("query_text", "")])

        all_vector_results: list[dict] = []
        all_graph_results: list[dict] = []
        all_lexical_results: list[dict] = []
        all_cognee_results: list[dict] = []

        for query in sub_queries:
            # Execute all four retrieval methods in parallel
            vector_task = self._vector_search(query)
            graph_task = self._graph_search(query)
            lexical_task = self._lexical_search(query)
            cognee_task = self._cognee_cloud_recall(query)

            vector_results, graph_results, lexical_results, cognee_results = await asyncio.gather(
                vector_task, graph_task, lexical_task, cognee_task,
                return_exceptions=True,
            )

            if isinstance(vector_results, list):
                all_vector_results.extend(vector_results)
            if isinstance(graph_results, list):
                all_graph_results.extend(graph_results)
            if isinstance(lexical_results, list):
                all_lexical_results.extend(lexical_results)
            if isinstance(cognee_results, list):
                all_cognee_results.extend(cognee_results)

        # Merge and rank all evidence
        evidence = self._ranker.rank(
            vector_results=all_vector_results,
            graph_results=all_graph_results,
            lexical_results=all_lexical_results,
            cognee_results=all_cognee_results,
        )

        logger.info(
            "retrieval_completed",
            vector_hits=len(all_vector_results),
            graph_hits=len(all_graph_results),
            lexical_hits=len(all_lexical_results),
            cognee_hits=len(all_cognee_results),
            total_evidence=len(evidence),
        )

        return {
            "retrieved_chunks": all_vector_results,
            "graph_neighbors": all_graph_results,
            "lexical_matches": all_lexical_results,
            "cognee_matches": all_cognee_results,
            "evidence": evidence[:20],  # Top 20 pieces of evidence
            "evidence_count": len(evidence),
            "nodes_visited": ["retriever"],
        }

    async def _vector_search(self, query: str) -> list[dict]:
        """Semantic vector similarity search."""
        try:
            query_vector = await self._embedding_service.embed_query(query)
            results = await self._vector_store.search_similar(
                query_vector=query_vector,
                limit=10,
                score_threshold=0.3,
            )
            return [
                {
                    "evidence_id": str(chunk.chunk_id),
                    "memory_id": str(chunk.memory_id),
                    "content": chunk.content,
                    "similarity_score": score,
                    "source": "vector",
                }
                for chunk, score in results
            ]
        except Exception as e:
            logger.warning("vector_search_failed", error=str(e))
            return []

    async def _graph_search(self, query: str) -> list[dict]:
        """Knowledge graph traversal — find entities mentioned in the query."""
        try:
            # Search for nodes matching terms in the query
            words = [w for w in query.split() if len(w) > 3]
            results: list[dict] = []

            for word in words[:5]:  # Limit to first 5 significant words
                nodes = await self._graph_repo.find_nodes_by_name(word, fuzzy=True)
                for node in nodes:
                    # Get neighbors for context
                    subgraph = await self._graph_repo.get_neighbors(node.id, depth=1)
                    results.append({
                        "node_id": str(node.id),
                        "name": node.name,
                        "type": node.entity_type.value,
                        "description": node.description,
                        "pagerank": node.pagerank_score,
                        "neighbors": len(subgraph.nodes),
                        "source": "graph",
                    })

            # Deduplicate by node_id
            seen: set[str] = set()
            unique: list[dict] = []
            for r in results:
                if r["node_id"] not in seen:
                    seen.add(r["node_id"])
                    unique.append(r)

            return unique[:10]
        except Exception as e:
            logger.warning("graph_search_failed", error=str(e))
            return []

    async def _lexical_search(self, query: str) -> list[dict]:
        """Keyword/lexical search for exact matches (error codes, method names).

        Uses the graph repository's name search with exact matching.
        """
        try:
            # Look for exact technical terms
            technical_terms = self._extract_technical_terms(query)
            results: list[dict] = []

            for term in technical_terms:
                nodes = await self._graph_repo.find_nodes_by_name(term, fuzzy=False)
                for node in nodes:
                    results.append({
                        "node_id": str(node.id),
                        "name": node.name,
                        "type": node.entity_type.value,
                        "content": node.description,
                        "score": 1.0,  # Exact match = max score
                        "source": "lexical",
                    })

            return results[:10]
        except Exception as e:
            logger.warning("lexical_search_failed", error=str(e))
            return []

    @staticmethod
    def _extract_technical_terms(query: str) -> list[str]:
        """Extract likely technical terms from a query.

        Identifies PascalCase, snake_case, kebab-case, and ALL_CAPS terms.
        """
        import re
        terms: list[str] = []

        # PascalCase: UserService, PaymentGateway
        terms.extend(re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", query))

        # snake_case or kebab-case: user_service, payment-gateway
        terms.extend(re.findall(r"\b[a-z]+[-_][a-z]+(?:[-_][a-z]+)*\b", query))

        # ALL_CAPS: HTTP, API, REST, SQL
        terms.extend(re.findall(r"\b[A-Z]{2,}\b", query))

        # Error codes: ERR-404, E001
        terms.extend(re.findall(r"\b[A-Z]{1,3}[-_]?\d{2,}\b", query))

        return list(set(terms))

    async def _cognee_cloud_recall(self, query: str) -> list[dict]:
        """Query Cognee Cloud's recall API for entities and graph insights."""
        import os
        import httpx
        cognee_url = os.environ.get("COGNEE_BASE_URL")
        cognee_key = os.environ.get("COGNEE_API_KEY")
        if not cognee_url or not cognee_key:
            logger.debug("cognee_cloud_credentials_missing_skipping_recall")
            return []

        try:
            base_url = cognee_url.rstrip("/")
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {
                    "X-Api-Key": cognee_key,
                    "Content-Type": "application/json",
                }
                response = await client.post(
                    f"{base_url}/api/v1/recall",
                    headers=headers,
                    json={"query": query},
                )
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    for idx, item in enumerate(data):
                        text = item.get("text") or item.get("raw", {}).get("value", "")
                        if text:
                            import hashlib
                            import uuid
                            h = hashlib.md5(text.encode("utf-8")).hexdigest()
                            evidence_id = str(uuid.UUID(h))

                            results.append({
                                "evidence_id": evidence_id,
                                "memory_id": "cognee-cloud",
                                "source_uri": "https://cognee.ai",
                                "similarity_score": 0.85,
                                "content": text,
                                "source": "cognee-cloud",
                            })
                    logger.info("cognee_cloud_recall_success", hits=len(results))
                    return results
                else:
                    logger.warning(
                        "cognee_cloud_recall_error_status",
                        status=response.status_code,
                        text=response.text,
                    )
        except Exception as e:
            logger.warning("cognee_cloud_recall_failed", error=str(e))

        return []
