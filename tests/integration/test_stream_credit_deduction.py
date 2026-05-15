"""Regression tests for credit deduction on /api/v1/timepoints/generate/stream.

Covers task el-1obje: before the fix, the SSE streaming endpoint only ran the
``require_credits`` pre-flight balance check and never called
``spend_credits``, so authenticated callers generated timepoints for free.

These tests pin the behavior:
    1. ``stream_generation`` refunds credits via ``grant_credits`` when the
       pipeline fails before emitting the terminal ``done`` event.
    2. ``stream_generation`` does NOT refund when ``refund_cost == 0``
       (e.g. ``X-Gateway-Metered: true`` requests where Flash never deducted).
    3. ``generate_timepoint_stream`` is wired with the
       ``X-Gateway-Metered`` short-circuit and the up-front ``spend_credits``
       call (verified via source inspection — the full HTTP flow needs an
       AUTH_ENABLED test client which the existing harness does not provide).
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1 import timepoints as timepoints_module
from app.api.v1.timepoints import generate_timepoint_stream, stream_generation
from app.auth.credits import spend_credits
from app.models_auth import CreditAccount, TransactionType, User


@pytest.mark.asyncio
@pytest.mark.fast
async def test_stream_refunds_on_pipeline_exception(db_session):
    """When the pipeline raises, ``stream_generation`` refunds the cost.

    Mirrors the refund path in ``/generate/sync``: charge up-front, refund
    if generation fails before the terminal ``done`` event.
    """
    user = User(apple_sub="stream-refund-001")
    db_session.add(user)
    await db_session.flush()

    account = CreditAccount(user_id=user.id, balance=10, lifetime_earned=10, lifetime_spent=0)
    db_session.add(account)
    await db_session.flush()

    # Simulate the endpoint's up-front deduction.
    await spend_credits(db_session, user.id, 5, TransactionType.GENERATION, description="up-front")
    await db_session.commit()
    assert account.balance == 5

    # Force the pipeline to raise so the failure path runs.
    class _BoomPipeline:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def run_streaming(self, *args, **kwargs):  # pragma: no cover
            raise RuntimeError("boom")
            yield  # make this an async generator

        def state_to_timepoint(self, state):  # pragma: no cover
            raise NotImplementedError

        def state_to_generation_logs(self, state):  # pragma: no cover
            raise NotImplementedError

    with patch.object(timepoints_module, "GenerationPipeline", _BoomPipeline):
        gen = stream_generation(
            query="declaration of independence",
            generate_image=False,
            user_id=user.id,
            refund_cost=5,
            preset_label="balanced",
        )
        events = [event async for event in gen]

    # Stream should have emitted an error event but no ``done`` event.
    assert any("error" in event for event in events), events
    assert not any('"event":"done"' in event for event in events), events

    # Refund issued — balance restored to original.
    await db_session.refresh(account)
    assert account.balance == 10, f"expected refund to restore balance to 10, got {account.balance}"


@pytest.mark.asyncio
@pytest.mark.fast
async def test_stream_does_not_refund_when_cost_zero(db_session):
    """If ``refund_cost == 0`` no refund is attempted.

    This covers the gateway-metered path (Flash never deducted, so it must
    not refund either).
    """
    user = User(apple_sub="stream-refund-002")
    db_session.add(user)
    await db_session.flush()

    account = CreditAccount(user_id=user.id, balance=10, lifetime_earned=10, lifetime_spent=0)
    db_session.add(account)
    await db_session.flush()
    await db_session.commit()

    grant_spy = AsyncMock()
    with patch.object(timepoints_module, "grant_credits", grant_spy):

        class _BoomPipeline:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def run_streaming(self, *args, **kwargs):  # pragma: no cover
                raise RuntimeError("boom")
                yield

            def state_to_timepoint(self, state):  # pragma: no cover
                raise NotImplementedError

            def state_to_generation_logs(self, state):  # pragma: no cover
                raise NotImplementedError

        with patch.object(timepoints_module, "GenerationPipeline", _BoomPipeline):
            gen = stream_generation(
                query="declaration of independence",
                generate_image=False,
                user_id=user.id,
                refund_cost=0,
                preset_label="balanced",
            )
            _ = [event async for event in gen]

    grant_spy.assert_not_awaited()


@pytest.mark.fast
def test_stream_endpoint_signature_accepts_session():
    """Regression guard: the endpoint must take a session dependency so it
    can call ``spend_credits`` at request time."""
    sig = inspect.signature(generate_timepoint_stream)
    assert "session" in sig.parameters, (
        "generate_timepoint_stream must accept a session dependency to deduct credits"
    )


@pytest.mark.fast
def test_stream_endpoint_calls_spend_credits():
    """Regression guard: the endpoint source must call ``spend_credits``.

    Before el-1obje the endpoint only used ``require_credits`` (balance
    check) and never deducted. We pin the source-level invariant so the
    deduction can't silently regress.
    """
    source = inspect.getsource(generate_timepoint_stream)
    assert "spend_credits(" in source, (
        "generate_timepoint_stream must call spend_credits — credit deduction "
        "regressed to pre-el-1obje behavior"
    )
    assert "X-Gateway-Metered" in source, (
        "generate_timepoint_stream must honor X-Gateway-Metered to avoid "
        "double-charging when the Gateway already metered the request"
    )
