# TIMEPOINT Flash v2.0

**Status**: 🚧 Under Active Development

AI-powered photorealistic time travel system with multi-agent workflows, temporal navigation, and batteries-included developer experience.

---

## 🚧 v2.0 Refactor In Progress

This repository is undergoing a complete architectural rebuild. The v1.0 codebase has been archived.

### Access v1.0

The working v1.0 system is available at:

- **Branch**: `archive/v1-legacy`
- **Tag**: `v1.0.0-legacy`
- **Docs**: See `archive/` directory

```bash
git checkout archive/v1-legacy
```

### What's New in v2.0

**Core Architecture:**
- 🎯 Clean provider abstraction (Google AI + OpenRouter)
- 🔧 Mirascope for unified LLM interface
- ⏰ Synthetic time system with temporal navigation
- 🎨 11-agent LangGraph workflow
- ✅ Test-driven development (>80% coverage)

**Developer Experience:**
- 🚀 One-command generation: `tp "signing of the declaration"`
- 📊 Temporal navigation: `--next 10 --unit days`
- 📦 Batch processing: `tp batch timeline.csv`
- 🔍 Dynamic model discovery (300+ models via OpenRouter)

**Production Ready:**
- ⚡ FastAPI with OpenAPI spec
- 🖼️ HTMX lightweight viewer
- 📡 Real-time SSE updates
- 🗄️ SQLite (dev) + PostgreSQL (prod)
- 📈 Logfire observability

### Migration Timeline

- ✅ **Week 1**: GitHub cleanup (COMPLETED)
- 🔄 **Week 2**: Core infrastructure (IN PROGRESS)
- 📅 **Week 3**: Temporal system
- 📅 **Week 4-5**: Rebuild agents with Mirascope
- 📅 **Week 6**: CLI + API + HTMX viewer
- 📅 **Week 7**: Testing & polish
- 📅 **Week 8**: Launch v2.0.0

See `REFACTOR.md` for complete plan.

---

## Quick Start (Coming Soon)

```bash
# Setup (one command)
pip install -e .

# Generate timepoint (autopilot)
tp "signing of the declaration of independence"

# View result
open http://localhost:8000
```

---

## Current Status: Phase 2 - Core Infrastructure

**Now Building:**
- [ ] Provider abstraction layer (`app/core/providers.py`)
- [ ] Google AI provider (`app/core/providers/google.py`)
- [ ] OpenRouter provider (`app/core/providers/openrouter.py`)
- [ ] LLM Router with Mirascope (`app/core/llm_router.py`)
- [ ] Base FastAPI app (`app/main.py`)
- [ ] Database models (`app/models.py`)
- [ ] pytest configuration (`tests/conftest.py`)

**Next Up:**
- Synthetic time system
- Temporal navigation
- Agent rebuilds

---

## Contributing

v2.0 is under active development. Please check `archive/REFACTOR.md` for the complete plan before contributing.

---

## License

MIT License - see LICENSE file for details.

---

**Built with** ⚡ FastAPI | 🧠 LangGraph | 🎨 Google Gemini | 🔧 Mirascope | ⏰ Synthetic Time

**v2.0 Refactor Started**: 2025-11-26
**Status**: Active Development
**Target Launch**: 2026-01-21 (Week 8)
