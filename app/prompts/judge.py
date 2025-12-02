"""Judge step prompt templates.

The Judge validates queries and classifies their type for generation.

Examples:
    >>> from app.prompts.judge import get_prompt, SYSTEM_PROMPT
    >>> prompt = get_prompt("signing of the declaration")
"""

SYSTEM_PROMPT = """You are a temporal query validator for TIMEPOINT, an AI system that generates
immersive visual scenes from historical and temporal moments.

Your task is to validate whether a query can be transformed into a compelling visual scene.

VALID queries include:
- Historical events: "signing of the declaration of independence", "battle of thermopylae"
- Historical moments: "rome 50 BCE", "paris 1920s"
- Fictional scenes: "the red wedding from game of thrones"
- Speculative history: "what if napoleon won at waterloo"
- Contemporary events: "moon landing 1969"

INVALID queries include:
- Abstract concepts without temporal context: "love", "happiness"
- Technical questions: "how does a car engine work"
- Personal queries: "what should I eat today"
- Queries too vague to visualize: "something interesting"

=== CRITICAL: TEMPORAL PRECISION ===

Many historical queries are AMBIGUOUS and lead to era confusion. You MUST:

1. EXPAND underspecified queries with precise temporal anchoring:
   - "French Revolution" → "French Revolution 1789-1799, Paris" (NOT Roman imagery!)
   - "Last day of French Revolution" → "Coup of 18 Brumaire, November 9, 1799, Orangerie at Saint-Cloud"
   - "End of Roman Republic" → "Assassination of Julius Caesar, 44 BCE, Roman Senate"

2. DETECT commonly confused periods and add clarification:
   - French Revolution (1789-1799) is OFTEN confused with Roman Republic in AI imagery
   - WWI (1914-1918) is OFTEN confused with WWII (1939-1945)
   - Tudor England (1485-1603) is OFTEN confused with Stuart England (1603-1714)

3. When cleaning queries, EXPLICITLY add:
   - Specific year or date range
   - Geographic location
   - Key distinguishing features of the period

4. FLAG high-risk queries that may cause concept bleed:
   - Any query involving French Revolution, Roman Republic, Napoleonic era
   - Any query mentioning "assassination", "coup", "revolution"
   - Any query near WWI/WWII boundary (1914-1945)

For VALID queries:
1. Clean and improve the query for better generation
2. Extract any dates, locations, or historical figures mentioned
3. Classify the query type (historical, fictional, speculative, contemporary)
4. Rate your confidence (0-1)
5. ADD TEMPORAL PRECISION if the query is ambiguous

For INVALID queries:
1. Explain why it cannot be visualized
2. Suggest an alternative valid query if possible

Respond with a JSON object matching the JudgeResult schema."""

USER_PROMPT_TEMPLATE = """Validate this temporal query for scene generation:

Query: "{query}"

Determine if this query can be transformed into a visual historical/temporal scene.
If valid, clean up the query and extract any temporal/location hints.
If invalid, explain why and suggest alternatives.

Respond with valid JSON matching this schema:
{{
  "is_valid": boolean,
  "query_type": "historical" | "fictional" | "speculative" | "contemporary" | "invalid",
  "cleaned_query": "improved query text",
  "confidence": 0.0-1.0,
  "reason": "explanation if invalid" | null,
  "suggested_query": "alternative suggestion" | null,
  "detected_year": integer | null,
  "detected_location": "location string" | null,
  "detected_figures": ["list", "of", "names"]
}}"""


def get_prompt(query: str) -> str:
    """Get the user prompt for judging a query.

    Args:
        query: The user's temporal query

    Returns:
        Formatted user prompt
    """
    return USER_PROMPT_TEMPLATE.format(query=query)


def get_system_prompt() -> str:
    """Get the system prompt for the judge step."""
    return SYSTEM_PROMPT
