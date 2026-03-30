"""Entity Grounding Agent for web-search-based entity enrichment.

Uses OpenRouter web search plugins (Perplexity Sonar) to research real-world
entities detected in the generation pipeline. Produces structured GroundingProfile
objects with biography, appearance, affiliations, and source citations.

This agent runs AFTER GroundingAgent (Google Search for scene/event verification)
and enriches individual entities with real-world data.

Examples:
    >>> from app.agents.entity_grounding import EntityGroundingAgent
    >>> agent = EntityGroundingAgent(router)
    >>> profiles = await agent.run(["Marc Andreessen", "Jensen Huang"])
    >>> profiles["Marc Andreessen"].biography_summary
    "Co-founder of Andreessen Horowitz and Netscape..."

Tests:
    - tests/unit/test_agents/test_entity_grounding.py
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from app.core.llm_router import LLMRouter
from app.schemas.grounding_profile import GroundingProfile

logger = logging.getLogger(__name__)

# Default model for entity grounding via web search
GROUNDING_MODEL = "perplexity/sonar"

# System prompt for entity research
ENTITY_RESEARCH_SYSTEM = (
    "You are a factual research assistant. You MUST respond with valid JSON only. "
    "No markdown, no explanation, no code fences — just the JSON object."
)

ENTITY_RESEARCH_PROMPT = """Research the following person or entity: {name}

Provide the following information based ONLY on verifiable facts from your search results:

1. biography_summary: A concise (2-3 sentence) biographical summary
2. appearance_description: Physical description if the person is publicly known (height, build, distinguishing features). Say "No public description available" if unknown.
3. known_affiliations: List of organizations, companies, or groups they are associated with
4. recent_activity_summary: What they have been doing recently (last 1-2 years)
5. confidence: Your confidence in the accuracy of this information (0.0 to 1.0)

Respond with ONLY a JSON object in this exact format:
{{
  "biography_summary": "...",
  "appearance_description": "...",
  "known_affiliations": ["org1", "org2"],
  "recent_activity_summary": "...",
  "confidence": 0.85
}}"""


class EntityGroundingAgent:
    """Agent that grounds entities using OpenRouter web search plugins.

    For each entity name, calls OpenRouter with the web search plugin
    enabled (via Perplexity Sonar) to gather real-world data, then
    parses the response into a structured GroundingProfile.

    Attributes:
        router: LLM router for making API calls.
        model: Model to use for grounding (default: perplexity/sonar).
    """

    def __init__(self, router: LLMRouter, model: str = GROUNDING_MODEL) -> None:
        """Initialize the entity grounding agent.

        Args:
            router: LLM router for API calls.
            model: Model ID for grounding (default: perplexity/sonar).
        """
        self.router = router
        self.model = model

    async def run(self, entity_names: list[str]) -> dict[str, GroundingProfile]:
        """Ground a list of entity names via web search.

        For each unique entity name, performs a web search via OpenRouter
        and produces a GroundingProfile. Failures are gracefully degraded
        — a failed entity is simply omitted from the result.

        Args:
            entity_names: List of entity names to research.

        Returns:
            Mapping of {entity_name: GroundingProfile} for successfully grounded entities.
            Returns empty dict on total failure — never raises.
        """
        if not entity_names:
            return {}

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_names: list[str] = []
        for name in entity_names:
            normalized = name.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_names.append(normalized)

        profiles: dict[str, GroundingProfile] = {}

        for name in unique_names:
            try:
                profile = await self._ground_entity(name)
                if profile is not None:
                    profiles[name] = profile
            except Exception:
                logger.warning(
                    f"Entity grounding failed for '{name}' — skipping",
                    exc_info=True,
                )
                continue

        logger.info(
            f"Entity grounding: {len(profiles)}/{len(unique_names)} entities grounded"
        )
        return profiles

    async def _ground_entity(self, name: str) -> GroundingProfile | None:
        """Ground a single entity via web search.

        Args:
            name: Entity name to research.

        Returns:
            GroundingProfile if successful, None on failure.
        """
        prompt = ENTITY_RESEARCH_PROMPT.format(name=name)

        try:
            # Get the OpenRouter provider from the router
            from app.config import ProviderType
            from app.core.providers.openrouter import OpenRouterProvider

            provider = self.router.get_provider(ProviderType.OPENROUTER)
            if not isinstance(provider, OpenRouterProvider):
                logger.warning("OpenRouter provider not available for entity grounding")
                return None

            # Call with web search plugin enabled
            response = await provider.call_text(
                prompt=prompt,
                model=self.model,
                system=ENTITY_RESEARCH_SYSTEM,
                plugins=[{"id": "web", "max_results": 5}],
                temperature=0.3,
                max_tokens=1024,
            )

            raw_content = response.raw_response or (
                response.content if isinstance(response.content, str) else ""
            )

            if not raw_content:
                logger.warning(f"Empty response for entity '{name}'")
                return None

            # Parse JSON from response
            parsed = self._parse_json_response(raw_content)
            if parsed is None:
                logger.warning(f"Could not parse JSON response for entity '{name}'")
                return None

            # Extract annotations (web search citations) from response metadata
            annotations = response.metadata.get("annotations", [])
            source_citations = self._extract_citations(annotations)

            # Build GroundingProfile
            profile = GroundingProfile(
                entity_name=name,
                grounding_model=self.model,
                grounded_at=datetime.now(timezone.utc),
                biography_summary=parsed.get("biography_summary", ""),
                appearance_description=parsed.get("appearance_description", ""),
                known_affiliations=parsed.get("known_affiliations", []),
                recent_activity_summary=parsed.get("recent_activity_summary", ""),
                source_citations=source_citations,
                confidence=min(max(float(parsed.get("confidence", 0.5)), 0.0), 1.0),
            )

            return profile

        except Exception:
            logger.warning(
                f"Entity grounding request failed for '{name}'",
                exc_info=True,
            )
            return None

    @staticmethod
    def _parse_json_response(raw: str) -> dict | None:
        """Parse JSON from an LLM response, handling markdown fences.

        Args:
            raw: Raw LLM response string.

        Returns:
            Parsed dict or None on failure.
        """
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (with optional language tag)
            cleaned = re.sub(r"^```\w*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None

    @staticmethod
    def _extract_citations(annotations: list[dict]) -> list[str]:
        """Extract unique source URLs from OpenRouter annotations.

        Args:
            annotations: List of annotation dicts from the API response.

        Returns:
            List of unique source URLs.
        """
        urls: list[str] = []
        seen: set[str] = set()

        for ann in annotations:
            if ann.get("type") == "url_citation":
                url = ann.get("url_citation", {}).get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    urls.append(url)

        return urls
