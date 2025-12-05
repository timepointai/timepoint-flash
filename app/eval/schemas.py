"""Pydantic schemas for multi-model evaluation.

This module defines the data structures for model evaluation requests,
results, and comparative analysis.

Examples:
    >>> config = EvalModelConfig(
    ...     model_id="gemini-2.5-flash",
    ...     provider="google",
    ...     label="Gemini 2.5 Flash"
    ... )
    >>> request = EvalRequest(query="moon landing 1969", models=[config])
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ModelPreset(str, Enum):
    """Predefined model sets for evaluation.

    Attributes:
        VERIFIED: All verified working models from VerifiedModels
        GOOGLE_NATIVE: Google native API models only
        OPENROUTER: OpenRouter models only
        ALL: All available models
    """

    VERIFIED = "verified"
    GOOGLE_NATIVE = "google_native"
    OPENROUTER = "openrouter"
    ALL = "all"


class EvalModelConfig(BaseModel):
    """Configuration for a single model to evaluate.

    Attributes:
        model_id: The model identifier (e.g., "gemini-2.5-flash")
        provider: Provider name ("google" or "openrouter")
        label: Human-readable name for reports
    """

    model_id: str = Field(..., description="Model identifier")
    provider: str = Field(..., description="Provider: 'google' or 'openrouter'")
    label: str = Field(..., description="Human-readable label for reports")


class EvalModelResult(BaseModel):
    """Result from evaluating a single model.

    Attributes:
        model_id: The model that was tested
        provider: The provider used
        label: Human-readable model name
        success: Whether the call succeeded
        latency_ms: Time from request to response in milliseconds
        output: The model's response text (truncated for large outputs)
        output_length: Character count of full output
        output_preview: First 200 chars of output for display
        error: Error message if failed
        started_at: When the test started
        completed_at: When the test completed
    """

    model_id: str
    provider: str
    label: str
    success: bool
    latency_ms: int = 0
    output: str | None = None
    output_length: int = 0
    output_preview: str | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime

    @property
    def latency_seconds(self) -> float:
        """Latency in seconds."""
        return self.latency_ms / 1000.0


class EvalLatencyStats(BaseModel):
    """Latency statistics across all successful model runs.

    Attributes:
        min_ms: Minimum latency
        max_ms: Maximum latency
        avg_ms: Average latency
        median_ms: Median latency
        range_ms: Max - Min
    """

    min_ms: int = 0
    max_ms: int = 0
    avg_ms: int = 0
    median_ms: int = 0
    range_ms: int = 0


class EvalComparison(BaseModel):
    """Aggregated comparison across all evaluated models.

    Attributes:
        query: The prompt that was tested
        prompt_type: Type of prompt (e.g., "judge", "timeline")
        timestamp: When the evaluation was run
        total_duration_ms: Total wall-clock time for all tests
        models_tested: Number of models evaluated
        results: Individual results for each model
        fastest_model: Model ID of fastest successful response
        slowest_model: Model ID of slowest successful response
        success_count: Number of successful responses
        failure_count: Number of failed responses
        success_rate: Percentage of successful responses
        latency_stats: Latency statistics
        ranking: Models ranked by latency (fastest first)
    """

    query: str
    prompt_type: str = "text"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_duration_ms: int = 0
    models_tested: int = 0
    results: list[EvalModelResult] = Field(default_factory=list)
    fastest_model: str | None = None
    slowest_model: str | None = None
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    latency_stats: EvalLatencyStats = Field(default_factory=EvalLatencyStats)
    ranking: list[str] = Field(default_factory=list)

    def compute_stats(self) -> None:
        """Compute statistics from results."""
        self.models_tested = len(self.results)

        successful = [r for r in self.results if r.success]
        self.success_count = len(successful)
        self.failure_count = self.models_tested - self.success_count
        self.success_rate = (
            (self.success_count / self.models_tested * 100)
            if self.models_tested > 0 else 0.0
        )

        if successful:
            # Sort by latency
            sorted_results = sorted(successful, key=lambda r: r.latency_ms)
            self.ranking = [r.model_id for r in sorted_results]

            self.fastest_model = sorted_results[0].model_id
            self.slowest_model = sorted_results[-1].model_id

            latencies = [r.latency_ms for r in successful]
            self.latency_stats = EvalLatencyStats(
                min_ms=min(latencies),
                max_ms=max(latencies),
                avg_ms=int(sum(latencies) / len(latencies)),
                median_ms=latencies[len(latencies) // 2],
                range_ms=max(latencies) - min(latencies),
            )


class EvalRequest(BaseModel):
    """Request to run a multi-model evaluation.

    Attributes:
        query: The prompt to send to all models
        models: Specific models to test (optional)
        preset: Predefined model set to use (alternative to models)
        prompt_type: Type of prompt for context
        timeout_seconds: Maximum time per model call
    """

    query: str = Field(..., min_length=1, description="Prompt to evaluate")
    models: list[EvalModelConfig] | None = Field(
        None, description="Specific models to test"
    )
    preset: ModelPreset | None = Field(
        None, description="Predefined model set to use"
    )
    prompt_type: str = Field("text", description="Type of prompt")
    timeout_seconds: int = Field(120, ge=10, le=600, description="Timeout per model")

    def model_post_init(self, __context: Any) -> None:
        """Validate that either models or preset is provided."""
        if not self.models and not self.preset:
            # Default to verified preset
            self.preset = ModelPreset.VERIFIED


class EvalModelsResponse(BaseModel):
    """Response listing available models for evaluation.

    Attributes:
        presets: Available presets with their model counts
        models: All available model configurations
    """

    presets: dict[str, int] = Field(
        default_factory=dict, description="Preset name -> model count"
    )
    models: list[EvalModelConfig] = Field(
        default_factory=list, description="All available models"
    )
