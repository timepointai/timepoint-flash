"""Multi-model evaluation system for TIMEPOINT Flash.

This module provides tools to compare LLM model performance across
the same prompt/context, measuring latency, output quality, and success rates.

Features:
    - Parallel execution of multiple models on same prompt
    - Timing metrics (latency, time-to-completion)
    - Comparative analysis (fastest, slowest, avg latency)
    - Support for predefined model sets

Examples:
    >>> from app.eval import ModelEvaluator, EvalRequest
    >>> evaluator = ModelEvaluator()
    >>> request = EvalRequest(query="battle of thermopylae", preset="verified")
    >>> comparison = await evaluator.compare(request)
    >>> print(f"Fastest: {comparison.fastest_model}")

Tests:
    - tests/unit/test_eval.py
"""

from app.eval.schemas import (
    EvalModelConfig,
    EvalModelResult,
    EvalComparison,
    EvalRequest,
    ModelPreset,
)
from app.eval.runner import ModelEvaluator

__all__ = [
    "EvalModelConfig",
    "EvalModelResult",
    "EvalComparison",
    "EvalRequest",
    "ModelPreset",
    "ModelEvaluator",
]
