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
    """
    try:
        # Use configured model or fallback to config default
        # Map "judge" etc to actual model names if passed generic names
        actual_model = model
        if model == "judge":
            actual_model = settings.JUDGE_MODEL
        elif model == "creative":
            actual_model = settings.CREATIVE_MODEL
            
        logger.info(f"[GoogleAI] Calling {actual_model}")

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
                response_schema=response_model
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
    Returns: Base64 data URL or public URL if available.
    """
    if not model:
        model = settings.IMAGE_MODEL

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
    """
    if not model:
        model = settings.CREATIVE_MODEL 

    logger.info(f"[Vision] Analyzing image for: {objects_to_segment}")
    
    return {
        "segmentation_data": "Segmentation not fully implemented in migration.",
        "color_map": {},
        "type": "text"
    }
