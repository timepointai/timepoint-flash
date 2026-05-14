"""Quick-Sim prompt templates.

Two prompt builders here:

1. ``build_future_moment_query(goal, opportunity)`` produces the
   future-tense query string handed to the standard 14-agent
   ``GenerationPipeline``. The pipeline renders the moment when the
   user is in the middle of pursuing the opportunity — a TDF used as
   the visual anchor on the Find Money selection page.

2. ``get_metrics_prompt(...)`` / ``get_metrics_system_prompt()`` produce
   the prompt fed to the metrics agent, which extracts the structured
   fit fields (probability of award, fit score, effort, risks, levers)
   conditioned on both the user's goal and the rendered scene.

Both prompt builders are deliberately small — they wrap, not replace,
the existing scene-generation pipeline.

Examples:
    >>> from app.prompts.quick_sim import build_future_moment_query
    >>> q = build_future_moment_query(
    ...     goal="$50k operating grant by Sept 2026",
    ...     opportunity={"title": "Climate Action Fund", "amount": 25000},
    ... )

Tests:
    - tests/unit/test_prompts_quick_sim.py
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Future-tense moment query (fed to GenerationPipeline as the user query)
# ---------------------------------------------------------------------------

FUTURE_MOMENT_TEMPLATE = (
    "Future moment, three months from today: the user is in the midst of pursuing "
    'the opportunity "{title}" toward their goal — {goal}. '
    "Render the room, the people, and the tension at the decisive beat of the "
    "application/pitch/submission. "
    "Opportunity details: {summary} Amount: {amount}. Deadline: {deadline}. "
    "Source: {source_url}."
)


def build_future_moment_query(goal: str, opportunity: dict[str, Any]) -> str:
    """Construct a future-tense query string for the scene pipeline.

    Keeps the result under 500 characters (Flash's hard ``query`` limit)
    by truncating the summary if necessary.

    Args:
        goal: User's free-text goal (passed verbatim from the request).
        opportunity: Dict with keys ``title``, ``source_url``, ``summary``,
            ``amount``, ``deadline``. Any/all may be missing.

    Returns:
        Query string suitable for ``GenerationPipeline.run(query)``.
    """
    title = (opportunity.get("title") or "this opportunity").strip()
    summary = (opportunity.get("summary") or "").strip()
    amount = opportunity.get("amount")
    deadline = (opportunity.get("deadline") or "unspecified").strip() or "unspecified"
    source_url = (opportunity.get("source_url") or "unspecified").strip() or "unspecified"

    amount_str: str
    if amount is None:
        amount_str = "unspecified"
    else:
        amount_str = str(amount)

    # Hard-cap summary so the full query stays under Flash's 500-char limit.
    # We allow up to ~200 chars of summary; the framing takes ~250.
    if len(summary) > 200:
        summary = summary[:197].rstrip() + "..."

    query = FUTURE_MOMENT_TEMPLATE.format(
        title=title,
        goal=goal.strip(),
        summary=summary or "see source for details.",
        amount=amount_str,
        deadline=deadline,
        source_url=source_url,
    )

    # Final safety: enforce 500-char cap to match GenerateRequest.query
    if len(query) > 500:
        query = query[:497].rstrip() + "..."
    return query


# ---------------------------------------------------------------------------
# Quick-Sim metrics agent prompts
# ---------------------------------------------------------------------------

METRICS_SYSTEM_PROMPT = """You are a Quick-Sim analyst for TIMEPOINT's Find Money workflow.

You read three inputs:
1. The user's goal — what they actually want.
2. An opportunity stub — a grant, RFP, contract, or similar that may serve that goal.
3. A rendered future-moment scene description — the moment the user is in the middle of pursuing this opportunity.

You produce a structured fit assessment with five fields:

- probability_of_award (0.0-1.0): Honest probability the user wins/secures this
  opportunity if they pursue it. Anchor against base rates: cold applications
  to competitive grants are 0.05-0.20; warm referrals 0.30-0.60; sole-source
  or extremely well-fit 0.60+. Avoid clustering at 0.5.

- fit_score (0.0-1.0): Alignment between the user's stated goal and what the
  opportunity actually funds. A perfect-shape grant for the wrong amount is
  ~0.5. A loose-shape grant for the right amount is ~0.4. Misaligned timing
  or eligibility caps this below 0.3.

- effort_score (0.0-1.0): Normalised effort to pursue this opportunity, where
  higher means more work. 0.0-0.3 = a light-touch application (a few hours, a
  short form); 0.4-0.6 = a moderate proposal (a couple of days, a narrative +
  one or two artefacts); 0.7-1.0 = a heavy full submission (a week or more,
  full proposal, budget, references, site visit). This MUST be consistent with
  effort_estimate.

- effort_estimate: One short phrase. Examples: "low — 4h application",
  "moderate — 20h proposal + 1 reference letter", "high — 60h full proposal,
  budget, and site visit". Be concrete about hours and artefacts.

- key_risks: 1-5 short bullet phrases. Real failure modes that could sink
  this pursuit (timing, eligibility, competition, capacity, fit drift).

- key_levers: 1-5 short bullet phrases. Concrete moves that materially raise
  the probability of award (a specific intro to ask for, a tighter framing,
  a complementary co-applicant).

- rationale: One sentence summarizing why these numbers, anchored in the
  rendered scene.

You MUST be honest. The downstream Pro deep-sim is expensive — your job is to
help the user pick the 5 opportunities most worth that spend. Cluster
probabilities, refuse to differentiate, or hand back generic risks and you
waste their money. Calibrate."""


METRICS_USER_TEMPLATE = """Assess this opportunity for the user's goal.

USER GOAL:
{goal}

OPPORTUNITY:
- title: {title}
- source: {source_url}
- summary: {summary}
- amount: {amount}
- deadline: {deadline}

RENDERED FUTURE-MOMENT SCENE (the moment the user is in the midst of pursuing this):
{scene_context}

Respond with valid JSON matching this schema:
{{
  "probability_of_award": 0.0-1.0,
  "fit_score": 0.0-1.0,
  "effort_score": 0.0-1.0,
  "effort_estimate": "short phrase with hours",
  "key_risks": ["risk 1", "risk 2", "..."],
  "key_levers": ["lever 1", "lever 2", "..."],
  "rationale": "one-sentence summary anchored in the scene"
}}"""


def get_metrics_system_prompt() -> str:
    """Return the system prompt for the Quick-Sim metrics agent."""
    return METRICS_SYSTEM_PROMPT


def get_metrics_prompt(
    *,
    goal: str,
    opportunity: dict[str, Any],
    scene_context: str,
) -> str:
    """Return the user prompt for the Quick-Sim metrics agent.

    Args:
        goal: User's free-text goal.
        opportunity: Opportunity stub dict.
        scene_context: Compact, model-readable summary of the future-moment
            TDF (scene + moment + dialog highlights). Built by
            :func:`app.api.v1.find_money.summarize_tdf_for_metrics`.

    Returns:
        Formatted user prompt.
    """
    return METRICS_USER_TEMPLATE.format(
        goal=goal.strip(),
        title=(opportunity.get("title") or "unspecified").strip(),
        source_url=(opportunity.get("source_url") or "unspecified") or "unspecified",
        summary=(opportunity.get("summary") or "unspecified") or "unspecified",
        amount=str(
            opportunity.get("amount") if opportunity.get("amount") is not None else "unspecified"
        ),
        deadline=(opportunity.get("deadline") or "unspecified") or "unspecified",
        scene_context=scene_context.strip() or "(no scene context available)",
    )
