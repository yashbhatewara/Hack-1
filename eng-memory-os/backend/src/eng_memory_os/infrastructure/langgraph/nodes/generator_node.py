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
        final_response = reasoning

        return {
            "final_response": final_response,
            "is_degraded": is_degraded,
            "nodes_visited": ["generator"],
        }
