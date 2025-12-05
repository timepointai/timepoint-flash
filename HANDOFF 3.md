# HANDOFF - TIMEPOINT Flash v2.0

**Status**: v2.2.0 - Model Selection for Interactions
**Date**: 2025-12-04
**Branch**: `main`

---

## What's Done

### Phase 1: Cleanup
- GitHub cleanup complete
- v1.0 archived to `archive/v1-legacy` branch + `v1.0.0-legacy` tag
- Clean `main` branch with fresh start

### Phase 2: Core Infrastructure
- `pyproject.toml` with all dependencies
- Provider abstraction (`app/core/providers.py`)
- Google Gen AI SDK integration
- OpenRouter API client
- LLM Router with capability-based routing
- Database with SQLite + PostgreSQL support
- FastAPI app with health endpoints

### Phase 3: Generation Pipeline
- Temporal system (`app/core/temporal.py`)
- Generation schemas (`app/schemas/`)
- Prompt templates (`app/prompts/`)
- Generation pipeline (`app/core/pipeline.py`)
- API endpoints (`app/api/v1/timepoints.py`)

### Phase 4: Agent Rebuild
- **10 agents implemented** with Mirascope-style patterns
- New schemas for Moment, Camera, Graph
- New prompts for Moment, Camera, Graph
- Pipeline refactored to use agent classes

### Phase 5: API Completion
- Streaming SSE endpoint
- Delete endpoint with cascade
- Temporal navigation API (next/prior/sequence)
- Model discovery API
- Image generation integration

### Phase 6: Testing & Documentation
- **362 tests passing** (39 integration tests, 20 character parallel tests, 50 tier/parallelism tests, 25 rate limiter tests)
- Integration tests for all API endpoints
- Complete documentation suite

### Phase 7: Deployment & Production
- **Docker Setup**
  - Multi-stage Dockerfile (builder, production, development)
  - docker-compose.yml with PostgreSQL
  - docker-compose.dev.yml for development
  - Health check configuration
- **Database Migrations**
  - Alembic configuration for async SQLAlchemy
  - Initial migration for all tables
  - PostgreSQL + SQLite support
- **Cloud Deployment**
  - Railway configuration (`railway.json`)
  - Render Blueprint (`render.yaml`)
  - Environment variable templates (`.env.example`)
- **Documentation**
  - `docs/DEPLOYMENT.md` - Complete deployment guide
  - Updated README with deployment section

### Phase 8: Streaming Refactor & Developer Experience
- **Real-time Streaming Pipeline**
  - `run_streaming()` async generator in `pipeline.py`
  - Yields `(step, result, state)` after each step completes
  - True real-time SSE progress (not batched at end)
  - Step error handling with continuation
- **API Enhancements**
  - `include_image` query parameter on GET /timepoints/{id}
  - Updated streaming endpoint to use async generator
  - Better error event formatting
- **Demo CLI Improvements** (`demo.sh`)
  - Interactive timepoint browser with number selection
  - Viewer links after generation
  - Image generation prompts with auto-save/open
  - Robust bash heredoc handling via environment variables
- **Server Runner** (`run.sh`)
  - CLI flags for port, host, workers, reload
  - Production mode (`-P`) and debug mode (`-d`)
  - Colored terminal output with ASCII banner

### Phase 9: Free Model Support & Rate Limit Resilience
- **Free Model Discovery API** (`/api/v1/models/free`)
  - Real-time fetch of available free models from OpenRouter
  - `best` recommendation (highest context/capability)
  - `fastest` recommendation (Gemini Flash priority, 32K minimum context)
  - Model capability validation for structured JSON output
- **Rate Limit Cascade Fallback** (`app/core/llm_router.py`)
  - Three-tier fallback: free model → paid model → Google provider
  - Exponential backoff retry (5 attempts, 2s-120s)
  - Automatic detection of `:free` model suffixes
  - `PAID_FALLBACK_MODEL` constant for cascade target
- **Image Generation Fix**
  - Fixed model name format mismatch (OpenRouter vs Google native)
  - Default `IMAGE_MODEL` now uses native format (`gemini-2.5-flash-image`)
  - Router strips `google/` prefix for native Google provider
- **Demo CLI Enhancements** (`demo.sh`)
  - RAPID TEST - One-click hyper preset test
  - RAPID TEST FREE - Zero-cost testing with free model + native image gen
  - Custom model selection (browse, natural language, manual)
  - Anachronism mitigation prompts
  - Port conflict handling (`-k` kill flag, adaptive port)
- **Dialog Agent Improvements**
  - Historical authenticity constraints
  - Anachronism detection and avoidance
  - Period-appropriate vocabulary enforcement
- **Schema Fixes**
  - Fixed `MomentData.plot_beats` type annotation
  - Fixed `CameraData.composition` type annotation
  - Fixed `CharacterData` schema validation

### Phase 10: Parallel Pipeline Execution
- **Parallel LLM Calls** (`app/core/pipeline.py`)
  - Three-phase execution strategy for optimal parallelism
  - Phase 1 (sequential): Judge → Timeline → Scene → Characters
  - Phase 2 (parallel): Graph + Moment + Camera run concurrently
  - Phase 3 (sequential): Dialog → ImagePrompt → ImageGen
  - `asyncio.gather()` for parallel execution in `run()`
  - `asyncio.as_completed()` for streaming with parallel results
- **Configurable Parallelism** (`app/config.py`)
  - `PIPELINE_MAX_PARALLELISM` setting (1-5, default 3)
  - Semaphore-controlled concurrency to prevent rate limiting
  - Environment variable override support
- **Demo CLI Fix** (`demo.sh`)
  - Cross-platform millisecond timestamps using Python
  - Fixed macOS `date +%N` incompatibility (outputs literal "N")
  - `get_ms()` helper function for timing calculations

### Phase 11: Parallel Character Bio Generation
- **Two-Phase Character Generation** (`app/core/pipeline.py`)
  - Phase 1: `CharacterIdentificationAgent` - Fast identification of who's in the scene
  - Phase 2: `CharacterBioAgent` - Detailed bio for each character (runs in parallel!)
  - Fallback to single-call `CharactersAgent` if identification fails
- **New Schemas** (`app/schemas/character_identification.py`)
  - `CharacterStub` - Lightweight character identification
  - `CharacterIdentification` - Phase 1 result with cast context
  - `get_cast_context()` method for relationship coherence
- **New Agents** (`app/agents/`)
  - `CharacterIdentificationAgent` - Fast identification (temperature 0.5)
  - `CharacterBioAgent` - Detailed bio generation (temperature 0.7)
  - `create_fallback_character()` for error handling
- **New Prompts** (`app/prompts/`)
  - `character_identification.py` - Fast ID prompt (brief descriptions only)
  - `character_bio.py` - Single bio prompt with full cast context
- **Performance Improvement**
  - Character bios now generated in parallel (up to 8 concurrent calls)
  - Each bio call receives full cast context for relationship coherence
  - Graceful fallback with `create_fallback_character()` on individual failures

### Phase 12: Adaptive Parallelism with Model Tier Planning
- **Model Tier Classification** (`app/core/llm_router.py`)
  - `ModelTier` enum: FREE, PAID, NATIVE
  - `get_model_tier()` method on LLMRouter to classify current model
  - `get_recommended_parallelism()` method for tier-based parallelism
  - `TIER_PARALLELISM` configuration: FREE=1, PAID=2, NATIVE=3
- **Proactive Execution Planning** (`app/core/pipeline.py`)
  - `_plan_execution()` method determines parallelism before execution
  - `model_tier` property for cached tier access
  - `use_parallel_characters` property: FALSE for FREE tier
  - Execution plan logged at pipeline start
- **Tier-Aware Character Generation**
  - FREE tier: Uses single-call `CharactersAgent` (avoids rate limits)
  - PAID/NATIVE tier: Uses parallel bio generation
  - Proactive strategy vs reactive retry mechanism
- **Rate Limit Prevention**
  - FREE models run sequentially (parallelism=1)
  - Prevents 429 errors instead of relying on exponential backoff
  - Logs execution strategy at pipeline start
- **New Tests** (`tests/unit/test_model_tier.py`)
  - 19 tests for ModelTier, is_free_model, tier detection, parallelism

### Phase 13: Graph-Informed Character Bios
- **Integrated Graph Generation** (`app/core/pipeline.py`)
  - Graph now runs INSIDE `_step_characters()` between identification and bios
  - Three-phase character generation: CharacterID → Graph → Parallel Bios
  - Character bios receive relationship context from graph data
  - Pipeline flow: Judge → Timeline → Scene → Characters(ID→Graph→Bios) → Moment+Camera → Dialog → ImagePrompt
- **CharacterBioInput Enhancement** (`app/agents/character_bio.py`)
  - Added `graph_data: GraphData | None` field to CharacterBioInput
  - Updated `from_identification()` factory to accept graph_data parameter
  - `get_prompt()` extracts relationships for the specific character
- **Character Bio Prompt** (`app/prompts/character_bio.py`)
  - Added `relationship_context` parameter for graph relationships
  - New "RELATIONSHIP GRAPH" section in prompt when graph data available
  - Character expressions/poses informed by relationship dynamics
- **Pipeline Simplification**
  - Parallel phase now only runs Moment + Camera (Graph moved to Characters)
  - Progress percentages updated: Characters=50%, Moment/Camera=65%, Dialog=80%
- **Improved Character Consistency**
  - Character bios now reflect relationship tensions (ally, rival, mentor, etc.)
  - Emotional tones from graph inform character expressions
  - Better coherence between character portrayals in the same scene

### Phase 14: Hyper Parallelism Mode
- **ParallelismMode Enum** (`app/config.py`)
  - Four modes: SEQUENTIAL (1 at a time), NORMAL (tier default), AGGRESSIVE (higher), MAX (provider limit - 1)
  - `PRESET_PARALLELISM` maps quality presets to parallelism modes (HYPER → MAX)
  - `PROVIDER_RATE_LIMITS` defines per-provider concurrent limits (Google=8, OpenRouter=5)
  - `TIER_CONCURRENT_LIMITS` defines tier×mode matrix for max concurrent calls
- **LLMRouter Parallelism Methods** (`app/core/llm_router.py`)
  - `get_provider_limit()` - Returns provider's max concurrent calls
  - `get_effective_max_concurrent()` - Combines tier + mode + provider limits
  - `get_parallelism_mode()` - Returns mode from preset or default NORMAL
  - For MAX mode: uses provider limit - 1 to leave headroom
- **Optimized Pipeline Execution** (`app/core/pipeline.py`)
  - Two execution flows: standard (SEQUENTIAL/NORMAL) and optimized (AGGRESSIVE/MAX)
  - **Standard flow**: Characters → Moment + Camera (parallel)
  - **Optimized flow**: Camera starts immediately after Scene (doesn't wait for Characters)
  - `_run_standard_flow()` - Original execution path
  - `_run_optimized_flow()` - Camera parallel with Characters
  - `_step_characters_optimized()` - CharacterID → Graph + Moment + Bios (parallel)
  - `use_optimized_flow` property triggers optimized path for AGGRESSIVE/MAX modes
- **Preset Integration**
  - HYPER preset automatically uses MAX parallelism mode
  - HD and BALANCED presets use NORMAL mode
  - Presets regulate parallelism based on tier AND call limits
- **New Tests** (`tests/unit/test_model_tier.py`)
  - 31 new tests for Phase 14 parallelism modes
  - Tests for ParallelismMode, PRESET_PARALLELISM, PROVIDER_RATE_LIMITS
  - Tests for get_preset_parallelism(), get_tier_max_concurrent()
  - Tests for LLMRouter parallelism methods

### Phase 15: Proactive Rate Limiting & Cleanup
- **Token Bucket Rate Limiter** (`app/core/rate_limiter.py`)
  - `TokenBucket` class with capacity, refill rate, async-safe locking
  - `RateLimiterRegistry` manages per-tier rate limiters
  - `TIER_RATE_LIMITS`: FREE (8 rpm, burst 2), PAID (45 rpm, burst 5), NATIVE (58 rpm, burst 8)
  - `acquire_rate_limit()` convenience function for model-based tier detection
  - `get_tier_from_model()` detects tier from model ID (`:free`, `gemini-*`, OpenRouter)
  - Graceful degradation: disables itself after 5 consecutive failures
- **LLM Router Integration** (`app/core/llm_router.py`)
  - `_call_with_retry()` now acquires rate limit token BEFORE making API call
  - Proactive rate limiting prevents 429s instead of reactive retry
  - **Transient error retry**: Now retries on 500/502/503/504 errors (not just 429)
  - Combined proactive + reactive retry with exponential backoff for defense in depth
- **File Cleanup**
  - Deleted duplicate files: `README 2.md`, `config 2.py`, `conftest 2.py`, etc.
  - Archived outdated docs: `REFACTOR.md`, `TESTING.md`, `VERIFICATION_CHECKLIST.md` → `archive/`
- **New Tests** (`tests/unit/test_rate_limiter.py`)
  - 25 tests for TokenBucket, tier detection, registry, concurrency
  - Tests for graceful degradation and failure tracking

### Phase 16: HD Preset Fix & Comprehensive Testing
- **HD Preset Configuration Fix** (`app/config.py`)
  - Fixed HD preset `text_model` from unavailable `gemini-3-pro-preview` to `gemini-2.5-pro-preview`
  - Updated HD preset `judge_model` to `gemini-2.5-flash` for fast validation
  - Updated HD preset `image_model` to reliable `gemini-2.5-flash-image`
  - HD preset now uses working Google native models throughout
- **SSE Streaming Fix** (`app/api/v1/timepoints.py`)
  - Fixed SSE start event to include `preset` in data payload
  - Demo CLI now shows correct preset being used
- **Demo CLI Improvements** (`demo.sh`)
  - Fixed case statement to explicitly handle option 2 for Balanced preset
  - Updated HD preset description to reflect new model configuration
- **Comprehensive Test Suite** (`test-demo.sh` v2.0.5)
  - **Preset Configuration Tests**: Validates all 3 presets are accepted
  - **Generation Tests**: Supports per-preset testing with `--preset` flag
  - **Bulk Mode**: `--bulk` flag tests all presets end-to-end
  - **Delete Test**: Create and delete timepoint validation
  - **Error Handling Tests**: Invalid ID (404), empty query (422)
  - **SSE Validation**: Verifies start event includes preset
  - **Verbose Mode**: `--verbose` flag for detailed output
  - 18 tests total (15 quick + 3 generation-dependent)

### Phase 17: Bulletproof Model Validation
- **VerifiedModels Class** (`app/config.py`)
  - `GOOGLE_TEXT`: Verified working text models (`gemini-2.5-flash`, `gemini-2.0-flash`)
  - `GOOGLE_IMAGE`: Verified working image models (`gemini-2.5-flash-image`)
  - `OPENROUTER_TEXT`: Verified OpenRouter models (`google/gemini-2.0-flash-001`)
  - `TEXT_FALLBACK_CHAIN`: Ordered fallback models for reliability
  - Helper methods: `is_verified_text_model()`, `get_safe_text_model()`, `get_safe_image_model()`
- **Startup Validation** (`app/main.py`)
  - `validate_presets_or_raise()` called at startup
  - Server fails fast if any preset uses unverified model
  - Logs confirmation: "Model configuration validated - all presets use verified models"
- **Preset Configuration Hardening** (`app/config.py`)
  - All presets now reference `VerifiedModels` constants
  - HD: `gemini-2.5-flash` (with extended thinking) + `gemini-2.5-flash-image`
  - Balanced: `gemini-2.5-flash` + `gemini-2.5-flash-image`
  - Hyper: `google/gemini-2.0-flash-001` (OpenRouter) + `gemini-2.5-flash-image`
  - Comments indicate which VerifiedModels constant each model comes from
- **LLM Router Fallback Hardening** (`app/core/llm_router.py`)
  - `PAID_FALLBACK_MODEL` now uses `VerifiedModels.OPENROUTER_TEXT[0]`
  - Fallback to Google provider uses `VerifiedModels.get_safe_text_model()`
  - All fallback paths guaranteed to use working models
- **Settings Default Fix** (`app/config.py`)
  - `CREATIVE_MODEL` default changed from unavailable `gemini-3-pro-preview` to `gemini-2.5-flash`
- **validate_presets() Function** (`app/config.py`)
  - Validates text_model, judge_model, image_model for each preset
  - Checks against correct VerifiedModels list based on provider
  - Returns list of errors or empty list if valid

### Phase 18: Character Interactions
- **Character Chat System** (`app/agents/character_chat.py`)
  - `CharacterChatAgent` - In-character conversations with historical figures
  - `ChatInput` - Character context, message, history
  - `ChatOutput` - Response with emotional tone detection
  - `ChatSessionManager` - In-memory session management with conversation history
- **Dialog Extension** (`app/agents/dialog_extension.py`)
  - `DialogExtensionAgent` - Generate additional dialog lines
  - Sequential roleplay mode for authentic character voices
  - Prompt-directed dialog generation (e.g., "discuss the risks")
- **Survey System** (`app/agents/survey.py`)
  - `SurveyAgent` - Survey multiple characters with questions
  - Parallel mode (faster) and sequential mode (context-aware)
  - Chain prompts option to share prior answers
  - Sentiment analysis: positive, negative, mixed, neutral
  - Emotional tone detection and key points extraction
- **Chat Schemas** (`app/schemas/chat.py`)
  - `ChatMessage`, `ChatSession`, `ChatSessionSummary`
  - `ChatRequest`, `ChatResponse`
  - `DialogExtensionRequest`, `DialogExtensionResponse`
  - `SurveyRequest`, `SurveyResult`, `SurveyMode`
- **Interactions API** (`app/api/v1/interactions.py`)
  - POST `/api/v1/interactions/{id}/chat` - Chat with character
  - POST `/api/v1/interactions/{id}/chat/stream` - SSE streaming chat
  - POST `/api/v1/interactions/{id}/dialog` - Extend dialog
  - POST `/api/v1/interactions/{id}/dialog/stream` - SSE streaming dialog
  - POST `/api/v1/interactions/{id}/survey` - Survey characters
  - POST `/api/v1/interactions/{id}/survey/stream` - SSE streaming survey
  - GET `/api/v1/interactions/sessions/{timepoint_id}` - List sessions
  - GET/DELETE `/api/v1/interactions/session/{session_id}` - Get/delete session
- **Demo CLI Integration** (`demo.sh`)
  - Menu item 11: Chat with Character
  - Menu item 12: Extend Dialog
  - Menu item 13: Survey Characters
- **Test Coverage** (`test-demo.sh` v2.0.7)
  - Character interaction endpoint tests (router mounted, validation)
  - Integration tests with real timepoints (chat, dialog, survey)

### Phase 19: Character Chat Streaming Fixes
- **LLMRouter Streaming Support** (`app/core/llm_router.py`)
  - Added `stream()` async generator method for token-by-token streaming
  - Added `AsyncIterator` import from `collections.abc`
  - Wraps `call()` method and yields complete response (true streaming can be added later)
  - Fixes `'LLMRouter' object has no attribute 'stream'` error
- **Demo CLI Field Name Fix** (`demo.sh`)
  - Fixed chat endpoint JSON field: `character_name` → `character`
  - Fixed dialog endpoint JSON field: `character_name` → `character`
  - Fixed survey endpoint JSON field: `character_names` → `characters`
  - Fixes 422 Unprocessable Entity validation errors
- **Demo CLI SSE Event Fix** (`demo.sh`)
  - Fixed chat streaming event handler to use correct event names
  - Changed from `response|chunk` events to `token|done` events
  - Fixes empty response display despite 200 OK status
- **Test Coverage** (`test-demo.sh` v2.0.8)
  - Added SSE event validation test for chat streaming
  - Verifies API returns `token` and `done` events (not `response` or `chunk`)

### Phase 20: Model Selection for Character Interactions
- **Model Selection in Interaction APIs** (`app/api/v1/interactions.py`)
  - Added `model` and `response_format` fields to `ChatAPIRequest`, `DialogAPIRequest`, `SurveyAPIRequest`
  - Agents receive model and response_format from API requests
  - Supports Google native models (`gemini-2.5-flash`) and OpenRouter models (`google/gemini-2.0-flash-001`)
- **ResponseFormat Enum** (`app/schemas/chat.py`)
  - Three modes: `STRUCTURED` (JSON schema), `TEXT` (plain text), `AUTO` (detect from model)
  - Added to `ChatRequest`, `DialogExtensionRequest`, `SurveyRequest`
- **Model Capability Detection** (`app/core/model_capabilities.py`)
  - `TextModelCapability` enum for JSON schema, JSON mode, function calling, streaming
  - `TextModelConfig` dataclass with model capabilities and limits
  - `TEXT_MODEL_REGISTRY` with known model configurations
  - `supports_structured_output()` checks if model can use structured responses
  - `infer_provider_from_model_id()` detects provider from model ID pattern
  - `get_available_interaction_models()` returns models for UI selection
- **Agent Model Support** (`app/agents/`)
  - `CharacterChatAgent`, `DialogExtensionAgent`, `SurveyAgent` accept `model` and `response_format`
  - `_should_use_structured()` method determines response format based on model capabilities
  - Router created with custom model if specified
- **Demo CLI Model Selection** (`demo.sh`)
  - `select_interaction_model()` function with 7 model options
  - Model selection before Chat (11), Dialog (12), Survey (13)
  - `build_interaction_payload()` helper adds model/response_format to JSON
  - Visual feedback showing selected model during operation
- **Test Coverage** (`test-demo.sh` v2.1.0)
  - Tests for model parameter acceptance on all interaction endpoints
  - Integration test with model override (`gemini-2.5-flash`)
  - Response format validation tests

---

## Repository Structure

```
timepoint-flash/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Pydantic settings
│   ├── models.py            # SQLAlchemy models
│   ├── database.py          # Database connection
│   ├── agents/              # 15 agent implementations (10 pipeline + 3 interaction + 2 bio)
│   ├── core/                # Provider, router, temporal
│   ├── schemas/             # Pydantic response models
│   ├── prompts/             # Prompt templates
│   └── api/v1/              # API routes (timepoints, temporal, models, interactions)
├── tests/
│   ├── unit/                # Fast unit tests
│   └── integration/         # API integration tests
├── alembic/                 # Database migrations
│   ├── env.py              # Async migration environment
│   └── versions/           # Migration scripts
├── scripts/
│   ├── init-db.sql         # PostgreSQL initialization
│   └── start.sh            # Docker startup script
├── docs/
│   ├── API.md              # Complete API reference
│   ├── TEMPORAL.md         # Temporal navigation guide
│   └── DEPLOYMENT.md       # Deployment guide
├── Dockerfile              # Multi-stage Docker build
├── docker-compose.yml      # Production compose
├── docker-compose.dev.yml  # Development compose
├── railway.json            # Railway deployment
├── render.yaml             # Render Blueprint
├── alembic.ini             # Alembic configuration
├── .env.example            # Environment template
├── README.md               # v2.0 documentation
├── QUICKSTART.md           # Getting started guide
├── HANDOFF.md              # This file
├── archive/                # Archived v1 docs and outdated files
├── demo.sh                 # Interactive demo CLI
└── run.sh                  # Server runner script
```

---

## Quick Commands

```bash
# Install dependencies
pip install -e .

# Run fast tests
python3.10 -m pytest -m fast -v

# Run integration tests
python3.10 -m pytest -m integration -v

# Start server (development with auto-reload)
./run.sh -r

# Start server (production mode)
./run.sh -P

# Interactive demo CLI
./demo.sh

# Docker production
docker compose up -d

# Docker development
docker compose -f docker-compose.dev.yml up

# Database migrations
alembic upgrade head
```

---

## API Endpoints Summary

### Timepoints API (`/api/v1/timepoints`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/generate` | Generate timepoint |
| POST | `/generate/stream` | SSE streaming |
| GET | `/{id}` | Get by ID |
| GET | `/slug/{slug}` | Get by slug |
| GET | `/` | List (pagination) |
| DELETE | `/{id}` | Delete |

### Temporal API (`/api/v1/temporal`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/{id}/next` | Next moment |
| POST | `/{id}/prior` | Prior moment |
| GET | `/{id}/sequence` | Sequence |

### Models API (`/api/v1/models`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List models |
| GET | `/providers` | Provider status |
| GET | `/{model_id}` | Model details |

### Interactions API (`/api/v1/interactions`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/{id}/chat` | Chat with character |
| POST | `/{id}/chat/stream` | Stream chat response |
| POST | `/{id}/dialog` | Extend dialog |
| POST | `/{id}/dialog/stream` | Stream dialog lines |
| POST | `/{id}/survey` | Survey characters |
| POST | `/{id}/survey/stream` | Stream survey results |
| GET | `/sessions/{id}` | List chat sessions |
| GET | `/session/{id}` | Get session |
| DELETE | `/session/{id}` | Delete session |

---

## Environment Variables

```bash
# Required (at least one)
GOOGLE_API_KEY=your-key
OPENROUTER_API_KEY=your-key

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# Application
ENVIRONMENT=production
DEBUG=false
PORT=8000

# Pipeline
PIPELINE_MAX_PARALLELISM=3  # 1-5, concurrent LLM calls
```

See `.env.example` for complete list.

---

## Deployment Options

1. **Docker Compose**: Local/VPS with PostgreSQL
2. **Railway**: Auto-deploys from `railway.json`
3. **Render**: Uses `render.yaml` Blueprint
4. **Kubernetes**: See `docs/DEPLOYMENT.md`

---

## Important Notes

- **Python 3.10** required for SQLAlchemy compatibility
- **15 specialized agents** - 10 pipeline + 3 interaction + 2 character bio
- **All APIs complete** - CRUD, streaming, temporal, models, interactions
- **Production ready** - Docker, migrations, cloud configs
- **Adaptive parallelism** - FREE models run sequentially to avoid rate limits
- **Hyper parallelism** - HYPER preset uses MAX mode with optimized execution flow
- **Proactive rate limiting** - Token bucket prevents 429s before they happen
- **Character interactions** - Chat, dialog extension, survey with SSE streaming

---

## v2.1.0 Release

**Tag**: `v2.1.0`
**Date**: 2025-12-04

### New in v2.1.0
- **Character Interactions** - Chat with characters, extend dialog, survey multiple characters
- **SSE Streaming** - All interaction endpoints support real-time streaming
- **Sentiment Analysis** - Survey responses include sentiment (positive/negative/mixed/neutral)
- **Emotional Tone** - Character responses include emotional tone detection
- **Session Management** - In-memory conversation history with session continuation
- **Demo CLI** - Menu items 11, 12, 13 for character interactions
- **Test Suite** - test-demo.sh v2.0.7 with interaction endpoint tests

### Technical Details
- 3 new agents: CharacterChatAgent, DialogExtensionAgent, SurveyAgent
- New schema module: `app/schemas/chat.py`
- Interactions API: `/api/v1/interactions/`
- Survey modes: parallel (faster) and sequential (context-aware)
- Chain prompts option for sequential surveys

### Endpoints Added
- POST `/api/v1/interactions/{id}/chat` - Chat with character
- POST `/api/v1/interactions/{id}/chat/stream` - Stream chat
- POST `/api/v1/interactions/{id}/dialog` - Extend dialog
- POST `/api/v1/interactions/{id}/dialog/stream` - Stream dialog
- POST `/api/v1/interactions/{id}/survey` - Survey characters
- POST `/api/v1/interactions/{id}/survey/stream` - Stream survey
- GET `/api/v1/interactions/sessions/{id}` - List sessions
- GET/DELETE `/api/v1/interactions/session/{id}` - Session CRUD

---

## v2.0.11 Release

**Tag**: `v2.0.11`
**Date**: 2025-12-03

### New in v2.0.11
- **Bulletproof Model Validation** - Impossible to use invalid models
- **VerifiedModels Class** - Centralized list of tested, working models
- **Startup Validation** - Server fails fast if preset uses unverified model
- **Fallback Hardening** - All fallback paths use verified models

### Technical Details
- `VerifiedModels` class in `app/config.py` with all working models
- `validate_presets_or_raise()` called at server startup
- All presets reference VerifiedModels constants (with comments)
- LLM router fallback uses `VerifiedModels.get_safe_text_model()`
- `CREATIVE_MODEL` default fixed from `gemini-3-pro-preview` to `gemini-2.5-flash`

### Verified Models
```python
GOOGLE_TEXT = ["gemini-2.5-flash", "gemini-2.0-flash"]
GOOGLE_IMAGE = ["gemini-2.5-flash-image"]
OPENROUTER_TEXT = ["google/gemini-2.0-flash-001", "google/gemini-2.0-flash-001:free"]
```

### Safety Guarantees
1. **Startup Check** - Invalid presets prevent server start
2. **Fallback Safety** - All fallback models are verified
3. **Comment Documentation** - Each preset model has VerifiedModels reference
4. **Helper Methods** - `get_safe_text_model()`, `get_safe_image_model()`

---

## v2.0.10 Release

**Tag**: `v2.0.10`
**Date**: 2025-12-03

### New in v2.0.10
- **HD Preset Fix** - Updated HD preset to use working `gemini-2.5-pro-preview` model
- **SSE Preset Display** - Fixed start event to include preset in data payload
- **Comprehensive Test Suite** - `test-demo.sh` v2.0.5 with bulk testing support
- **Demo CLI Improvements** - Fixed case statement and updated preset descriptions

### Technical Details
- HD preset `text_model`: `gemini-3-pro-preview` → `gemini-2.5-pro-preview`
- HD preset `image_model`: `gemini-3-pro-image-preview` → `gemini-2.5-flash-image` (reliable)
- SSE start event now includes `preset` field for display
- `test-demo.sh` supports `--bulk`, `--preset <name>`, `--verbose` flags

### Test Suite Features
- **Quick Mode** (`--quick`): 15 fast endpoint tests
- **Standard Mode**: 18 tests including hyper generation
- **Bulk Mode** (`--bulk`): Tests all presets (hyper, balanced, hd)
- **Preset Mode** (`--preset hd`): Test specific preset only
- **Verbose Mode** (`--verbose`): Detailed output for debugging

---

## v2.0.9 Release

**Tag**: `v2.0.9`
**Date**: 2025-12-03

### New in v2.0.9
- **Proactive Rate Limiting** - Token bucket algorithm prevents 429 errors before they happen
- **Tier-Based Rate Limits** - FREE (8 rpm), PAID (45 rpm), NATIVE (58 rpm)
- **Transient Error Retry** - Now retries on 500/502/503/504 server errors (not just 429)
- **Graceful Degradation** - Rate limiter disables itself after 5 consecutive failures
- **File Cleanup** - Removed duplicate files and archived outdated docs

### Technical Details
- `TokenBucket` class in `app/core/rate_limiter.py`
- `RateLimiterRegistry` for per-tier rate limiters
- `TIER_RATE_LIMITS`: FREE (8 rpm, burst 2), PAID (45 rpm, burst 5), NATIVE (58 rpm, burst 8)
- `acquire_rate_limit()` integrates at `_call_with_retry()` level
- Combined proactive (token bucket) + reactive (exponential backoff) rate limit handling

### Rate Limiting Strategy
1. **Proactive**: Token bucket waits BEFORE making API call if bucket empty
2. **Reactive**: Exponential backoff retries if 429 still occurs (defense in depth)
3. **Graceful**: Disables itself if rate limiter fails repeatedly (allows requests through)

### Test Coverage
- 362 tests passing (25 new rate limiter tests)

---

## v2.0.8 Release

**Tag**: `v2.0.8`
**Date**: 2025-12-03

### New in v2.0.8
- **Hyper Parallelism Mode** - HYPER preset uses MAX parallelism for fastest generation
- **Optimized Execution Flow** - Camera starts immediately after Scene in AGGRESSIVE/MAX modes
- **ParallelismMode Enum** - Four modes: SEQUENTIAL, NORMAL, AGGRESSIVE, MAX
- **Provider-Aware Limits** - Respects per-provider concurrent call limits (Google=8, OpenRouter=5)
- **Tier-Based Parallelism Matrix** - FREE/PAID/NATIVE tiers × parallelism modes

### Technical Details
- `ParallelismMode` enum in `app/config.py`
- `PRESET_PARALLELISM`: HYPER→MAX, HD/BALANCED→NORMAL
- `get_effective_max_concurrent()`: combines tier + mode + provider limits
- For MAX mode: uses provider limit - 1 to leave headroom
- Optimized flow: Camera parallel with Characters, Moment parallel with Graph+Bios

### Execution Flows
**Standard Flow (SEQUENTIAL/NORMAL)**:
- Judge → Timeline → Scene → Characters (with Graph) → Moment+Camera (parallel) → Dialog → ImagePrompt

**Optimized Flow (AGGRESSIVE/MAX)**:
- Judge → Timeline → Scene → Camera (starts immediately) + Characters (CharacterID → Graph+Moment+Bios parallel) → Dialog → ImagePrompt

### Test Coverage
- 340 tests passing (31 new Phase 14 tests)

---

## v2.0.7 Release

**Tag**: `v2.0.7`
**Date**: 2025-12-03

### New in v2.0.7
- **Graph-Informed Character Bios** - Character bios now receive relationship context from graph
- **Integrated Graph Generation** - Graph runs inside character step, before bios
- **Three-Phase Character Generation** - CharacterID → Graph → Parallel Bios
- **Improved Character Consistency** - Expressions and poses reflect relationship dynamics

### Technical Details
- `CharacterBioInput.graph_data` field for relationship context
- `character_bio.py` prompt includes "RELATIONSHIP GRAPH" section
- Pipeline flow: Characters(ID→Graph→Bios) → Moment+Camera (parallel) → Dialog
- Progress percentages: Characters=50%, Moment/Camera=65%, Dialog=80%

### Test Coverage
- 309 tests passing

---

## v2.0.6 Release

**Tag**: `v2.0.6`
**Date**: 2025-12-03

### New in v2.0.6
- **Adaptive Parallelism** - Model tier classification determines execution strategy
- **Proactive Rate Limit Prevention** - FREE models run sequentially instead of hitting 429 errors
- **Model Tier Classification** - FREE (`:free` suffix), PAID (OpenRouter), NATIVE (Google)
- **Execution Planning** - `_plan_execution()` determines strategy before pipeline runs

### Technical Details
- `ModelTier` enum in `app/core/llm_router.py`
- `TIER_PARALLELISM`: FREE=1, PAID=2, NATIVE=3
- `get_model_tier()` classifies current model
- `use_parallel_characters` property skips parallel bios for FREE tier

### Test Coverage
- 309 tests passing (19 new tier detection tests)

---

## v2.0.5 Release

**Tag**: `v2.0.5`
**Date**: 2025-12-02

### New in v2.0.5
- **Parallel Character Bio Generation** - Character bios now generated in parallel
- **Two-Phase Character Generation** - Fast identification + parallel detailed bios
- **2 New Agents** - `CharacterIdentificationAgent` and `CharacterBioAgent`
- **2 New Prompts** - `character_identification.py` and `character_bio.py`
- **New Schema** - `CharacterIdentification` with `CharacterStub` for lightweight ID

### Performance Improvement
- Character step now runs 1 identification call + N parallel bio calls (N = character count)
- Up to 8 character bios generated concurrently
- Each bio call receives full cast context for relationship coherence

### Technical Details
- `CharacterIdentificationAgent`: Fast identification (temperature 0.5)
- `CharacterBioAgent`: Detailed bio generation (temperature 0.7)
- `create_fallback_character()`: Graceful error handling for individual failures
- Falls back to single-call `CharactersAgent` if identification fails

### Test Coverage
- 290 tests passing (20 new character parallel tests)

---

## v2.0.4 Release

**Tag**: `v2.0.4`
**Date**: 2025-12-02

### New in v2.0.4
- **Parallel Pipeline Execution** - Graph, Moment, and Camera steps run concurrently
- **Configurable Parallelism** - `PIPELINE_MAX_PARALLELISM` env var (1-5, default 3)
- **Semaphore Control** - Prevents rate limiting with concurrent LLM calls
- **Cross-platform Demo CLI** - Fixed macOS millisecond timing using Python

### Performance Improvement
- 3 LLM calls now execute in parallel during pipeline phase 2
- ~30-40% faster generation for independent steps
- Streaming endpoint yields parallel results as they complete

### Bug Fixes
- Fixed `date +%s%3N` bash arithmetic error on macOS

---

## v2.0.3 Release

**Tag**: `v2.0.3`
**Date**: 2025-12-02

### New in v2.0.3
- **Free Model Support** - `/api/v1/models/free` endpoint for zero-cost generation
- **Rate Limit Resilience** - Three-tier cascade fallback (free → paid → Google)
- **Image Generation Fix** - RAPID TEST FREE now generates images correctly
- **Demo CLI** - RAPID TEST, RAPID TEST FREE, custom model selection
- **Anachronism Mitigation** - Historical authenticity in dialog generation

### Bug Fixes
- Fixed `IMAGE_MODEL` default format (removed `google/` prefix)
- Fixed model routing for Google native image generation
- Fixed `MomentData.plot_beats` and `CameraData.composition` types
- Fixed `CharacterData` schema validation

---

## v2.0.1 Release

**Tag**: `v2.0.1`
**Date**: 2025-12-01

### New in v2.0.1
- **Real-time streaming** - Pipeline yields after each step for true SSE progress
- **Demo CLI** - Interactive `demo.sh` with browse, generate, and image features
- **Server runner** - `run.sh` with dev/prod modes and CLI options
- **API improvements** - `include_image` parameter on GET endpoint

### Features (from v2.0.0)
- 10 specialized AI agents for temporal generation
- Full CRUD API with SSE streaming
- Temporal navigation (next/prior/sequence)
- Multi-provider support (Google AI, OpenRouter)
- PostgreSQL with async SQLAlchemy
- Docker deployment with health checks
- Railway and Render deployment configs

### Test Coverage
- 265 unit tests (fast, no API calls)
- 39 integration tests (database required)

### Documentation
- README.md - Project overview
- QUICKSTART.md - Getting started
- docs/API.md - API reference
- docs/TEMPORAL.md - Temporal navigation
- docs/DEPLOYMENT.md - Deployment guide
