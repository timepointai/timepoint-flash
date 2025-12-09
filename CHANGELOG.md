# Changelog

All notable changes to TIMEPOINT Flash will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Claude Opus 4.5 and Sonnet 4.5 to demo.sh model selection menu (11 models total)

### Fixed
- Image generation `response_modalities` configuration (`["TEXT", "IMAGE"]` per Google docs)
- test-demo.sh query validation (use valid historical query for JudgeAgent)

## [2.2.0] - 2025-12-04

### Added
- Model selection for character interactions (chat, dialog, survey)
- `ResponseFormat` enum: STRUCTURED, TEXT, AUTO
- `TextModelConfig` dataclass for model capability detection
- `TEXT_MODEL_REGISTRY` with known model configurations
- Demo CLI model picker with 7 model options

### Changed
- Interaction agents now accept `model` and `response_format` parameters
- `_should_use_structured()` method determines response format based on model capabilities

## [2.1.0] - 2025-12-04

### Added
- Character chat system with `CharacterChatAgent`
- Dialog extension with `DialogExtensionAgent`
- Survey system with `SurveyAgent` (parallel and sequential modes)
- SSE streaming for all interaction endpoints
- Sentiment analysis for survey responses
- Emotional tone detection
- In-memory session management with conversation history
- New API endpoints: `/api/v1/interactions/`

### Changed
- LLMRouter now has `stream()` async generator method

## [2.0.11] - 2025-12-03

### Added
- `VerifiedModels` class for bulletproof model validation
- Startup validation with `validate_presets_or_raise()`
- Fallback hardening with verified models only

### Fixed
- `CREATIVE_MODEL` default changed from unavailable model to `gemini-2.5-flash`

## [2.0.10] - 2025-12-03

### Added
- Comprehensive test suite `test-demo.sh` v2.0.5 with bulk testing

### Fixed
- HD preset `text_model` to use working `gemini-2.5-pro-preview`
- SSE start event now includes `preset` in data payload

## [2.0.9] - 2025-12-03

### Added
- Token bucket rate limiter for proactive rate limiting
- Tier-based rate limits: FREE (8 rpm), PAID (45 rpm), NATIVE (58 rpm)
- Graceful degradation after consecutive failures

### Changed
- Transient error retry now includes 500/502/503/504 errors

## [2.0.8] - 2025-12-03

### Added
- Hyper parallelism mode with `ParallelismMode` enum
- Optimized execution flow for AGGRESSIVE/MAX modes
- Provider-aware concurrent call limits

## [2.0.7] - 2025-12-03

### Added
- Graph-informed character bios with relationship context
- Three-phase character generation: CharacterID -> Graph -> Parallel Bios

### Changed
- Character bio prompt includes "RELATIONSHIP GRAPH" section

## [2.0.6] - 2025-12-03

### Added
- Adaptive parallelism with `ModelTier` classification
- Proactive execution planning with `_plan_execution()`
- 19 tests for tier detection

### Changed
- FREE models run sequentially to prevent rate limits

## [2.0.5] - 2025-12-02

### Added
- Parallel character bio generation
- `CharacterIdentificationAgent` and `CharacterBioAgent`
- New prompts for character identification and bio generation

## [2.0.4] - 2025-12-02

### Added
- Parallel pipeline execution with `asyncio.gather()`
- `PIPELINE_MAX_PARALLELISM` configuration (1-5)
- Semaphore-controlled concurrency

### Fixed
- macOS millisecond timing in demo CLI

## [2.0.3] - 2025-12-02

### Added
- Free model discovery API (`/api/v1/models/free`)
- Rate limit cascade fallback (free -> paid -> Google)
- RAPID TEST and RAPID TEST FREE in demo CLI

### Fixed
- Image generation model format mismatch
- Schema type annotations for MomentData, CameraData, CharacterData

## [2.0.1] - 2025-12-01

### Added
- Real-time streaming pipeline with async generator
- Interactive demo CLI (`demo.sh`)
- Server runner script (`run.sh`)
- `include_image` query parameter on GET endpoint

## [2.0.0] - 2025-12-01

### Added
- Complete rewrite with 10 specialized AI agents
- Multi-provider support (Google AI, OpenRouter)
- FastAPI with async SQLAlchemy
- SSE streaming for generation progress
- Temporal navigation API (next/prior/sequence)
- Model discovery API
- Docker deployment with PostgreSQL
- Railway and Render deployment configs
- Alembic database migrations
- 265+ unit tests

### Changed
- Architecture redesigned with LangGraph-style agent patterns
- Pydantic v2 schemas throughout

[2.2.0]: https://github.com/realityinspector/timepoint-flash/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/realityinspector/timepoint-flash/compare/v2.0.11...v2.1.0
[2.0.11]: https://github.com/realityinspector/timepoint-flash/compare/v2.0.10...v2.0.11
[2.0.10]: https://github.com/realityinspector/timepoint-flash/compare/v2.0.9...v2.0.10
[2.0.9]: https://github.com/realityinspector/timepoint-flash/compare/v2.0.8...v2.0.9
[2.0.8]: https://github.com/realityinspector/timepoint-flash/compare/v2.0.7...v2.0.8
[2.0.7]: https://github.com/realityinspector/timepoint-flash/compare/v2.0.6...v2.0.7
[2.0.6]: https://github.com/realityinspector/timepoint-flash/compare/v2.0.5...v2.0.6
[2.0.5]: https://github.com/realityinspector/timepoint-flash/compare/v2.0.4...v2.0.5
[2.0.4]: https://github.com/realityinspector/timepoint-flash/compare/v2.0.3...v2.0.4
[2.0.3]: https://github.com/realityinspector/timepoint-flash/compare/v2.0.1...v2.0.3
[2.0.1]: https://github.com/realityinspector/timepoint-flash/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/realityinspector/timepoint-flash/releases/tag/v2.0.0
