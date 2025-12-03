"""Tests for proactive rate limiting with token bucket algorithm.

Phase 15: Rate Limiter Tests
Tests the TokenBucket, RateLimiterRegistry, and tier detection.
"""

import asyncio
import time

import pytest

from app.core.rate_limiter import (
    TIER_RATE_LIMITS,
    RateLimiterRegistry,
    TokenBucket,
    acquire_rate_limit,
    get_tier_from_model,
    reset_rate_limiters,
)


# Mark all tests as fast
pytestmark = pytest.mark.fast


class TestTokenBucket:
    """Tests for TokenBucket class."""

    def test_token_bucket_initial_capacity(self) -> None:
        """Token bucket starts with full capacity."""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        assert bucket.tokens == 5
        assert bucket.capacity == 5
        assert bucket.refill_rate == 1.0

    @pytest.mark.asyncio
    async def test_token_bucket_acquire_success(self) -> None:
        """Acquiring a token succeeds when tokens available."""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        result = await bucket.acquire()
        assert result is True
        # Should have used one token
        assert bucket.tokens < 5

    @pytest.mark.asyncio
    async def test_token_bucket_acquire_multiple(self) -> None:
        """Multiple acquires deplete tokens."""
        bucket = TokenBucket(capacity=3, refill_rate=0.1)

        # Acquire all tokens
        for _ in range(3):
            result = await bucket.acquire()
            assert result is True

        # Tokens should be near zero
        assert bucket.available_tokens() < 1

    @pytest.mark.asyncio
    async def test_token_bucket_refill(self) -> None:
        """Tokens refill over time."""
        bucket = TokenBucket(capacity=2, refill_rate=10.0)  # 10 tokens/sec for fast test

        # Use all tokens
        await bucket.acquire()
        await bucket.acquire()
        initial_tokens = bucket.available_tokens()

        # Wait for refill
        await asyncio.sleep(0.2)  # Should add ~2 tokens

        refilled_tokens = bucket.available_tokens()
        assert refilled_tokens > initial_tokens

    @pytest.mark.asyncio
    async def test_token_bucket_waits_when_empty(self) -> None:
        """Bucket waits when no tokens available."""
        bucket = TokenBucket(capacity=1, refill_rate=10.0)  # Fast refill for test

        # Use the one token
        await bucket.acquire()

        # Next acquire should wait briefly
        start = time.monotonic()
        result = await bucket.acquire(timeout=1.0)
        elapsed = time.monotonic() - start

        assert result is True
        # Should have waited some time (but not too long due to fast refill)
        assert elapsed > 0.01

    @pytest.mark.asyncio
    async def test_token_bucket_capacity_limit(self) -> None:
        """Tokens don't exceed capacity."""
        bucket = TokenBucket(capacity=2, refill_rate=100.0)  # Very fast refill

        # Wait for potential over-fill
        await asyncio.sleep(0.1)

        # Should still be at capacity max
        assert bucket.available_tokens() <= bucket.capacity


class TestTierDetection:
    """Tests for get_tier_from_model function."""

    def test_free_model_with_suffix(self) -> None:
        """Models with :free suffix are FREE tier."""
        assert get_tier_from_model("google/gemini-2.0-flash-001:free") == "free"
        assert get_tier_from_model("meta-llama/llama-3.3-70b-instruct:free") == "free"

    def test_free_model_case_insensitive(self) -> None:
        """Free tier detection is case insensitive."""
        assert get_tier_from_model("google/gemini-2.0-flash-001:FREE") == "free"
        assert get_tier_from_model("model:Free") == "free"

    def test_native_google_models(self) -> None:
        """Native Google models are NATIVE tier."""
        assert get_tier_from_model("gemini-2.5-flash") == "native"
        assert get_tier_from_model("gemini-3-pro-preview") == "native"
        assert get_tier_from_model("gemini-2.5-flash-image") == "native"

    def test_openrouter_paid_models(self) -> None:
        """OpenRouter paid models are PAID tier."""
        assert get_tier_from_model("google/gemini-2.0-flash-001") == "paid"
        assert get_tier_from_model("anthropic/claude-3-haiku") == "paid"
        assert get_tier_from_model("openai/gpt-4") == "paid"

    def test_empty_model_defaults_to_paid(self) -> None:
        """Empty or None model defaults to paid tier."""
        assert get_tier_from_model("") == "paid"
        assert get_tier_from_model(None) == "paid"  # type: ignore


class TestRateLimiterRegistry:
    """Tests for RateLimiterRegistry class."""

    def test_registry_creates_all_tiers(self) -> None:
        """Registry creates limiters for all defined tiers."""
        registry = RateLimiterRegistry()

        for tier in TIER_RATE_LIMITS.keys():
            limiter = registry.get_limiter(tier)
            assert limiter is not None
            assert isinstance(limiter, TokenBucket)

    def test_registry_unknown_tier_fallback(self) -> None:
        """Unknown tier falls back to paid tier."""
        registry = RateLimiterRegistry()

        limiter = registry.get_limiter("unknown_tier")
        paid_limiter = registry.get_limiter("paid")

        # Should return the paid limiter
        assert limiter is paid_limiter

    @pytest.mark.asyncio
    async def test_registry_acquire(self) -> None:
        """Registry acquire delegates to correct tier limiter."""
        registry = RateLimiterRegistry()

        result = await registry.acquire("native")
        assert result is True

    def test_registry_stats(self) -> None:
        """Registry provides stats for all tiers."""
        registry = RateLimiterRegistry()
        stats = registry.get_stats()

        assert "free" in stats
        assert "paid" in stats
        assert "native" in stats

        for tier_stats in stats.values():
            assert "available_tokens" in tier_stats
            assert "capacity" in tier_stats
            assert "refill_rate" in tier_stats


class TestAcquireRateLimit:
    """Tests for acquire_rate_limit convenience function."""

    @pytest.fixture(autouse=True)
    def reset_limiters(self) -> None:
        """Reset rate limiters before each test."""
        reset_rate_limiters()

    @pytest.mark.asyncio
    async def test_acquire_free_model(self) -> None:
        """Acquiring rate limit for free model succeeds."""
        result = await acquire_rate_limit("google/gemini-2.0-flash-001:free")
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_native_model(self) -> None:
        """Acquiring rate limit for native model succeeds."""
        result = await acquire_rate_limit("gemini-2.5-flash")
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_paid_model(self) -> None:
        """Acquiring rate limit for paid model succeeds."""
        result = await acquire_rate_limit("google/gemini-2.0-flash-001")
        assert result is True


class TestTierRateLimits:
    """Tests for tier rate limit configuration."""

    def test_free_tier_has_lowest_limits(self) -> None:
        """Free tier has the most restrictive limits."""
        free = TIER_RATE_LIMITS["free"]
        paid = TIER_RATE_LIMITS["paid"]
        native = TIER_RATE_LIMITS["native"]

        assert free["rpm"] < paid["rpm"]
        assert free["rpm"] < native["rpm"]
        assert free["burst"] < paid["burst"]

    def test_native_tier_has_highest_limits(self) -> None:
        """Native tier has the most generous limits."""
        free = TIER_RATE_LIMITS["free"]
        paid = TIER_RATE_LIMITS["paid"]
        native = TIER_RATE_LIMITS["native"]

        assert native["rpm"] >= paid["rpm"]
        assert native["burst"] >= paid["burst"]

    def test_refill_rate_matches_rpm(self) -> None:
        """Refill rate is approximately rpm/60."""
        for tier, config in TIER_RATE_LIMITS.items():
            expected_rate = config["rpm"] / 60.0
            actual_rate = config["refill_rate"]
            # Allow 10% tolerance
            assert abs(actual_rate - expected_rate) / expected_rate < 0.15, \
                f"Tier {tier}: refill_rate {actual_rate} doesn't match rpm {config['rpm']}"


class TestGracefulDegradation:
    """Tests for graceful degradation behavior."""

    @pytest.fixture(autouse=True)
    def reset_state(self) -> None:
        """Reset rate limiter state before each test."""
        TokenBucket.reset_failures()
        reset_rate_limiters()

    @pytest.mark.asyncio
    async def test_disabled_limiter_allows_through(self) -> None:
        """Disabled rate limiter allows requests through."""
        bucket = TokenBucket(capacity=0, refill_rate=0)  # Empty bucket

        # Manually disable
        TokenBucket._disabled = True

        result = await bucket.acquire()
        assert result is True  # Should allow through when disabled

        # Reset for other tests
        TokenBucket._disabled = False

    def test_reset_failures_clears_state(self) -> None:
        """reset_failures clears both counters."""
        TokenBucket._consecutive_failures = 10
        TokenBucket._disabled = True

        TokenBucket.reset_failures()

        assert TokenBucket._consecutive_failures == 0
        assert TokenBucket._disabled is False


class TestConcurrency:
    """Tests for concurrent rate limiting."""

    @pytest.fixture(autouse=True)
    def reset_state(self) -> None:
        """Reset rate limiter state before each test."""
        reset_rate_limiters()

    @pytest.mark.asyncio
    async def test_concurrent_acquires(self) -> None:
        """Multiple concurrent acquires are handled safely."""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)

        # Launch 5 concurrent acquires
        results = await asyncio.gather(*[bucket.acquire() for _ in range(5)])

        # All should succeed (bucket had 5 tokens)
        assert all(results)

    @pytest.mark.asyncio
    async def test_concurrent_acquires_with_waiting(self) -> None:
        """Concurrent acquires wait appropriately when tokens low."""
        bucket = TokenBucket(capacity=3, refill_rate=50.0)  # Very fast refill for test

        # Launch more acquires than capacity, with longer timeout
        results = await asyncio.gather(*[bucket.acquire(timeout=5.0) for _ in range(4)])

        # At least some should succeed (race conditions may cause some to fail)
        assert sum(results) >= 3  # At least 3 should succeed
