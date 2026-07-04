"""
Gateway Node — Intent classification and routing.

First node in the graph. Classifies the user's query intent
to route downstream processing.
"""

from __future__ import annotations

from eng_memory_os.cmd.config import get_settings
from eng_memory_os.domain.gateway.entities import LLMProvider, LLMRequest
from eng_memory_os.domain.gateway.interfaces import LLMGateway
from eng_memory_os.infrastructure.langgraph.state import AgentState

INTENT_SYSTEM_PROMPT = """You are a query intent classifier for an engineering knowledge system.
Classify the user's query into exactly ONE of these intents:

- search: Finding specific information (e.g., "What config does service X use?")
- explain: Explaining a concept or decision (e.g., "Why did we choose Kafka?")
- compare: Comparing approaches (e.g., "Compare REST vs gRPC for our API")
- timeline: Chronological history (e.g., "History of auth service changes")
- impact_analysis: Assessing change impact (e.g., "What would break if we remove Redis?")
- root_cause: Root cause analysis (e.g., "Why did the payment outage happen?")
- summarize: Summarizing a topic (e.g., "Summarize this quarter's architecture changes")

Respond with ONLY the intent string, nothing else."""


class GatewayNode:
    """Classifies query intent and initializes the agent state."""

    def __init__(self, llm_gateway: LLMGateway) -> None:
        self._llm = llm_gateway
        self._model = get_settings().openai_model

    async def __call__(self, state: AgentState) -> dict:
        query_text = state.get("query_text", "")

        request = LLMRequest.create(
            provider=LLMProvider.OPENAI,
            model=self._model,
            messages=[{"role": "user", "content": query_text}],
            system_prompt=INTENT_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=20,
        )

        try:
            response = await self._llm.complete(request)
            intent = response.content.strip().lower().replace('"', "").replace("'", "")
            valid_intents = {
                "search", "explain", "compare", "timeline",
                "impact_analysis", "root_cause", "summarize",
            }
            if intent not in valid_intents:
                intent = "search"  # Default fallback
        except Exception:
            intent = "search"

        return {
            "classified_intent": intent,
            "loop_count": 0,
            "max_loops": 3,
            "should_retry": False,
            "is_degraded": False,
            "nodes_visited": ["gateway"],
        }
