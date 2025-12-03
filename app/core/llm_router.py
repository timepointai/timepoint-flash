"""LLM Router with Mirascope integration and provider fallback.

This module provides unified LLM routing with automatic provider selection,
fallback handling, and Mirascope integration for structured outputs.

Features:
    - Automatic provider selection based on capability
    - Graceful fallback for free model rate limits
    - Retry with exponential backoff for transient errors
    - Model cascade: free model -> paid model -> different provider
    - Model tier classification for adaptive parallelism

Examples:
    >>> from app.core.llm_router import LLMRouter, ModelTier
    >>> router = LLMRouter()
    >>> tier = router.get_model_tier()
    >>> print(tier)  # ModelTier.NATIVE, ModelTier.PAID, or ModelTier.FREE
    >>> response = await router.call(
    ...     prompt="Explain quantum computing",
    ...     capability=ModelCapability.TEXT
    ... )

Tests:
    - tests/unit/test_llm_router.py::test_router_initialization
    - tests/unit/test_llm_router.py::test_router_provider_selection
    - tests/integration/test_llm_router.py::test_router_fallback
"""

import asyncio
import logging
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel

from app.config import (
    PRESET_CONFIGS,
    PRESET_PARALLELISM,
    PROVIDER_RATE_LIMITS,
    ParallelismMode,
    ProviderType,
    QualityPreset,
    get_preset_parallelism,
    get_settings,
    get_tier_max_concurrent,
)
from app.core.rate_limiter import acquire_rate_limit, get_tier_from_model
from app.core.providers import (
    LLMProvider,
    LLMResponse,
    ModelCapability,
    ProviderConfig,
    ProviderError,
    RateLimitError,
)
from app.core.providers.google import GoogleProvider
from app.core.providers.openrouter import OpenRouterProvider

logger = logging.getLogger(__name__)

# Type variable for structured response models
T = TypeVar("T", bound=BaseModel)

# Default fallback model for when free models hit rate limits
PAID_FALLBACK_MODEL = "google/gemini-2.0-flash-001"

# Rate limit retry settings
MAX_RETRIES = 5
INITIAL_BACKOFF = 2.0  # seconds
MAX_BACKOFF = 120.0  # seconds (2 minutes)
BACKOFF_MULTIPLIER = 2.0


class ModelTier(str, Enum):
    """Model tier classification for adaptive parallelism.

    Determines execution strategy based on model type:
    - FREE: Rate-limited free models (e.g., :free suffix) - sequential execution
    - PAID: Paid API models (OpenRouter paid) - moderate parallelism
    - NATIVE: Native Google API - high parallelism

    Attributes:
        parallelism: Recommended max parallel calls for this tier
    """

    FREE = "free"       # :free models - parallelism=1 (sequential)
    PAID = "paid"       # OpenRouter paid - parallelism=2-3
    NATIVE = "native"   # Google native - parallelism=3-5


# Parallelism settings per tier (used by pipeline)
TIER_PARALLELISM = {
    ModelTier.FREE: 1,    # Sequential to avoid rate limits
    ModelTier.PAID: 2,    # Moderate parallelism
    ModelTier.NATIVE: 3,  # Higher parallelism for native API
}


def is_free_model(model_id: str) -> bool:
    """Check if a model is a free tier model on OpenRouter.

    Args:
        model_id: The model identifier

    Returns:
        True if the model appears to be a free tier model
    """
    if not model_id:
        return False
    model_lower = model_id.lower()
    return ":free" in model_lower or "/free" in model_lower


class LLMRouter:
    """Route LLM calls with provider selection and fallback.

    Provides a unified interface for LLM calls across providers.
    Handles automatic fallback when primary provider fails.

    Attributes:
        config: Provider configuration
        providers: Dictionary of initialized providers
        preset: Quality preset for model selection

    Features:
        - Automatic provider selection based on capability
        - Fallback to secondary provider on failure
        - Retry with exponential backoff for transient errors
        - Graceful degradation from free to paid models on rate limits
        - Mirascope-style structured outputs via Pydantic models
        - Quality presets (HD, HYPER, BALANCED) for different use cases

    Examples:
        >>> router = LLMRouter()
        >>> response = await router.call(
        ...     prompt="Hello",
        ...     capability=ModelCapability.TEXT
        ... )

        >>> # With preset for fast generation
        >>> router = LLMRouter(preset=QualityPreset.HYPER)

        >>> # With structured output
        >>> class MyResponse(BaseModel):
        ...     answer: str
        >>> response = await router.call_structured(
        ...     prompt="What is 2+2?",
        ...     response_model=MyResponse,
        ...     capability=ModelCapability.TEXT
        ... )
    """

    def __init__(
        self,
        config: ProviderConfig | None = None,
        preset: QualityPreset | None = None,
        text_model: str | None = None,
        image_model: str | None = None,
    ) -> None:
        """Initialize LLM router.

        Args:
            config: Provider configuration. If not provided, uses settings.
            preset: Quality preset (HD, HYPER, BALANCED). Overrides config models.
            text_model: Custom text model override (overrides preset).
            image_model: Custom image model override (overrides preset).
        """
        settings = get_settings()
        self.preset = preset
        self._preset_config = PRESET_CONFIGS.get(preset) if preset else None
        self._custom_text_model = text_model
        self._custom_image_model = image_model

        # Build config from settings if not provided
        if config is None:
            # Start with preset or default models
            if self._preset_config:
                effective_text_model = self._preset_config["text_model"]
                judge_model = self._preset_config["judge_model"]
                effective_image_model = self._preset_config["image_model"]
                primary = self._preset_config.get("text_provider", settings.PRIMARY_PROVIDER)
            else:
                effective_text_model = settings.CREATIVE_MODEL
                judge_model = settings.JUDGE_MODEL
                effective_image_model = settings.IMAGE_MODEL
                primary = settings.PRIMARY_PROVIDER

            # Apply custom model overrides (highest priority)
            if text_model:
                effective_text_model = text_model
                logger.info(f"Using custom text model: {text_model}")
                # If custom model looks like OpenRouter model, adjust primary provider
                if "/" in text_model and not text_model.startswith("gemini"):
                    primary = ProviderType.OPENROUTER
            if image_model:
                effective_image_model = image_model
                logger.info(f"Using custom image model: {image_model}")

            config = ProviderConfig(
                primary=primary,
                fallback=settings.FALLBACK_PROVIDER,
                capabilities={
                    ModelCapability.TEXT: effective_text_model,
                    ModelCapability.CODE: effective_text_model,
                    ModelCapability.VISION: judge_model,
                    ModelCapability.IMAGE: effective_image_model,
                },
            )

        self.config = config
        self.providers: dict[ProviderType, LLMProvider] = {}

        # Initialize providers
        self._init_providers(settings)

    def _init_providers(self, settings: Any) -> None:
        """Initialize available providers.

        Args:
            settings: Application settings with API keys.
        """
        if settings.has_provider(ProviderType.GOOGLE):
            self.providers[ProviderType.GOOGLE] = GoogleProvider(
                api_key=settings.GOOGLE_API_KEY
            )
            logger.info("Initialized Google provider")

        if settings.has_provider(ProviderType.OPENROUTER):
            self.providers[ProviderType.OPENROUTER] = OpenRouterProvider(
                api_key=settings.OPENROUTER_API_KEY
            )
            logger.info("Initialized OpenRouter provider")

    def _get_provider(self, provider_type: ProviderType) -> LLMProvider:
        """Get provider instance by type.

        Args:
            provider_type: The provider type.

        Returns:
            LLMProvider instance.

        Raises:
            ValueError: If provider is not configured.
        """
        if provider_type not in self.providers:
            raise ValueError(
                f"Provider {provider_type.value} not configured. "
                f"Available: {list(self.providers.keys())}"
            )
        return self.providers[provider_type]

    def _get_model_for_capability(
        self,
        capability: ModelCapability,
        provider: ProviderType,
    ) -> str:
        """Get model ID for a capability and provider.

        Args:
            capability: The model capability needed.
            provider: The target provider.

        Returns:
            Model ID string.
        """
        model = self.config.get_model(capability)

        # Map Google models to OpenRouter equivalents if needed
        if provider == ProviderType.OPENROUTER:
            google_to_openrouter = {
                "gemini-3-pro-preview": "google/gemini-2.0-flash-001",
                "gemini-2.5-flash": "google/gemini-2.0-flash-001",
                "gemini-2.5-pro": "google/gemini-2.0-flash-001",
                # Image models use native Google, no OpenRouter mapping needed
            }
            model = google_to_openrouter.get(model, model)
        elif provider == ProviderType.GOOGLE:
            # Strip OpenRouter-style prefixes for native Google provider
            # e.g., "google/gemini-2.5-flash-image" -> "gemini-2.5-flash-image"
            if model.startswith("google/"):
                model = model[len("google/"):]
                logger.debug(f"Stripped google/ prefix for native Google: {model}")

        return model

    def get_model_tier(self) -> ModelTier:
        """Determine the model tier for adaptive parallelism.

        Classifies the current model configuration into tiers:
        - FREE: OpenRouter models with :free suffix (rate limited)
        - PAID: OpenRouter paid models (moderate rate limits)
        - NATIVE: Google native API (highest throughput)

        Returns:
            ModelTier indicating the execution tier

        Examples:
            >>> router = LLMRouter(text_model="google/gemini-2.0-flash-001:free")
            >>> router.get_model_tier()
            ModelTier.FREE

            >>> router = LLMRouter()  # Default Google native
            >>> router.get_model_tier()
            ModelTier.NATIVE
        """
        # Check the text model being used
        text_model = self.config.get_model(ModelCapability.TEXT)

        # Check for free model indicators
        if is_free_model(text_model):
            logger.debug(f"Model tier: FREE (model={text_model})")
            return ModelTier.FREE

        # Check provider type
        if self.config.primary == ProviderType.GOOGLE:
            logger.debug(f"Model tier: NATIVE (provider=Google, model={text_model})")
            return ModelTier.NATIVE

        # OpenRouter without :free suffix is PAID
        if self.config.primary == ProviderType.OPENROUTER:
            logger.debug(f"Model tier: PAID (provider=OpenRouter, model={text_model})")
            return ModelTier.PAID

        # Default to PAID for unknown configurations
        logger.debug(f"Model tier: PAID (default, model={text_model})")
        return ModelTier.PAID

    def get_recommended_parallelism(self) -> int:
        """Get recommended parallelism for current model tier.

        Returns the optimal number of concurrent LLM calls based on
        the model's tier classification.

        Returns:
            int: Recommended max parallel calls (1-5)

        Examples:
            >>> router = LLMRouter(text_model="google/gemini-2.0-flash-001:free")
            >>> router.get_recommended_parallelism()
            1  # Sequential for free models

            >>> router = LLMRouter()  # Google native
            >>> router.get_recommended_parallelism()
            3  # Higher parallelism for native
        """
        tier = self.get_model_tier()
        return TIER_PARALLELISM.get(tier, 2)

    def get_provider_limit(self) -> int:
        """Get the maximum concurrent calls allowed by the current provider.

        Returns the provider's hard limit for concurrent API calls,
        which should never be exceeded regardless of parallelism mode.

        Returns:
            int: Maximum concurrent calls for the provider

        Examples:
            >>> router = LLMRouter()  # Google native
            >>> router.get_provider_limit()
            8

            >>> router = LLMRouter(preset=QualityPreset.HYPER)  # OpenRouter
            >>> router.get_provider_limit()
            5
        """
        provider = self.config.primary
        limits = PROVIDER_RATE_LIMITS.get(provider, PROVIDER_RATE_LIMITS[ProviderType.GOOGLE])
        return limits["max_concurrent"]

    def get_effective_max_concurrent(
        self,
        mode: ParallelismMode | None = None,
    ) -> int:
        """Get effective maximum concurrent calls considering all constraints.

        Combines model tier, parallelism mode, and provider limits to
        determine the safe maximum concurrent calls. For MAX mode,
        returns provider limit - 1 to leave headroom.

        Args:
            mode: Parallelism mode. If None, uses preset's default mode.

        Returns:
            int: Effective maximum concurrent calls (respects all limits)

        Examples:
            >>> router = LLMRouter(preset=QualityPreset.HYPER)
            >>> router.get_effective_max_concurrent()  # MAX mode
            7  # Google limit (8) - 1

            >>> router = LLMRouter(preset=QualityPreset.BALANCED)
            >>> router.get_effective_max_concurrent()  # NORMAL mode
            3  # Tier limit for native + normal

            >>> router = LLMRouter(text_model="google/gemini-2.0-flash-001:free")
            >>> router.get_effective_max_concurrent(ParallelismMode.MAX)
            2  # Free tier max limit
        """
        # Determine parallelism mode
        if mode is None:
            if self.preset:
                mode = get_preset_parallelism(self.preset)
            else:
                mode = ParallelismMode.NORMAL

        # Get tier-based limit
        tier = self.get_model_tier()
        tier_limit = get_tier_max_concurrent(tier.value, mode)

        # Get provider hard limit
        provider_limit = self.get_provider_limit()

        # For MAX mode, use provider limit - 1 for headroom
        if mode == ParallelismMode.MAX:
            effective_provider_limit = provider_limit - 1
        else:
            effective_provider_limit = provider_limit

        # Return the minimum of tier and provider limits
        effective = min(tier_limit, effective_provider_limit)

        logger.debug(
            f"Effective max concurrent: {effective} "
            f"(tier={tier.value}, mode={mode.value}, "
            f"tier_limit={tier_limit}, provider_limit={provider_limit})"
        )

        return effective

    def get_parallelism_mode(self) -> ParallelismMode:
        """Get the parallelism mode for current configuration.

        Returns:
            ParallelismMode based on preset or default NORMAL

        Examples:
            >>> router = LLMRouter(preset=QualityPreset.HYPER)
            >>> router.get_parallelism_mode()
            ParallelismMode.MAX

            >>> router = LLMRouter()
            >>> router.get_parallelism_mode()
            ParallelismMode.NORMAL
        """
        if self.preset:
            return get_preset_parallelism(self.preset)
        return ParallelismMode.NORMAL

    async def _call_with_retry(
        self,
        provider: LLMProvider,
        model: str,
        prompt: str,
        response_model: type[T] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call provider with proactive rate limiting and exponential backoff retry.

        Handles rate limits gracefully with:
        1. Proactive rate limiting (token bucket) to prevent 429s
        2. Reactive retry with exponential backoff if 429s still occur

        Args:
            provider: The LLM provider to use
            model: Model ID
            prompt: The prompt text
            response_model: Optional Pydantic model for structured output
            **kwargs: Additional parameters

        Returns:
            LLMResponse from the provider

        Raises:
            ProviderError: If all retries fail
        """
        last_error = None
        backoff = INITIAL_BACKOFF

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Proactive rate limiting: wait for token before making call
                tier = get_tier_from_model(model)
                acquired = await acquire_rate_limit(model, timeout=30.0)
                if not acquired:
                    logger.warning(
                        f"Rate limit token not acquired for {model} (tier={tier}), "
                        "proceeding anyway with risk of 429"
                    )

                return await provider.call_text(
                    prompt, model, response_model=response_model, **kwargs
                )
            except RateLimitError as e:
                last_error = e

                # Get retry-after from headers if available
                wait_time = e.retry_after if e.retry_after else backoff
                wait_time = min(wait_time, MAX_BACKOFF)

                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"Rate limit hit on {model} (attempt {attempt}/{MAX_RETRIES}). "
                        f"Waiting {wait_time:.1f}s before retry..."
                    )
                    await asyncio.sleep(wait_time)
                    backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF)
                else:
                    logger.warning(
                        f"Rate limit persists after {MAX_RETRIES} attempts on {model}"
                    )
            except ProviderError as e:
                # Non-rate-limit errors should not be retried
                raise

        # All retries exhausted
        raise last_error or ProviderError(
            message="All retry attempts exhausted",
            provider=provider.provider_type,
            retryable=False,
        )

    async def call(
        self,
        prompt: str,
        capability: ModelCapability = ModelCapability.TEXT,
        **kwargs: Any,
    ) -> LLMResponse[str]:
        """Call LLM with automatic provider selection and fallback.

        Implements a cascade: primary model -> fallback model -> different provider.
        For free models, automatically falls back to paid model on rate limits.

        Args:
            prompt: The input prompt.
            capability: Required model capability.
            **kwargs: Additional parameters passed to provider.

        Returns:
            LLMResponse containing the generated text.

        Raises:
            ProviderError: If all providers fail.

        Examples:
            >>> response = await router.call(
            ...     prompt="Explain AI",
            ...     capability=ModelCapability.TEXT,
            ...     temperature=0.7
            ... )
        """
        primary_model = self._get_model_for_capability(capability, self.config.primary)

        # Try primary provider
        try:
            provider = self._get_provider(self.config.primary)
            logger.debug(f"Calling {self.config.primary.value} with model {primary_model}")
            return await self._call_with_retry(provider, primary_model, prompt, **kwargs)

        except RateLimitError as e:
            logger.warning(f"Rate limit exhausted on {primary_model}: {e}")

            # If using a free model, try falling back to paid model on same provider
            if is_free_model(primary_model) and self.config.primary == ProviderType.OPENROUTER:
                logger.info(f"Free model rate limited. Falling back to paid model: {PAID_FALLBACK_MODEL}")
                try:
                    provider = self._get_provider(ProviderType.OPENROUTER)
                    return await self._call_with_retry(
                        provider, PAID_FALLBACK_MODEL, prompt, **kwargs
                    )
                except (ProviderError, RateLimitError) as e2:
                    logger.warning(f"Paid model fallback also failed: {e2}")

            # Try Google provider as ultimate fallback
            if ProviderType.GOOGLE in self.providers and self.config.primary != ProviderType.GOOGLE:
                logger.info("Falling back to Google provider")
                try:
                    provider = self._get_provider(ProviderType.GOOGLE)
                    settings = get_settings()
                    google_model = settings.CREATIVE_MODEL
                    return await self._call_with_retry(
                        provider, google_model, prompt, **kwargs
                    )
                except ProviderError as e3:
                    logger.warning(f"Google provider fallback failed: {e3}")

            # All fallbacks exhausted
            raise ProviderError(
                message=f"All providers failed. Last error: {e}",
                provider=self.config.primary,
                retryable=False,
            ) from e

        except ProviderError as e:
            logger.warning(f"Primary provider failed: {e}")

            # Try fallback if configured
            if self.config.fallback and self.config.fallback in self.providers:
                logger.info(f"Falling back to {self.config.fallback.value}")
                try:
                    provider = self._get_provider(self.config.fallback)
                    model = self._get_model_for_capability(capability, self.config.fallback)
                    return await self._call_with_retry(provider, model, prompt, **kwargs)
                except ProviderError as e2:
                    logger.warning(f"Fallback provider also failed: {e2}")

            # No fallback available or fallback failed
            raise

    async def call_structured(
        self,
        prompt: str,
        response_model: type[T],
        capability: ModelCapability = ModelCapability.TEXT,
        **kwargs: Any,
    ) -> LLMResponse[T]:
        """Call LLM with structured output.

        Uses Pydantic models for type-safe structured responses.
        Similar to Mirascope's response_model pattern.

        Args:
            prompt: The input prompt.
            response_model: Pydantic model for response parsing.
            capability: Required model capability.
            **kwargs: Additional parameters passed to provider.

        Returns:
            LLMResponse containing the parsed structured output.

        Raises:
            ProviderError: If all providers fail.

        Examples:
            >>> class SceneData(BaseModel):
            ...     location: str
            ...     time_period: str
            ...     characters: list[str]
            >>> response = await router.call_structured(
            ...     prompt="Describe the signing of the Declaration",
            ...     response_model=SceneData
            ... )
            >>> print(response.content.location)
        """
        primary_model = self._get_model_for_capability(capability, self.config.primary)

        # Try primary provider
        try:
            provider = self._get_provider(self.config.primary)
            logger.debug(f"Calling {self.config.primary.value} structured with model {primary_model}")
            return await self._call_with_retry(
                provider, primary_model, prompt, response_model=response_model, **kwargs
            )

        except RateLimitError as e:
            logger.warning(f"Rate limit exhausted on {primary_model}: {e}")

            # If using a free model, try falling back to paid model on same provider
            if is_free_model(primary_model) and self.config.primary == ProviderType.OPENROUTER:
                logger.info(f"Free model rate limited. Falling back to paid model: {PAID_FALLBACK_MODEL}")
                try:
                    provider = self._get_provider(ProviderType.OPENROUTER)
                    return await self._call_with_retry(
                        provider, PAID_FALLBACK_MODEL, prompt,
                        response_model=response_model, **kwargs
                    )
                except (ProviderError, RateLimitError) as e2:
                    logger.warning(f"Paid model fallback also failed: {e2}")

            # Try Google provider as ultimate fallback
            if ProviderType.GOOGLE in self.providers and self.config.primary != ProviderType.GOOGLE:
                logger.info("Falling back to Google provider")
                try:
                    provider = self._get_provider(ProviderType.GOOGLE)
                    settings = get_settings()
                    google_model = settings.CREATIVE_MODEL
                    return await self._call_with_retry(
                        provider, google_model, prompt,
                        response_model=response_model, **kwargs
                    )
                except ProviderError as e3:
                    logger.warning(f"Google provider fallback failed: {e3}")

            # All fallbacks exhausted
            raise ProviderError(
                message=f"All providers failed. Last error: {e}",
                provider=self.config.primary,
                retryable=False,
            ) from e

        except ProviderError as e:
            logger.warning(f"Primary provider failed: {e}")

            # Try fallback if configured
            if self.config.fallback and self.config.fallback in self.providers:
                logger.info(f"Falling back to {self.config.fallback.value}")
                try:
                    provider = self._get_provider(self.config.fallback)
                    model = self._get_model_for_capability(capability, self.config.fallback)
                    return await self._call_with_retry(
                        provider, model, prompt, response_model=response_model, **kwargs
                    )
                except ProviderError as e2:
                    logger.warning(f"Fallback provider also failed: {e2}")

            raise

    async def generate_image(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> LLMResponse[str]:
        """Generate an image from a prompt.

        Routes to appropriate provider based on preset configuration:
        - HD: Google native Nano Banana Pro (2K resolution)
        - Balanced: Google native Nano Banana
        - Hyper: OpenRouter fast image model

        Args:
            prompt: The image generation prompt.
            **kwargs: Additional parameters (aspect_ratio, image_size).

        Returns:
            LLMResponse containing base64-encoded image.

        Raises:
            ProviderError: If image generation fails.
        """
        # Determine provider for image generation
        # Prefer preset's image_provider, then Google native, then fallback
        if self._preset_config and "image_provider" in self._preset_config:
            image_provider = self._preset_config["image_provider"]
        elif ProviderType.GOOGLE in self.providers:
            image_provider = ProviderType.GOOGLE
        elif ProviderType.OPENROUTER in self.providers:
            image_provider = ProviderType.OPENROUTER
        else:
            image_provider = self.config.primary

        provider = self._get_provider(image_provider)
        model = self._get_model_for_capability(ModelCapability.IMAGE, image_provider)

        # Merge preset config params (image_size, etc.) with kwargs
        image_kwargs = dict(kwargs)
        if self._preset_config:
            if "image_size" in self._preset_config and "image_size" not in image_kwargs:
                image_kwargs["image_size"] = self._preset_config["image_size"]
            if "aspect_ratio" in self._preset_config and "aspect_ratio" not in image_kwargs:
                image_kwargs["aspect_ratio"] = self._preset_config["aspect_ratio"]

        logger.debug(f"Image generation: using {image_provider.value} with model {model}")

        return await provider.generate_image(prompt, model, **image_kwargs)

    async def analyze_image(
        self,
        image: str,
        prompt: str,
        **kwargs: Any,
    ) -> LLMResponse[dict[str, Any]]:
        """Analyze an image with a prompt.

        Args:
            image: Base64-encoded image or URL.
            prompt: The analysis prompt.
            **kwargs: Additional parameters.

        Returns:
            LLMResponse containing analysis results.

        Raises:
            ProviderError: If vision analysis fails.
        """
        provider = self._get_provider(self.config.primary)
        model = self._get_model_for_capability(ModelCapability.VISION, self.config.primary)

        return await provider.analyze_image(image, prompt, model, **kwargs)

    async def health_check(self) -> dict[str, bool]:
        """Check health of all configured providers.

        Returns:
            Dictionary mapping provider names to health status.
        """
        results = {}
        for provider_type, provider in self.providers.items():
            results[provider_type.value] = await provider.health_check()
        return results

    async def close(self) -> None:
        """Close all provider connections."""
        for provider in self.providers.values():
            if hasattr(provider, "close"):
                await provider.close()


# Convenience function for one-off calls
async def quick_call(
    prompt: str,
    capability: ModelCapability = ModelCapability.TEXT,
    **kwargs: Any,
) -> str:
    """Quick LLM call without router setup.

    Convenience function for simple one-off LLM calls.

    Args:
        prompt: The input prompt.
        capability: Required model capability.
        **kwargs: Additional parameters.

    Returns:
        Generated text string.

    Examples:
        >>> result = await quick_call("What is 2+2?")
        >>> print(result)
        "4"
    """
    router = LLMRouter()
    try:
        response = await router.call(prompt, capability, **kwargs)
        return response.content
    finally:
        await router.close()
