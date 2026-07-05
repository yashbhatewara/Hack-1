"""
Evidence Ranking Algorithm.

Ranks retrieved evidence using the composite scoring formula:
Score = (Similarity * 0.4) + (PageRank * 0.3) + (Freshness * 0.2) + (Importance * 0.1)
"""

from __future__ import annotations

from datetime import datetime, timezone


class EvidenceRanker:
    """Ranks and merges evidence from multiple retrieval sources."""

    # Weights from the master spec
    SIMILARITY_WEIGHT = 0.4
    PAGERANK_WEIGHT = 0.3
    FRESHNESS_WEIGHT = 0.2
    IMPORTANCE_WEIGHT = 0.1

    def rank(
        self,
        vector_results: list[dict],
        graph_results: list[dict],
        lexical_results: list[dict],
        cognee_results: list[dict] | None = None,
    ) -> list[dict]:
        """Merge and rank evidence from all retrieval sources.

        Each result dict is augmented with a 'final_score' field.
        Results are deduplicated by evidence_id and sorted by final_score descending.
        """
        all_evidence: list[dict] = []

        # Score vector results
        for r in vector_results:
            r["final_score"] = self._compute_score(
                similarity=r.get("similarity_score", 0.0),
                pagerank=0.0,  # Vector results don't have pagerank
                freshness=1.0,  # Assume fresh for now
                importance=0.5,  # Default importance
            )
            all_evidence.append(r)

        # Score graph results
        for r in graph_results:
            r["final_score"] = self._compute_score(
                similarity=0.5,  # Graph matches get medium similarity
                pagerank=r.get("pagerank", 0.0),
                freshness=1.0,
                importance=0.7,  # Graph entities tend to be important
            )
            # Ensure graph results have content field
            if "content" not in r:
                r["content"] = r.get("description", r.get("name", ""))
            if "evidence_id" not in r:
                r["evidence_id"] = r.get("node_id", "")
            all_evidence.append(r)

        # Score lexical results
        for r in lexical_results:
            r["final_score"] = self._compute_score(
                similarity=r.get("score", 1.0),
                pagerank=0.0,
                freshness=1.0,
                importance=0.8,  # Exact matches are very important
            )
            if "evidence_id" not in r:
                r["evidence_id"] = r.get("node_id", "")
            all_evidence.append(r)

        # Score Cognee Cloud results
        if cognee_results:
            for r in cognee_results:
                r["final_score"] = self._compute_score(
                    similarity=r.get("similarity_score", 0.8),
                    pagerank=0.0,
                    freshness=1.0,
                    importance=0.9,  # Cognee Cloud extracted entities/relationships are highly relevant
                )
                all_evidence.append(r)

        # Deduplicate by evidence_id
        seen: set[str] = set()
        unique: list[dict] = []
        for e in all_evidence:
            eid = e.get("evidence_id", "")
            if eid and eid not in seen:
                seen.add(eid)
                unique.append(e)
            elif not eid:
                unique.append(e)

        # Sort by final_score descending
        unique.sort(key=lambda x: x.get("final_score", 0), reverse=True)

        return unique

    def _compute_score(
        self,
        similarity: float,
        pagerank: float,
        freshness: float,
        importance: float,
    ) -> float:
        """Compute the composite evidence score."""
        return (
            similarity * self.SIMILARITY_WEIGHT
            + pagerank * self.PAGERANK_WEIGHT
            + freshness * self.FRESHNESS_WEIGHT
            + importance * self.IMPORTANCE_WEIGHT
        )
