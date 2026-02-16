"""Billing provider protocol and default no-op implementation.

The open-source app ships with NoOpBilling (unlimited access).
When the private timepoint-billing package is installed, it registers
a real provider via set_billing_provider().
"""

from __future__ import annotations

from typing import Protocol


class BillingProvider(Protocol):
    """Abstract billing provider. Private modules override this."""

    async def check_credits(self, user_id: str, cost: int) -> bool: ...
    async def on_credits_granted(self, user_id: str, amount: int, source: str) -> None: ...


class NoOpBilling:
    """Default: open access, no billing. Used when timepoint-billing is not installed."""

    async def check_credits(self, user_id: str, cost: int) -> bool:
        return True

    async def on_credits_granted(self, user_id: str, amount: int, source: str) -> None:
        pass


_provider: BillingProvider = NoOpBilling()


def get_billing_provider() -> BillingProvider:
    return _provider


def set_billing_provider(provider: BillingProvider) -> None:
    global _provider
    _provider = provider
