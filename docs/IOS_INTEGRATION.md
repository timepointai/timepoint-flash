# iOS Integration Guide

Reference for building the TIMEPOINT Flash iOS client. Covers credentials, auth flow, endpoint map, and client-side conventions.

---

## 1. Credential Inventory

| Env Var | Required | Default | Purpose |
|---------|----------|---------|---------|
| `GOOGLE_API_KEY` | Yes (one provider) | — | Google Gemini LLM + image generation |
| `OPENROUTER_API_KEY` | Optional | — | OpenRouter multi-model access (hyper/gemini3 presets) |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./timepoint.db` | Database connection string |
| `AUTH_ENABLED` | No | `false` | Set `true` for iOS app mode (requires JWT auth) |
| `JWT_SECRET_KEY` | If auth enabled | `change-me` | HS256 signing key — **generate a random 32+ char string** |
| `JWT_ACCESS_EXPIRE_MINUTES` | No | `15` | Access token lifetime |
| `JWT_REFRESH_EXPIRE_DAYS` | No | `30` | Refresh token lifetime |
| `APPLE_BUNDLE_ID` | If auth enabled | — | iOS app bundle ID for Apple Sign-In validation |
| `SIGNUP_CREDITS` | No | `50` | Free credits on first sign-in |
| `ADMIN_API_KEY` | No | `""` | Secret key for dev admin endpoints (test user creation, credit grants). Empty = disabled. |
| `ENVIRONMENT` | No | `development` | `development`, `staging`, or `production` |
| `DEBUG` | No | `true` | Enables `/docs` and `/redoc` Swagger UI |
| `RATE_LIMIT` | No | `60` | Requests per minute per IP |
| `BLOB_STORAGE_ENABLED` | No | `false` | Write asset folders per generation |
| `BLOB_STORAGE_ROOT` | No | `./output/timepoints` | Root dir for blob output |
| `SHARE_URL_BASE` | No | `""` | Base URL for share links (e.g. `https://timepointai.com/t`). Empty = no share_url in responses. |
| `LOGFIRE_TOKEN` | No | — | Observability (optional) |

---

## 2. Auth Flow

### Dev Admin Setup (Testing Without iOS)

To test the full auth flow without an iOS device, set the `ADMIN_API_KEY` secret and use the dev admin endpoints:

```bash
# Create a test user and get JWTs
curl -X POST $BASE/api/v1/auth/dev/token \
  -H "X-Admin-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# Grant additional credits
curl -X POST $BASE/api/v1/credits/admin/grant \
  -H "X-Admin-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "<id>", "amount": 100}'
```

These endpoints are gated behind `ADMIN_API_KEY` and return 403 when the key is empty or missing.

### Apple Sign-In → JWT Pair

```
iOS App                          Backend
  │                                │
  │  1. ASAuthorizationAppleIDCredential
  │     (identity_token)           │
  │  ──────────────────────────►   │
  │  POST /api/v1/auth/apple       │
  │  { "identity_token": "..." }   │
  │                                │
  │  ◄──────────────────────────   │
  │  { access_token, refresh_token,│
  │    token_type, expires_in }    │
  │                                │
  │  2. Use access_token as Bearer │
  │  ──────────────────────────►   │
  │  Authorization: Bearer <AT>    │
  │                                │
  │  3. When AT expires, rotate    │
  │  ──────────────────────────►   │
  │  POST /api/v1/auth/refresh     │
  │  { "refresh_token": "..." }    │
  │                                │
  │  ◄──────────────────────────   │
  │  { new access_token,           │
  │    new refresh_token, ... }    │
```

**Key points:**

- Access tokens are HS256 JWTs, valid for 15 minutes (configurable).
- Refresh tokens are opaque random strings, stored hashed server-side, valid for 30 days.
- Refresh rotation: each refresh invalidates the old token and issues a new pair.
- Reuse of a revoked refresh token triggers revocation of **all** tokens for that user (theft detection).

### Logout

```
POST /api/v1/auth/logout
{ "refresh_token": "..." }
→ 200 { "detail": "Logged out" }
```

Revokes the specified refresh token. Always returns 200 (does not leak whether the token existed).

---

## 3. Credit System

### Costs

| Operation | Credits |
|-----------|---------|
| `generate_balanced` | 5 |
| `generate_hd` | 10 |
| `generate_hyper` | 5 |
| `generate_gemini3` | 5 |
| `chat` | 1 |
| `temporal_jump` | 2 |

Fetch live costs: `GET /api/v1/credits/costs` (no auth required).

### Balance Check

`GET /api/v1/credits/balance` → `{ balance, lifetime_earned, lifetime_spent }`

### How Spending Works

Credits are checked before the operation runs. If insufficient, the endpoint returns **402 Payment Required** with `"detail": "Insufficient credits. This operation costs N credits."`.

On success, the credit ledger (`credit_transactions`) records every deduction with a reference to the timepoint ID.

### 402 Handling in iOS

When receiving a 402:
1. Show the user their current balance
2. Explain the cost of the attempted operation
3. Future: direct to credit purchase flow (not yet implemented — see Future Notes)

---

## 4. Endpoint Map for iOS MVP

All endpoints are under `/api/v1`. Prefix with your Railway base URL (e.g. `https://your-app.up.railway.app`).

### Auth (requires `AUTH_ENABLED=true`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/apple` | None | Apple Sign-In → JWT pair |
| `POST` | `/auth/dev/token` | `X-Admin-Key` | Dev admin: create test user → JWT pair |
| `POST` | `/auth/refresh` | None | Rotate refresh token |
| `GET` | `/auth/me` | Bearer | Current user profile |
| `POST` | `/auth/logout` | None | Revoke refresh token |
| `DELETE` | `/auth/account` | Bearer | Soft-delete user account |

### Credits

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/credits/balance` | Bearer | Current balance |
| `GET` | `/credits/history` | Bearer | Paginated ledger (`?limit=20&offset=0`) |
| `POST` | `/credits/admin/grant` | `X-Admin-Key` | Dev admin: grant credits to any user |
| `GET` | `/credits/costs` | None | Cost table |

### Generation

| Method | Path | Auth | Credits | Description |
|--------|------|------|---------|-------------|
| `POST` | `/timepoints/generate/sync` | Bearer | 5-10 | Synchronous generation (recommended for iOS) |
| `POST` | `/timepoints/generate` | Bearer | 5-10 | Background generation + poll |
| `POST` | `/timepoints/generate/stream` | Bearer | 5-10 | SSE streaming (see SSE note below) |

### Retrieval

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/timepoints/{id}` | Bearer | Get scene (`?full=true&include_image=false`). Returns 403 for private non-owner. |
| `GET` | `/timepoints` | Bearer | List scenes (paginated, `?visibility=public\|private`). Anonymous sees only public. |
| `PATCH` | `/timepoints/{id}/visibility` | Bearer | Set visibility: `{"visibility": "public\|private"}`. Owner-only. |

### Interactions

| Method | Path | Auth | Credits | Description |
|--------|------|------|---------|-------------|
| `POST` | `/interactions/{id}/chat` | Bearer | 1 | Chat with a character |
| `POST` | `/interactions/{id}/dialog` | Bearer | 1 | Generate more dialog |
| `POST` | `/interactions/{id}/survey` | Bearer | 1 | Ask all characters |

### Time Travel

| Method | Path | Auth | Credits | Description |
|--------|------|------|---------|-------------|
| `POST` | `/temporal/{id}/next` | Bearer | 2 | Jump forward |
| `POST` | `/temporal/{id}/prior` | Bearer | 2 | Jump backward |
| `GET` | `/temporal/{id}/sequence` | Bearer | 0 | Get linked timeline |

### User

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/users/me/timepoints` | Bearer | Paginated user timepoints (`?page=1&page_size=20&status=completed`) |
| `GET` | `/users/me/export` | Bearer | Full GDPR data export |
| `POST` | `/users/resolve` | `X-Service-Key` | Find or create user by `external_id` (service-to-service only) |

---

## 5. SSE Streaming Guidance

`POST /timepoints/generate/stream` uses Server-Sent Events. The event format:

```
data: {"event": "start", "step": "initialization", "progress": 0}
data: {"event": "step_complete", "step": "judge", "progress": 10}
...
data: {"event": "done", "progress": 100, "data": {"timepoint_id": "...", "status": "completed"}}
```

**iOS recommendation:** `URLSession` does not natively support SSE. Options:

1. **Preferred:** Use `POST /timepoints/generate/sync` — blocks until complete (30-120s). Set a generous `URLSession` timeout.
2. **Alternative:** Use `POST /timepoints/generate` (returns immediately) + poll `GET /timepoints/{id}` every 3-5 seconds until `status == "completed"`.
3. **If SSE needed:** Use a third-party library like [EventSource](https://github.com/inaka/EventSource) or [LDSwiftEventSource](https://github.com/launchdarkly/swift-eventsource).

---

## 6. Image Handling

- **Default:** Request scenes with `include_image=false` (or omit the param). The response includes `image_url` (a hosted URL) and `has_image: true/false`.
- **Display:** Load images from `image_url` using standard `URLSession` or `AsyncImage`.
- **Offline/export:** Fetch with `include_image=true` to get `image_base64` (base64-encoded JPEG). Only do this when explicitly needed — the payload is large.
- **Generation:** Set `generate_image: true` in the generation request to include image generation (costs the same credits).

---

## 7. Token Storage

| Token | Storage | Rationale |
|-------|---------|-----------|
| **Refresh token** | iOS Keychain (`kSecClassGenericPassword`) | Survives app restarts, encrypted at rest |
| **Access token** | In-memory property | Short-lived, re-derived from refresh on app launch |

On app launch:
1. Read refresh token from Keychain
2. Call `POST /auth/refresh` to get a fresh access token
3. If refresh fails (401), redirect to Apple Sign-In

---

## 8. Error Codes

| HTTP Code | Meaning | iOS Action |
|-----------|---------|------------|
| **401 Unauthorized** | Token expired or invalid | Attempt refresh; if that fails, re-authenticate via Apple Sign-In |
| **402 Payment Required** | Insufficient credits | Show balance, explain cost, prompt for top-up (future) |
| **403 Forbidden** | Private timepoint, not the owner | Show "This scene is private" message |
| **404 Not Found** | Resource doesn't exist | Show appropriate empty state |
| **422 Validation Error** | Bad request body | Show validation errors to user |
| **429 Too Many Requests** | Rate limited | Exponential backoff (start at 1s, max 30s) |
| **500 Server Error** | Internal error | Retry once, then show error state |

---

## 9. User Sync

Fetch the authenticated user's generation history:

```
GET /api/v1/users/me/timepoints?page=1&page_size=20&status=completed
```

Response:
```json
{
  "items": [
    {
      "id": "...",
      "query": "Oppenheimer Trinity test 1945",
      "slug": "oppenheimer-trinity-test-1945-a1b2c3",
      "status": "completed",
      "year": 1945,
      "location": "Jornada del Muerto, New Mexico",
      "has_image": true,
      "created_at": "2026-02-09T12:00:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

Use this to populate the user's "My Scenes" tab. Then fetch full scene detail with `GET /timepoints/{id}?full=true`.

---

## 10. Account Deletion

**Required for App Store review.** Apple rejects apps without account deletion.

```
DELETE /api/v1/auth/account
Authorization: Bearer <access_token>
→ 200 { "detail": "Account deactivated" }
```

This soft-deletes the account:
- Sets `user.is_active = false`
- Revokes all refresh tokens
- Does NOT hard-delete data (preserves ledger integrity)

Show a confirmation dialog before calling this endpoint. After success, clear Keychain and navigate to the sign-in screen.

---

## 11. Visibility & Sharing

Timepoints have a `visibility` field: `"public"` (default) or `"private"`.

### Response Fields

Every `TimepointResponse` now includes:
- `visibility` — `"public"` or `"private"`
- `share_url` — Pre-built share link (only when `SHARE_URL_BASE` is configured and visibility is public). Example: `"https://timepointai.com/t/oppenheimer-trinity-abc123"`

### Behavior

| Scenario | `GET /{id}` | `GET /` list | Interactions |
|----------|-------------|-------------|--------------|
| **Public, anyone** | Full data | Included | Allowed |
| **Private, owner** | Full data | Included | Allowed |
| **Private, non-owner** | 403 Forbidden | Excluded | 403 Forbidden |
| **Private, anonymous** | 403 Forbidden | Excluded | 403 Forbidden |

### Setting Visibility

```
PATCH /api/v1/timepoints/{id}/visibility
Authorization: Bearer <access_token>
{ "visibility": "private" }
→ 200 (updated TimepointResponse)
```

Owner-only. When `AUTH_ENABLED=false`, any caller can change visibility.

### Generation

Pass `"visibility": "private"` in the generate request to create a private scene:
```json
{
  "query": "My private moment",
  "visibility": "private"
}
```

---

## 12. User Model Notes

The `User` model includes:
- `id` — Flash internal UUID (primary key)
- `apple_sub` — Apple Sign-In subject identifier
- `external_id` — Auth0 sub or other external identity provider ID (added in migration 0009). Unique, indexed. Used by `POST /users/resolve` for find-or-create and by service-key auth for user lookup via `X-User-ID`.
- `email`, `display_name` — optional profile fields

The admin grant endpoint (`POST /credits/admin/grant`) now accepts an optional `transaction_type` parameter (e.g. `stripe_purchase`, `apple_iap`, `subscription_grant`) for proper ledger categorization when credits are granted by the billing service.

---

## 13. Billing Hooks

The open-source app includes a `BillingProvider` protocol (`app/services/billing.py`) with a default `NoOpBilling` implementation (unlimited access). The deployed version (`timepoint-flash-deploy`) uses a separate billing microservice that handles Apple IAP and Stripe payments, proxying billing requests through the main app.

The billing hooks provide:
- `check_credits(user_id, cost)` — called before credit-consuming operations
- `on_credits_granted(user_id, amount, source)` — called after credits are granted

The deployed fork adds `/api/v1/billing/*` proxy endpoints and `/internal/credits/*` internal API for service-to-service communication with the billing microservice.

---

## 14. Future Notes

- **Push notifications:** Not yet implemented. Future phase may add APNs for generation-complete notifications.
- **Rate limiting:** Currently per-IP (60/min). Future: per-user rate limiting tied to credit tier.

---

## 15. Doc Index

| File | Contents |
|------|----------|
| `README.md` | Overview, quick start, examples |
| `docs/API.md` | Full endpoint reference |
| `docs/AGENTS.md` | Pipeline architecture (14 agents) |
| `docs/TEMPORAL.md` | Time travel mechanics |
| `docs/DEPLOY.md` | Deployment guide (local, Railway, Docker) |
| `docs/EVAL_ROADMAP.md` | Quality benchmarks |
| `docs/IOS_INTEGRATION.md` | This file |

---

*Last updated: 2026-02-18*
