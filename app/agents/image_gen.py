"""Image Gen Agent for image generation.

The Image Gen Agent generates images from assembled prompts
using the configured image generation model.

Examples:
    >>> from app.agents.image_gen import ImageGenAgent
    >>> agent = ImageGenAgent()
    >>> result = await agent.run("A photorealistic scene of...")
    >>> print(len(result.content))  # Base64 image data

Tests:
    - tests/unit/test_agents/test_image_gen.py::test_image_gen_initialization
    - tests/integration/test_image_gen.py::test_image_generation
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_router import LLMRouter
from app.core.providers import ModelCapability

logger = logging.getLogger(__name__)


@dataclass
class ImageGenResult:
    """Result from image generation.

    Attributes:
        image_base64: Base64-encoded image data
        format: Image format (png, jpeg, etc.)
        width: Image width in pixels
        height: Image height in pixels
        prompt_used: The prompt that was used
        model_used: The model that generated the image
    """

    image_base64: str
    format: str = "png"
    width: int = 1024
    height: int = 1024
    prompt_used: str = ""
    model_used: str | None = None


@dataclass
class ImageGenInput:
    """Input for image generation.

    Attributes:
        prompt: The image generation prompt
        style: Optional style modifier
        aspect_ratio: Aspect ratio (1:1, 16:9, etc.)
        quality: Quality setting (standard, hd)
    """

    prompt: str
    style: str | None = None
    aspect_ratio: str = "1:1"
    quality: str = "standard"


class ImageGenAgent(BaseAgent[ImageGenInput, ImageGenResult]):
    """Agent that generates images from prompts.

    Uses the configured image generation model
    (e.g., Imagen 3, Nano Banana Pro) to create images.

    Attributes:
        name: "ImageGenAgent"
        capability: ModelCapability.IMAGE

    Examples:
        >>> agent = ImageGenAgent()
        >>> result = await agent.run(ImageGenInput(
        ...     prompt="A photorealistic scene of the signing...",
        ...     style="photorealistic",
        ...     aspect_ratio="16:9"
        ... ))
        >>> if result.success:
        ...     save_image(result.content.image_base64)

    Tests:
        - tests/unit/test_agents/test_image_gen.py::test_initialization
        - tests/integration/test_image_gen.py::test_generate_image
    """

    # Image generation uses special capability
    capability = ModelCapability.IMAGE
    response_model = ImageGenResult  # Not used for image gen

    def __init__(
        self,
        router: LLMRouter | None = None,
    ) -> None:
        """Initialize Image Gen Agent."""
        super().__init__(router=router, name="ImageGenAgent")

    def get_system_prompt(self) -> str:
        """Not used for image generation."""
        return ""

    def get_prompt(self, input_data: ImageGenInput) -> str:
        """Get the formatted image prompt."""
        prompt = input_data.prompt

        # Add style modifier if provided
        if input_data.style:
            prompt = f"{input_data.style} style: {prompt}"

        return prompt

    async def run(self, input_data: ImageGenInput) -> AgentResult[ImageGenResult]:
        """Generate an image from the prompt.

        Args:
            input_data: ImageGenInput with prompt and settings

        Returns:
            AgentResult containing ImageGenResult with base64 image

        Note:
            This agent uses the router's generate_image method
            rather than the standard call_structured method.
        """
        start_time = time.perf_counter()

        try:
            prompt = self.get_prompt(input_data)

            logger.debug(f"{self.name}: generating image")

            response = await self.router.generate_image(
                prompt=prompt,
                aspect_ratio=input_data.aspect_ratio,
            )

            latency = int((time.perf_counter() - start_time) * 1000)

            # Create result
            result_data = ImageGenResult(
                image_base64=response.content,
                prompt_used=prompt,
                model_used=response.model,
            )

            logger.debug(f"{self.name}: generated in {latency}ms")

            return AgentResult(
                success=True,
                content=result_data,
                latency_ms=latency,
                model_used=response.model,
            )

        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            error_msg = str(e)

            logger.error(f"{self.name}: failed - {error_msg}")

            return AgentResult(
                success=False,
                error=error_msg,
                latency_ms=latency,
            )
