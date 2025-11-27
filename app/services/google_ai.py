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

def _truncate_long_fields(data: dict, model: Type[BaseModel]) -> dict:
    """
    Truncate string fields that exceed max_length constraints in the Pydantic model.

    This is a safety net for when LLMs don't respect character limits in prompts.
    """
    if not isinstance(data, dict):
        return data

    # Get field info from Pydantic model
    model_fields = model.model_fields

    truncated = {}
    for key, value in data.items():
        if key not in model_fields:
            truncated[key] = value
            continue

        field_info = model_fields[key]

        # Check for max_length constraint on string fields
        if isinstance(value, str) and hasattr(field_info, 'metadata'):
            for constraint in field_info.metadata:
                if hasattr(constraint, 'max_length') and constraint.max_length:
                    if len(value) > constraint.max_length:
                        logger.warning(
                            f"[Truncation] Field '{key}' exceeded {constraint.max_length} chars "
                            f"({len(value)} chars), truncating..."
                        )
                        value = value[:constraint.max_length]
                        break

        # Recursively handle nested Pydantic models
        if hasattr(field_info.annotation, '__bases__') and BaseModel in field_info.annotation.__bases__:
            value = _truncate_long_fields(value, field_info.annotation)
        # Handle lists of Pydantic models
        elif isinstance(value, list) and value:
            if hasattr(field_info.annotation, '__args__'):
                item_type = field_info.annotation.__args__[0]
                if hasattr(item_type, '__bases__') and BaseModel in item_type.__bases__:
                    value = [_truncate_long_fields(item, item_type) for item in value]

        truncated[key] = value

    return truncated

def _is_valid_google_key() -> bool:
    """Check if GOOGLE_API_KEY is valid (not None, empty, or placeholder)."""
    if not settings.GOOGLE_API_KEY:
        return False
    invalid_values = {"placeholder", "your_key_here", "YOUR_API_KEY", ""}
    return settings.GOOGLE_API_KEY.strip() not in invalid_values

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

        # If no valid Google API key, route to OpenRouter
        if not _is_valid_google_key():
            logger.info(f"[GoogleAI] No valid Google API key, routing to OpenRouter for {actual_model}")
            from app.services.openrouter import call_llm as openrouter_call_llm

            # Map model names to OpenRouter equivalents
            # Gemini 2.5 models use same name in OpenRouter: google/gemini-2.5-*
            # Gemini 1.5 models have different naming on OpenRouter
            openrouter_models = {
                # Gemini 2.5 (current, recommended)
                "gemini-2.5-flash": "google/gemini-2.5-flash",
                "gemini-2.5-pro": "google/gemini-2.5-pro",
                # Gemini 1.5 (legacy, may be deprecated on OpenRouter)
                "gemini-1.5-flash": "google/gemini-pro-1.5",  # fallback to pro
                "gemini-1.5-pro": "google/gemini-pro-1.5",
                "gemini-1.5-flash-latest": "google/gemini-pro-1.5",
                "gemini-1.5-pro-latest": "google/gemini-pro-1.5",
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

        # Create enhanced system prompt with schema information
        schema_prompt = f"{system_prompt}\n\nIMPORTANT: You MUST return valid JSON that EXACTLY matches this schema:\n{json.dumps(response_model.model_json_schema(), indent=2)}"

        # Create the model without response_schema (instructor will handle validation)
        # Note: Using JSON mode without schema for better compatibility
        gen_model = genai.GenerativeModel(
            model_name=actual_model,
            system_instruction=schema_prompt,
            safety_settings=_get_safety_settings(),
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json"
                # Not using response_schema - let instructor validate instead
            )
        )

        # Generate content
        response = await gen_model.generate_content_async(user_prompt)

        # Check if response was blocked by safety filters
        # finish_reason = 2 means SAFETY block
        if not response.parts and hasattr(response, 'candidates'):
            for candidate in response.candidates:
                if hasattr(candidate, 'finish_reason') and candidate.finish_reason == 2:
                    logger.warning(
                        f"[GoogleAI] Content blocked by safety filters (finish_reason=2), "
                        f"falling back to OpenRouter"
                    )
                    # Fall back to OpenRouter
                    from app.services.openrouter import call_llm as openrouter_call_llm

                    openrouter_models = {
                        "gemini-2.5-flash": "google/gemini-2.5-flash",
                        "gemini-2.5-pro": "google/gemini-2.5-pro",
                        "gemini-1.5-flash": "google/gemini-pro-1.5",
                        "gemini-1.5-pro": "google/gemini-pro-1.5",
                        "gemini-1.5-flash-latest": "google/gemini-pro-1.5",
                        "gemini-1.5-pro-latest": "google/gemini-pro-1.5",
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

        # Parse result
        json_text = response.text
        logger.info(f"[GoogleAI] Response received ({len(json_text)} chars)")

        # Parse JSON to dict first
        data = json.loads(json_text)

        # Truncate any overly long fields (safety net)
        data = _truncate_long_fields(data, response_model)

        # Validate with Pydantic
        return response_model.model_validate(data)

    except ValueError as e:
        # Handle cases where response.text fails (blocked content)
        if "finish_reason" in str(e) and settings.OPENROUTER_API_KEY:
            logger.warning(f"[GoogleAI] Response blocked, falling back to OpenRouter: {e}")
            from app.services.openrouter import call_llm as openrouter_call_llm

            openrouter_models = {
                "gemini-2.5-flash": "google/gemini-2.5-flash",
                "gemini-2.5-pro": "google/gemini-2.5-pro",
                "gemini-1.5-flash": "google/gemini-pro-1.5",
                "gemini-1.5-pro": "google/gemini-pro-1.5",
                "gemini-1.5-flash-latest": "google/gemini-pro-1.5",
                "gemini-1.5-pro-latest": "google/gemini-pro-1.5",
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
        else:
            logger.error(f"[GoogleAI] Error calling {model}: {e}", exc_info=True)
            raise
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

    # If no valid Google API key OR model is an OpenRouter path, use OpenRouter
    if not _is_valid_google_key() or model.startswith("google/"):
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

    # If no valid Google API key OR model is an OpenRouter path, use OpenRouter
    if not _is_valid_google_key() or model.startswith("google/"):
        logger.info(f"[Vision] Routing to OpenRouter for segmentation with {model}")
        from app.services.openrouter import segment_image as openrouter_segment_image
        return await openrouter_segment_image(image_data, objects_to_segment, model)

    logger.info(f"[Vision] Analyzing image for: {objects_to_segment}")
    
    return {
        "segmentation_data": "Segmentation not fully implemented in migration.",
        "color_map": {},
        "type": "text"
    }
