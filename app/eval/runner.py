"""Multi-model evaluation runner.

This module provides the ModelEvaluator class that runs the same prompt
across multiple models in parallel and collects comparative metrics.

Features:
    - Parallel execution via asyncio.gather()
    - Per-model timing measurement
    - Support for predefined model sets
    - Integration with existing rate limiting

Examples:
    >>> evaluator = ModelEvaluator()
    >>> request = EvalRequest(query="Tell me about Rome", preset="verified")
    >>> comparison = await evaluator.compare(request)
    >>> for r in comparison.results:
    ...     print(f"{r.label}: {r.latency_ms}ms")
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from app.config import ProviderType, VerifiedModels, get_settings
from app.core.providers import ModelCapability
from app.core.providers.google import GoogleProvider
from app.core.providers.openrouter import OpenRouterProvider
from app.eval.schemas import (
    EvalComparison,
    EvalModelConfig,
    EvalModelResult,
    EvalModelsResponse,
    EvalRequest,
    ModelPreset,
)

logger = logging.getLogger(__name__)


def get_preset_models(preset: ModelPreset) -> list[EvalModelConfig]:
    """Get model configurations for a preset.

    Args:
        preset: The preset to expand

    Returns:
        List of model configurations
    """
    models: list[EvalModelConfig] = []

    if preset in (ModelPreset.VERIFIED, ModelPreset.ALL, ModelPreset.GOOGLE_NATIVE):
        # Add Google native models
        for model_id in VerifiedModels.GOOGLE_TEXT:
            models.append(EvalModelConfig(
                model_id=model_id,
                provider="google",
                label=f"Google {model_id}",
            ))

    if preset in (ModelPreset.VERIFIED, ModelPreset.ALL, ModelPreset.OPENROUTER):
        # Add OpenRouter models
        for model_id in VerifiedModels.OPENROUTER_TEXT:
            # Skip free models for more reliable comparison
            if ":free" not in model_id:
                models.append(EvalModelConfig(
                    model_id=model_id,
                    provider="openrouter",
                    label=f"OpenRouter {model_id.split('/')[-1]}",
                ))

    return models


def get_all_available_models() -> list[EvalModelConfig]:
    """Get all available models for evaluation.

    Returns:
        List of all model configurations
    """
    return get_preset_models(ModelPreset.ALL)


class ModelEvaluator:
    """Evaluates multiple models with the same prompt in parallel.

    Uses existing provider infrastructure and respects rate limiting.

    Attributes:
        google_provider: Google API provider instance
        openrouter_provider: OpenRouter API provider instance

    Examples:
        >>> evaluator = ModelEvaluator()
        >>> comparison = await evaluator.compare(
        ...     EvalRequest(query="Hello", preset=ModelPreset.VERIFIED)
        ... )
    """

    def __init__(self) -> None:
        """Initialize evaluator with providers."""
        settings = get_settings()

        self.google_provider: GoogleProvider | None = None
        self.openrouter_provider: OpenRouterProvider | None = None

        if settings.has_provider(ProviderType.GOOGLE):
            self.google_provider = GoogleProvider(api_key=settings.GOOGLE_API_KEY)
            logger.info("Initialized Google provider for eval")

        if settings.has_provider(ProviderType.OPENROUTER):
            self.openrouter_provider = OpenRouterProvider(api_key=settings.OPENROUTER_API_KEY)
            logger.info("Initialized OpenRouter provider for eval")

    def _get_provider(self, provider_name: str):
        """Get provider instance by name.

        Args:
            provider_name: "google" or "openrouter"

        Returns:
            Provider instance

        Raises:
            ValueError: If provider not configured
        """
        if provider_name == "google":
            if not self.google_provider:
                raise ValueError("Google provider not configured")
            return self.google_provider
        elif provider_name == "openrouter":
            if not self.openrouter_provider:
                raise ValueError("OpenRouter provider not configured")
            return self.openrouter_provider
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    async def run_single(
        self,
        model_config: EvalModelConfig,
        query: str,
        timeout_seconds: int = 120,
    ) -> EvalModelResult:
        """Run evaluation for a single model.

        Args:
            model_config: Model configuration
            query: The prompt to send
            timeout_seconds: Maximum time to wait

        Returns:
            EvalModelResult with timing and output
        """
        started_at = datetime.utcnow()
        start_time = time.time()

        try:
            provider = self._get_provider(model_config.provider)

            # Call the model with timeout
            response = await asyncio.wait_for(
                provider.call_text(query, model_config.model_id),
                timeout=timeout_seconds,
            )

            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            # Extract output
            output = response.content if response.content else ""
            output_length = len(output)
            output_preview = output[:200] + "..." if len(output) > 200 else output

            return EvalModelResult(
                model_id=model_config.model_id,
                provider=model_config.provider,
                label=model_config.label,
                success=True,
                latency_ms=latency_ms,
                output=output,
                output_length=output_length,
                output_preview=output_preview,
                error=None,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except asyncio.TimeoutError:
            return EvalModelResult(
                model_id=model_config.model_id,
                provider=model_config.provider,
                label=model_config.label,
                success=False,
                latency_ms=timeout_seconds * 1000,
                error=f"Timeout after {timeout_seconds}s",
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            return EvalModelResult(
                model_id=model_config.model_id,
                provider=model_config.provider,
                label=model_config.label,
                success=False,
                latency_ms=latency_ms,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    async def compare(self, request: EvalRequest) -> EvalComparison:
        """Run multi-model comparison.

        Executes all models in parallel and collects results.

        Args:
            request: Evaluation request with query and models/preset

        Returns:
            EvalComparison with all results and statistics
        """
        start_time = time.time()

        # Get models to test
        if request.models:
            models = request.models
        elif request.preset:
            models = get_preset_models(request.preset)
        else:
            models = get_preset_models(ModelPreset.VERIFIED)

        if not models:
            return EvalComparison(
                query=request.query,
                prompt_type=request.prompt_type,
                models_tested=0,
            )

        logger.info(f"Running eval comparison with {len(models)} models")

        # Run all models in parallel
        tasks = [
            self.run_single(model, request.query, request.timeout_seconds)
            for model in models
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results: list[EvalModelResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Create error result for exceptions
                model = models[i]
                processed_results.append(EvalModelResult(
                    model_id=model.model_id,
                    provider=model.provider,
                    label=model.label,
                    success=False,
                    error=str(result),
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                ))
            else:
                processed_results.append(result)

        end_time = time.time()
        total_duration_ms = int((end_time - start_time) * 1000)

        # Build comparison
        comparison = EvalComparison(
            query=request.query,
            prompt_type=request.prompt_type,
            total_duration_ms=total_duration_ms,
            results=processed_results,
        )
        comparison.compute_stats()

        logger.info(
            f"Eval complete: {comparison.success_count}/{comparison.models_tested} successful, "
            f"fastest={comparison.fastest_model}, "
            f"total_time={total_duration_ms}ms"
        )

        return comparison

    def get_available_models(self) -> EvalModelsResponse:
        """Get all available models for evaluation.

        Returns:
            Response with presets and model list
        """
        all_models = get_all_available_models()

        presets = {
            ModelPreset.VERIFIED.value: len(get_preset_models(ModelPreset.VERIFIED)),
            ModelPreset.GOOGLE_NATIVE.value: len(get_preset_models(ModelPreset.GOOGLE_NATIVE)),
            ModelPreset.OPENROUTER.value: len(get_preset_models(ModelPreset.OPENROUTER)),
            ModelPreset.ALL.value: len(all_models),
        }

        return EvalModelsResponse(presets=presets, models=all_models)

    async def close(self) -> None:
        """Close provider connections."""
        if self.google_provider and hasattr(self.google_provider, 'close'):
            await self.google_provider.close()
        if self.openrouter_provider and hasattr(self.openrouter_provider, 'close'):
            await self.openrouter_provider.close()


def format_comparison_report(comparison: EvalComparison) -> str:
    """Format comparison results as an ASCII report.

    Args:
        comparison: The comparison results

    Returns:
        Formatted string report
    """
    lines = []
    width = 70

    lines.append("=" * width)
    lines.append("MULTI-MODEL EVALUATION REPORT".center(width))
    lines.append("=" * width)
    lines.append("")
    lines.append(f"Query: {comparison.query[:60]}{'...' if len(comparison.query) > 60 else ''}")
    lines.append(f"Models Tested: {comparison.models_tested}")
    lines.append(f"Total Time: {comparison.total_duration_ms}ms")
    lines.append(f"Success Rate: {comparison.success_rate:.1f}%")
    lines.append("")
    lines.append("-" * width)
    lines.append("RESULTS (sorted by latency)".center(width))
    lines.append("-" * width)

    # Sort by latency (successful first, then failed)
    successful = sorted(
        [r for r in comparison.results if r.success],
        key=lambda r: r.latency_ms
    )
    failed = [r for r in comparison.results if not r.success]

    medals = ["1st", "2nd", "3rd"]

    for i, result in enumerate(successful):
        rank = medals[i] if i < len(medals) else f"{i+1}th"
        status = "OK"
        lines.append(f"  {rank:4} {result.label[:35]:35} {result.latency_ms:6}ms  [{status}]")
        if result.output_preview:
            preview = result.output_preview[:50].replace('\n', ' ')
            lines.append(f"       Output: {preview}...")

    for result in failed:
        status = "FAIL"
        lines.append(f"       {result.label[:35]:35} {'N/A':>6}   [{status}]")
        if result.error:
            lines.append(f"       Error: {result.error[:50]}")

    lines.append("")
    lines.append("-" * width)
    lines.append("STATISTICS".center(width))
    lines.append("-" * width)

    if comparison.latency_stats.min_ms > 0:
        lines.append(f"  Fastest: {comparison.fastest_model}")
        lines.append(f"  Slowest: {comparison.slowest_model}")
        lines.append(f"  Avg Latency: {comparison.latency_stats.avg_ms}ms")
        lines.append(f"  Latency Range: {comparison.latency_stats.min_ms}ms - {comparison.latency_stats.max_ms}ms")

        # Calculate speedup factor
        if comparison.latency_stats.avg_ms > 0:
            speedup = comparison.latency_stats.avg_ms / comparison.latency_stats.min_ms
            lines.append(f"  Fastest is {speedup:.1f}x faster than average")
    else:
        lines.append("  No successful results to analyze")

    lines.append("")
    lines.append("=" * width)

    return "\n".join(lines)
