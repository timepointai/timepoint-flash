"""Pydantic schemas for generation pipeline.

Re-exports all schemas for convenient imports.

Examples:
    >>> from app.schemas import JudgeResult, TimelineData, SceneData
    >>> result = JudgeResult(is_valid=True, query_type="historical")
"""

from app.schemas.camera import CameraData
from app.schemas.characters import Character, CharacterData, CharacterRole
from app.schemas.character_identification import CharacterIdentification, CharacterStub
from app.schemas.dialog import DialogData, DialogLine
from app.schemas.graph import Faction, GraphData, Relationship
from app.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatRole,
    ChatSession,
    ChatSessionSummary,
    ChatStreamEvent,
    CharacterSurveyResponse,
    DialogExtensionRequest,
    DialogExtensionResponse,
    DialogStreamEvent,
    ResponseFormat,
    SurveyMode,
    SurveyRequest,
    SurveyResult,
    SurveyStreamEvent,
)
from app.schemas.image_prompt import ImagePromptData
from app.schemas.judge import JudgeResult, QueryType
from app.schemas.moment import MomentData
from app.schemas.scene import SceneData, SensoryDetail
from app.schemas.timeline import TimelineData

__all__ = [
    # Judge
    "JudgeResult",
    "QueryType",
    # Timeline
    "TimelineData",
    # Scene
    "SceneData",
    "SensoryDetail",
    # Characters
    "Character",
    "CharacterData",
    "CharacterRole",
    # Character Identification (for parallel generation)
    "CharacterIdentification",
    "CharacterStub",
    # Moment
    "MomentData",
    # Dialog
    "DialogData",
    "DialogLine",
    # Camera
    "CameraData",
    # Graph
    "GraphData",
    "Relationship",
    "Faction",
    # Image Prompt
    "ImagePromptData",
    # Chat & Interactions
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ChatRole",
    "ChatSession",
    "ChatSessionSummary",
    "ChatStreamEvent",
    "CharacterSurveyResponse",
    "DialogExtensionRequest",
    "DialogExtensionResponse",
    "DialogStreamEvent",
    "ResponseFormat",
    "SurveyMode",
    "SurveyRequest",
    "SurveyResult",
    "SurveyStreamEvent",
]
