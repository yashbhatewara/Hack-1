"""
Planner Node — Query decomposition.

Breaks complex queries into actionable sub-tasks for the retriever.
"""

from __future__ import annotations

import json

from eng_memory_os.domain.gateway.entities import LLMProvider, LLMRequest
from eng_memory_os.domain.gateway.interfaces import LLMGateway
from eng_memory_os.infrastructure.langgraph.state import AgentState

PLANNER_SYSTEM_PROMPT = """You are a query planner for an engineering knowledge system.
Break the user's question into 1-4 focused sub-queries that can each be answered
independently from the knowledge base.

Rules:
- Each sub-query should target a specific piece of information.
- If the question is already simple and focused, return it as a single sub-query.
- Return a JSON array of strings, nothing else.

Example:
Input: "Why did the payment outage happen last week and what was the impact?"
Output: ["What caused the payment service outage last week?", "What was the impact of the payment outage?", "What services were affected by the payment outage?"]"""


class PlannerNode:
    """Decomposes complex queries into sub-tasks."""

    def __init__(self, llm_gateway: LLMGateway) -> None:
        self._llm = llm_gateway

    async def __call__(self, state: AgentState) -> dict:
        query_text = state.get("refined_query") or state.get("query_text", "")

        request = LLMRequest.create(
            provider=LLMProvider.OPENAI,
            model="gpt-4o",
            messages=[{"role": "user", "content": query_text}],
            system_prompt=PLANNER_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=500,
        )

        try:
            response = await self._llm.complete(request)
            text = response.content.strip()
            if text.startswith("```"):
                text = text.strip("`").strip("json").strip()
            sub_queries = json.loads(text)
            if not isinstance(sub_queries, list):
                sub_queries = [query_text]
        except Exception:
            sub_queries = [query_text]

        return {
            "sub_queries": sub_queries,
            "nodes_visited": ["planner"],
        }
