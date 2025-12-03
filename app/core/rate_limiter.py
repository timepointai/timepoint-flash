"""Proactive rate limiting with token bucket algorithm.

This module provides proactive rate limiting to prevent 429 errors before they happen.
Uses the token bucket algorithm for smooth request distribution.

Features:
    - Token bucket with configurable capacity and refill rate
    - Tier-based rate limits (FREE, PAID, NATIVE)
    - Async-safe with proper locking
    - Graceful degradation if rate limiter fails
    - Registry for per-model rate limiters

Examples:
    >>> from app.core.rate_limiter import get_rate_limiter, ModelTier
    >>> limiter = get_rate_limiter("google/gemini-2.0-flash-001:free")
    >>> await limiter.acquire()  # Waits if necessary
    >>> # Make API call

Tests:
    - tests/unit/test_rate_limiter.py::test_token_bucket_acquire
    - tests/unit/test_rate_limiter.py::test_rate_limiter_registry
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import ClassVar

logger = logging.getLogger(__name__)


# Rate limits per tier (requests per minute and burst capacity)
# These are conservative estimates based on observed provider behavior
TIER_RATE_LIMITS: dict[str, dict[str, float]] = {
    "free": {
        "rpm": 8,          # Requests per minute (conservative for :free models)
        "burst": 2,        # Max burst capacity
        "refill_rate": 0.13,  # ~8 per minute = 0.13 per second
    },
    "paid": {
        "rpm": 45,         # OpenRouter paid tier
        "burst": 5,        # Allow small bursts
        "refill_rate": 0.75,  # ~45 per minute = 0.75 per second
    },
    "native": {
        "rpm": 58,         # Google native (leave headroom from 60)
        "burst": 8,        # Higher burst for native
        "refill_rate": 0.97,  # ~58 per minute
    },
}


@dataclass
class TokenBucket:
    """Token bucket rate limiter for smooth request distribution.

    The token bucket algorithm allows for controlled bursting while
    maintaining a sustainable average rate.

    Attributes:
        capacity: Maximum tokens (burst capacity)
        refill_rate: Tokens added per second
        tokens: Current available tokens
        last_refill: Timestamp of last refill

    Examples:
        >>> bucket = TokenBucket(capacity=5, refill_rate=0.5)
        >>> await bucket.acquire()  # Uses 1 token
        >>> await bucket.acquire()  # Uses another token
    """

    capacity: float
    refill_rate: float
    tokens: float = field(default=None)  # type: ignore
    last_refill: float = field(default_factory=time.monotonic)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    # Class-level tracking for graceful degradation
    _consecutive_failures: ClassVar[int] = 0
    _disabled: ClassVar[bool] = False

    def __post_init__(self) -> None:
        """Initialize tokens to capacity if not set."""
        if self.tokens is None:
            self.tokens = self.capacity

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    async def acquire(self, timeout: float = 30.0) -> bool:
        """Acquire a token, waiting if necessary.

        Args:
            timeout: Maximum time to wait for a token (seconds)

        Returns:
            True if token was acquired, False if timeout or disabled

        Raises:
            asyncio.TimeoutError: If timeout exceeded (only when timeout > 0)
        """
        # Graceful degradation: if rate limiter is disabled, allow through
        if TokenBucket._disabled:
            logger.debug("Rate limiter disabled, allowing request through")
            return True

        try:
            async with self._lock:
                self._refill()

                if self.tokens >= 1:
                    self.tokens -= 1
                    TokenBucket._consecutive_failures = 0
                    return True

                # Calculate wait time for next token
                wait_time = (1 - self.tokens) / self.refill_rate
                wait_time = min(wait_time, timeout)

                if wait_time > 0:
                    logger.debug(
                        f"Rate limit: waiting {wait_time:.2f}s for token "
                        f"(tokens={self.tokens:.2f}, rate={self.refill_rate:.3f}/s)"
                    )

            # Wait outside the lock
            if wait_time > 0:
                await asyncio.sleep(wait_time)

            # Try again after waiting
            async with self._lock:
                self._refill()
                if self.tokens >= 1:
                    self.tokens -= 1
                    TokenBucket._consecutive_failures = 0
                    return True

                # Still not enough tokens after waiting
                logger.warning(
                    f"Rate limit wait exceeded: tokens={self.tokens:.2f}, "
                    f"wait_time={wait_time:.2f}s"
                )
                return False

        except Exception as e:
            # Graceful degradation: track failures and disable if too many
            TokenBucket._consecutive_failures += 1
            if TokenBucket._consecutive_failures >= 5:
                logger.error(
                    f"Rate limiter failing repeatedly ({TokenBucket._consecutive_failures}x), "
                    "disabling for safety"
                )
                TokenBucket._disabled = True
            logger.warning(f"Rate limiter error (allowing request): {e}")
            return True

    def available_tokens(self) -> float:
        """Get current available tokens without acquiring."""
        self._refill()
        return self.tokens

    @classmethod
    def reset_failures(cls) -> None:
        """Reset failure tracking (for testing)."""
        cls._consecutive_failures = 0
        cls._disabled = False


class RateLimiterRegistry:
    """Registry for per-tier rate limiters.

    Manages rate limiters for different model tiers, ensuring each tier
    has appropriate rate limiting based on its constraints.

    Attributes:
        limiters: Dictionary of tier -> TokenBucket

    Examples:
        >>> registry = RateLimiterRegistry()
        >>> limiter = registry.get_limiter("free")
        >>> await limiter.acquire()
    """

    def __init__(self) -> None:
        """Initialize the registry with tier-based limiters."""
        self._limiters: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

        # Pre-create limiters for all tiers
        for tier, config in TIER_RATE_LIMITS.items():
            self._limiters[tier] = TokenBucket(
                capacity=config["burst"],
                refill_rate=config["refill_rate"],
            )
            logger.debug(
                f"Created rate limiter for tier '{tier}': "
                f"capacity={config['burst']}, rate={config['refill_rate']:.3f}/s"
            )

    def get_limiter(self, tier: str) -> TokenBucket:
        """Get the rate limiter for a tier.

        Args:
            tier: Model tier ('free', 'paid', 'native')

        Returns:
            TokenBucket for the specified tier

        Falls back to 'paid' tier if unknown tier specified.
        """
        if tier not in self._limiters:
            logger.warning(f"Unknown tier '{tier}', using 'paid' tier limits")
            tier = "paid"
        return self._limiters[tier]

    async def acquire(self, tier: str, timeout: float = 30.0) -> bool:
        """Acquire a token for the specified tier.

        Args:
            tier: Model tier
            timeout: Maximum wait time

        Returns:
            True if token acquired, False otherwise
        """
        limiter = self.get_limiter(tier)
        return await limiter.acquire(timeout=timeout)

    def get_stats(self) -> dict[str, dict[str, float]]:
        """Get current stats for all tiers.

        Returns:
            Dictionary of tier -> {tokens, capacity, refill_rate}
        """
        return {
            tier: {
                "available_tokens": limiter.available_tokens(),
                "capacity": limiter.capacity,
                "refill_rate": limiter.refill_rate,
            }
            for tier, limiter in self._limiters.items()
        }


# Global registry instance
_registry: RateLimiterRegistry | None = None
_registry_lock = asyncio.Lock()


async def get_registry() -> RateLimiterRegistry:
    """Get or create the global rate limiter registry.

    Returns:
        The singleton RateLimiterRegistry instance

    Thread-safe and async-safe initialization.
    """
    global _registry
    if _registry is None:
        async with _registry_lock:
            if _registry is None:
                _registry = RateLimiterRegistry()
                logger.info("Initialized global rate limiter registry")
    return _registry


def get_tier_from_model(model_id: str) -> str:
    """Determine the tier from a model ID.

    Args:
        model_id: The model identifier (e.g., "google/gemini-2.0-flash-001:free")

    Returns:
        Tier string: 'free', 'paid', or 'native'
    """
    if not model_id:
        return "paid"

    model_lower = model_id.lower()

    # Free models have :free suffix
    if ":free" in model_lower or "/free" in model_lower:
        return "free"

    # Native Google models (no provider prefix or explicit gemini)
    if model_lower.startswith("gemini-") or (
        "/" not in model_lower and "gemini" in model_lower
    ):
        return "native"

    # Everything else is paid (OpenRouter with provider/model format)
    return "paid"


async def acquire_rate_limit(model_id: str, timeout: float = 30.0) -> bool:
    """Acquire a rate limit token for the given model.

    Convenience function that handles tier detection and registry lookup.

    Args:
        model_id: The model identifier
        timeout: Maximum wait time in seconds

    Returns:
        True if token acquired, False if timeout

    Examples:
        >>> await acquire_rate_limit("google/gemini-2.0-flash-001:free")
        True  # May wait up to timeout if rate limited
    """
    tier = get_tier_from_model(model_id)
    registry = await get_registry()
    return await registry.acquire(tier, timeout=timeout)


def reset_rate_limiters() -> None:
    """Reset all rate limiters (for testing).

    Clears the global registry and resets failure tracking.
    """
    global _registry
    _registry = None
    TokenBucket.reset_failures()
    logger.debug("Rate limiters reset")
