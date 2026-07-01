"""
Entity extractor using LLM-based extraction.

Extracts engineering entities (actors, components, decisions, incidents)
and their relationships from raw text content.
"""

from __future__ import annotations

import json
import re

import structlog

from eng_memory_os.domain.knowledge.entities import (
    EntityType,
    KnowledgeEdge,
    KnowledgeNode,
    RelationshipType,
)
from eng_memory_os.domain.knowledge.value_objects import EntityMention
from eng_memory_os.domain.gateway.entities import LLMProvider, LLMRequest
from eng_memory_os.domain.gateway.interfaces import LLMGateway

logger = structlog.get_logger(__name__)

# System prompt for entity extraction
EXTRACTION_SYSTEM_PROMPT = """You are a precise entity extraction engine for engineering knowledge.
Given a text document about software engineering, extract ALL entities and relationships.

Return a JSON object with this exact structure:
{
  "entities": [
    {
      "name": "Entity Name",
      "type": "actor|component|decision|incident|technology|concept|metric|document|environment|api_endpoint",
      "description": "Brief description of the entity",
      "properties": {}
    }
  ],
  "relationships": [
    {
      "source": "Source Entity Name",
      "target": "Target Entity Name",
      "type": "implemented|decided|caused|resolved|depends_on|replaced|uses|authored|references|affected|monitors|member_of|deployed_to|exposes|related_to",
      "description": "Brief description of the relationship"
    }
  ]
}

Rules:
- Extract EVERY identifiable entity, even if mentioned briefly.
- Prefer specific entity types over "concept" where possible.
- Include people/teams as "actor", services/libraries as "component".
- All relationships must reference entities in the "entities" list.
- Return ONLY valid JSON, no markdown or explanation."""


class EntityExtractor:
    """Extracts engineering entities and relationships from text using an LLM."""

    def __init__(self, llm_gateway: LLMGateway) -> None:
        self._llm_gateway = llm_gateway

    async def extract(
        self,
        content: str,
        source_memory_id: str,
        chunk_index: int = 0,
    ) -> tuple[list[KnowledgeNode], list[tuple[str, str, KnowledgeEdge]]]:
        """Extract entities and relationships from text content.

        Returns:
            A tuple of:
            - List of KnowledgeNode objects
            - List of (source_name, target_name, KnowledgeEdge) tuples
              (names are used instead of IDs because node IDs are generated here)
        """
        request = LLMRequest.create(
            provider=LLMProvider.OPENAI,
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            temperature=0.1,  # Low temperature for precise extraction
            max_tokens=4096,
        )

        try:
            response = await self._llm_gateway.complete(request)
            extraction = self._parse_extraction_response(response.content)
        except Exception as e:
            logger.warning(
                "llm_extraction_failed",
                error=str(e),
                memory_id=source_memory_id,
            )
            # Fall back to rule-based extraction
            extraction = self._rule_based_extraction(content)

        # Convert to domain objects
        nodes: list[KnowledgeNode] = []
        edges: list[tuple[str, str, KnowledgeEdge]] = []

        # Create nodes
        node_name_map: dict[str, KnowledgeNode] = {}
        for entity_data in extraction.get("entities", []):
            entity_type = self._parse_entity_type(entity_data.get("type", "concept"))
            mention = EntityMention(
                entity_name=entity_data["name"],
                entity_type=entity_type.value,
                memory_id=source_memory_id,
                chunk_index=chunk_index,
                start_offset=0,
                end_offset=0,
                context_snippet=content[:200],
            )

            node = KnowledgeNode.create(
                entity_type=entity_type,
                name=entity_data["name"],
                description=entity_data.get("description", ""),
                source_memory_id=source_memory_id,
                mention=mention,
                properties=entity_data.get("properties", {}),
            )
            nodes.append(node)
            node_name_map[entity_data["name"].lower()] = node

        # Create edges
        for rel_data in extraction.get("relationships", []):
            source_name = rel_data.get("source", "").lower()
            target_name = rel_data.get("target", "").lower()

            source_node = node_name_map.get(source_name)
            target_node = node_name_map.get(target_name)

            if source_node and target_node:
                rel_type = self._parse_relationship_type(rel_data.get("type", "related_to"))
                edge = KnowledgeEdge.create(
                    source_node_id=source_node.id,
                    target_node_id=target_node.id,
                    relationship_type=rel_type,
                    description=rel_data.get("description", ""),
                    source_memory_id=source_memory_id,
                )
                edges.append((rel_data.get("source", ""), rel_data.get("target", ""), edge))

        logger.info(
            "entities_extracted",
            memory_id=source_memory_id,
            entity_count=len(nodes),
            relationship_count=len(edges),
        )

        return nodes, edges

    def _parse_extraction_response(self, response_text: str) -> dict:
        """Parse the LLM's JSON response, handling common formatting issues."""
        # Strip markdown code fences if present
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("extraction_json_parse_failed", response_preview=cleaned[:200])
            return {"entities": [], "relationships": []}

    def _rule_based_extraction(self, content: str) -> dict:
        """Fallback rule-based entity extraction using pattern matching.

        Used when the LLM is unavailable or fails.
        """
        entities: list[dict] = []
        relationships: list[dict] = []

        # Detect technology mentions
        tech_patterns = [
            "python", "javascript", "typescript", "react", "nextjs", "next.js",
            "fastapi", "django", "flask", "postgresql", "postgres", "redis",
            "docker", "kubernetes", "k8s", "aws", "gcp", "azure",
            "kafka", "rabbitmq", "graphql", "rest", "grpc",
            "terraform", "ansible", "jenkins", "github actions",
        ]
        content_lower = content.lower()
        for tech in tech_patterns:
            if tech in content_lower:
                entities.append({
                    "name": tech.title() if len(tech) > 3 else tech.upper(),
                    "type": "technology",
                    "description": f"Technology mentioned in content",
                    "properties": {},
                })

        # Detect component-like patterns (PascalCase or service names)
        pascal_case = re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", content)
        for name in set(pascal_case):
            if name not in ("GitHub", "GitLab", "PagerDuty"):
                entities.append({
                    "name": name,
                    "type": "component",
                    "description": f"Component identified by naming pattern",
                    "properties": {},
                })

        # Detect service names with patterns like "xxx-service", "xxx-api"
        service_patterns = re.findall(
            r"\b([a-z]+-(?:service|api|worker|gateway|proxy|db))\b",
            content_lower,
        )
        for svc in set(service_patterns):
            entities.append({
                "name": svc,
                "type": "component",
                "description": f"Service identified by naming pattern",
                "properties": {},
            })

        return {"entities": entities, "relationships": relationships}

    @staticmethod
    def _parse_entity_type(type_str: str) -> EntityType:
        try:
            return EntityType(type_str.lower())
        except ValueError:
            return EntityType.CONCEPT

    @staticmethod
    def _parse_relationship_type(type_str: str) -> RelationshipType:
        try:
            return RelationshipType(type_str.lower())
        except ValueError:
            return RelationshipType.RELATED_TO
