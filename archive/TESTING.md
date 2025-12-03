# Testing Guide for TIMEPOINT Flash

Comprehensive guide to running, writing, and understanding tests for TIMEPOINT Flash.

## 🚨 First Time Here?

**Run setup first**:
```bash
./setup.sh       # One-command setup (installs deps, configures API key)
```

**See**: [QUICKSTART.md](QUICKSTART.md) for complete setup instructions.

---

## Quick Start

```bash
# Fast unit tests (5-10 seconds, no API calls)
./test.sh fast

# E2E integration tests (10-15 minutes, requires API key)
./test.sh e2e

# All tests
./test.sh all

# With coverage report
./test.sh coverage
```

---

## Test Categories

### Fast Tests (`@pytest.mark.fast`)
- **Duration**: 5-10 seconds
- **Requirements**: None (no API keys needed)
- **Coverage**: Database models, API endpoints, rate limiting logic, basic validation
- **Run**: `pytest -m fast`

**Use case**: Quick verification during development, CI/CD for every commit.

### E2E Tests (`@pytest.mark.e2e`)
- **Duration**: 10-30 minutes (depending on scenarios)
- **Requirements**: OPENROUTER_API_KEY (or GOOGLE_API_KEY)
- **Coverage**: Full workflow (all 11 agents), image generation, LLM judge evaluation
- **Run**: `pytest -m e2e`

**Use case**: Pre-release validation, comprehensive quality assurance.

### Slow Tests (`@pytest.mark.slow`)
- **Duration**: Varies (includes long-running operations)
- **Requirements**: API keys
- **Coverage**: Full timepoint generation (60s+), image segmentation
- **Run**: `pytest -m slow`

**Use case**: Subset of e2e tests that take longest (image generation, full workflows).

---

## Running Specific Tests

### By File
```bash
# All tests in a file
pytest tests/test_fast.py -v

# E2E agent tests only
pytest tests/test_e2e_agents.py -v

# Image generation tests
pytest tests/test_e2e_image.py -v

# API behavior tests
pytest tests/test_e2e_api.py -v
```

### By Test Name
```bash
# Run a specific test
pytest tests/test_e2e.py::test_timepoint_generation_with_judge -v

# Run tests matching a pattern
pytest -k "judge" -v
pytest -k "image" -v
```

### By Scenario
```bash
# Run specific parameterized scenario
pytest tests/test_e2e.py::test_timepoint_generation_with_judge[Medieval] -v
```

---

## Test Infrastructure

### Database Support

Tests automatically adapt to the available database:

**SQLite (default)**:
- In-memory: `sqlite:///:memory:` (fastest, ephemeral)
- File-based: `sqlite:///./test.db` (persistent)

**PostgreSQL** (when configured):
```bash
DATABASE_URL=postgresql://localhost/test_db pytest -m e2e
```

**Fallback logic**:
1. If `DATABASE_URL` is set to PostgreSQL:
   - Test connection
   - Use PostgreSQL if available
   - Fallback to in-memory SQLite if unavailable (with warning)
2. Otherwise: Use SQLite

### Test Isolation

**Automatic cleanup** between tests:
- Test emails (test-*@example.com) are deleted
- Associated timepoints, rate limits, processing sessions removed
- IP rate limits cleared
- Database state is clean for next test

**Implementation**: `cleanup_test_data_fixture` in `conftest.py` (autouse)

### Retry Logic

E2E tests automatically retry on transient failures:
- **Max attempts**: 2-3 (configurable)
- **Backoff**: Exponential (1s, 2s, 4s...)
- **Triggers**: 500, 502, 503, 504 HTTP errors, network timeouts

**Usage**:
```python
@retry_on_api_error(max_attempts=3, backoff_factor=2.0)
async def test_with_retry():
    # Automatically retries on transient failures
    pass
```

### Smart Polling

Instead of hardcoded `await asyncio.sleep(60)`, use smart polling:

```python
from tests.utils.test_helpers import wait_for_completion

async def check_completion():
    response = client.get(f"/api/timepoint/details/{slug}")
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "completed":
            return (True, data)
    return (False, None)

result = await wait_for_completion(
    check_func=check_completion,
    timeout_seconds=180,
    poll_interval=3.0,
    description="timepoint generation"
)
```

**Benefits**:
- Completes as soon as possible (no wasted time)
- Clear timeout behavior
- Progress logging

---

## Mock Mode (Offline Testing)

Run tests without making real API calls:

```bash
USE_MOCKS=true pytest -m e2e
```

**Benefits**:
- **Faster**: No network latency
- **Free**: No API credits used
- **Offline**: Work without internet
- **Deterministic**: Same responses every time

**Limitations**:
- Doesn't test actual API integration
- Mock responses may not reflect real behavior

**Implementation**: See `tests/fixtures/mock_responses.py`

---

## Writing New Tests

### Test Structure

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.utils.test_helpers import generate_unique_test_email

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_my_feature(
    client: TestClient,
    db_session: Session,
    openrouter_api_key: str
):
    """Test description."""
    # Use unique email for test isolation
    email = generate_unique_test_email("test-myfeature")

    # Make API call
    response = client.post(
        "/api/timepoint/create",
        json={"input_query": "...", "requester_email": email}
    )

    # Assertions
    assert response.status_code in [200, 201]
```

### Best Practices

1. **Use unique emails**: `generate_unique_test_email()` ensures no conflicts
2. **Use smart polling**: Don't hardcode sleep times
3. **Add retry logic**: Use `@retry_on_api_error` for flaky tests
4. **Validate structure**: Use `verify_timepoint_structure()` helper
5. **Verify images**: Use `verify_image_data()` for image validation
6. **Mark appropriately**: `@pytest.mark.fast`, `@pytest.mark.e2e`, `@pytest.mark.slow`
7. **Document clearly**: Add docstrings explaining what's tested

### Test Fixtures

Available fixtures (see `conftest.py`):
- `client` - FastAPI TestClient
- `db_session` - Database session
- `db_engine` - Database engine
- `openrouter_api_key` - API key from environment
- `test_settings` - Test configuration
- `db_type` - Database type ("sqlite" or "postgresql")

---

## Troubleshooting

### "OPENROUTER_API_KEY not set"
```bash
# Set in .env file
echo "OPENROUTER_API_KEY=your_key_here" >> .env

# Or export directly
export OPENROUTER_API_KEY="your_key_here"
```

### "PostgreSQL unavailable, falling back to SQLite"
- PostgreSQL is configured but not running
- Check: `pg_isready` or start PostgreSQL service
- Tests will automatically use SQLite fallback (warning only)

### Tests timing out
- Increase timeout: `wait_for_completion(timeout_seconds=300)`
- Check API rate limits (may be hitting OpenRouter limits)
- Try with `USE_MOCKS=true` to isolate issue

### Image validation failing
- Check image format (should be PNG)
- Verify base64 encoding is valid
- Ensure image URL has data URI prefix: `data:image/png;base64,...`

### Rate limit errors (429)
- Tests use high rate limits (MAX_TIMEPOINTS_PER_HOUR=100)
- If hitting limits, unique emails prevent conflicts
- Check database cleanup is working

### Flaky test failures
- Add `@retry_on_api_error` decorator
- Increase poll_interval in `wait_for_completion`
- Check if test isolation is working (cleanup fixture)

---

## CI/CD Integration

### GitHub Actions

Tests run automatically on:
- Every push to `main` or `develop`
- Every PR to `main` or `develop`

**Fast tests**: Run on every commit (~5s)
**E2E tests**: Run only on `main` branch or PRs to `main` (~30min)

**Configuration**: `.github/workflows/test.yml`

### Required Secrets

Set in GitHub repository settings:
- `OPENROUTER_API_KEY` - For e2e tests
- `GOOGLE_API_KEY` (optional) - Fallback provider

### Workflow Jobs

1. **fast-tests** - Unit tests, runs always
2. **e2e-tests** - Integration tests, runs on main/PRs
3. **code-quality** - Ruff linting, mypy type checking

---

## Test Coverage

Current coverage: **31%** (target: 70%+)

Generate coverage report:
```bash
./test.sh coverage
# Report saved to htmlcov/index.html
```

View report:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

---

## LLM Judge Evaluation

E2E tests use an LLM-based judge to evaluate quality:

**Criteria** (weighted):
- Historical Accuracy (30%)
- Character Quality (25%)
- Dialog Quality (25%)
- Scene Coherence (20%)

**Scoring**: 0-100 for each criterion
**Passing threshold**: 65.0 (configurable per test)

**Implementation**: `tests/utils/llm_judge.py`

---

## Test Utilities

### `tests/utils/test_helpers.py`
- `wait_for_completion()` - Smart polling
- `verify_image_data()` - Validate images
- `verify_timepoint_structure()` - Schema validation
- `cleanup_test_data()` - Database cleanup
- `generate_unique_test_email()` - Unique emails

### `tests/utils/retry.py`
- `@retry_on_api_error()` - Auto-retry decorator
- `@skip_on_api_unavailable()` - Graceful skip decorator
- `is_transient_error()` - Error classification

### `tests/utils/llm_judge.py`
- `judge_timepoint()` - Quality evaluation
- `JudgementResult` - Evaluation result dataclass

### `tests/fixtures/mock_responses.py`
- `get_mock_llm_response()` - Mock LLM responses
- `get_mock_image()` - Mock images
- `get_mock_timepoint()` - Complete mock timepoint

---

## Performance Benchmarks

| Test Suite | Count | Duration | API Calls |
|------------|-------|----------|-----------|
| Fast tests | 13 | ~5-10s | 0 |
| E2E scenarios | 10 | ~10-15min | ~15/scenario |
| Agent tests | 8 | ~5-10min | ~5-10/test |
| Image tests | 3 | ~3-5min | ~1/test |
| API tests | 8 | ~2-4min | ~1-2/test |

**Total**: 42 tests, ~20-30 minutes for full suite

---

## Resources

- **pytest docs**: https://docs.pytest.org/
- **FastAPI testing**: https://fastapi.tiangolo.com/tutorial/testing/
- **SQLAlchemy testing**: https://docs.sqlalchemy.org/en/14/orm/session_transaction.html
- **GitHub Actions**: https://docs.github.com/en/actions

---

**Questions? Issues?**
- Check existing test examples in `tests/` directory
- Review this guide and test utilities documentation
- Open an issue on GitHub with `[testing]` tag
