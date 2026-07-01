"""Unit tests for the LangGraph evidence ranker."""

from __future__ import annotations

import pytest

from eng_memory_os.infrastructure.langgraph.evidence_ranker import EvidenceRanker


class TestEvidenceRanker:

    @pytest.fixture
    def ranker(self):
        return EvidenceRanker()

    @pytest.mark.unit
    def test_vector_results_scored_with_similarity_weight(self, ranker):
        vector_results = [
            {"evidence_id": "a", "similarity_score": 0.9, "content": "text", "source": "vector"},
            {"evidence_id": "b", "similarity_score": 0.5, "content": "text2", "source": "vector"},
        ]
        ranked = ranker.rank(vector_results=vector_results, graph_results=[], lexical_results=[])

        # Higher similarity should rank first
        assert ranked[0]["evidence_id"] == "a"
        assert ranked[0]["final_score"] > ranked[1]["final_score"]

    @pytest.mark.unit
    def test_graph_results_use_pagerank_weight(self, ranker):
        graph_results = [
            {"node_id": "x", "pagerank": 0.9, "name": "AuthService", "source": "graph"},
            {"node_id": "y", "pagerank": 0.1, "name": "LogService",  "source": "graph"},
        ]
        ranked = ranker.rank(vector_results=[], graph_results=graph_results, lexical_results=[])

        assert ranked[0]["node_id"] == "x"

    @pytest.mark.unit
    def test_lexical_exact_matches_score_high(self, ranker):
        lexical = [{"node_id": "z", "score": 1.0, "name": "gRPC", "source": "lexical"}]
        vector = [{"evidence_id": "a", "similarity_score": 0.6, "content": "some text", "source": "vector"}]
        ranked = ranker.rank(vector_results=vector, graph_results=[], lexical_results=lexical)

        # Exact match with score=1.0 and importance=0.8 should outscore similarity=0.6
        lexical_item = next(r for r in ranked if r.get("node_id") == "z")
        assert lexical_item is not None

    @pytest.mark.unit
    def test_deduplication_by_evidence_id(self, ranker):
        """Same evidence_id appearing in multiple sources should be deduplicated."""
        v1 = {"evidence_id": "dup-id", "similarity_score": 0.8, "content": "c1", "source": "vector"}
        v2 = {"evidence_id": "dup-id", "similarity_score": 0.7, "content": "c2", "source": "vector"}
        ranked = ranker.rank(vector_results=[v1, v2], graph_results=[], lexical_results=[])

        dup_ids = [r["evidence_id"] for r in ranked if r.get("evidence_id") == "dup-id"]
        assert len(dup_ids) == 1

    @pytest.mark.unit
    def test_empty_inputs_return_empty_list(self, ranker):
        ranked = ranker.rank(vector_results=[], graph_results=[], lexical_results=[])
        assert ranked == []

    @pytest.mark.unit
    def test_composite_formula_correctness(self, ranker):
        """Verify the exact composite scoring formula."""
        vector = [{"evidence_id": "e1", "similarity_score": 0.8, "content": "text", "source": "vector"}]
        ranked = ranker.rank(vector_results=vector, graph_results=[], lexical_results=[])

        expected_score = (
            0.8 * 0.4   # similarity
            + 0.0 * 0.3  # pagerank (vector has 0)
            + 1.0 * 0.2  # freshness (default 1.0)
            + 0.5 * 0.1  # importance (default 0.5 for vector)
        )
        assert abs(ranked[0]["final_score"] - expected_score) < 0.001

    @pytest.mark.unit
    def test_results_sorted_descending(self, ranker):
        vector = [
            {"evidence_id": "low",  "similarity_score": 0.2, "content": "c", "source": "vector"},
            {"evidence_id": "high", "similarity_score": 0.95, "content": "c", "source": "vector"},
            {"evidence_id": "mid",  "similarity_score": 0.5, "content": "c", "source": "vector"},
        ]
        ranked = ranker.rank(vector_results=vector, graph_results=[], lexical_results=[])
        scores = [r["final_score"] for r in ranked]
        assert scores == sorted(scores, reverse=True)
