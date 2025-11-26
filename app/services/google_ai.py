"""
Google Generative AI Suite integration.
"""
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from pydantic import BaseModel
from typing import Type, TypeVar, Optional, Any
import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# Configure the SDK
if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
else:
    logger.warning("GOOGLE_API_KEY not set. Google AI calls will fail.")

T = TypeVar('T', bound=BaseModel)

def _get_safety_settings():
    return {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }

def _clean_schema_for_google(schema: dict, is_root: bool = True) -> dict:
    """
    Remove fields from Pydantic schema that Google's protobuf doesn't support.

    Google's protobuf Schema message doesn't support:
    - "default" field (at any level)
    - "title" field (at any level)
    - "examples", "additionalProperties" and other JSON Schema extensions
    - "$defs" (use inline definitions instead)

    This recursively cleans the schema to be compatible.
    """
    if not isinstance(schema, dict):
        return schema

    # Fields to remove at all levels
    # Google's protobuf Schema only supports: type, format, description, nullable, enum, items, properties, required
    unsupported_fields = {
        "default",
        "examples",
        "additionalProperties",
        "title",
        "$defs",
        "definitions",
        "anyOf",  # Union types - not supported
        "oneOf",  # Alternative union syntax
        "allOf",  # Composition - not supported
        "not",  # Negation - not supported
        "const",  # Constant values - use enum instead
        "minLength",  # String constraints
        "maxLength",
        "pattern",
        "minimum",  # Number constraints
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minItems",  # Array constraints
        "maxItems",
        "uniqueItems",
        "minProperties",  # Object constraints
        "maxProperties",
        "patternProperties",
        "dependencies",
        "propertyNames",
        "if",  # Conditional schemas
        "then",
        "else",
        "$schema",  # Schema metadata
        "$id",
        "$ref",  # References - inline instead
    }

    cleaned = {}
    for key, value in schema.items():
        # Skip unsupported fields
        if key in unsupported_fields:
            continue

        # Recursively clean nested dicts
        if isinstance(value, dict):
            cleaned[key] = _clean_schema_for_google(value, is_root=False)
        # Recursively clean lists of dicts
        elif isinstance(value, list):
            cleaned[key] = [
                _clean_schema_for_google(item, is_root=False) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned[key] = value

    return cleaned

async def call_llm(
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_model: Type[T],
    temperature: float = 0.7,
    max_tokens: int = 8192
) -> T:
    """
    Call Google Gemini model with structured JSON output.

    Automatically falls back to OpenRouter if GOOGLE_API_KEY is not configured.
    """
    try:
        # Use configured model or fallback to config default
        # Map "judge" etc to actual model names if passed generic names
        actual_model = model
        if model == "judge":
            actual_model = settings.JUDGE_MODEL
        elif model == "creative":
            actual_model = settings.CREATIVE_MODEL

        # If no Google API key, route to OpenRouter
        if not settings.GOOGLE_API_KEY:
            logger.info(f"[GoogleAI] No Google API key, routing to OpenRouter for {actual_model}")
            from app.services.openrouter import call_llm as openrouter_call_llm

            # Map model names to OpenRouter equivalents
            openrouter_models = {
                "gemini-1.5-flash": "google/gemini-1.5-flash",
                "gemini-1.5-pro": "google/gemini-1.5-pro",
                "gemini-1.5-flash-latest": "google/gemini-1.5-flash",
                "gemini-1.5-pro-latest": "google/gemini-1.5-pro",
            }
            openrouter_model = openrouter_models.get(actual_model, f"google/{actual_model}")

            return await openrouter_call_llm(
                model=openrouter_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=response_model,
                temperature=temperature,
                max_tokens=max_tokens
            )

        logger.info(f"[GoogleAI] Calling {actual_model}")

        # Get Pydantic schema and clean it for Google AI compatibility
        raw_schema = response_model.model_json_schema()
        cleaned_schema = _clean_schema_for_google(raw_schema)

        logger.debug(f"[GoogleAI] Using cleaned schema: {json.dumps(cleaned_schema, indent=2)[:500]}")

        # Create the model
        # Note: system_instruction is supported in newer SDK versions
        gen_model = genai.GenerativeModel(
            model_name=actual_model,
            system_instruction=system_prompt,
            safety_settings=_get_safety_settings(),
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
                response_schema=cleaned_schema
            )
        )

        # Generate content
        response = await gen_model.generate_content_async(user_prompt)
        
        # Parse result
        json_text = response.text
        logger.info(f"[GoogleAI] Response received ({len(json_text)} chars)")
        
        # Parse into Pydantic model
        return response_model.model_validate_json(json_text)

    except Exception as e:
        logger.error(f"[GoogleAI] Error calling {model}: {e}", exc_info=True)
        raise

async def generate_image(prompt: str, model: str = None) -> str:
    """
    Generate image using Imagen 3 via Google Gen AI SDK.

    Automatically falls back to OpenRouter if GOOGLE_API_KEY is not configured.

    Returns: Base64 data URL or public URL if available.
    """
    if not model:
        model = settings.IMAGE_MODEL

    # If no Google API key OR model is an OpenRouter path, use OpenRouter
    if not settings.GOOGLE_API_KEY or model.startswith("google/"):
        logger.info(f"[Imagen] Routing to OpenRouter for {model}")
        from app.services.openrouter import generate_image as openrouter_generate_image
        return await openrouter_generate_image(prompt, model)

    logger.info(f"[Imagen] Generating image with {model}")
    
    try:
        gen_model = genai.GenerativeModel(model)
        
        # Attempt 1: Use generate_images (standard for Imagen models in some SDKs)
        if hasattr(gen_model, 'generate_images'):
            response = await gen_model.generate_images_async(
                prompt=prompt,
                number_of_images=1,
                aspect_ratio="16:9",
                safety_filter_level="block_only_high"
            )
            if response.images:
                # Convert PIL image to base64
                import base64
                from io import BytesIO
                
                img = response.images[0]
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                return f"data:image/png;base64,{img_str}"
        
        # Attempt 2: Try generate_content (some models use this)
        response = await gen_model.generate_content_async(prompt)
        
        # If we reach here without image, raise error
        raise NotImplementedError("Image generation not fully supported with this SDK version/model combo yet.")

    except Exception as e:
        logger.error(f"[Imagen] Failed: {e}")
        # Fallback to OpenRouter if configured and Google fails
        if settings.OPENROUTER_API_KEY:
            logger.info("Falling back to OpenRouter for image generation")
            from app.services.openrouter_fallback import generate_image_fallback
            return await generate_image_fallback(prompt, model)
        raise

async def segment_image(
    image_data: str,
    objects_to_segment: list[str],
    model: str = None
) -> dict:
    """
    Analyze image for characters using Gemini Vision.

    Automatically falls back to OpenRouter if GOOGLE_API_KEY is not configured.
    """
    if not model:
        model = settings.IMAGE_MODEL  # Use image model for segmentation

    # If no Google API key OR model is an OpenRouter path, use OpenRouter
    if not settings.GOOGLE_API_KEY or model.startswith("google/"):
        logger.info(f"[Vision] Routing to OpenRouter for segmentation with {model}")
        from app.services.openrouter import segment_image as openrouter_segment_image
        return await openrouter_segment_image(image_data, objects_to_segment, model)

    logger.info(f"[Vision] Analyzing image for: {objects_to_segment}")
    
    return {
        "segmentation_data": "Segmentation not fully implemented in migration.",
        "color_map": {},
        "type": "text"
    }
