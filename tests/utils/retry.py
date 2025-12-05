"""
Retry decorator with exponential backoff for handling transient API failures.

Automatically retries failed operations with increasing delays between attempts.
Useful for flaky external API calls (OpenRouter, Google AI, etc.).
"""
import asyncio
import functools
import time
from typing import Callable, TypeVar, Any, Type
import httpx
from fastapi import HTTPException

# Type variables for generic decorator
T = TypeVar('T')


# Transient error codes that should trigger retries
TRANSIENT_HTTP_CODES = {500, 502, 503, 504, 429}  # Server errors + rate limit

# Transient exception types
TRANSIENT_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.NetworkError,
    ConnectionError,
    TimeoutError,
)


def is_transient_error(exception: Exception) -> bool:
    """
    Determine if an exception is a transient error that should be retried.

    Args:
        exception: The exception to check

    Returns:
        True if the error is transient and should be retried
    """
    # Check exception type
    if isinstance(exception, TRANSIENT_EXCEPTIONS):
        return True

    # Check HTTP exception status codes
    if isinstance(exception, HTTPException):
        return exception.status_code in TRANSIENT_HTTP_CODES

    # Check httpx.HTTPStatusError
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in TRANSIENT_HTTP_CODES

    return False


def retry_on_api_error(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple[Type[Exception], ...] = TRANSIENT_EXCEPTIONS
):
    """
    Decorator that retries a function on transient API errors with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        backoff_factor: Multiplier for delay between retries (default: 2.0)
        initial_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay between retries (default: 60.0)
        exceptions: Tuple of exception types to catch (default: TRANSIENT_EXCEPTIONS)

    Example:
        @retry_on_api_error(max_attempts=3, backoff_factor=2.0)
        async def call_external_api():
            response = await client.get("https://api.example.com/data")
            return response.json()

    Behavior:
        - Attempt 1: Immediate execution
        - Attempt 2: Wait 1.0s (initial_delay)
        - Attempt 3: Wait 2.0s (1.0 * backoff_factor)
        - Attempt 4: Wait 4.0s (2.0 * backoff_factor)
        - ...up to max_delay
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Handle both sync and async functions
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                last_exception = None
                delay = initial_delay

                for attempt in range(1, max_attempts + 1):
                    try:
                        return await func(*args, **kwargs)

                    except Exception as e:
                        last_exception = e

                        # Check if this is a transient error worth retrying
                        if not is_transient_error(e):
                            # Not a transient error, raise immediately
                            print(f"✗ Non-transient error, not retrying: {e}")
                            raise

                        # Don't retry if this was the last attempt
                        if attempt >= max_attempts:
                            print(f"✗ Max retry attempts ({max_attempts}) reached")
                            break

                        # Log retry attempt
                        print(
                            f"⚠ Transient error (attempt {attempt}/{max_attempts}): {e}"
                        )
                        print(f"  Retrying in {delay:.1f}s...")

                        # Wait before retry
                        await asyncio.sleep(delay)

                        # Increase delay for next attempt (exponential backoff)
                        delay = min(delay * backoff_factor, max_delay)

                # All retries exhausted, raise the last exception
                print(f"✗ All {max_attempts} retry attempts failed")
                raise last_exception

            return async_wrapper

        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> T:
                last_exception = None
                delay = initial_delay

                for attempt in range(1, max_attempts + 1):
                    try:
                        return func(*args, **kwargs)

                    except Exception as e:
                        last_exception = e

                        # Check if this is a transient error worth retrying
                        if not is_transient_error(e):
                            # Not a transient error, raise immediately
                            print(f"✗ Non-transient error, not retrying: {e}")
                            raise

                        # Don't retry if this was the last attempt
                        if attempt >= max_attempts:
                            print(f"✗ Max retry attempts ({max_attempts}) reached")
                            break

                        # Log retry attempt
                        print(
                            f"⚠ Transient error (attempt {attempt}/{max_attempts}): {e}"
                        )
                        print(f"  Retrying in {delay:.1f}s...")

                        # Wait before retry
                        time.sleep(delay)

                        # Increase delay for next attempt (exponential backoff)
                        delay = min(delay * backoff_factor, max_delay)

                # All retries exhausted, raise the last exception
                print(f"✗ All {max_attempts} retry attempts failed")
                raise last_exception

            return sync_wrapper

    return decorator


def skip_on_api_unavailable(error_message: str = "External API unavailable"):
    """
    Decorator that skips a test if external API is unavailable.

    This provides graceful degradation - test is skipped instead of failed
    when there are known external dependency issues.

    Args:
        error_message: Custom skip message (default: "External API unavailable")

    Example:
        @skip_on_api_unavailable("OpenRouter API unavailable")
        async def test_with_external_api():
            # Test that requires OpenRouter
            pass
    """
    import pytest

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if is_transient_error(e):
                        # Transient error - skip test instead of failing
                        pytest.skip(f"{error_message}: {str(e)}")
                    else:
                        # Real error - let it fail
                        raise

            return async_wrapper

        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> T:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if is_transient_error(e):
                        # Transient error - skip test instead of failing
                        pytest.skip(f"{error_message}: {str(e)}")
                    else:
                        # Real error - let it fail
                        raise

            return sync_wrapper

    return decorator
