"""Tests for ModelTier classification and adaptive parallelism (Phase 12 & 14).

Tests for:
- ModelTier enum values
- is_free_model() function
- LLMRouter.get_model_tier() method
- LLMRouter.get_recommended_parallelism() method
- TIER_PARALLELISM configuration
- ParallelismMode enum (Phase 14)
- get_preset_parallelism() function (Phase 14)
- get_tier_max_concurrent() function (Phase 14)
- LLMRouter.get_provider_limit() method (Phase 14)
- LLMRouter.get_effective_max_concurrent() method (Phase 14)
- LLMRouter.get_parallelism_mode() method (Phase 14)
"""

import pytest
from unittest.mock import patch, MagicMock

from app.core.llm_router import (
    ModelTier,
    TIER_PARALLELISM,
    is_free_model,
    LLMRouter,
)
from app.config import (
    ParallelismMode,
    ProviderType,
    QualityPreset,
    PRESET_PARALLELISM,
    PROVIDER_RATE_LIMITS,
    TIER_CONCURRENT_LIMITS,
    get_preset_parallelism,
    get_tier_max_concurrent,
)


# ModelTier Tests


@pytest.mark.fast
class TestModelTier:
    """Tests for ModelTier enum."""

    def test_tier_values(self):
        """Test that all tier values are correct."""
        assert ModelTier.FREE.value == "free"
        assert ModelTier.PAID.value == "paid"
        assert ModelTier.NATIVE.value == "native"

    def test_tier_is_string_enum(self):
        """Test that ModelTier is a string enum."""
        assert str(ModelTier.FREE) == "ModelTier.FREE"
        assert ModelTier.FREE == "free"

    def test_all_tiers_have_parallelism(self):
        """Test that all tiers have parallelism settings."""
        for tier in ModelTier:
            assert tier in TIER_PARALLELISM
            assert isinstance(TIER_PARALLELISM[tier], int)
            assert TIER_PARALLELISM[tier] >= 1


# TIER_PARALLELISM Tests


@pytest.mark.fast
class TestTierParallelism:
    """Tests for TIER_PARALLELISM configuration."""

    def test_free_tier_sequential(self):
        """Test that FREE tier has parallelism=1 (sequential)."""
        assert TIER_PARALLELISM[ModelTier.FREE] == 1

    def test_paid_tier_moderate(self):
        """Test that PAID tier has moderate parallelism."""
        assert TIER_PARALLELISM[ModelTier.PAID] == 2

    def test_native_tier_high(self):
        """Test that NATIVE tier has higher parallelism."""
        assert TIER_PARALLELISM[ModelTier.NATIVE] == 3

    def test_parallelism_ordering(self):
        """Test that parallelism increases from FREE to NATIVE."""
        assert TIER_PARALLELISM[ModelTier.FREE] < TIER_PARALLELISM[ModelTier.PAID]
        assert TIER_PARALLELISM[ModelTier.PAID] <= TIER_PARALLELISM[ModelTier.NATIVE]


# is_free_model Tests


@pytest.mark.fast
class TestIsFreeModel:
    """Tests for is_free_model() function."""

    def test_free_suffix_lowercase(self):
        """Test detection of :free suffix."""
        assert is_free_model("google/gemini-2.0-flash-001:free") is True

    def test_free_suffix_mixed_case(self):
        """Test detection of :FREE suffix (case insensitive)."""
        assert is_free_model("google/gemini-2.0-flash-001:FREE") is True

    def test_free_path_lowercase(self):
        """Test detection of /free in path."""
        assert is_free_model("meta-llama/llama-3.2-3b/free") is True

    def test_paid_model(self):
        """Test paid model is not detected as free."""
        assert is_free_model("google/gemini-2.0-flash-001") is False

    def test_native_model(self):
        """Test native Google model is not detected as free."""
        assert is_free_model("gemini-3-pro-preview") is False

    def test_empty_string(self):
        """Test empty string returns False."""
        assert is_free_model("") is False

    def test_none_handling(self):
        """Test None handling."""
        assert is_free_model(None) is False


# LLMRouter.get_model_tier Tests


@pytest.mark.fast
class TestRouterGetModelTier:
    """Tests for LLMRouter.get_model_tier() method."""

    @patch("app.core.llm_router.get_settings")
    def test_free_model_tier(self, mock_settings):
        """Test that free model returns FREE tier."""
        mock_settings.return_value = MagicMock(
            GOOGLE_API_KEY=None,
            OPENROUTER_API_KEY="test-key",
            PRIMARY_PROVIDER=ProviderType.OPENROUTER,
            FALLBACK_PROVIDER=None,
            CREATIVE_MODEL="google/gemini-2.0-flash-001:free",
            JUDGE_MODEL="google/gemini-2.0-flash-001:free",
            IMAGE_MODEL="gemini-2.5-flash-image",
            has_provider=lambda x: x == ProviderType.OPENROUTER,
        )
        router = LLMRouter(text_model="google/gemini-2.0-flash-001:free")
        tier = router.get_model_tier()
        assert tier == ModelTier.FREE

    @patch("app.core.llm_router.get_settings")
    def test_paid_openrouter_tier(self, mock_settings):
        """Test that paid OpenRouter model returns PAID tier."""
        mock_settings.return_value = MagicMock(
            GOOGLE_API_KEY=None,
            OPENROUTER_API_KEY="test-key",
            PRIMARY_PROVIDER=ProviderType.OPENROUTER,
            FALLBACK_PROVIDER=None,
            CREATIVE_MODEL="google/gemini-2.0-flash-001",
            JUDGE_MODEL="google/gemini-2.0-flash-001",
            IMAGE_MODEL="gemini-2.5-flash-image",
            has_provider=lambda x: x == ProviderType.OPENROUTER,
        )
        router = LLMRouter(text_model="google/gemini-2.0-flash-001")
        tier = router.get_model_tier()
        assert tier == ModelTier.PAID

    @patch("app.core.llm_router.get_settings")
    def test_native_google_tier(self, mock_settings):
        """Test that native Google model returns NATIVE tier."""
        mock_settings.return_value = MagicMock(
            GOOGLE_API_KEY="test-key",
            OPENROUTER_API_KEY=None,
            PRIMARY_PROVIDER=ProviderType.GOOGLE,
            FALLBACK_PROVIDER=None,
            CREATIVE_MODEL="gemini-3-pro-preview",
            JUDGE_MODEL="gemini-2.5-flash",
            IMAGE_MODEL="gemini-2.5-flash-image",
            has_provider=lambda x: x == ProviderType.GOOGLE,
        )
        router = LLMRouter()
        tier = router.get_model_tier()
        assert tier == ModelTier.NATIVE


# LLMRouter.get_recommended_parallelism Tests


@pytest.mark.fast
class TestRouterGetRecommendedParallelism:
    """Tests for LLMRouter.get_recommended_parallelism() method."""

    @patch("app.core.llm_router.get_settings")
    def test_free_tier_parallelism(self, mock_settings):
        """Test that free tier recommends parallelism=1."""
        mock_settings.return_value = MagicMock(
            GOOGLE_API_KEY=None,
            OPENROUTER_API_KEY="test-key",
            PRIMARY_PROVIDER=ProviderType.OPENROUTER,
            FALLBACK_PROVIDER=None,
            CREATIVE_MODEL="google/gemini-2.0-flash-001:free",
            JUDGE_MODEL="google/gemini-2.0-flash-001:free",
            IMAGE_MODEL="gemini-2.5-flash-image",
            has_provider=lambda x: x == ProviderType.OPENROUTER,
        )
        router = LLMRouter(text_model="google/gemini-2.0-flash-001:free")
        parallelism = router.get_recommended_parallelism()
        assert parallelism == 1

    @patch("app.core.llm_router.get_settings")
    def test_native_tier_parallelism(self, mock_settings):
        """Test that native tier recommends parallelism=3."""
        mock_settings.return_value = MagicMock(
            GOOGLE_API_KEY="test-key",
            OPENROUTER_API_KEY=None,
            PRIMARY_PROVIDER=ProviderType.GOOGLE,
            FALLBACK_PROVIDER=None,
            CREATIVE_MODEL="gemini-3-pro-preview",
            JUDGE_MODEL="gemini-2.5-flash",
            IMAGE_MODEL="gemini-2.5-flash-image",
            has_provider=lambda x: x == ProviderType.GOOGLE,
        )
        router = LLMRouter()
        parallelism = router.get_recommended_parallelism()
        assert parallelism == 3


# =============================================================================
# Phase 14: Hyper Parallelism Mode Tests
# =============================================================================


# ParallelismMode Tests


@pytest.mark.fast
class TestParallelismMode:
    """Tests for ParallelismMode enum (Phase 14)."""

    def test_mode_values(self):
        """Test that all mode values are correct."""
        assert ParallelismMode.SEQUENTIAL.value == "sequential"
        assert ParallelismMode.NORMAL.value == "normal"
        assert ParallelismMode.AGGRESSIVE.value == "aggressive"
        assert ParallelismMode.MAX.value == "max"

    def test_mode_is_string_enum(self):
        """Test that ParallelismMode is a string enum."""
        assert ParallelismMode.SEQUENTIAL == "sequential"
        assert ParallelismMode.MAX == "max"


# PRESET_PARALLELISM Tests


@pytest.mark.fast
class TestPresetParallelism:
    """Tests for PRESET_PARALLELISM configuration (Phase 14)."""

    def test_hd_preset_normal_mode(self):
        """Test that HD preset uses NORMAL parallelism."""
        assert PRESET_PARALLELISM[QualityPreset.HD] == ParallelismMode.NORMAL

    def test_balanced_preset_normal_mode(self):
        """Test that BALANCED preset uses NORMAL parallelism."""
        assert PRESET_PARALLELISM[QualityPreset.BALANCED] == ParallelismMode.NORMAL

    def test_hyper_preset_max_mode(self):
        """Test that HYPER preset uses MAX parallelism."""
        assert PRESET_PARALLELISM[QualityPreset.HYPER] == ParallelismMode.MAX

    def test_all_presets_have_parallelism(self):
        """Test that all presets have parallelism settings."""
        for preset in QualityPreset:
            assert preset in PRESET_PARALLELISM
            assert isinstance(PRESET_PARALLELISM[preset], ParallelismMode)


# PROVIDER_RATE_LIMITS Tests


@pytest.mark.fast
class TestProviderRateLimits:
    """Tests for PROVIDER_RATE_LIMITS configuration (Phase 14)."""

    def test_google_limits(self):
        """Test Google provider limits."""
        limits = PROVIDER_RATE_LIMITS[ProviderType.GOOGLE]
        assert limits["rpm"] == 60
        assert limits["max_concurrent"] == 8

    def test_openrouter_limits(self):
        """Test OpenRouter provider limits."""
        limits = PROVIDER_RATE_LIMITS[ProviderType.OPENROUTER]
        assert limits["rpm"] == 30
        assert limits["max_concurrent"] == 5

    def test_google_higher_than_openrouter(self):
        """Test that Google has higher limits than OpenRouter."""
        google = PROVIDER_RATE_LIMITS[ProviderType.GOOGLE]
        openrouter = PROVIDER_RATE_LIMITS[ProviderType.OPENROUTER]
        assert google["max_concurrent"] > openrouter["max_concurrent"]


# TIER_CONCURRENT_LIMITS Tests


@pytest.mark.fast
class TestTierConcurrentLimits:
    """Tests for TIER_CONCURRENT_LIMITS configuration (Phase 14)."""

    def test_free_tier_limits(self):
        """Test FREE tier concurrent limits."""
        limits = TIER_CONCURRENT_LIMITS["free"]
        assert limits["sequential"] == 1
        assert limits["normal"] == 1
        assert limits["aggressive"] == 2
        assert limits["max"] == 2

    def test_paid_tier_limits(self):
        """Test PAID tier concurrent limits."""
        limits = TIER_CONCURRENT_LIMITS["paid"]
        assert limits["sequential"] == 1
        assert limits["normal"] == 3
        assert limits["aggressive"] == 5
        assert limits["max"] == 6

    def test_native_tier_limits(self):
        """Test NATIVE tier concurrent limits."""
        limits = TIER_CONCURRENT_LIMITS["native"]
        assert limits["sequential"] == 1
        assert limits["normal"] == 3
        assert limits["aggressive"] == 5
        assert limits["max"] == 8

    def test_sequential_always_one(self):
        """Test that sequential mode is always 1 for all tiers."""
        for tier in ["free", "paid", "native"]:
            assert TIER_CONCURRENT_LIMITS[tier]["sequential"] == 1

    def test_max_mode_highest(self):
        """Test that MAX mode has highest parallelism for each tier."""
        for tier in ["free", "paid", "native"]:
            limits = TIER_CONCURRENT_LIMITS[tier]
            assert limits["max"] >= limits["aggressive"]
            assert limits["aggressive"] >= limits["normal"]
            assert limits["normal"] >= limits["sequential"]


# get_preset_parallelism Tests


@pytest.mark.fast
class TestGetPresetParallelism:
    """Tests for get_preset_parallelism() function (Phase 14)."""

    def test_hyper_returns_max(self):
        """Test that HYPER preset returns MAX mode."""
        mode = get_preset_parallelism(QualityPreset.HYPER)
        assert mode == ParallelismMode.MAX

    def test_balanced_returns_normal(self):
        """Test that BALANCED preset returns NORMAL mode."""
        mode = get_preset_parallelism(QualityPreset.BALANCED)
        assert mode == ParallelismMode.NORMAL

    def test_hd_returns_normal(self):
        """Test that HD preset returns NORMAL mode."""
        mode = get_preset_parallelism(QualityPreset.HD)
        assert mode == ParallelismMode.NORMAL


# get_tier_max_concurrent Tests


@pytest.mark.fast
class TestGetTierMaxConcurrent:
    """Tests for get_tier_max_concurrent() function (Phase 14)."""

    def test_free_sequential(self):
        """Test FREE tier with SEQUENTIAL mode."""
        result = get_tier_max_concurrent("free", ParallelismMode.SEQUENTIAL)
        assert result == 1

    def test_free_max(self):
        """Test FREE tier with MAX mode."""
        result = get_tier_max_concurrent("free", ParallelismMode.MAX)
        assert result == 2

    def test_native_max(self):
        """Test NATIVE tier with MAX mode."""
        result = get_tier_max_concurrent("native", ParallelismMode.MAX)
        assert result == 8

    def test_paid_aggressive(self):
        """Test PAID tier with AGGRESSIVE mode."""
        result = get_tier_max_concurrent("paid", ParallelismMode.AGGRESSIVE)
        assert result == 5

    def test_unknown_tier_defaults_to_paid(self):
        """Test that unknown tier defaults to paid limits."""
        result = get_tier_max_concurrent("unknown", ParallelismMode.NORMAL)
        expected = TIER_CONCURRENT_LIMITS["paid"]["normal"]
        assert result == expected


# LLMRouter.get_provider_limit Tests


@pytest.mark.fast
class TestRouterGetProviderLimit:
    """Tests for LLMRouter.get_provider_limit() method (Phase 14)."""

    @patch("app.core.llm_router.get_settings")
    def test_google_provider_limit(self, mock_settings):
        """Test that Google provider returns limit of 8."""
        mock_settings.return_value = MagicMock(
            GOOGLE_API_KEY="test-key",
            OPENROUTER_API_KEY=None,
            PRIMARY_PROVIDER=ProviderType.GOOGLE,
            FALLBACK_PROVIDER=None,
            CREATIVE_MODEL="gemini-3-pro-preview",
            JUDGE_MODEL="gemini-2.5-flash",
            IMAGE_MODEL="gemini-2.5-flash-image",
            has_provider=lambda x: x == ProviderType.GOOGLE,
        )
        router = LLMRouter()
        limit = router.get_provider_limit()
        assert limit == 8

    @patch("app.core.llm_router.get_settings")
    def test_openrouter_provider_limit(self, mock_settings):
        """Test that OpenRouter provider returns limit of 5."""
        mock_settings.return_value = MagicMock(
            GOOGLE_API_KEY=None,
            OPENROUTER_API_KEY="test-key",
            PRIMARY_PROVIDER=ProviderType.OPENROUTER,
            FALLBACK_PROVIDER=None,
            CREATIVE_MODEL="google/gemini-2.0-flash-001",
            JUDGE_MODEL="google/gemini-2.0-flash-001",
            IMAGE_MODEL="gemini-2.5-flash-image",
            has_provider=lambda x: x == ProviderType.OPENROUTER,
        )
        router = LLMRouter(text_model="google/gemini-2.0-flash-001")
        limit = router.get_provider_limit()
        assert limit == 5


# LLMRouter.get_effective_max_concurrent Tests


@pytest.mark.fast
class TestRouterGetEffectiveMaxConcurrent:
    """Tests for LLMRouter.get_effective_max_concurrent() method (Phase 14)."""

    @patch("app.core.llm_router.get_settings")
    def test_native_normal_mode(self, mock_settings):
        """Test NATIVE tier with NORMAL mode (default)."""
        mock_settings.return_value = MagicMock(
            GOOGLE_API_KEY="test-key",
            OPENROUTER_API_KEY=None,
            PRIMARY_PROVIDER=ProviderType.GOOGLE,
            FALLBACK_PROVIDER=None,
            CREATIVE_MODEL="gemini-3-pro-preview",
            JUDGE_MODEL="gemini-2.5-flash",
            IMAGE_MODEL="gemini-2.5-flash-image",
            has_provider=lambda x: x == ProviderType.GOOGLE,
        )
        router = LLMRouter()
        # NATIVE tier + NORMAL mode = 3 (from TIER_CONCURRENT_LIMITS)
        result = router.get_effective_max_concurrent(ParallelismMode.NORMAL)
        assert result == 3

    @patch("app.core.llm_router.get_settings")
    def test_native_max_mode_with_headroom(self, mock_settings):
        """Test NATIVE tier with MAX mode (provider limit - 1)."""
        mock_settings.return_value = MagicMock(
            GOOGLE_API_KEY="test-key",
            OPENROUTER_API_KEY=None,
            PRIMARY_PROVIDER=ProviderType.GOOGLE,
            FALLBACK_PROVIDER=None,
            CREATIVE_MODEL="gemini-3-pro-preview",
            JUDGE_MODEL="gemini-2.5-flash",
            IMAGE_MODEL="gemini-2.5-flash-image",
            has_provider=lambda x: x == ProviderType.GOOGLE,
        )
        router = LLMRouter()
        # NATIVE tier + MAX mode = min(8, 8-1) = 7
        result = router.get_effective_max_concurrent(ParallelismMode.MAX)
        assert result == 7

    @patch("app.core.llm_router.get_settings")
    def test_free_max_mode_capped(self, mock_settings):
        """Test FREE tier with MAX mode is capped at tier limit."""
        mock_settings.return_value = MagicMock(
            GOOGLE_API_KEY=None,
            OPENROUTER_API_KEY="test-key",
            PRIMARY_PROVIDER=ProviderType.OPENROUTER,
            FALLBACK_PROVIDER=None,
            CREATIVE_MODEL="google/gemini-2.0-flash-001:free",
            JUDGE_MODEL="google/gemini-2.0-flash-001:free",
            IMAGE_MODEL="gemini-2.5-flash-image",
            has_provider=lambda x: x == ProviderType.OPENROUTER,
        )
        router = LLMRouter(text_model="google/gemini-2.0-flash-001:free")
        # FREE tier + MAX mode = min(2, 5-1) = 2 (tier limit)
        result = router.get_effective_max_concurrent(ParallelismMode.MAX)
        assert result == 2

    @patch("app.core.llm_router.get_settings")
    def test_hyper_preset_uses_max_mode(self, mock_settings):
        """Test HYPER preset uses MAX mode automatically."""
        mock_settings.return_value = MagicMock(
            GOOGLE_API_KEY="test-key",
            OPENROUTER_API_KEY="test-key",
            PRIMARY_PROVIDER=ProviderType.OPENROUTER,  # HYPER uses OpenRouter
            FALLBACK_PROVIDER=ProviderType.GOOGLE,
            CREATIVE_MODEL="google/gemini-2.0-flash-001",
            JUDGE_MODEL="google/gemini-2.0-flash-001",
            IMAGE_MODEL="gemini-2.5-flash-image",
            has_provider=lambda x: True,
        )
        router = LLMRouter(preset=QualityPreset.HYPER)
        # Uses preset's default mode (MAX for HYPER)
        result = router.get_effective_max_concurrent()
        # PAID tier + MAX mode = min(6, 5-1) = 4 (OpenRouter limit)
        assert result == 4


# LLMRouter.get_parallelism_mode Tests


@pytest.mark.fast
class TestRouterGetParallelismMode:
    """Tests for LLMRouter.get_parallelism_mode() method (Phase 14)."""

    @patch("app.core.llm_router.get_settings")
    def test_no_preset_returns_normal(self, mock_settings):
        """Test that no preset returns NORMAL mode."""
        mock_settings.return_value = MagicMock(
            GOOGLE_API_KEY="test-key",
            OPENROUTER_API_KEY=None,
            PRIMARY_PROVIDER=ProviderType.GOOGLE,
            FALLBACK_PROVIDER=None,
            CREATIVE_MODEL="gemini-3-pro-preview",
            JUDGE_MODEL="gemini-2.5-flash",
            IMAGE_MODEL="gemini-2.5-flash-image",
            has_provider=lambda x: x == ProviderType.GOOGLE,
        )
        router = LLMRouter()
        mode = router.get_parallelism_mode()
        assert mode == ParallelismMode.NORMAL

    @patch("app.core.llm_router.get_settings")
    def test_hyper_preset_returns_max(self, mock_settings):
        """Test that HYPER preset returns MAX mode."""
        mock_settings.return_value = MagicMock(
            GOOGLE_API_KEY="test-key",
            OPENROUTER_API_KEY="test-key",
            PRIMARY_PROVIDER=ProviderType.OPENROUTER,
            FALLBACK_PROVIDER=ProviderType.GOOGLE,
            CREATIVE_MODEL="google/gemini-2.0-flash-001",
            JUDGE_MODEL="google/gemini-2.0-flash-001",
            IMAGE_MODEL="gemini-2.5-flash-image",
            has_provider=lambda x: True,
        )
        router = LLMRouter(preset=QualityPreset.HYPER)
        mode = router.get_parallelism_mode()
        assert mode == ParallelismMode.MAX

    @patch("app.core.llm_router.get_settings")
    def test_balanced_preset_returns_normal(self, mock_settings):
        """Test that BALANCED preset returns NORMAL mode."""
        mock_settings.return_value = MagicMock(
            GOOGLE_API_KEY="test-key",
            OPENROUTER_API_KEY=None,
            PRIMARY_PROVIDER=ProviderType.GOOGLE,
            FALLBACK_PROVIDER=None,
            CREATIVE_MODEL="gemini-3-pro-preview",
            JUDGE_MODEL="gemini-2.5-flash",
            IMAGE_MODEL="gemini-2.5-flash-image",
            has_provider=lambda x: x == ProviderType.GOOGLE,
        )
        router = LLMRouter(preset=QualityPreset.BALANCED)
        mode = router.get_parallelism_mode()
        assert mode == ParallelismMode.NORMAL
