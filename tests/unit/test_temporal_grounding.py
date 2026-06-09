"""Tests for current-date grounding in pipeline prompts.

Tests:
    - current_date_grounding() embeds the actual current UTC date
    - judge, timeline, and quick-sim metrics prompts include the grounding block
"""

from datetime import datetime, timezone

import pytest

from app.prompts import judge as judge_prompts
from app.prompts import quick_sim as quick_sim_prompts
from app.prompts import timeline as timeline_prompts
from app.prompts.temporal_grounding import current_date_grounding


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@pytest.mark.fast
class TestCurrentDateGrounding:
    """Tests for the shared grounding block builder."""

    def test_contains_current_utc_date(self):
        assert _today_utc() in current_date_grounding()

    def test_explicit_now_override(self):
        now = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
        block = current_date_grounding(now=now)
        assert "2026-06-09" in block
        assert "Tuesday" in block

    def test_instructs_relative_resolution(self):
        block = current_date_grounding()
        assert "Current real-world date:" in block
        assert "tomorrow" in block


@pytest.mark.fast
class TestPromptsEmbedGrounding:
    """Each date-sensitive prompt must embed the grounding block."""

    def test_judge_prompt_grounded(self):
        prompt = judge_prompts.get_prompt("tomorrow at 10am I meet Maria")
        assert _today_utc() in prompt

    def test_timeline_prompt_grounded(self):
        prompt = timeline_prompts.get_prompt(
            "tomorrow at 10am I meet Maria",
            query_type="personal_future",
        )
        assert _today_utc() in prompt

    def test_quick_sim_metrics_prompt_grounded(self):
        prompt = quick_sim_prompts.get_metrics_prompt(
            goal="$50k operating grant",
            opportunity={"title": "Climate Action Fund", "deadline": "2026-06-12"},
            scene_context="a tense grant-review meeting",
        )
        assert _today_utc() in prompt
