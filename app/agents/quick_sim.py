"""Quick-Sim metrics agent.

A small wrapper on :class:`app.agents.base.BaseAgent` that takes a user
goal, an opportunity stub, and a rendered future-moment scene summary
and returns a :class:`app.schemas.quick_sim.QuickSimMetrics`.

This agent is intentionally narrow — it does not generate scenes,
characters, or dialog. It only extracts the five decision-fit fields
the Find Money selection page needs. Scene generation is reused
verbatim from the existing 14-agent ``GenerationPipeline``.

Examples:
    >>> from app.agents.quick_sim import QuickSimMetricsAgent, QuickSimMetricsInput
    >>> agent = QuickSimMetricsAgent()
    >>> result = await agent.run(QuickSimMetricsInput(
    ...     goal="$50k operating grant by Sept 2026",
    ...     opportunity={"title": "Climate Action Fund"},
    ...     scene_context="The user sits across a polished oak table...",
    ... ))

Tests:
    - tests/unit/test_agents/test_quick_sim.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_router import LLMRouter
from app.prompts import quick_sim as quick_sim_prompts
from app.schemas.quick_sim import QuickSimMetrics


@dataclass
class QuickSimMetricsInput:
    """Input bundle for the Quick-Sim metrics agent.

    Attributes:
        goal: User's free-text goal (passed through from the request).
        opportunity: Opportunity stub dict (title/summary/amount/...).
        scene_context: Compact, model-readable summary of the future-moment
            TDF — built by the endpoint after the scene pipeline runs.
    """

    goal: str
    opportunity: dict[str, Any]
    scene_context: str


class QuickSimMetricsAgent(BaseAgent[QuickSimMetricsInput, QuickSimMetrics]):
    """Extract structured fit metrics for a single opportunity.

    Runs a single LLM call. The system prompt forces calibration discipline
    (no clustering at 0.5, base-rate-anchored probabilities, concrete risks
    and levers). The response is parsed as :class:`QuickSimMetrics`.

    Attributes:
        response_model: :class:`QuickSimMetrics`
        name: ``"QuickSimMetricsAgent"``
    """

    response_model = QuickSimMetrics

    def __init__(self, router: LLMRouter | None = None) -> None:
        super().__init__(router=router, name="QuickSimMetricsAgent")

    def get_system_prompt(self) -> str:
        return quick_sim_prompts.get_metrics_system_prompt()

    def get_prompt(self, input_data: QuickSimMetricsInput) -> str:
        return quick_sim_prompts.get_metrics_prompt(
            goal=input_data.goal,
            opportunity=input_data.opportunity,
            scene_context=input_data.scene_context,
        )

    async def run(
        self, input_data: QuickSimMetricsInput
    ) -> AgentResult[QuickSimMetrics]:
        """Execute the metrics agent.

        Args:
            input_data: Goal + opportunity + scene context bundle.

        Returns:
            AgentResult with QuickSimMetrics on success, error otherwise.
        """
        return await self._call_llm(input_data, temperature=0.3)
