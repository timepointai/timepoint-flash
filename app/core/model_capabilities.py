"""Model capabilities registry for model-adaptive responses.

This module defines model-specific configurations, capabilities, and requirements.
Different models have different parameter formats, response structures, and constraints.
The registry enables adaptive handling based on the specific model being used.

Examples:
    >>> from app.core.model_capabilities import get_image_model_config
    >>> config = get_image_model_config("gemini-2.5-flash-image")
    >>> config.response_modalities
    ['IMAGE']

Tests:
    - tests/unit/test_model_capabilities.py
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ImageModelType(str, Enum):
    """Type of image generation model."""

    GEMINI_NATIVE = "gemini_native"  # Gemini with native image gen (Nano Banana)
    GEMINI_PRO = "gemini_pro"  # Gemini 3 Pro Image (Nano Banana Pro)
    IMAGEN = "imagen"  # Legacy Imagen API


@dataclass
class ImageModelConfig:
    """Configuration for an image generation model.

    Attributes:
        model_id: The model identifier
        model_type: Type of image model
        response_modalities: Required response modalities for config
        supports_image_size: Whether model supports imageSize parameter
        supported_sizes: List of supported image sizes (if any)
        max_resolution: Maximum resolution in pixels
        supports_aspect_ratio: Whether model supports aspectRatio parameter
        use_camel_case_params: Whether to use camelCase for parameters
        fallback_models: List of fallback models to try on failure
        timeout_multiplier: Multiplier for timeout (image gen is slower)
    """

    model_id: str
    model_type: ImageModelType
    response_modalities: list[str] = field(default_factory=lambda: ["TEXT", "IMAGE"])
    supports_image_size: bool = False
    supported_sizes: list[str] = field(default_factory=list)
    max_resolution: int = 1024
    supports_aspect_ratio: bool = True
    use_camel_case_params: bool = True
    fallback_models: list[str] = field(default_factory=list)
    timeout_multiplier: float = 2.0
    notes: str = ""


# =============================================================================
# MODEL CAPABILITIES REGISTRY
# =============================================================================
# This registry defines the capabilities and requirements for each image model.
# When a model fails, consult this to understand what parameters it supports.
#
# Last updated: 2024-12-04
# =============================================================================

IMAGE_MODEL_REGISTRY: dict[str, ImageModelConfig] = {
    # Nano Banana - Fast, reliable, 1024px max
    "gemini-2.5-flash-image": ImageModelConfig(
        model_id="gemini-2.5-flash-image",
        model_type=ImageModelType.GEMINI_NATIVE,
        response_modalities=["IMAGE"],  # Can use IMAGE-only
        supports_image_size=False,  # Only supports default 1024px
        supported_sizes=[],
        max_resolution=1024,
        supports_aspect_ratio=True,
        use_camel_case_params=True,
        fallback_models=[],
        timeout_multiplier=2.0,
        notes="GA model, fast and reliable. 1024px only.",
    ),
    # Nano Banana Pro - Higher quality, up to 4096px
    "gemini-3-pro-image-preview": ImageModelConfig(
        model_id="gemini-3-pro-image-preview",
        model_type=ImageModelType.GEMINI_PRO,
        response_modalities=["TEXT", "IMAGE"],  # Requires both
        supports_image_size=True,
        supported_sizes=["1K", "2K", "4K"],
        max_resolution=4096,
        supports_aspect_ratio=True,
        use_camel_case_params=True,
        fallback_models=["gemini-2.5-flash-image"],
        timeout_multiplier=3.0,  # Higher quality takes longer
        notes="Preview model, best quality. Supports 1K/2K/4K.",
    ),
    # Legacy Imagen - Uses different API
    "imagen-3.0-generate-002": ImageModelConfig(
        model_id="imagen-3.0-generate-002",
        model_type=ImageModelType.IMAGEN,
        response_modalities=[],  # Not applicable - uses generate_images API
        supports_image_size=False,
        supported_sizes=[],
        max_resolution=1024,
        supports_aspect_ratio=True,
        use_camel_case_params=False,  # Imagen uses snake_case
        fallback_models=["gemini-2.5-flash-image"],
        timeout_multiplier=2.0,
        notes="Legacy Imagen API. Uses generate_images() not generate_content().",
    ),
}

# Default config for unknown models (conservative settings)
DEFAULT_IMAGE_CONFIG = ImageModelConfig(
    model_id="unknown",
    model_type=ImageModelType.GEMINI_NATIVE,
    response_modalities=["TEXT", "IMAGE"],  # Safest default
    supports_image_size=False,
    supported_sizes=[],
    max_resolution=1024,
    supports_aspect_ratio=True,
    use_camel_case_params=True,
    fallback_models=["gemini-2.5-flash-image"],
    timeout_multiplier=2.0,
    notes="Unknown model - using conservative defaults.",
)


def get_image_model_config(model_id: str) -> ImageModelConfig:
    """Get configuration for an image model.

    Args:
        model_id: The model identifier.

    Returns:
        ImageModelConfig for the model, or default config if unknown.

    Examples:
        >>> config = get_image_model_config("gemini-2.5-flash-image")
        >>> config.max_resolution
        1024
    """
    return IMAGE_MODEL_REGISTRY.get(model_id, DEFAULT_IMAGE_CONFIG)


def get_model_response_modalities(model_id: str) -> list[str]:
    """Get the required response modalities for a model.

    Args:
        model_id: The model identifier.

    Returns:
        List of response modalities to use.
    """
    config = get_image_model_config(model_id)
    return config.response_modalities


def should_include_image_size(model_id: str, requested_size: str | None) -> bool:
    """Check if imageSize should be included for this model.

    Args:
        model_id: The model identifier.
        requested_size: The requested image size (e.g., "2K").

    Returns:
        True if the model supports the requested size.
    """
    config = get_image_model_config(model_id)
    if not config.supports_image_size:
        return False
    if requested_size and config.supported_sizes:
        return requested_size in config.supported_sizes
    return config.supports_image_size


def get_fallback_models(model_id: str) -> list[str]:
    """Get fallback models to try if the primary fails.

    Args:
        model_id: The primary model identifier.

    Returns:
        List of fallback model IDs.
    """
    config = get_image_model_config(model_id)
    return config.fallback_models


def build_image_config_params(
    model_id: str,
    aspect_ratio: str | None = None,
    image_size: str | None = None,
) -> dict[str, Any]:
    """Build image config parameters for a model.

    Handles model-specific parameter naming and validation.

    Args:
        model_id: The model identifier.
        aspect_ratio: Optional aspect ratio (e.g., "16:9").
        image_size: Optional image size (e.g., "2K").

    Returns:
        Dictionary of parameters for the image config.
    """
    config = get_image_model_config(model_id)
    params: dict[str, Any] = {}

    if aspect_ratio and config.supports_aspect_ratio:
        key = "aspectRatio" if config.use_camel_case_params else "aspect_ratio"
        params[key] = aspect_ratio

    if image_size and should_include_image_size(model_id, image_size):
        key = "imageSize" if config.use_camel_case_params else "image_size"
        params[key] = image_size

    return params


def is_imagen_model(model_id: str) -> bool:
    """Check if model uses Imagen API (generate_images).

    Args:
        model_id: The model identifier.

    Returns:
        True if model uses Imagen API.
    """
    config = get_image_model_config(model_id)
    return config.model_type == ImageModelType.IMAGEN


def is_gemini_image_model(model_id: str) -> bool:
    """Check if model uses Gemini image generation (generate_content with IMAGE modality).

    Args:
        model_id: The model identifier.

    Returns:
        True if model uses Gemini image generation.
    """
    config = get_image_model_config(model_id)
    return config.model_type in (ImageModelType.GEMINI_NATIVE, ImageModelType.GEMINI_PRO)


# =============================================================================
# TEXT MODEL CAPABILITIES
# =============================================================================
# Defines which text models support structured JSON output.
# This enables model-adaptive response handling.
# =============================================================================


class TextModelCapability(str, Enum):
    """Capabilities that text models may support."""

    JSON_SCHEMA = "json_schema"  # Native JSON schema support (Google response_schema)
    JSON_MODE = "json_mode"  # JSON mode via response_format (OpenRouter)
    FUNCTION_CALLING = "function_calling"  # Function/tool calling
    STREAMING = "streaming"  # Token-by-token streaming
    EXTENDED_THINKING = "extended_thinking"  # Extended thinking/reasoning


@dataclass
class TextModelConfig:
    """Configuration for a text generation model.

    Attributes:
        model_id: The model identifier
        provider: Provider type (google, openrouter)
        supports_json_schema: Native JSON schema output (Google's response_schema)
        supports_json_mode: JSON mode via response_format
        supports_function_calling: Function/tool calling
        supports_streaming: Token streaming
        supports_extended_thinking: Extended thinking/reasoning
        max_output_tokens: Maximum output tokens
        notes: Additional notes about the model
    """

    model_id: str
    provider: str  # "google" or "openrouter"
    supports_json_schema: bool = True
    supports_json_mode: bool = True
    supports_function_calling: bool = True
    supports_streaming: bool = True
    supports_extended_thinking: bool = False
    max_output_tokens: int = 8192
    notes: str = ""


# Registry of known text models and their capabilities
TEXT_MODEL_REGISTRY: dict[str, TextModelConfig] = {
    # Google Native Models
    "gemini-2.5-flash": TextModelConfig(
        model_id="gemini-2.5-flash",
        provider="google",
        supports_json_schema=True,
        supports_json_mode=True,
        supports_function_calling=True,
        supports_streaming=True,
        supports_extended_thinking=True,
        max_output_tokens=8192,
        notes="Fast, reliable, supports extended thinking",
    ),
    "gemini-2.5-pro": TextModelConfig(
        model_id="gemini-2.5-pro",
        provider="google",
        supports_json_schema=True,
        supports_json_mode=True,
        supports_function_calling=True,
        supports_streaming=True,
        supports_extended_thinking=True,
        max_output_tokens=8192,
        notes="Higher quality, supports extended thinking",
    ),
    "gemini-2.5-pro-preview": TextModelConfig(
        model_id="gemini-2.5-pro-preview",
        provider="google",
        supports_json_schema=True,
        supports_json_mode=True,
        supports_function_calling=True,
        supports_streaming=True,
        supports_extended_thinking=True,
        max_output_tokens=8192,
        notes="Preview version of 2.5 Pro",
    ),
    "gemini-2.0-flash": TextModelConfig(
        model_id="gemini-2.0-flash",
        provider="google",
        supports_json_schema=True,
        supports_json_mode=True,
        supports_function_calling=True,
        supports_streaming=True,
        supports_extended_thinking=False,
        max_output_tokens=8192,
        notes="Older but stable",
    ),
    # OpenRouter Models
    "google/gemini-2.0-flash-001": TextModelConfig(
        model_id="google/gemini-2.0-flash-001",
        provider="openrouter",
        supports_json_schema=False,  # OpenRouter uses json_mode, not schema
        supports_json_mode=True,
        supports_function_calling=True,
        supports_streaming=True,
        supports_extended_thinking=False,
        max_output_tokens=8192,
        notes="Via OpenRouter, fast",
    ),
    "google/gemini-2.0-flash-001:free": TextModelConfig(
        model_id="google/gemini-2.0-flash-001:free",
        provider="openrouter",
        supports_json_schema=False,
        supports_json_mode=True,
        supports_function_calling=True,
        supports_streaming=True,
        supports_extended_thinking=False,
        max_output_tokens=8192,
        notes="Free tier, rate limited",
    ),
    "google/gemini-2.5-flash-preview": TextModelConfig(
        model_id="google/gemini-2.5-flash-preview",
        provider="openrouter",
        supports_json_schema=False,
        supports_json_mode=True,
        supports_function_calling=True,
        supports_streaming=True,
        supports_extended_thinking=True,
        max_output_tokens=8192,
        notes="2.5 Flash via OpenRouter",
    ),
    "anthropic/claude-3.5-sonnet": TextModelConfig(
        model_id="anthropic/claude-3.5-sonnet",
        provider="openrouter",
        supports_json_schema=False,
        supports_json_mode=True,
        supports_function_calling=True,
        supports_streaming=True,
        supports_extended_thinking=False,
        max_output_tokens=8192,
        notes="Claude 3.5 Sonnet via OpenRouter",
    ),
    "openai/gpt-4o": TextModelConfig(
        model_id="openai/gpt-4o",
        provider="openrouter",
        supports_json_schema=False,  # OpenRouter doesn't pass schema
        supports_json_mode=True,
        supports_function_calling=True,
        supports_streaming=True,
        supports_extended_thinking=False,
        max_output_tokens=16384,
        notes="GPT-4o via OpenRouter",
    ),
    "openai/gpt-4o-mini": TextModelConfig(
        model_id="openai/gpt-4o-mini",
        provider="openrouter",
        supports_json_schema=False,
        supports_json_mode=True,
        supports_function_calling=True,
        supports_streaming=True,
        supports_extended_thinking=False,
        max_output_tokens=16384,
        notes="GPT-4o Mini via OpenRouter",
    ),
}

# Default config for unknown models (conservative - assume JSON mode works)
DEFAULT_TEXT_CONFIG = TextModelConfig(
    model_id="unknown",
    provider="unknown",
    supports_json_schema=False,  # Conservative: don't assume schema support
    supports_json_mode=True,  # Most modern models support JSON mode
    supports_function_calling=True,
    supports_streaming=True,
    supports_extended_thinking=False,
    max_output_tokens=8192,
    notes="Unknown model - using conservative defaults",
)


def get_text_model_config(model_id: str) -> TextModelConfig:
    """Get configuration for a text model.

    Args:
        model_id: The model identifier.

    Returns:
        TextModelConfig for the model, or default config if unknown.

    Examples:
        >>> config = get_text_model_config("gemini-2.5-flash")
        >>> config.supports_json_schema
        True
    """
    return TEXT_MODEL_REGISTRY.get(model_id, DEFAULT_TEXT_CONFIG)


def supports_structured_output(model_id: str) -> bool:
    """Check if model supports structured JSON output.

    This checks if the model supports either native JSON schema (Google)
    or JSON mode (OpenRouter/others). Most modern models support at least
    JSON mode.

    Args:
        model_id: The model identifier.

    Returns:
        True if model supports structured JSON output.

    Examples:
        >>> supports_structured_output("gemini-2.5-flash")
        True
        >>> supports_structured_output("google/gemini-2.0-flash-001")
        True
    """
    config = get_text_model_config(model_id)
    return config.supports_json_schema or config.supports_json_mode


def supports_json_schema(model_id: str) -> bool:
    """Check if model supports native JSON schema output.

    Native JSON schema output (like Google's response_schema) provides
    guaranteed schema compliance. If False, use JSON mode with parsing.

    Args:
        model_id: The model identifier.

    Returns:
        True if model supports native JSON schema.

    Examples:
        >>> supports_json_schema("gemini-2.5-flash")
        True
        >>> supports_json_schema("google/gemini-2.0-flash-001")
        False
    """
    config = get_text_model_config(model_id)
    return config.supports_json_schema


def get_model_provider(model_id: str) -> str:
    """Get the provider for a model.

    Args:
        model_id: The model identifier.

    Returns:
        Provider name ("google", "openrouter", or "unknown").

    Examples:
        >>> get_model_provider("gemini-2.5-flash")
        'google'
        >>> get_model_provider("google/gemini-2.0-flash-001")
        'openrouter'
    """
    config = get_text_model_config(model_id)
    return config.provider


def infer_provider_from_model_id(model_id: str) -> str:
    """Infer provider from model ID pattern if not in registry.

    Args:
        model_id: The model identifier.

    Returns:
        Inferred provider name.

    Examples:
        >>> infer_provider_from_model_id("anthropic/claude-3-opus")
        'openrouter'
        >>> infer_provider_from_model_id("gemini-2.5-flash")
        'google'
    """
    # Check registry first
    if model_id in TEXT_MODEL_REGISTRY:
        return TEXT_MODEL_REGISTRY[model_id].provider

    # Infer from model ID pattern
    if "/" in model_id:
        # OpenRouter format: provider/model-name
        return "openrouter"
    elif model_id.startswith("gemini-"):
        # Google native format: gemini-X.X-...
        return "google"
    else:
        return "unknown"


def get_available_interaction_models() -> list[dict]:
    """Get list of models suitable for character interactions.

    Returns models that support streaming and JSON mode for
    interactive character chat, dialog, and surveys.

    Returns:
        List of model info dicts with id, provider, and notes.
    """
    models = []
    for model_id, config in TEXT_MODEL_REGISTRY.items():
        if config.supports_streaming and config.supports_json_mode:
            models.append({
                "id": model_id,
                "provider": config.provider,
                "supports_json_schema": config.supports_json_schema,
                "supports_extended_thinking": config.supports_extended_thinking,
                "notes": config.notes,
            })
    return models
