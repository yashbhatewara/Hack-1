"""
Generator Node — Final response formatting.

Formats the final response with proper citations and a degradation
disclaimer if confidence threshold was not met.
"""

from __future__ import annotations

from eng_memory_os.infrastructure.langgraph.state import AgentState


class GeneratorNode:
    """Formats the final response for the user."""

    async def __call__(self, state: AgentState) -> dict:
        reasoning = state.get("reasoning_text", "")
        confidence = state.get("confidence_score", 0.0)
        is_degraded = state.get("is_degraded", False)
        citations = state.get("citations_used", [])
        loop_count = state.get("loop_count", 0)

        # Build the final response
        response_parts: list[str] = []

        if is_degraded:
            response_parts.append(reasoning)
            response_parts.append("")
            response_parts.append(
                "---\n"
                "⚠️ **Low Confidence Response**\n\n"
                "I do not have sufficient historical data to fully answer this question "
                "with high confidence. The above is based on limited evidence and should "
                "be independently verified."
            )
        else:
            response_parts.append(reasoning)

        # Add citations footer
        if citations:
            response_parts.append("")
            response_parts.append("---\n**Sources:**")
            for i, citation in enumerate(citations, 1):
                eid = citation.get("evidence_id", "")[:8]
                source = citation.get("source_uri", "unknown source")
                score = citation.get("relevance_score", 0)
                response_parts.append(
                    f"{i}. `[E-{eid}]` — {source} (relevance: {score:.0%})"
                )

        final_response = "\n".join(response_parts)

        return {
            "final_response": final_response,
            "is_degraded": is_degraded,
            "nodes_visited": ["generator"],
        }
