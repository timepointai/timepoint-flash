# TIMEPOINT Flash — Implementation Plan

## Overview

This is the open-source core of TIMEPOINT Flash. It provides the full scene generation pipeline, auth system, credit system, and billing hooks. The deployed fork (`timepoint-flash-deploy`) adds deployment infrastructure and billing microservice integration.

## Billing Hooks (v2.4.0)

### What's Included

The open-source app includes billing-compatible hooks in `app/services/billing.py`:

- **`BillingProvider`** — Protocol defining `check_credits()` and `on_credits_granted()` methods
- **`NoOpBilling`** — Default implementation (unlimited access, all credit checks return `true`)
- **`get_billing_provider()`** — Returns the active billing provider

### How It Works

By default, `NoOpBilling` is the active provider — no billing integration is needed. The deployed fork overrides this with a billing microservice that handles Apple IAP and Stripe payments.

### Transaction Types

The `TransactionType` enum in `app/models_auth.py` includes billing-related types:
- `apple_iap` — Apple In-App Purchase
- `stripe_purchase` — Stripe one-time purchase
- `subscription_grant` — Monthly subscription credit grant

### What's NOT Included (deploy-only)

These exist only in the deployed fork (`timepoint-flash-deploy`):
- `app/api/v1/billing_proxy.py` — Proxy billing requests to billing microservice
- `app/api/v1/internal_credits.py` — Internal credits API for service-to-service calls
- Billing microservice integration (`BILLING_SERVICE_URL`, `BILLING_API_KEY` config)

## Three-Repo Architecture

| Repo | Purpose | Billing Role |
|------|---------|-------------|
| `timepoint-flash` (this repo) | Open-source core | Billing hooks (BillingProvider protocol, NoOpBilling) |
| `timepoint-flash-deploy` | Deployed fork on Railway | Billing proxy, internal credits API |
| `timepoint-billing` | Private billing microservice | Apple IAP, Stripe, credit management |

---

*Last updated: 2026-02-17*
