# TIMEPOINT Flash v1.0 - Archived Documentation

This directory contains documentation from TIMEPOINT Flash v1.0, archived during the v2.0 refactor.

## Archive Contents

- **README-v1.md** - Original README from v1.0
- **QUICKSTART-v1.md** - Original quick start guide
- **TESTING-v1.md** - Original testing documentation

## Accessing v1.0 Code

The complete v1.0 codebase is preserved in:

- **Branch**: `archive/v1-legacy`
- **Tag**: `v1.0.0-legacy`

To access the v1.0 codebase:

```bash
# View the archive branch
git checkout archive/v1-legacy

# Or create a local branch from the tag
git checkout -b v1-local v1.0.0-legacy
```

## What Changed in v2.0

TIMEPOINT Flash v2.0 is a complete architectural rebuild featuring:

1. **Clean Provider Abstraction** - Separate Google AI and OpenRouter implementations
2. **Mirascope Integration** - Unified LLM interface across providers
3. **Synthetic Time System** - Temporal navigation (next/prior moments)
4. **Batteries-Included CLI** - `tp "query"` for autopilot generation
5. **Test-Driven Development** - >80% coverage with pytest
6. **Production FastAPI** - Tight server with OpenAPI and HTMX viewer

See `REFACTOR.md` in the root directory for the complete migration plan.

---

**Archived**: 2025-11-26
**Last v1.0 Commit**: 90fa634
