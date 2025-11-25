"""
OpenRouter API integration for multi-model LLM access.

Supports:
- Llama 4 Scout (free) - input validation
- Gemini 2.5 Flash Image Preview - image generation
- Llama 4 Maverick (free) - test validation
"""
import httpx
from pydantic import BaseModel
from typing import Type, TypeVar, Optional
import instructor
from app.config import settings

T = TypeVar('T', bound=BaseModel)


async def call_llm(
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_model: Type[T],
    temperature: float = 0.7,
    max_tokens: int = 16000  # Increased from 2000 - models support 4K-128K tokens
) -> T:
    """
    Call OpenRouter API with structured output using instructor.

    Args:
        model: Model name (e.g., "meta-llama/llama-4-scout:free")
        system_prompt: System instructions
        user_prompt: User message
        response_model: Pydantic model for structured output
        temperature: Sampling temperature (0-1)
        max_tokens: Maximum tokens to generate

    Returns:
        Parsed response in the specified Pydantic model format
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"[LLM] Calling model: {model}")
    logger.info(f"[LLM] Response model: {response_model.__name__}")
    logger.info(f"[LLM] User prompt: {user_prompt[:200]}...")

    from openai import AsyncOpenAI

    # Create OpenAI-compatible client for OpenRouter
    openai_client = AsyncOpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL
    )

    # Patch with instructor for structured outputs
    # Use JSON mode instead of function calling to avoid multiple tool calls error
    # Free models like llama-4-scout don't support function calling properly
    instructor_client = instructor.from_openai(openai_client, mode=instructor.Mode.JSON)

    try:
        logger.info(f"[LLM] Sending request to OpenRouter...")
        response = await instructor_client.chat.completions.create(
            model=model,
            response_model=response_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        logger.info(f"[LLM] Response received successfully")
        return response
    except Exception as e:
        logger.error(f"[LLM] Error calling {model}: {str(e)}", exc_info=True)
        raise


async def generate_image(
    prompt: str,
    model: str = None
) -> str:
    """
    Generate image using Gemini 2.5 Flash Image via OpenRouter.

    Args:
        prompt: Image generation prompt
        model: Model to use (defaults to IMAGE_MODEL from settings)

    Returns:
        Base64 encoded image data URL
    """
    import logging
    logger = logging.getLogger(__name__)

    if model is None:
        model = settings.IMAGE_MODEL

    logger.info(f"[IMAGE_GEN] Generating image with model: {model}")
    logger.info(f"[IMAGE_GEN] Prompt length: {len(prompt)} chars")

    from openai import AsyncOpenAI

    # Create OpenAI-compatible client for OpenRouter
    client = AsyncOpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL
    )

    try:
        # Gemini Flash Image uses chat completions with modalities to generate images
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt  # Just the prompt, not "Generate an image:"
                }
            ],
            extra_body={
                "modalities": ["image", "text"]  # Required for image generation
            },
            max_tokens=4096
        )

        # Log response received (skip model dump to avoid base64 in logs)
        logger.info(f"[IMAGE_GEN] Response received: {type(response)}")

        # Extract image from response
        # OpenRouter returns images in the "images" field, not "content"
        if response.choices and len(response.choices) > 0:
            choice = response.choices[0]
            message = choice.message

            # Check for images field (OpenRouter format)
            if hasattr(message, 'images') and message.images:
                logger.info(f"[IMAGE_GEN] Found {len(message.images)} image(s) in response")
                # Get the first image
                image_obj = message.images[0]
                logger.info(f"[IMAGE_GEN] Image object type: {type(image_obj)}")

                # Extract URL from image object
                if hasattr(image_obj, 'image_url'):
                    image_url = image_obj.image_url
                    if hasattr(image_url, 'url'):
                        url = image_url.url
                    else:
                        url = image_url
                elif hasattr(image_obj, 'url'):
                    url = image_obj.url
                elif isinstance(image_obj, dict):
                    url = image_obj.get('image_url', {}).get('url') or image_obj.get('url')
                else:
                    url = str(image_obj)

                # Log image type without base64 data
                if str(url).startswith('data:image'):
                    logger.info(f"[IMAGE_GEN] Extracted base64 image successfully")
                else:
                    logger.info(f"[IMAGE_GEN] Extracted image URL: {str(url)[:100]}...")

                if url and (url.startswith('data:image') or url.startswith('http')):
                    logger.info(f"[IMAGE_GEN] Image generated successfully")
                    return url
                else:
                    url_preview = "base64 data" if str(url).startswith('data:') else str(url)[:100]
                    logger.error(f"[IMAGE_GEN] Invalid image URL format: {url_preview}")
                    raise Exception("Invalid image URL format")

            # Fallback: check content field (some models might return here)
            elif message.content:
                content = message.content
                content_preview = "base64 image data" if content.startswith('data:image') else content[:100]
                logger.info(f"[IMAGE_GEN] No images field, checking content: {content_preview}...")

                if content.startswith('data:image') or content.startswith('http'):
                    logger.info(f"[IMAGE_GEN] Image found in content field")
                    return content
                else:
                    logger.error(f"[IMAGE_GEN] Content exists but is not an image: {content[:100]}")
                    raise Exception("No image data in response. Content is text, not image.")
            else:
                logger.error(f"[IMAGE_GEN] No images field and no content in message")
                raise Exception("No image data in response. Message has neither images nor content.")
        else:
            logger.error(f"[IMAGE_GEN] No choices in response")
            raise Exception("No choices in response")

    except Exception as e:
        logger.error(f"[IMAGE_GEN] Failed to generate image: {str(e)}", exc_info=True)
        raise


async def segment_image(
    image_data: str,
    objects_to_segment: list[str],
    model: str = None
) -> dict:
    """
    Perform conversational image segmentation using Gemini 2.5 Flash Image.

    Requests a painted segmented image where each character is highlighted with
    a different colored overlay, using Gemini's segmentation capabilities.

    Args:
        image_data: Base64 image data or URL
        objects_to_segment: List of character names to segment (e.g., ["Benjamin Franklin", "George Washington"])
        model: Model to use (defaults to IMAGE_MODEL from settings)

    Returns:
        Dict with segmented image URL (painted overlay) or text description
    """
    import logging
    logger = logging.getLogger(__name__)

    if model is None:
        model = settings.IMAGE_MODEL

    logger.info(f"[IMAGE_SEG] Requesting painted segmentation for: {objects_to_segment[:5]}...")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL
    )

    try:
        # Create segmentation prompt requesting painted overlay with color map
        character_list = ', '.join(objects_to_segment[:10])  # Limit to first 10
        seg_prompt = f"""Generate a segmented version of this image where each of these people is highlighted with a different brightly colored transparent overlay:

{character_list}

Use these specific colors:
1st person: bright magenta/pink (#FF00FF)
2nd person: cyan (#00FFFF)
3rd person: yellow (#FFFF00)
4th person: lime green (#00FF00)
5th person: orange (#FF8000)
6th person: deep pink (#FF1493)
7th person: aqua (#00CED1)
8th person: gold (#FFD700)
9th person: chartreuse (#7FFF00)
10th person: hot pink (#FF69B4)

Paint over each person with a semi-transparent colored mask while keeping the original image visible underneath. Only highlight people who are actually present and identifiable in the image.

After generating the image, also provide a JSON color map in your text response showing which character got which color."""

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": seg_prompt
                        }
                    ]
                }
            ],
            extra_body={
                "modalities": ["image", "text"]  # Request both image and text
            },
            max_tokens=4096
        )

        # Check for segmented image in response
        if response.choices and len(response.choices) > 0:
            choice = response.choices[0]
            message = choice.message

            # Build default color map
            color_map = {
                objects_to_segment[i]: [
                    "#FF00FF", "#00FFFF", "#FFFF00", "#00FF00", "#FF8000",
                    "#FF1493", "#00CED1", "#FFD700", "#7FFF00", "#FF69B4"
                ][i] if i < 10 else "#FFFFFF"
                for i in range(len(objects_to_segment))
            }

            # Extract color map from text if present
            text_content = message.content if message.content else ""

            # Try to parse JSON color map from text
            import json
            import re
            json_match = re.search(r'\{[^{}]*"[^"]+"\s*:\s*"#[0-9A-Fa-f]{6}"[^{}]*\}', text_content)
            if json_match:
                try:
                    parsed_map = json.loads(json_match.group(0))
                    color_map.update(parsed_map)
                    logger.info(f"[IMAGE_SEG] Parsed color map: {color_map}")
                except:
                    pass

            # Check for images field (segmented image)
            if hasattr(message, 'images') and message.images:
                logger.info(f"[IMAGE_SEG] Found segmented image in response")
                image_obj = message.images[0]

                # Extract URL from image object
                if hasattr(image_obj, 'image_url'):
                    image_url = image_obj.image_url
                    if hasattr(image_url, 'url'):
                        url = image_url.url
                    else:
                        url = image_url
                elif hasattr(image_obj, 'url'):
                    url = image_obj.url
                elif isinstance(image_obj, dict):
                    url = image_obj.get('image_url', {}).get('url') or image_obj.get('url')
                else:
                    url = str(image_obj)

                if str(url).startswith('data:image'):
                    logger.info(f"[IMAGE_SEG] Segmented image generated successfully (base64)")
                else:
                    logger.info(f"[IMAGE_SEG] Segmented image URL: {str(url)[:100]}...")

                return {
                    "segmentation_image": url,
                    "color_map": color_map,
                    "type": "image"
                }

            # Fallback: text description
            elif text_content:
                # Check if it's a refusal message
                refusal_keywords = ["cannot", "sorry", "unable", "can't", "apologize", "not able to", "don't have the ability"]
                is_refusal = any(keyword in text_content.lower() for keyword in refusal_keywords)

                if is_refusal:
                    logger.info(f"[IMAGE_SEG] Model refused segmentation request")
                    raise Exception("Segmentation not available - model refused request")

                logger.info(f"[IMAGE_SEG] Got text description instead of image: {text_content[:100]}...")
                return {
                    "segmentation_data": text_content,
                    "color_map": color_map,
                    "type": "text"
                }
            else:
                raise Exception("No segmentation data in response")
        else:
            raise Exception("No choices in response")

    except Exception as e:
        logger.error(f"[IMAGE_SEG] Segmentation failed: {str(e)}", exc_info=True)
        raise
