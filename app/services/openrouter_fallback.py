"""
Fallback to OpenRouter for features not yet fully stable in Google SDK.
"""
from app.config import settings
import logging

logger = logging.getLogger(__name__)

async def generate_image_fallback(prompt: str, model: str = None) -> str:
    """
    Generate image using OpenRouter (e.g. google/gemini-2.5-flash-image).
    """
    if not settings.OPENROUTER_API_KEY:
        raise Exception("OpenRouter API key not set for fallback.")

    if model is None:
        # Use the one from config, defaulting to something OpenRouter understands
        # if the main IMAGE_MODEL is an Imagen ID, we might need to map it.
        # For now, assume the config might have a fallback or we use a hardcoded one.
        model = "google/gemini-2.5-flash-image"

    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL
    )

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            extra_body={"modalities": ["image", "text"]},
            max_tokens=4096
        )

        if response.choices and len(response.choices) > 0:
            message = response.choices[0].message
            if hasattr(message, 'images') and message.images:
                image_obj = message.images[0]
                # Handle object or dict
                if hasattr(image_obj, 'url'):
                    return image_obj.url
                elif isinstance(image_obj, dict):
                    return image_obj.get('url')
                return str(image_obj)
            elif message.content and (message.content.startswith('http') or message.content.startswith('data:')):
                return message.content
                
        raise Exception("No image in response")

    except Exception as e:
        logger.error(f"OpenRouter fallback failed: {e}")
        raise

