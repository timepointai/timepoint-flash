"""Judge step schema for query validation.

The Judge determines if a query is valid for timepoint generation
and classifies its type.

Examples:
    >>> from app.schemas.judge import JudgeResult, QueryType
    >>> result = JudgeResult(
    ...     is_valid=True,
    ...     query_type=QueryType.HISTORICAL,
    ...     cleaned_query="Signing of the Declaration of Independence",
    ...     confidence=0.95
    ... )

Tests:
    - tests/unit/test_schemas.py::test_judge_result_valid
    - tests/unit/test_schemas.py::test_judge_result_invalid
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class QueryType(str, Enum):
    """Types of temporal queries.

    Determines the generation approach and validation rules.
    """

    HISTORICAL = "historical"  # Real historical event
    FICTIONAL = "fictional"  # Fictional/literary scene
    SPECULATIVE = "speculative"  # "What if" scenarios
    CONTEMPORARY = "contemporary"  # Modern/recent events
    INVALID = "invalid"  # Not a valid temporal query


class JudgeResult(BaseModel):
    """Result of query validation by the Judge step.

    Attributes:
        is_valid: Whether the query can be processed
        query_type: Classification of the query
        cleaned_query: Normalized/improved query text
        confidence: Confidence score (0-1)
        reason: Explanation for invalid queries
        suggested_query: Alternative if invalid

    Examples:
        >>> result = JudgeResult(
        ...     is_valid=True,
        ...     query_type=QueryType.HISTORICAL,
        ...     cleaned_query="The signing of the Declaration of Independence"
        ... )
    """

    is_valid: bool = Field(..., description="Whether query is valid for generation")
    query_type: QueryType = Field(
        default=QueryType.HISTORICAL,
        description="Classification of the temporal query",
    )
    cleaned_query: str | None = Field(
        default=None,
        description="Normalized/improved version of the query (null for invalid queries)",
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score for the judgment",
    )
    reason: str | None = Field(
        default=None,
        description="Explanation if query is invalid",
    )
    suggested_query: str | None = Field(
        default=None,
        description="Alternative query suggestion if invalid",
    )

    # Metadata extracted during judging
    detected_year: int | None = Field(
        default=None,
        description="Year detected in query (if any)",
    )
    detected_location: str | None = Field(
        default=None,
        description="Location detected in query (if any)",
    )
    detected_figures: list[str] = Field(
        default_factory=list,
        description="Historical figures detected in query",
    )
