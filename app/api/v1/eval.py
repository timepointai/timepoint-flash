"""Multi-model evaluation API endpoints.

This module provides endpoints for comparing model performance.

Endpoints:
    POST /api/v1/eval/compare - Run multi-model comparison
    GET /api/v1/eval/models - List available models for evaluation

Examples:
    >>> # Compare models
    >>> curl -X POST http://localhost:8000/api/v1/eval/compare \
    ...     -H "Content-Type: application/json" \
    ...     -d '{"query": "moon landing 1969", "preset": "verified"}'

    >>> # List models
    >>> curl http://localhost:8000/api/v1/eval/models
"""

import logging

from fastapi import APIRouter, HTTPException

from app.eval import (
    EvalComparison,
    EvalRequest,
    ModelEvaluator,
)
from app.eval.runner import format_comparison_report
from app.eval.schemas import EvalModelsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eval", tags=["eval"])


@router.post(
    "/compare",
    response_model=EvalComparison,
    summary="Run multi-model comparison",
    description="Execute the same prompt across multiple models in parallel and compare results.",
)
async def compare_models(request: EvalRequest) -> EvalComparison:
    """Run multi-model comparison.

    Executes the provided query across all specified models (or preset)
    in parallel and returns comparative timing metrics.

    Args:
        request: Evaluation request with query and models/preset

    Returns:
        EvalComparison with results for all models and statistics

    Raises:
        HTTPException: If evaluation fails
    """
    logger.info(f"Starting model comparison: query='{request.query[:50]}...', preset={request.preset}")

    try:
        evaluator = ModelEvaluator()
        try:
            comparison = await evaluator.compare(request)
            return comparison
        finally:
            await evaluator.close()

    except Exception as e:
        logger.error(f"Eval comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/compare/report",
    response_model=dict,
    summary="Run comparison and get formatted report",
    description="Execute comparison and return both JSON data and formatted ASCII report.",
)
async def compare_models_with_report(request: EvalRequest) -> dict:
    """Run comparison and return formatted report.

    Args:
        request: Evaluation request

    Returns:
        Dictionary with 'comparison' (JSON) and 'report' (ASCII text)
    """
    logger.info(f"Starting model comparison with report: query='{request.query[:50]}...'")

    try:
        evaluator = ModelEvaluator()
        try:
            comparison = await evaluator.compare(request)
            report = format_comparison_report(comparison)
            return {
                "comparison": comparison.model_dump(),
                "report": report,
            }
        finally:
            await evaluator.close()

    except Exception as e:
        logger.error(f"Eval comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/models",
    response_model=EvalModelsResponse,
    summary="List available models for evaluation",
    description="Get all available models and presets for evaluation.",
)
async def list_eval_models() -> EvalModelsResponse:
    """List available models for evaluation.

    Returns:
        EvalModelsResponse with presets and model list
    """
    evaluator = ModelEvaluator()
    try:
        return evaluator.get_available_models()
    finally:
        await evaluator.close()
