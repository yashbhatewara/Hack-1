"""
Critic / Verifier Node — Cross-checks reasoning against evidence.

Evaluates the Reasoner's output for hallucinations and confidence.
If confidence < 0.85 or hallucination detected, triggers a retry loop.
"""

from __future__ import annotations

import json

from eng_memory_os.domain.gateway.entities import LLMProvider, LLMRequest
from eng_memory_os.domain.gateway.interfaces import LLMGateway
from eng_memory_os.infrastructure.langgraph.state import AgentState

CRITIC_SYSTEM_PROMPT = """You are a strict fact-checking critic for an engineering knowledge system.
Evaluate the REASONING against the EVIDENCE and check for:

1. Hallucinations: Claims not supported by the provided evidence
2. Missing citations: Claims without [E-<id>] citations
3. Accuracy: Whether citations actually support the claims they're attached to
4. Completeness: Whether important evidence was overlooked

Return a JSON object with:
{
  "confidence": <float 0.0 to 1.0>,
  "hallucination_detected": <boolean>,
  "feedback": "<specific feedback about issues found>",
  "refined_query": "<improved query if retry is needed, or empty string>"
}

Be strict. Only assign confidence >= 0.85 if ALL claims are properly cited and accurate."""


class CriticNode:
    """Verifies reasoning against evidence; triggers retries if needed."""

    def __init__(self, llm_gateway: LLMGateway) -> None:
        self._llm = llm_gateway

    async def __call__(self, state: AgentState) -> dict:
        reasoning = state.get("reasoning_text", "")
        evidence = state.get("evidence", [])
        loop_count = state.get("loop_count", 0)
        max_loops = state.get("max_loops", 3)

        # If no evidence was found, skip critic and mark as degraded
        if not evidence:
            return {
                "confidence_score": 0.0,
                "hallucination_detected": False,
                "critic_feedback": "No evidence available",
                "should_retry": False,
                "is_degraded": True,
                "loop_count": loop_count,
                "nodes_visited": ["critic"],
            }

        # Format evidence for the critic
        evidence_summary = "\n".join(
            f"[E-{e.get('evidence_id', 'x')[:8]}]: {e.get('content', e.get('description', ''))[:300]}"
            for e in evidence[:10]
        )

        prompt = f"""REASONING:
{reasoning}

EVIDENCE:
{evidence_summary}

Evaluate the reasoning strictly against the evidence."""

        request = LLMRequest.create(
            provider=LLMProvider.OPENAI,
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            system_prompt=CRITIC_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=500,
        )

        try:
            response = await self._llm.complete(request)
            evaluation = self._parse_evaluation(response.content)
        except Exception:
            # On critic failure, pass through with medium confidence
            evaluation = {
                "confidence": 0.7,
                "hallucination_detected": False,
                "feedback": "Critic evaluation failed; proceeding with caution.",
                "refined_query": "",
            }

        confidence = evaluation.get("confidence", 0.5)
        hallucination = evaluation.get("hallucination_detected", False)
        feedback = evaluation.get("feedback", "")
        refined = evaluation.get("refined_query", "")

        # Determine if we should retry
        should_retry = (
            (confidence < 0.85 or hallucination)
            and loop_count < max_loops
        )

        return {
            "confidence_score": confidence,
            "hallucination_detected": hallucination,
            "critic_feedback": feedback,
            "refined_query": refined if refined else state.get("query_text", ""),
            "should_retry": should_retry,
            "is_degraded": not should_retry and confidence < 0.85,
            "loop_count": loop_count + 1,
            "nodes_visited": ["critic"],
        }

    @staticmethod
    def _parse_evaluation(response_text: str) -> dict:
        """Parse the critic's JSON response."""
        import re
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            result = json.loads(cleaned)
            # Validate and clamp confidence
            result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
            result["hallucination_detected"] = bool(result.get("hallucination_detected", False))
            return result
        except (json.JSONDecodeError, ValueError):
            return {
                "confidence": 0.5,
                "hallucination_detected": False,
                "feedback": "Could not parse critic evaluation.",
                "refined_query": "",
            }
