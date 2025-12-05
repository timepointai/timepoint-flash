"""Unit tests for multi-model evaluation system.

Tests for app/eval/ module - ModelEvaluator, schemas, and report formatting.

Run with:
    pytest tests/unit/test_eval.py -v
    pytest tests/unit/test_eval.py -v -m fast
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.eval.schemas import (
    EvalComparison,
    EvalLatencyStats,
    EvalModelConfig,
    EvalModelResult,
    EvalModelsResponse,
    EvalRequest,
    ModelPreset,
)
from app.eval.runner import (
    ModelEvaluator,
    format_comparison_report,
    get_all_available_models,
    get_preset_models,
)


@pytest.mark.fast
class TestModelPreset:
    """Tests for ModelPreset enum."""

    def test_preset_values(self):
        """Test ModelPreset has expected values."""
        assert ModelPreset.VERIFIED.value == "verified"
        assert ModelPreset.GOOGLE_NATIVE.value == "google_native"
        assert ModelPreset.OPENROUTER.value == "openrouter"
        assert ModelPreset.ALL.value == "all"

    def test_preset_is_string_enum(self):
        """Test ModelPreset is a string enum."""
        assert isinstance(ModelPreset.VERIFIED.value, str)


@pytest.mark.fast
class TestEvalModelConfig:
    """Tests for EvalModelConfig schema."""

    def test_basic_config(self):
        """Test basic model config creation."""
        config = EvalModelConfig(
            model_id="gemini-2.0-flash",
            provider="google",
            label="Google Gemini 2.0 Flash",
        )
        assert config.model_id == "gemini-2.0-flash"
        assert config.provider == "google"
        assert config.label == "Google Gemini 2.0 Flash"

    def test_config_with_label(self):
        """Test model config requires label."""
        config = EvalModelConfig(
            model_id="test-model",
            provider="openrouter",
            label="Test Model Label",
        )
        assert config.model_id == "test-model"
        assert config.provider == "openrouter"
        assert config.label == "Test Model Label"


@pytest.mark.fast
class TestEvalRequest:
    """Tests for EvalRequest schema."""

    def test_basic_request(self):
        """Test basic request creation."""
        request = EvalRequest(query="battle of thermopylae")
        assert request.query == "battle of thermopylae"
        assert request.preset == ModelPreset.VERIFIED  # default
        assert request.timeout_seconds == 120  # default

    def test_request_with_preset(self):
        """Test request with custom preset."""
        request = EvalRequest(
            query="test query",
            preset=ModelPreset.GOOGLE_NATIVE,
        )
        assert request.preset == ModelPreset.GOOGLE_NATIVE

    def test_request_with_custom_models(self):
        """Test request with custom model list."""
        models = [
            EvalModelConfig(model_id="model1", provider="google", label="Model 1"),
            EvalModelConfig(model_id="model2", provider="openrouter", label="Model 2"),
        ]
        request = EvalRequest(
            query="test query",
            models=models,
        )
        assert len(request.models) == 2
        assert request.models[0].model_id == "model1"

    def test_request_with_timeout(self):
        """Test request with custom timeout."""
        request = EvalRequest(
            query="test query",
            timeout_seconds=60,
        )
        assert request.timeout_seconds == 60


@pytest.mark.fast
class TestEvalModelResult:
    """Tests for EvalModelResult schema."""

    def test_successful_result(self):
        """Test successful model result."""
        result = EvalModelResult(
            model_id="gemini-2.0-flash",
            provider="google",
            label="Google Gemini",
            success=True,
            latency_ms=1500,
            output="Test output text",
            output_length=16,
            output_preview="Test output text",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        assert result.success is True
        assert result.latency_ms == 1500
        assert result.output == "Test output text"
        assert result.error is None

    def test_failed_result(self):
        """Test failed model result."""
        result = EvalModelResult(
            model_id="gemini-2.0-flash",
            provider="google",
            label="Google Gemini",
            success=False,
            latency_ms=5000,
            error="Timeout after 5s",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        assert result.success is False
        assert result.error == "Timeout after 5s"
        assert result.output is None


@pytest.mark.fast
class TestEvalLatencyStats:
    """Tests for EvalLatencyStats schema."""

    def test_latency_stats(self):
        """Test latency statistics."""
        stats = EvalLatencyStats(
            min_ms=500,
            max_ms=3000,
            avg_ms=1500,
            median_ms=1200,
        )
        assert stats.min_ms == 500
        assert stats.max_ms == 3000
        assert stats.avg_ms == 1500
        assert stats.median_ms == 1200


@pytest.mark.fast
class TestEvalComparison:
    """Tests for EvalComparison schema."""

    def test_empty_comparison(self):
        """Test comparison with no results."""
        comparison = EvalComparison(
            query="test query",
            prompt_type="text",
            models_tested=0,
        )
        assert comparison.models_tested == 0
        assert comparison.results == []

    def test_comparison_with_results(self):
        """Test comparison with results."""
        results = [
            EvalModelResult(
                model_id="model1",
                provider="google",
                label="Model 1",
                success=True,
                latency_ms=1000,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            ),
            EvalModelResult(
                model_id="model2",
                provider="openrouter",
                label="Model 2",
                success=True,
                latency_ms=2000,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            ),
        ]
        comparison = EvalComparison(
            query="test query",
            prompt_type="text",
            total_duration_ms=2500,
            results=results,
        )
        comparison.compute_stats()

        assert comparison.models_tested == 2
        assert comparison.success_count == 2
        assert comparison.success_rate == 100.0
        # fastest_model and slowest_model use model_id
        assert comparison.fastest_model == "model1"
        assert comparison.slowest_model == "model2"
        assert comparison.latency_stats.min_ms == 1000
        assert comparison.latency_stats.max_ms == 2000

    def test_comparison_compute_stats(self):
        """Test compute_stats method."""
        results = [
            EvalModelResult(
                model_id="fast-model",
                provider="google",
                label="Fast Model",
                success=True,
                latency_ms=500,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            ),
            EvalModelResult(
                model_id="slow-model",
                provider="openrouter",
                label="Slow Model",
                success=True,
                latency_ms=1500,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            ),
            EvalModelResult(
                model_id="failed-model",
                provider="openrouter",
                label="Failed Model",
                success=False,
                latency_ms=0,
                error="Error",
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            ),
        ]
        comparison = EvalComparison(
            query="test",
            prompt_type="text",
            results=results,
        )
        comparison.compute_stats()

        assert comparison.models_tested == 3
        assert comparison.success_count == 2
        assert comparison.success_rate == pytest.approx(66.67, rel=0.01)
        # fastest_model and slowest_model use model_id
        assert comparison.fastest_model == "fast-model"
        assert comparison.slowest_model == "slow-model"
        assert comparison.latency_stats.avg_ms == 1000  # (500 + 1500) / 2


@pytest.mark.fast
class TestEvalModelsResponse:
    """Tests for EvalModelsResponse schema."""

    def test_response(self):
        """Test models response."""
        response = EvalModelsResponse(
            presets={"verified": 5, "all": 10},
            models=[
                EvalModelConfig(model_id="model1", provider="google", label="Model 1"),
            ],
        )
        assert response.presets["verified"] == 5
        assert len(response.models) == 1


@pytest.mark.fast
class TestGetPresetModels:
    """Tests for get_preset_models function."""

    def test_verified_preset(self):
        """Test verified preset returns models."""
        models = get_preset_models(ModelPreset.VERIFIED)
        assert len(models) > 0
        # Should include both Google and OpenRouter models
        providers = {m.provider for m in models}
        assert "google" in providers

    def test_google_native_preset(self):
        """Test google_native preset returns only Google models."""
        models = get_preset_models(ModelPreset.GOOGLE_NATIVE)
        assert len(models) > 0
        for model in models:
            assert model.provider == "google"

    def test_openrouter_preset(self):
        """Test openrouter preset returns only OpenRouter models."""
        models = get_preset_models(ModelPreset.OPENROUTER)
        # May be empty if no OpenRouter models configured
        for model in models:
            assert model.provider == "openrouter"

    def test_all_preset(self):
        """Test all preset returns all available models."""
        all_models = get_preset_models(ModelPreset.ALL)
        verified = get_preset_models(ModelPreset.VERIFIED)
        # ALL should have at least as many as VERIFIED
        assert len(all_models) >= len(verified)


@pytest.mark.fast
class TestGetAllAvailableModels:
    """Tests for get_all_available_models function."""

    def test_returns_list(self):
        """Test returns a list of model configs."""
        models = get_all_available_models()
        assert isinstance(models, list)
        for model in models:
            assert isinstance(model, EvalModelConfig)


@pytest.mark.fast
class TestFormatComparisonReport:
    """Tests for format_comparison_report function."""

    def test_empty_report(self):
        """Test report with no results."""
        comparison = EvalComparison(
            query="test query",
            prompt_type="text",
            models_tested=0,
        )
        report = format_comparison_report(comparison)
        assert "MULTI-MODEL EVALUATION REPORT" in report
        assert "test query" in report

    def test_report_with_results(self):
        """Test report with results."""
        results = [
            EvalModelResult(
                model_id="model1",
                provider="google",
                label="Fast Model",
                success=True,
                latency_ms=1000,
                output="Test output",
                output_preview="Test output",
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            ),
            EvalModelResult(
                model_id="model2",
                provider="openrouter",
                label="Slow Model",
                success=True,
                latency_ms=2000,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            ),
        ]
        comparison = EvalComparison(
            query="test query",
            prompt_type="text",
            total_duration_ms=2500,
            results=results,
        )
        comparison.compute_stats()

        report = format_comparison_report(comparison)

        assert "MULTI-MODEL EVALUATION REPORT" in report
        assert "Fast Model" in report
        assert "Slow Model" in report
        assert "1000ms" in report
        assert "2000ms" in report
        assert "1st" in report
        assert "2nd" in report
        assert "Success Rate: 100.0%" in report

    def test_report_with_failed_models(self):
        """Test report includes failed models."""
        results = [
            EvalModelResult(
                model_id="model1",
                provider="google",
                label="Working Model",
                success=True,
                latency_ms=1000,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            ),
            EvalModelResult(
                model_id="model2",
                provider="openrouter",
                label="Broken Model",
                success=False,
                latency_ms=0,
                error="Connection timeout",
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            ),
        ]
        comparison = EvalComparison(
            query="test query",
            prompt_type="text",
            results=results,
        )
        comparison.compute_stats()

        report = format_comparison_report(comparison)

        assert "FAIL" in report
        assert "Broken Model" in report
        assert "Connection timeout" in report


@pytest.mark.fast
class TestModelEvaluator:
    """Tests for ModelEvaluator class."""

    def test_evaluator_init_no_providers(self):
        """Test evaluator initializes without providers."""
        with patch("app.eval.runner.get_settings") as mock_settings:
            mock_settings.return_value.has_provider.return_value = False
            evaluator = ModelEvaluator()
            assert evaluator.google_provider is None
            assert evaluator.openrouter_provider is None

    def test_evaluator_get_provider_invalid(self):
        """Test get_provider raises for invalid provider."""
        with patch("app.eval.runner.get_settings") as mock_settings:
            mock_settings.return_value.has_provider.return_value = False
            evaluator = ModelEvaluator()

            with pytest.raises(ValueError, match="Unknown provider"):
                evaluator._get_provider("invalid")

    def test_evaluator_get_available_models(self):
        """Test get_available_models returns response."""
        with patch("app.eval.runner.get_settings") as mock_settings:
            mock_settings.return_value.has_provider.return_value = False
            evaluator = ModelEvaluator()
            response = evaluator.get_available_models()

            assert isinstance(response, EvalModelsResponse)
            assert "verified" in response.presets
            assert "all" in response.presets


@pytest.mark.fast
class TestModelEvaluatorAsync:
    """Async tests for ModelEvaluator."""

    @pytest.mark.asyncio
    async def test_run_single_timeout(self):
        """Test run_single handles timeout."""
        with patch("app.eval.runner.get_settings") as mock_settings:
            mock_settings.return_value.has_provider.return_value = False
            evaluator = ModelEvaluator()

            config = EvalModelConfig(
                model_id="test-model",
                provider="google",
                label="Test Model",
            )

            # Should fail because no provider is configured
            result = await evaluator.run_single(config, "test query", timeout_seconds=1)

            assert result.success is False
            assert result.error is not None
            assert "Google provider not configured" in result.error

    @pytest.mark.asyncio
    async def test_compare_falls_back_to_preset(self):
        """Test compare falls back to preset when models is empty."""
        with patch("app.eval.runner.get_settings") as mock_settings:
            mock_settings.return_value.has_provider.return_value = False
            evaluator = ModelEvaluator()

            # Empty list falls back to VERIFIED preset
            request = EvalRequest(
                query="test query",
                models=[],
            )
            comparison = await evaluator.compare(request)

            # Should have attempted to test models from VERIFIED preset
            # (all will fail without providers, but models were tested)
            assert comparison.models_tested > 0
            assert comparison.query == "test query"

    @pytest.mark.asyncio
    async def test_compare_uses_preset(self):
        """Test compare uses preset to get models."""
        with patch("app.eval.runner.get_settings") as mock_settings:
            mock_settings.return_value.has_provider.return_value = False
            evaluator = ModelEvaluator()

            request = EvalRequest(
                query="test query",
                preset=ModelPreset.VERIFIED,
            )
            comparison = await evaluator.compare(request)

            # Should have attempted to test models from preset
            # (will fail without providers, but structure should be correct)
            assert comparison.query == "test query"
            assert comparison.total_duration_ms >= 0

    @pytest.mark.asyncio
    async def test_evaluator_close(self):
        """Test close method is callable."""
        with patch("app.eval.runner.get_settings") as mock_settings:
            mock_settings.return_value.has_provider.return_value = False
            evaluator = ModelEvaluator()

            # Should not raise
            await evaluator.close()
