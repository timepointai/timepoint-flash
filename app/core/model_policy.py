"""Model policy helpers — permissiveness classification and default selection.

Used by both the API layer (timepoints.py) and the pipeline (pipeline.py)
to keep provenance logic in one place.
"""

# Prefixes for open-weight / distillable model families on OpenRouter
PERMISSIVE_PREFIXES = (
    "meta-llama/",
    "deepseek/",
    "qwen/",
    "mistralai/",           # Mistral open-weight models (Apache 2.0)
    "microsoft/",           # Phi family
    "google/gemma",         # Gemma open-weight
    "allenai/",
    "nvidia/",
    "black-forest-labs/",   # FLUX open-weight image models
)

# Google-native model prefixes (always restricted)
GOOGLE_MODEL_PREFIXES = ("gemini", "imagen", "flux-schnell")

# Prefixes routed through OpenRouter (may be restricted or permissive)
OPENROUTER_PREFIXES = ("meta-llama/", "anthropic/", "mistralai/", "openai/", "deepseek/", "qwen/", "microsoft/", "black-forest-labs/")


def derive_model_provider(model_id: str | None) -> str:
    """Derive the routing provider from a model ID string."""
    if not model_id:
        return "unknown"
    lower = model_id.lower()
    if any(lower.startswith(p) for p in GOOGLE_MODEL_PREFIXES):
        return "google"
    if any(lower.startswith(p) for p in OPENROUTER_PREFIXES):
        return "openrouter"
    return "google"


def is_model_permissive(model_id: str | None) -> bool:
    """Check if a model ID is open-weight / permissively licensed."""
    if not model_id:
        return False
    lower = model_id.lower()
    return any(lower.startswith(p) for p in PERMISSIVE_PREFIXES)


def derive_model_permissiveness(model_id: str | None) -> str:
    """Derive distillation licensing permissiveness from a model ID.

    Open-weight models (Llama, DeepSeek, Qwen, Mistral, Phi, Gemma) are
    'permissive' — safe for distillation and derivative works.
    Frontier models (Google Gemini, Anthropic, OpenAI) are 'restricted'.
    """
    if not model_id:
        return "unknown"
    return "permissive" if is_model_permissive(model_id) else "restricted"
