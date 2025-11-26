"""
Mock fixtures for offline e2e testing.

Provides cached responses for external API calls to enable:
1. Faster test execution (no actual API calls)
2. Offline development/testing
3. Cost reduction (no API credits used)
4. Deterministic test behavior

Usage:
    Set USE_MOCKS=true environment variable to use mocks instead of real APIs.

    pytest -m e2e  # Real API calls
    USE_MOCKS=true pytest -m e2e  # Mock responses
"""
import os
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, Optional


def is_mocking_enabled() -> bool:
    """Check if mocking is enabled via environment variable."""
    return os.getenv("USE_MOCKS", "false").lower() in ("true", "1", "yes")


def create_mock_image(
    width: int = 1024,
    height: int = 1024,
    text: str = "Mock Image",
    format: str = "PNG"
) -> str:
    """
    Create a mock base64-encoded image for testing.

    Args:
        width: Image width (default: 1024)
        height: Image height (default: 1024)
        text: Text to display on image (default: "Mock Image")
        format: Image format (default: "PNG")

    Returns:
        Base64-encoded image string with data URI prefix
    """
    # Create a simple colored image
    img = Image.new('RGB', (width, height), color=(73, 109, 137))

    # Add text
    draw = ImageDraw.Draw(img)
    try:
        # Try to use a built-in font
        font = ImageFont.load_default()
    except:
        font = None

    # Calculate text position (centered)
    if font:
        # Get bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    else:
        text_width = len(text) * 6  # Approximate
        text_height = 10

    x = (width - text_width) // 2
    y = (height - text_height) // 2

    draw.text((x, y), text, fill=(255, 255, 255), font=font)

    # Convert to base64
    buffer = BytesIO()
    img.save(buffer, format=format)
    img_bytes = buffer.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode('utf-8')

    # Return with data URI prefix
    return f"data:image/{format.lower()};base64,{img_b64}"


# Mock LLM Responses
MOCK_LLM_RESPONSES = {
    "judge_valid": {
        "is_valid": True,
        "cleaned_query": "Medieval marketplace in London, winter 1250",
        "rejection_reason": None
    },
    "judge_invalid_future": {
        "is_valid": False,
        "cleaned_query": "",
        "rejection_reason": "Query contains a far-future date beyond 2024"
    },
    "judge_invalid_fictional": {
        "is_valid": False,
        "cleaned_query": "",
        "rejection_reason": "Query appears to be asking for a fictional or fantasy scene"
    },
    "timeline_medieval": {
        "year": 1250,
        "season": "winter",
        "location": "London, England",
        "exact_date": None,
        "slug": "london-marketplace-1250-winter"
    },
    "scene_medieval": {
        "setting": {
            "location_type": "outdoor",
            "environment": "Bustling medieval marketplace with wooden stalls",
            "time_of_day": "10:23 AM",
            "architecture_style": "Medieval timber-frame buildings",
            "time_period_details": "Wattle and daub construction, thatched roofs",
            "atmosphere": "Busy and lively with merchants calling out"
        },
        "weather": {
            "condition": "Overcast with light snow",
            "temperature": "Cold",
            "lighting": "Dim and gray"
        },
        "props": [
            {
                "name": "Wooden stall",
                "description": "Rough-hewn timber market stall with goods displayed",
                "location": "Center of scene",
                "historical_significance": "Common marketplace structure"
            },
            {
                "name": "Iron pot",
                "description": "Cast iron cooking pot hanging from a hook",
                "location": "Merchant stall on left",
                "historical_significance": "Essential cooking vessel"
            }
        ],
        "background_details": "Narrow cobblestone streets, medieval buildings with overhanging upper floors",
        "historical_context": "13th century London during the reign of Henry III"
    },
    "characters_medieval": {
        "characters": [
            {
                "name": "Thomas the Merchant",
                "age": 45,
                "gender": "male",
                "role": "Cloth merchant",
                "appearance": "Weathered face with graying beard, stocky build",
                "clothing": "Brown wool tunic, leather apron, felt cap",
                "social_class": "Merchant class",
                "personality": "Shrewd but fair trader",
                "background": "Third-generation cloth merchant",
                "motivations": "Provide for his family, expand business"
            },
            {
                "name": "Eleanor the Baker's Wife",
                "age": 32,
                "gender": "female",
                "role": "Baker's wife selling bread",
                "appearance": "Round face, kind eyes, flour-dusted hands",
                "clothing": "Simple linen kirtle, wool cloak, white coif",
                "social_class": "Craftsman class",
                "personality": "Warm and generous",
                "background": "Married to the local baker",
                "motivations": "Support her husband's business"
            }
        ],
        "crowd_present": True,
        "crowd_description": "Various townspeople browsing the market stalls"
    },
    "dialog_medieval": {
        "lines": [
            {
                "speaker": "Thomas the Merchant",
                "text": "Fine Flemish cloth, milady! Warmest wool in all of London!",
                "tone": "Enthusiastic",
                "action": "Gesturing to fabric bolts on his stall"
            },
            {
                "speaker": "Eleanor the Baker's Wife",
                "text": "Fresh bread, baked this morning! Tuppence a loaf!",
                "tone": "Cheerful",
                "action": "Holding up a round loaf"
            }
        ],
        "context": "Merchants calling out to potential customers in the marketplace"
    }
}


def get_mock_llm_response(model: str, prompt: str, response_type: str = "auto") -> Dict[str, Any]:
    """
    Get a mock LLM response for testing.

    Args:
        model: Model name (e.g., "gemini-1.5-flash", "gemini-1.5-pro")
        prompt: The prompt text (used to determine which mock to return)
        response_type: Type of response expected (auto-detected if not specified)

    Returns:
        Mock response dictionary
    """
    if not is_mocking_enabled():
        raise ValueError("Mocking not enabled. Set USE_MOCKS=true")

    # Auto-detect response type from prompt
    if response_type == "auto":
        if "validate" in prompt.lower() or "judge" in prompt.lower():
            if "future" in prompt.lower():
                response_type = "judge_invalid_future"
            elif "fictional" in prompt.lower() or "fantasy" in prompt.lower():
                response_type = "judge_invalid_fictional"
            else:
                response_type = "judge_valid"
        elif "timeline" in prompt.lower() or "temporal" in prompt.lower():
            response_type = "timeline_medieval"
        elif "scene" in prompt.lower() and "setting" in prompt.lower():
            response_type = "scene_medieval"
        elif "character" in prompt.lower():
            response_type = "characters_medieval"
        elif "dialog" in prompt.lower():
            response_type = "dialog_medieval"
        else:
            response_type = "judge_valid"  # Default

    return MOCK_LLM_RESPONSES.get(response_type, MOCK_LLM_RESPONSES["judge_valid"])


# Mock Image Generation Response
MOCK_IMAGE = create_mock_image(
    width=1024,
    height=1024,
    text="Mock Medieval Scene",
    format="PNG"
)


def get_mock_image(prompt: str) -> str:
    """
    Get a mock generated image for testing.

    Args:
        prompt: The image generation prompt (unused, for compatibility)

    Returns:
        Base64-encoded PNG image with data URI prefix
    """
    if not is_mocking_enabled():
        raise ValueError("Mocking not enabled. Set USE_MOCKS=true")

    return MOCK_IMAGE


# Mock Timepoint Data (complete example)
MOCK_TIMEPOINT_COMPLETE = {
    "id": "mock-uuid-1234",
    "slug": "london-marketplace-1250-winter",
    "year": 1250,
    "season": "winter",
    "location": "London, England",
    "input_query": "Medieval marketplace in London, winter 1250",
    "cleaned_query": "Medieval marketplace in London, winter 1250",
    "image_url": MOCK_IMAGE,
    "segmented_image_url": create_mock_image(text="Segmented", format="PNG"),
    "character_data_json": MOCK_LLM_RESPONSES["characters_medieval"]["characters"],
    "dialog_json": MOCK_LLM_RESPONSES["dialog_medieval"]["lines"],
    "scene_graph_json": {
        "nodes": [
            {"id": "char_1", "type": "character", "name": "Thomas the Merchant"},
            {"id": "char_2", "type": "character", "name": "Eleanor the Baker's Wife"},
            {"id": "prop_1", "type": "prop", "name": "Wooden stall"}
        ],
        "edges": [
            {"source": "char_1", "target": "prop_1", "relation": "stands_behind"}
        ]
    },
    "metadata_json": {
        "setting": MOCK_LLM_RESPONSES["scene_medieval"]["setting"],
        "weather": MOCK_LLM_RESPONSES["scene_medieval"]["weather"],
        "historical_context": MOCK_LLM_RESPONSES["scene_medieval"]["historical_context"]
    },
    "processing_time_ms": 45000,
    "created_at": "2024-11-26T12:00:00Z",
    "status": "completed"
}


def get_mock_timepoint(query: str, email: str = "test@example.com") -> Dict[str, Any]:
    """
    Get a mock complete timepoint for testing.

    Args:
        query: The original query (used to customize response)
        email: Email address for the timepoint

    Returns:
        Complete mock timepoint dictionary
    """
    if not is_mocking_enabled():
        raise ValueError("Mocking not enabled. Set USE_MOCKS=true")

    # Customize based on query
    mock_tp = MOCK_TIMEPOINT_COMPLETE.copy()
    mock_tp["input_query"] = query
    mock_tp["cleaned_query"] = query

    return mock_tp
