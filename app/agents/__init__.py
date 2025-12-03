"""Agent modules for timepoint generation pipeline.

Each agent handles a specific step in the generation process,
using Mirascope-style decorators for structured LLM outputs.

Agent Order:
    1. Judge Agent - Query validation
    2. Timeline Agent - Temporal extraction
    3. Scene Agent - Environment generation
    4. Characters Agent - Character creation (max 8)
    5. Moment Agent - Plot and tension
    6. Dialog Agent - Dialog generation (max 7 lines)
    7. Camera Agent - Composition and framing
    8. Graph Agent - Relationship mapping
    9. Image Prompt Agent - Prompt assembly
    10. Image Gen Agent - Image generation
    11. Segmentation Agent - Character masks

Examples:
    >>> from app.agents import JudgeAgent, TimelineAgent
    >>> agent = JudgeAgent(router)
    >>> result = await agent.run("signing of the declaration")

Tests:
    - tests/unit/test_agents/*.py
"""

from app.agents.base import BaseAgent
from app.agents.judge import JudgeAgent
from app.agents.timeline import TimelineAgent
from app.agents.scene import SceneAgent
from app.agents.characters import CharactersAgent
from app.agents.character_identification import CharacterIdentificationAgent
from app.agents.character_bio import CharacterBioAgent
from app.agents.moment import MomentAgent
from app.agents.dialog import DialogAgent
from app.agents.camera import CameraAgent
from app.agents.graph import GraphAgent
from app.agents.image_prompt import ImagePromptAgent
from app.agents.image_gen import ImageGenAgent

__all__ = [
    "BaseAgent",
    "JudgeAgent",
    "TimelineAgent",
    "SceneAgent",
    "CharactersAgent",
    "CharacterIdentificationAgent",
    "CharacterBioAgent",
    "MomentAgent",
    "DialogAgent",
    "CameraAgent",
    "GraphAgent",
    "ImagePromptAgent",
    "ImageGenAgent",
]
