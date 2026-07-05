"""
Reasoner Node — Evidence synthesis.

Synthesizes retrieved evidence against the original query,
producing a reasoning text with inline citations.
"""

from __future__ import annotations

from eng_memory_os.cmd.config import get_settings
from eng_memory_os.domain.gateway.entities import LLMProvider, LLMRequest
from eng_memory_os.domain.gateway.interfaces import LLMGateway
from eng_memory_os.infrastructure.langgraph.state import AgentState

REASONER_SYSTEM_PROMPT = """You are a reasoning engine for an engineering knowledge system.
You MUST synthesize an answer ONLY from the provided evidence. Follow these rules strictly:

1. Do NOT include any inline citations, source references, or mention evidence IDs (like [E-xxx] or E-<id>) in your response. Write a clean, natural response without citing any sources.
2. If the evidence is insufficient, explicitly state "I do not have historical data on this."
3. Do NOT invent or hallucinate information that is not in the evidence.
4. Structure your answer clearly with sections if the topic is complex.
5. Include specific details, names, dates, and technical specifics from the evidence.

You will receive evidence in this format:
EVIDENCE:
[E-<id>] (source: <source>, score: <score>): <content>

Synthesize a comprehensive, clean, natural answer without citing any sources."""


class ReasonerNode:
    """Synthesizes evidence into a reasoned answer with citations."""

    def __init__(self, llm_gateway: LLMGateway) -> None:
        self._llm = llm_gateway
        self._model = get_settings().openai_model

    async def __call__(self, state: AgentState) -> dict:
        query_text = state.get("query_text", "")
        evidence = state.get("evidence", [])

        if not evidence:
            return {
                "reasoning_text": "I do not have historical data on this topic.",
                "citations_used": [],
                "nodes_visited": ["reasoner"],
            }

        # Format evidence for the LLM
        evidence_text = self._format_evidence(evidence)

        prompt = f"""QUERY: {query_text}

{evidence_text}

Based ONLY on the above evidence, provide a comprehensive answer with inline citations."""

        request = LLMRequest.create(
            provider=LLMProvider.OPENAI,
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            system_prompt=REASONER_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=2048,
        )

        try:
            response = await self._llm.complete(request)
            reasoning_text = response.content.strip()
        except Exception as e:
            reasoning_text = f"Reasoning failed: {e}. Based on {len(evidence)} pieces of evidence found."

        # Extract which evidence IDs were actually cited
        citations_used = self._extract_cited_evidence(reasoning_text, evidence)

        return {
            "reasoning_text": reasoning_text,
            "citations_used": citations_used,
            "nodes_visited": ["reasoner"],
        }

    def _format_evidence(self, evidence: list[dict]) -> str:
        """Format evidence list into a readable block for the LLM."""
        lines = ["EVIDENCE:"]
        for e in evidence[:15]:  # Limit to top 15 to stay within context
            eid = (e.get("evidence_id") or "unknown")[:8]
            source = e.get("source", "unknown")
            score = e.get("final_score", e.get("similarity_score", 0))
            content = (e.get("content") or e.get("description") or "")[:500]
            lines.append(f"[E-{eid}] (source: {source}, score: {score:.2f}): {content}")
        return "\n".join(lines)

    @staticmethod
    def _extract_cited_evidence(text: str, evidence: list[dict]) -> list[dict]:
        """Find which evidence IDs were actually cited in the reasoning."""
        import re
        cited_ids = set(re.findall(r"\[E-([a-f0-9]+)\]", text))

        cited: list[dict] = []
        for e in evidence:
            eid = e.get("evidence_id", "")[:8]
            if eid in cited_ids:
                cited.append({
                    "evidence_id": e.get("evidence_id", ""),
                    "memory_id": e.get("memory_id", ""),
                    "source_uri": e.get("source_uri", ""),
                    "relevance_score": e.get("final_score", 0),
                })
        return cited
