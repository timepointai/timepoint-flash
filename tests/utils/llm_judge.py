"""
LLM-based performance judge for evaluating timepoint generation quality.

Uses Google Gemini models through OpenRouter to assess:
- Historical accuracy
- Character consistency
- Dialog quality
- Scene coherence
- Overall quality
"""
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
import httpx


@dataclass
class JudgementResult:
    """Result from LLM judge evaluation."""
    overall_score: float  # 0-100
    historical_accuracy: float  # 0-100
    character_quality: float  # 0-100
    dialog_quality: float  # 0-100
    scene_coherence: float  # 0-100
    feedback: str
    passed: bool  # True if overall_score >= threshold

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "overall_score": self.overall_score,
            "historical_accuracy": self.historical_accuracy,
            "character_quality": self.character_quality,
            "dialog_quality": self.dialog_quality,
            "scene_coherence": self.scene_coherence,
            "feedback": self.feedback,
            "passed": self.passed,
        }


class LLMPerformanceJudge:
    """
    LLM-based judge for evaluating timepoint generation quality.

    Uses Google Gemini 1.5 Pro through OpenRouter for comprehensive evaluation.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "google/gemini-1.5-pro",
        passing_threshold: float = 70.0
    ):
        """
        Initialize the LLM judge.

        Args:
            api_key: OpenRouter API key
            model: Model to use for judging (default: gemini-1.5-pro)
            passing_threshold: Minimum overall score to pass (default: 70.0)
        """
        self.api_key = api_key
        self.model = model
        self.passing_threshold = passing_threshold
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    async def judge_timepoint(
        self,
        query: str,
        timepoint_data: Dict[str, Any],
        timeout: int = 60
    ) -> JudgementResult:
        """
        Evaluate a generated timepoint.

        Args:
            query: Original user query
            timepoint_data: Generated timepoint data (full JSON)
            timeout: Request timeout in seconds

        Returns:
            JudgementResult with scores and feedback
        """
        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(query, timepoint_data)

        # Call LLM
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an expert historian and creative director evaluating "
                                "AI-generated historical timepoint scenes. Provide objective, "
                                "detailed assessments with numeric scores."
                            )
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,  # Low temperature for consistent evaluation
                    "max_tokens": 1000,
                }
            )
            response.raise_for_status()
            result = response.json()

        # Parse LLM response
        llm_output = result["choices"][0]["message"]["content"]
        scores = self._parse_scores(llm_output)

        # Calculate overall score
        overall_score = (
            scores["historical_accuracy"] * 0.3 +
            scores["character_quality"] * 0.25 +
            scores["dialog_quality"] * 0.25 +
            scores["scene_coherence"] * 0.2
        )

        return JudgementResult(
            overall_score=overall_score,
            historical_accuracy=scores["historical_accuracy"],
            character_quality=scores["character_quality"],
            dialog_quality=scores["dialog_quality"],
            scene_coherence=scores["scene_coherence"],
            feedback=scores["feedback"],
            passed=overall_score >= self.passing_threshold
        )

    def _build_evaluation_prompt(
        self,
        query: str,
        timepoint_data: Dict[str, Any]
    ) -> str:
        """Build evaluation prompt from timepoint data."""
        # Extract key information
        year = timepoint_data.get("year", "Unknown")
        season = timepoint_data.get("season", "Unknown")
        location = timepoint_data.get("location", "Unknown")
        cleaned_query = timepoint_data.get("cleaned_query", query)
        characters = timepoint_data.get("character_data", [])
        dialog = timepoint_data.get("dialog", [])
        scene_description = timepoint_data.get("scene_description", "")

        # Format characters
        characters_text = "\n".join([
            f"- {c.get('name', 'Unknown')}: {c.get('role', 'N/A')} - "
            f"{c.get('appearance', 'N/A')} wearing {c.get('clothing', 'N/A')}"
            for c in characters[:5]  # Limit to first 5 for brevity
        ])

        # Format dialog
        dialog_text = "\n".join([
            f"{d.get('speaker', 'Unknown')}: \"{d.get('text', '')}\""
            for d in dialog[:10]  # Limit to first 10 lines
        ])

        prompt = f"""Evaluate the following AI-generated historical timepoint scene:

**Original Query**: {query}

**Cleaned Query**: {cleaned_query}

**Setting**:
- Year: {year}
- Season: {season}
- Location: {location}

**Scene Description**:
{scene_description[:500]}...

**Characters** (showing first 5):
{characters_text}

**Dialog** (showing first 10 lines):
{dialog_text}

---

Please evaluate this timepoint on the following criteria, providing a score from 0-100 for each:

1. **Historical Accuracy** (0-100): Are the characters, clothing, dialog, and setting accurate for the time period and location? Consider anachronisms, period-appropriate language, and historical plausibility.

2. **Character Quality** (0-100): Are the characters well-developed, distinct, and believable? Do they have clear roles and appropriate appearances for the setting?

3. **Dialog Quality** (0-100): Is the dialog natural, engaging, and period-appropriate? Does it feel authentic to the characters and setting?

4. **Scene Coherence** (0-100): Does the scene make sense as a whole? Are all elements (characters, dialog, setting) working together cohesively?

**IMPORTANT**: Respond ONLY in this exact JSON format (no additional text):

{{
  "historical_accuracy": <score 0-100>,
  "character_quality": <score 0-100>,
  "dialog_quality": <score 0-100>,
  "scene_coherence": <score 0-100>,
  "feedback": "<2-3 sentence summary of strengths and weaknesses>"
}}
"""
        return prompt

    def _parse_scores(self, llm_output: str) -> Dict[str, Any]:
        """
        Parse scores from LLM output.

        Expects JSON format with scores and feedback.
        """
        try:
            # Try to extract JSON from output
            # Handle cases where LLM adds markdown code blocks
            if "```json" in llm_output:
                json_start = llm_output.find("```json") + 7
                json_end = llm_output.find("```", json_start)
                json_str = llm_output[json_start:json_end].strip()
            elif "```" in llm_output:
                json_start = llm_output.find("```") + 3
                json_end = llm_output.find("```", json_start)
                json_str = llm_output[json_start:json_end].strip()
            else:
                # Try to find JSON object
                json_start = llm_output.find("{")
                json_end = llm_output.rfind("}") + 1
                json_str = llm_output[json_start:json_end].strip()

            scores = json.loads(json_str)

            # Validate scores
            required_keys = [
                "historical_accuracy",
                "character_quality",
                "dialog_quality",
                "scene_coherence",
                "feedback"
            ]

            for key in required_keys:
                if key not in scores:
                    raise ValueError(f"Missing key: {key}")

            # Ensure scores are in range
            for key in required_keys[:-1]:  # Skip feedback
                score = float(scores[key])
                if not 0 <= score <= 100:
                    raise ValueError(f"Score {key} out of range: {score}")
                scores[key] = score

            return scores

        except (json.JSONDecodeError, ValueError) as e:
            # Fallback to default scores if parsing fails
            return {
                "historical_accuracy": 50.0,
                "character_quality": 50.0,
                "dialog_quality": 50.0,
                "scene_coherence": 50.0,
                "feedback": f"Failed to parse LLM response: {str(e)}. Output: {llm_output[:200]}"
            }


# Convenience function for quick evaluation
async def judge_timepoint(
    api_key: str,
    query: str,
    timepoint_data: Dict[str, Any],
    passing_threshold: float = 70.0
) -> JudgementResult:
    """
    Quick convenience function to judge a timepoint.

    Args:
        api_key: OpenRouter API key
        query: Original user query
        timepoint_data: Generated timepoint data
        passing_threshold: Minimum score to pass (default: 70.0)

    Returns:
        JudgementResult with evaluation
    """
    judge = LLMPerformanceJudge(
        api_key=api_key,
        passing_threshold=passing_threshold
    )
    return await judge.judge_timepoint(query, timepoint_data)
