"""Real-world current-date grounding for pipeline prompts.

LLMs default to their training-data sense of "now" (often a past year),
which breaks contemporary/personal-future queries that use relative
expressions like "tomorrow" or "next Tuesday". This helper produces a
grounding block, computed at request time, that prompts can embed so the
model resolves relative dates against the actual current date.

Examples:
    >>> from app.prompts.temporal_grounding import current_date_grounding
    >>> block = current_date_grounding()
    >>> "Current real-world date:" in block
    True
"""

from __future__ import annotations

from datetime import datetime, timezone


def current_date_grounding(now: datetime | None = None) -> str:
    """Build a current-date grounding block for prompt injection.

    Args:
        now: Override for the current datetime (must be timezone-aware);
            defaults to the actual current UTC time.

    Returns:
        A short instruction block stating the real current date and how
        to resolve relative temporal expressions against it.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    weekday = now.strftime("%A")
    return (
        f"Current real-world date: {date_str} ({weekday}, UTC). "
        'Relative temporal expressions in the query — "today", "tomorrow", '
        '"next Tuesday", "in two weeks", "this summer" — MUST be resolved '
        "against this date, NOT against your training data. For contemporary "
        "or personal-future scenarios, the moment's year/month/day must be "
        "consistent with this date (e.g. \"tomorrow\" is exactly one day "
        "after it)."
    )
