"""Prompt templates for generation pipeline.

Each module provides the system and user prompts for a pipeline step.

Examples:
    >>> from app.prompts import judge, timeline, scene
    >>> prompt = judge.get_prompt("signing of the declaration")
"""

from app.prompts import (
    camera,
    character_bio,
    character_identification,
    characters,
    dialog,
    graph,
    image_prompt,
    judge,
    moment,
    scene,
    timeline,
)

__all__ = [
    "judge",
    "timeline",
    "scene",
    "characters",
    "character_identification",
    "character_bio",
    "moment",
    "dialog",
    "camera",
    "graph",
    "image_prompt",
]
